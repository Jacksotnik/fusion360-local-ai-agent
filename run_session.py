"""Edit sessions: one conversation and one design, a series of requests; the design is checked after every step.

Usage:
    python -I -X utf8 run_session.py --prompt cad5 --tag s-v5 [--sessions S1-plate-boss] [--think]
"""
import argparse
import base64
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_ladder
from cad_api import CAD_PRELUDE
from fusion_side import CLOSE_ALL_BENCH_DOCS_SCRIPT, NEW_DOCUMENT_SCRIPT, reference_script
from mcp_client import FusionMcp
from reference_prelude import REFERENCE_PRELUDE

HERE = os.path.dirname(os.path.abspath(__file__))

SESSION_PRELUDE = REFERENCE_PRELUDE + r'''

def sketch_at_z(z_mm):
    planes = root.constructionPlanes
    plane_input = planes.createInput()
    plane_input.setByOffset(root.xYConstructionPlane, adsk.core.ValueInput.createByReal(z_mm * MM))
    return root.sketches.add(planes.add(plane_input))


def _all_profiles(sketch):
    collection = adsk.core.ObjectCollection.create()
    for profile in sketch.profiles:
        collection.add(profile)
    return collection


def cut_through(sketch):
    extrudes = root.features.extrudeFeatures
    cut_input = extrudes.createInput(_all_profiles(sketch), adsk.fusion.FeatureOperations.CutFeatureOperation)
    cut_input.setTwoSidesExtent(adsk.fusion.ThroughAllExtentDefinition.create(),
                                adsk.fusion.ThroughAllExtentDefinition.create())
    return extrudes.add(cut_input)


def cut_distance(profile, distance_mm):
    extrudes = root.features.extrudeFeatures
    cut_input = extrudes.createInput(profile, adsk.fusion.FeatureOperations.CutFeatureOperation)
    cut_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("%s mm" % distance_mm))
    return extrudes.add(cut_input)


def join(profile, distance_mm):
    extrudes = root.features.extrudeFeatures
    join_input = extrudes.createInput(profile, adsk.fusion.FeatureOperations.JoinFeatureOperation)
    join_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("%s mm" % distance_mm))
    return extrudes.add(join_input)
'''


def expected_signatures(fusion, session):
    """Signature of the reference design after each step."""
    run_ladder.must(fusion.run_script(NEW_DOCUMENT_SCRIPT), "new document")
    result = []
    try:
        for step in session["steps"]:
            run_ladder.must(fusion.run_script(reference_script(SESSION_PRELUDE, step["reference"])), "reference")
            result.append(run_ladder.signature(fusion))
    finally:
        fusion.run_script(CLOSE_ALL_BENCH_DOCS_SCRIPT)
    return result


def run_session(fusion, session, settings, out_dir):
    print("==", session["id"], flush=True)
    expected = expected_signatures(fusion, session)
    run_ladder.must(fusion.run_script(NEW_DOCUMENT_SCRIPT), "new document")
    messages = [{"role": "system", "content": settings["system_prompt"]}]
    steps = []
    started = time.time()
    try:
        for index, step in enumerate(session["steps"]):
            run_ladder.strip_thinking(messages)
            start_signature = run_ladder.signature(fusion)
            messages.append({"role": "user", "content": run_ladder.user_message(fusion, step["prompt"], settings)})
            step_started = time.time()
            result = run_ladder.agent_turn(fusion, messages, settings, start_signature)
            actual = run_ladder.signature(fusion)
            problems = run_ladder.compare(expected[index], actual)
            if result["status"] == "left_bench_document":
                problems = ["the agent left the bench document"]
            record = {
                "step": index + 1,
                "prompt": step["prompt"],
                "status": result["status"],
                "passed": not problems,
                "problems": problems,
                "model_calls": len(result["calls"]),
                "seconds": round(time.time() - step_started, 1),
                "calls": result["calls"],
                "final_answer": result["final_answer"],
                "expected": expected[index],
                "actual": actual,
            }
            steps.append(record)
            print("   step %d: %s, %d model calls, %.0f s %s" % (
                index + 1, "PASS" if record["passed"] else "FAIL", record["model_calls"], record["seconds"],
                "; ".join(problems)), flush=True)
            if result["status"] == "left_bench_document":
                break
        image = fusion.screenshot(direction="iso-top-right", width=1000, height=800, transparent_background=False)
        if image:
            with open(os.path.join(out_dir, session["id"] + ".png"), "wb") as file:
                file.write(base64.b64decode(image))
    finally:
        fusion.run_script(CLOSE_ALL_BENCH_DOCS_SCRIPT)

    summary = {"id": session["id"], "seconds": round(time.time() - started, 1), "steps": steps,
               "messages": run_ladder.loggable(messages)}
    with open(os.path.join(out_dir, session["id"] + ".json"), "w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=1)
    return summary


def write_summary(summaries, out_dir, args):
    lines = ["# %s" % args.tag, "",
             "Модель `%s`, промпт `%s`, think=%s." % (run_ladder.MODEL, args.prompt, args.think), ""]
    for summary in summaries:
        passed = sum(1 for step in summary["steps"] if step["passed"])
        lines.append("## %s: %d/%d шагов, %.0f с" % (summary["id"], passed, len(summary["steps"]), summary["seconds"]))
        lines.append("")
        lines.append("| Шаг | Запрос | Итог | Вызовов | Время, с | Расхождения |")
        lines.append("|---|---|---|---|---|---|")
        for step in summary["steps"]:
            lines.append("| %d | %s | %s | %d | %.0f | %s |" % (
                step["step"], step["prompt"], "✅" if step["passed"] else "❌", step["model_calls"], step["seconds"],
                "; ".join(step["problems"])))
        lines.append("")
    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="cad12")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--sessions", help="comma-separated session ids")
    parser.add_argument("--think", action="store_true")
    args = parser.parse_args()

    sessions = json.load(open(os.path.join(HERE, "sessions.json"), encoding="utf-8"))["sessions"]
    if args.sessions:
        wanted = args.sessions.split(",")
        sessions = [session for session in sessions if session["id"] in wanted]

    settings = {
        "system_prompt": open(os.path.join(HERE, "prompts", args.prompt + ".md"), encoding="utf-8").read(),
        "tools": run_ladder.build_tools(True),
        "prelude": CAD_PRELUDE,
        "think": args.think,
        "options": {"num_ctx": run_ladder.NUM_CTX,
                    "num_predict": run_ladder.MAX_REPLY_TOKENS_THINKING if args.think else run_ladder.MAX_REPLY_TOKENS},
        "attach_state": True,
    }
    out_dir = os.path.join(HERE, "results", args.tag)
    os.makedirs(out_dir, exist_ok=True)
    fusion = FusionMcp()
    summaries = []
    for session in sessions:
        summaries.append(run_session(fusion, session, settings, out_dir))
        write_summary(summaries, out_dir, args)


if __name__ == "__main__":
    main()
