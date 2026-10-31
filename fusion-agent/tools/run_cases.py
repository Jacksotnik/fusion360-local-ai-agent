"""Run fusion-agent's own task sets (cases/*.json) through the app's agent loop.

Every task has a start state and a reference written with the CAD helpers, and a volume computed by hand.
The reference is built in Fusion first and must match the hand volume (0.1 %), otherwise the task is not
run. The model's result is compared with the reference geometry the way the bench compares (volume 0.5 %,
sorted extents 0.05 mm, round-face diameters, body count, no broken features).

    .venv\\Scripts\\python -X utf8 tools\\run_cases.py --tag plain-r1 cases\\plain_dev.json
    .venv\\Scripts\\python -X utf8 tools\\run_cases.py --check-references cases\\plain_holdout.json

A task file may name a "start_prelude" (a Python file next to it with a PRELUDE string of builder functions):
its tasks start from "the user's own part" and the runner marks those start steps as the user's. A task with
"answer" is a question: the design must stay as it was and the final answer must contain every listed item.
"""
import argparse
import hashlib
import json
import math
import os
import re
import runpy
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)
sys.path.insert(0, APP_ROOT)

from fusion_agent import fusion_scripts  # noqa: E402
from fusion_agent.agent import TUNED_MODEL, Agent, load_prompt, loggable, must, wrap_script  # noqa: E402
from fusion_agent.cad_api import CAD_PRELUDE  # noqa: E402
from fusion_agent.fusion_mcp import FusionMcp  # noqa: E402
from fusion_agent.models import model_info  # noqa: E402
from fusion_agent.ollama import Ollama  # noqa: E402
from fusion_agent.session import DesignSession, new_session_id  # noqa: E402

CACHE_PATH = os.path.join(APP_ROOT, "cases", "expected_signatures.json")


def compare(expected, actual):
    """List of problems; empty means the result matches the reference (same rules as the bench)."""
    problems = []
    if actual["unhealthy"]:
        problems.append("unhealthy features: " + ", ".join(actual["unhealthy"]))
    expected_bodies = sorted(expected["bodies"], key=lambda body: body["volume_mm3"])
    actual_bodies = sorted(actual["bodies"], key=lambda body: body["volume_mm3"])
    if len(actual_bodies) != len(expected_bodies):
        problems.append("bodies: %d instead of %d" % (len(actual_bodies), len(expected_bodies)))
        return problems
    for index, (want, got) in enumerate(zip(expected_bodies, actual_bodies)):
        label = "body %d: " % (index + 1)
        if abs(got["volume_mm3"] - want["volume_mm3"]) > 0.005 * want["volume_mm3"]:
            problems.append(label + "volume %.3f instead of %.3f mm3" % (got["volume_mm3"], want["volume_mm3"]))
        if not all(abs(a - b) <= 0.05 for a, b in zip(got["extents_mm"], want["extents_mm"])):
            problems.append(label + "extents %s instead of %s mm" % (got["extents_mm"], want["extents_mm"]))
        want_diameters = want["cylinder_diameters_mm"]
        got_diameters = got["cylinder_diameters_mm"]
        if len(want_diameters) != len(got_diameters) or any(
                abs(a - b) > 0.02 for a, b in zip(got_diameters, want_diameters)):
            problems.append(label + "cylinder diameters %s instead of %s mm" % (got_diameters, want_diameters))
    return problems


def answer_numbers(answer):
    """Every number in an answer; "14 250" and "14,25" are read as 14250 and 14.25."""
    text = re.sub(r"(?<=\d)[ \u00a0\u202f](?=\d{3}\b)", "", answer)
    return [float(number.replace(",", ".")) for number in re.findall(r"\d+(?:[.,]\d+)?", text)]


def answer_problems(expected_items, answer):
    """Each expected item is a list of alternatives: a number (3 % tolerance) or a text (case-insensitive)."""
    numbers = answer_numbers(answer)
    lowered = answer.lower()
    problems = []
    for alternatives in expected_items:
        is_found = False
        for wanted in alternatives:
            if isinstance(wanted, str):
                if wanted.lower() in lowered:
                    is_found = True
                continue
            for number in numbers:
                if abs(number - wanted) <= max(0.03 * abs(wanted), 0.005):
                    is_found = True
        if not is_found:
            problems.append("the answer has none of %s" % alternatives)
    return problems


def load_cases(file_name):
    """The tasks of one file, each with its start prelude text ("" when none) and the user-part flag."""
    data = json.load(open(file_name, encoding="utf-8"))
    prelude = ""
    if data.get("start_prelude"):
        prelude_path = os.path.join(os.path.dirname(os.path.abspath(file_name)), data["start_prelude"])
        prelude = runpy.run_path(prelude_path)["PRELUDE"]
    cases = data["cases"]
    for case in cases:
        case["prelude"] = prelude
        case["is_user_part"] = bool(prelude)
    return cases


