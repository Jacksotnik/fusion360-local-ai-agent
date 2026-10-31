"""No-regression check: fusion-ladder's graded tasks through the agent loop of THIS package.

The tasks, the start states, the reference signatures and the comparison come from the bench (the
parent folder by default); only the model loop is fusion-agent's. Run it while no other Fusion runner
is running. Results: fusion-agent/results/<tag>/summary.md (+ one JSON per task).

    .venv\\Scripts\\python -X utf8 tools\\ladder_regression.py --tag reg1 cases.json cases_holdout2.json
"""
import argparse
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)
sys.path.insert(0, APP_ROOT)

from fusion_agent import fusion_scripts  # noqa: E402
from fusion_agent.agent import TUNED_MODEL, Agent, loggable, must  # noqa: E402
from fusion_agent.fusion_mcp import FusionMcp  # noqa: E402
from fusion_agent.models import model_info  # noqa: E402
from fusion_agent.ollama import Ollama  # noqa: E402
from fusion_agent.session import new_session_id  # noqa: E402


def load_ladder(ladder_dir):
    sys.path.insert(0, ladder_dir)
    import fusion_side
    import run_ladder
    return run_ladder, fusion_side


def run_case(case, by_id, cache, ladder, ladder_dir, fusion, ollama, details, model, out_dir):
    run_ladder, fusion_side = ladder
    started = time.time()
    expected = run_ladder.expected_signature(fusion, case, by_id, cache)
    run_ladder.build_reference_state(fusion, case, by_id, include_case_reference=False)
    session_id = new_session_id()
    # The bench document gets the app's session mark too, so the app's active-document check passes.
    must(fusion.run_script(fusion_scripts.mark_active_script(session_id)), "mark")
    record = {"id": case["id"], "prompt": case["prompt"], "expected": expected}
    try:
        agent = Agent(fusion, ollama, session_id, model=model, think=False, has_vision=details["has_vision"],
                      has_thinking=details["has_thinking"])
        images = None
        if case.get("image"):
            import base64
            with open(os.path.join(ladder_dir, case["image"]), "rb") as file:
                images = [base64.b64encode(file.read()).decode("ascii")]
        result = agent.turn(case["prompt"], images)
        actual = agent.signature()
        record.update({"status": result["status"], "calls": result["calls"], "nudges": result["nudges"],
                       "turn_seconds": result["seconds"], "actual": actual,
                       "messages": loggable(agent.messages)})
        record["problems"] = run_ladder.compare(expected, actual, case.get("ignore_extents", False))
    except Exception as error:
        record["status"] = "error"
        record["problems"] = ["runner error: %s: %s" % (type(error).__name__, error)]
    finally:
        fusion.run_script(fusion_side.CLOSE_ALL_BENCH_DOCS_SCRIPT)
    record["passed"] = not record["problems"]
    record["seconds"] = round(time.time() - started, 1)
    with open(os.path.join(out_dir, case["id"] + ".json"), "w", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False, indent=1)
    print("%-28s %s  %5.1f s  %s %s" % (case["id"], "PASS" if record["passed"] else "FAIL", record["seconds"],
                                        record["status"], "; ".join(record["problems"])), flush=True)
    return record


def write_summary(records, out_dir, args):
    passed = sum(1 for record in records if record["passed"])
    seconds = [record["seconds"] for record in records]
    lines = [
        "# %s" % args.tag,
        "",
        "fusion-agent loop, model `%s`, fast mode; tasks from fusion-ladder: %s." % (args.model, ", ".join(args.files)),
        "",
        "Passed %d/%d; time per task (whole case, like the bench): median %.1f s, max %.1f s." % (
            passed, len(records), statistics.median(seconds) if seconds else 0, max(seconds) if seconds else 0),
        "",
        "| Task | Result | Status | Model calls | Nudges | Time, s |",
        "|---|---|---|---|---|---|",
    ]
    for record in records:
        lines.append("| %s | %s | %s | %d | %d | %.0f |" % (
            record["id"], "PASS" if record["passed"] else "FAIL", record["status"], len(record.get("calls", [])),
            record.get("nudges", 0), record["seconds"]))
    lines.append("")
    for record in records:
        if record["problems"]:
            lines.append("- **%s:** %s" % (record["id"], "; ".join(record["problems"])))
    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="+", help="task files of fusion-ladder, e.g. cases.json cases_holdout2.json")
    parser.add_argument("--tag", required=True, help="results folder name")
    parser.add_argument("--ladder", default=os.path.dirname(APP_ROOT), help="the fusion-ladder folder")
    parser.add_argument("--model", default=TUNED_MODEL)
    args = parser.parse_args()

    ladder_dir = os.path.abspath(args.ladder)
    ladder = load_ladder(ladder_dir)
    run_ladder = ladder[0]
    curriculum = json.load(open(os.path.join(ladder_dir, "cases.json"), encoding="utf-8"))["cases"]
    selected = []
    for name in args.files:
        selected.extend(json.load(open(os.path.join(ladder_dir, name), encoding="utf-8"))["cases"])
    by_id = {case["id"]: case for case in curriculum + selected}
    cache = {}
    if os.path.exists(run_ladder.EXPECTED_CACHE):
        cache = json.load(open(run_ladder.EXPECTED_CACHE, encoding="utf-8"))

    out_dir = os.path.join(APP_ROOT, "results", args.tag)
    os.makedirs(out_dir, exist_ok=True)
    fusion = FusionMcp()
    ollama = Ollama()
    details = model_info(ollama, args.model)
    if details is None:
        raise SystemExit("%s is not installed" % args.model)
    records = []
    for case in selected:
        records.append(run_case(case, by_id, cache, ladder, ladder_dir, fusion, ollama, details, args.model, out_dir))
        write_summary(records, out_dir, args)
    passed = write_summary(records, out_dir, args)
    seconds = [record["seconds"] for record in records]
    print("passed %d/%d, median %.1f s, max %.1f s -> %s" % (
        passed, len(records), statistics.median(seconds), max(seconds), os.path.join(out_dir, "summary.md")))


if __name__ == "__main__":
    main()