class Bench:
    """New self-test designs for each task; only those designs are ever closed."""

    def __init__(self, fusion):
        self.fusion = fusion
        self.session = DesignSession(fusion, new_session_id())

    def fresh_design(self, case):
        self.session.new_design(is_selftest=True)
        if case["start"]:
            must(self.fusion.run_script(wrap_script(case["start"], CAD_PRELUDE + case["prelude"])), "start state")
        if case["is_user_part"]:
            self.session.mark_user_steps()

    def close(self):
        self.session.close_selftest_documents()

    def signature(self):
        return json.loads(must(self.fusion.run_script(fusion_scripts.SIGNATURE_SCRIPT, read_only=True), "signature"))


def expected_signature(bench, case, cache):
    """Build the reference, check it against the hand volume, cache it."""
    parts = [case["start"], case["reference"], case["volume"]]
    if case["prelude"]:
        parts.append(case["prelude"])
    key = hashlib.sha1(json.dumps(parts).encode("utf-8")).hexdigest()
    cached = cache.get(case["id"])
    if cached and cached["key"] == key:
        return cached["signature"]
    bench.fresh_design(case)
    try:
        must(bench.fusion.run_script(wrap_script(case["reference"], CAD_PRELUDE + case["prelude"])), "reference")
        signature = bench.signature()
    finally:
        bench.close()
    hand_volume = eval(case["volume"], {"math": math})
    built_volume = sum(body["volume_mm3"] for body in signature["bodies"])
    if abs(built_volume - hand_volume) > 0.001 * hand_volume:
        raise ValueError("%s: the reference has volume %.3f, the hand calculation %.3f" % (
            case["id"], built_volume, hand_volume))
    cache[case["id"]] = {"key": key, "signature": signature}
    with open(CACHE_PATH, "w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=1)
    return signature


def run_case(bench, case, cache, ollama, details, args, system_prompt, out_dir):
    started = time.time()
    expected = expected_signature(bench, case, cache)
    record = {"id": case["id"], "prompt": case["prompt"], "expected": expected}
    bench.fresh_design(case)
    try:
        agent = Agent(bench.fusion, ollama, bench.session.session_id, model=args.model, think=args.think,
                      has_vision=details["has_vision"], has_thinking=details["has_thinking"],
                      system_prompt=system_prompt)
        result = agent.turn(case["prompt"])
        actual = bench.signature()
        record.update({"status": result["status"], "calls": result["calls"], "nudges": result["nudges"],
                       "turn_seconds": result["seconds"], "actual": actual, "answer": result["final_answer"],
                       "messages": loggable(agent.messages)})
        record["problems"] = compare(expected, actual)
        if "answer" in case:
            record["problems"] += answer_problems(case["answer"], result["final_answer"])
    except Exception as error:
        record["status"] = "error"
        record["problems"] = ["runner error: %s: %s" % (type(error).__name__, error)]
    finally:
        bench.close()
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
        "fusion-agent loop, model `%s`, prompt `%s`, think=%s; tasks: %s." % (
            args.model, args.prompt, args.think, ", ".join(os.path.basename(name) for name in args.files)),
        "",
        "Passed %d/%d; time per task: median %.1f s, max %.1f s." % (
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
    parser.add_argument("files", nargs="+", help="task files, e.g. cases/plain_dev.json")
    parser.add_argument("--tag", help="results folder name (required unless --check-references)")
    parser.add_argument("--model", default=TUNED_MODEL)
    parser.add_argument("--prompt", default="cad12", help="prompt name in fusion_agent/prompts/")
    parser.add_argument("--think", action="store_true")
    parser.add_argument("--cases", help="comma-separated task ids to run (default: all)")
    parser.add_argument("--check-references", action="store_true", help="only build and check the references")
    args = parser.parse_args()

    cases = []
    for name in args.files:
        cases.extend(load_cases(name))
    if args.cases:
        wanted = set(args.cases.split(","))
        cases = [case for case in cases if case["id"] in wanted]
    cache = {}
    if os.path.exists(CACHE_PATH):
        cache = json.load(open(CACHE_PATH, encoding="utf-8"))
    bench = Bench(FusionMcp())

    if args.check_references:
        bad = 0
        for case in cases:
            try:
                signature = expected_signature(bench, case, cache)
                body = signature["bodies"][0] if signature["bodies"] else {}
                print("%-28s ok  %s mm3, %s mm" % (case["id"], body.get("volume_mm3"), body.get("extents_mm")))
            except Exception as error:
                bad += 1
                print("%-28s BAD %s" % (case["id"], error))
        print("%d references, %d bad" % (len(cases), bad))
        return

    if not args.tag:
        raise SystemExit("--tag is required")
    out_dir = os.path.join(APP_ROOT, "results", args.tag)
    os.makedirs(out_dir, exist_ok=True)
    ollama = Ollama()
    details = model_info(ollama, args.model)
    if details is None:
        raise SystemExit("%s is not installed" % args.model)
    system_prompt = load_prompt(args.prompt)
    records = []
    for case in cases:
        records.append(run_case(bench, case, cache, ollama, details, args, system_prompt, out_dir))
        write_summary(records, out_dir, args)
    passed = write_summary(records, out_dir, args)
    seconds = [record["seconds"] for record in records]
    print("passed %d/%d, median %.1f s, max %.1f s -> %s" % (
        passed, len(records), statistics.median(seconds), max(seconds), os.path.join(out_dir, "summary.md")))


if __name__ == "__main__":
    main()
