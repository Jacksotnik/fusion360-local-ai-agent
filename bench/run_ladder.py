"""Agent runner for the graded Fusion tasks: a local Ollama model models parts through the Fusion MCP server.

Usage:
    python -I -X utf8 run_ladder.py --level 1 --prompt raw --tag l1-raw [--think] [--cases id,id]
"""
import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cad_api import CAD_PRELUDE
from fusion_side import (ACTIVE_IS_BENCH_SCRIPT, CLOSE_ALL_BENCH_DOCS_SCRIPT, CLOSE_BENCH_DOC_SCRIPT,
                         NEW_DOCUMENT_SCRIPT, SIGNATURE_SCRIPT, fit_view_script, reference_script)
from mcp_client import FusionMcp
from reference_prelude import REFERENCE_PRELUDE

HERE = os.path.dirname(os.path.abspath(__file__))
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "gemma4-12b:q8_0"
NUM_CTX = 32768
MAX_MODEL_CALLS = 20
MAX_NUDGES = 2
TOOL_OUTPUT_CHARS = 6000
EXPECTED_CACHE = os.path.join(HERE, "expected_signatures.json")

MAX_REPLY_TOKENS = 1200
# With thinking on, the reasoning counts against the cap too and needs room.
MAX_REPLY_TOKENS_THINKING = 4000
TOO_LONG_TEXT = ("Твой ответ оборвался: он слишком длинный. Вызови fusion_script сразу, "
                 "в скрипте только код, без комментариев.")

REPEAT_TEXT = ("Note: this is exactly the script you already ran, with the same result. Repeating it will not "
               "help. Read the message again, find which number or which part is wrong, and change the approach.")

NUDGE_TEXT = ("Модель в Fusion не изменилась: геометрия та же, что была до задачи. "
              "Сделай это через fusion_script и проверь результат.")

# Scripts that touch documents could reach the owner's own designs, so the runner refuses them.
FORBIDDEN_SCRIPT_PATTERNS = [r"\.documents\b", r"\.save\s*\(", r"\.saveAs\s*\(", r"\.close\s*\(", r"executeTextCommand"]

SCREENSHOT_DIRECTIONS = ["current", "front", "back", "bottom", "top", "left", "right",
                         "iso-bottom-left", "iso-bottom-right", "iso-top-left", "iso-top-right"]

RAW_SCRIPT_DESCRIPTION = ("Run a Python script inside Fusion on the active design. The script must define "
                          "`def run(_context: str):` and use the Fusion API (adsk.core, adsk.fusion). Text printed "
                          "with print() is returned. Do not catch exceptions: the error text is returned to you.")
HELPER_SCRIPT_DESCRIPTION = ("Run Python inside Fusion on the active design. The CAD helper API from the system "
                             "prompt is already defined (all lengths in mm), so write only the statements, without "
                             "imports and without def run. Text printed with print() is returned. Do not catch "
                             "exceptions: the error text is returned to you.")


def build_tools(use_helpers):
    script_description = HELPER_SCRIPT_DESCRIPTION if use_helpers else RAW_SCRIPT_DESCRIPTION
    return [
        {"type": "function", "function": {
            "name": "fusion_script",
            "description": script_description,
            "parameters": {"type": "object", "properties": {
                "script": {"type": "string", "description": "Python source to run."},
                "readOnly": {"type": "boolean",
                             "description": "true only when the script reads the design and changes nothing."},
            }, "required": ["script"]},
        }},
        {"type": "function", "function": {
            "name": "fusion_screenshot",
            "description": "Take a screenshot of the Fusion view of the active design. The image comes back to you.",
            "parameters": {"type": "object", "properties": {
                "direction": {"type": "string", "enum": SCREENSHOT_DIRECTIONS,
                              "description": "Camera direction before the capture."},
            }, "required": []},
        }},
        {"type": "function", "function": {
            "name": "fusion_api_docs",
            "description": ("Search the Fusion API documentation. Returns classes with their members, or full "
                            "descriptions of members."),
            "parameters": {"type": "object", "properties": {
                "searchPattern": {"type": "string", "description": "Regular expression for class or member names."},
                "apiCategory": {"type": "string", "enum": ["class", "member", "description", "all"],
                                "description": "What to search: class names, member names, descriptions or all."},
                "filter": {"type": "string",
                           "description": "Limit to a namespace or class, e.g. 'adsk.fusion' or 'adsk.fusion.ExtrudeFeatures'."},
            }, "required": ["searchPattern"]},
        }},
    ]


def must(result, what):
    is_success, text = result
    if not is_success:
        raise RuntimeError(what + " failed: " + text)
    return text


def wrap_script(script, prelude):
    """Prepend the helper API; a bare body is wrapped into run()."""
    if re.search(r"^def run\(", script, re.MULTILINE):
        return prelude + "\n\n" + script
    # The body runs inside try so that an error reports the line number of the model's own script.
    indented = "\n".join("        " + line for line in script.splitlines())
    return (prelude + "\n\ndef run(_context: str):\n"
            + "    _first_line = _sys_for_lines._getframe().f_lineno + 2\n"
            + "    try:\n" + indented + "\n"
            + "        pass\n"
            + "    except Exception as _model_error:\n"
            + "        _report_model_error(_model_error, _first_line)\n")


def short_error(traceback_text, model_script, wrapped_script):
    """Turn a Fusion traceback into 'line N of your script: code' plus the error message.
    The traceback counts lines of the whole script sent to Fusion: the output guard, the helper
    prelude and the run() header come before the model's own lines."""
    lines = traceback_text.splitlines()
    last_frame = -1
    for index, line in enumerate(lines):
        if line.strip().startswith('File "'):
            last_frame = index
    message_lines = [line for line in lines[last_frame + 1:] if line.strip() and not line.startswith("    ")]
    message = "\n".join(message_lines) if message_lines else traceback_text.strip().splitlines()[-1]

    location = ""
    match = re.search(r"MODEL_LINE (\d+) \| (.*)", message, re.DOTALL)
    if match:
        model_line = int(match.group(1))
        message = match.group(2)
        model_lines = model_script.splitlines()
        if 1 <= model_line <= len(model_lines):
            location = "line %d of your script: %s\n" % (model_line, model_lines[model_line - 1].strip())
    return "Script failed.\n" + location + message


def truncate(text):
    if len(text) <= TOOL_OUTPUT_CHARS:
        return text
    return text[:TOOL_OUTPUT_CHARS] + "\n... [truncated, %d chars total]" % len(text)


def ollama_chat(messages, settings):
    body = {
        "model": MODEL,
        "messages": messages,
        "tools": settings["tools"],
        "stream": False,
        "think": settings["think"],
        "keep_alive": "30m",
        "options": settings["options"],
    }
    request = urllib.request.Request(OLLAMA_URL, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read().decode("utf-8"))


def signature(fusion):
    return json.loads(must(fusion.run_script(SIGNATURE_SCRIPT, read_only=True), "signature"))


def build_reference_state(fusion, case, by_id, include_case_reference):
    """New marked document with the start state, and optionally the case reference on top."""
    must(fusion.run_script(NEW_DOCUMENT_SCRIPT), "new document")
    if case["start"]:
        start_body = by_id[case["start"]]["reference"]
        must(fusion.run_script(reference_script(REFERENCE_PRELUDE, start_body)), "start reference")
    if include_case_reference:
        must(fusion.run_script(reference_script(REFERENCE_PRELUDE, case["reference"])), "case reference")


def expected_signature(fusion, case, by_id, cache):
    start_text = by_id[case["start"]]["reference"] if case["start"] else ""
    key = hashlib.sha1((start_text + "\n---\n" + case["reference"]).encode("utf-8")).hexdigest()
    cached = cache.get(case["id"])
    if cached and cached["key"] == key:
        return cached["signature"]

    build_reference_state(fusion, case, by_id, include_case_reference=True)
    try:
        result = signature(fusion)
    finally:
        must(fusion.run_script(CLOSE_BENCH_DOC_SCRIPT), "close")
    cache[case["id"]] = {"key": key, "signature": result}
    with open(EXPECTED_CACHE, "w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=1)
    return result


def compare(expected, actual, ignore_extents=False):
    """List of problems; empty means the result matches the reference within tolerance."""
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
        volume_error = abs(got["volume_mm3"] - want["volume_mm3"]) / want["volume_mm3"]
        if volume_error > 0.005:
            problems.append(label + "volume %.3f instead of %.3f mm3" % (got["volume_mm3"], want["volume_mm3"]))

        extents_match = all(abs(a - b) <= 0.05 for a, b in zip(got["extents_mm"], want["extents_mm"]))
        if not extents_match and not ignore_extents:
            problems.append(label + "extents %s instead of %s mm" % (got["extents_mm"], want["extents_mm"]))

        want_diameters = want["cylinder_diameters_mm"]
        got_diameters = got["cylinder_diameters_mm"]
        diameters_match = len(want_diameters) == len(got_diameters) and all(
            abs(a - b) <= 0.02 for a, b in zip(got_diameters, want_diameters))
        if not diameters_match:
            problems.append(label + "cylinder diameters %s instead of %s mm" % (got_diameters, want_diameters))
    return problems


def run_tool(fusion, call, screenshots, prelude):
    """Execute one tool call. Returns the text for the tool message; screenshots are collected separately."""
    function = call.get("function", {})
    name = function.get("name", "")
    arguments = function.get("arguments") or {}
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except ValueError:
            return "Error: arguments are not valid JSON."

    if name == "fusion_script":
        script = str(arguments.get("script", ""))
        if not script.strip():
            return "Error: empty script."
        for pattern in FORBIDDEN_SCRIPT_PATTERNS:
            if re.search(pattern, script):
                return "Error: this task does not allow working with documents (%s). Work in the active design." % pattern
        model_script = script
        if prelude:
            script = wrap_script(script, prelude)
        is_read_only = arguments.get("readOnly") is True
        is_success, text = fusion.run_script(script, read_only=is_read_only)
        if is_success:
            return truncate(text) if text.strip() else "Script finished, it printed nothing."
        if prelude:
            # Fusion rolls a failed script back completely; say so and show what the design is now.
            state = fusion.run_script(wrap_script("state_summary()", prelude), read_only=True)[1].strip()
            return truncate(short_error(text, model_script, script)
                            + "\nNothing of this script was kept: Fusion undid all of it. " + state)
        return truncate("Script failed:\n" + text)

    if name == "fusion_screenshot":
        direction = str(arguments.get("direction") or "iso-top-right")
        if direction not in SCREENSHOT_DIRECTIONS:
            direction = "iso-top-right"
        fusion.run_script(fit_view_script(direction), read_only=True)
        image = fusion.screenshot(direction="current", width=800, height=600, transparent_background=False)
        if image is None:
            return "Error: screenshot failed."
        screenshots.append({"direction": direction, "image": image})
        return "Screenshot taken (%s). The image follows in the next message." % direction

    if name == "fusion_api_docs":
        search_pattern = str(arguments.get("searchPattern", ""))
        if not search_pattern:
            return "Error: searchPattern is required."
        api_category = arguments.get("apiCategory")
        api_filter = arguments.get("filter")
        return truncate(fusion.api_docs(search_pattern, api_category, api_filter))

    return "Error: unknown tool " + name


def strip_thinking(messages):
    """Thinking of finished turns is dropped (Google's guidance for Gemma 4)."""
    for message in messages:
        if message.get("role") == "assistant" and "thinking" in message:
            del message["thinking"]


def loggable(messages):
    """Copy of the history without base64 images."""
    result = []
    for message in messages:
        copy = dict(message)
        if "images" in copy:
            copy["images"] = ["<png %d bytes>" % len(base64.b64decode(image)) for image in copy["images"]]
        result.append(copy)
    return result


def user_message(fusion, prompt, settings):
    """The request, with the current design state attached when the helpers are on (saves a describe() call)."""
    if not settings["prelude"] or not settings["attach_state"]:
        return prompt
    state = must(fusion.run_script(wrap_script("describe()", settings["prelude"]), read_only=True), "describe")
    if state.strip().startswith("bodies: 0"):
        return "The design is empty.\n\n" + prompt
    return "Current design (describe()):\n" + state.strip() + "\n\n" + prompt


def run_agent(fusion, case, settings, start_signature):
    messages = [
        {"role": "system", "content": settings["system_prompt"]},
        {"role": "user", "content": user_message(fusion, case["prompt"], settings)},
    ]
    if case.get("image"):
        with open(os.path.join(HERE, case["image"]), "rb") as file:
            messages[1]["images"] = [base64.b64encode(file.read()).decode("ascii")]
    result = agent_turn(fusion, messages, settings, start_signature)
    result["messages"] = loggable(messages)
    return result


def agent_turn(fusion, messages, settings, start_signature):
    """Answer the last user message of the conversation: the model calls tools until it gives a final answer."""
    calls = []
    nudges = 0
    status = "max_calls"
    final_answer = ""
    previous_call = (None, None)

    for _ in range(MAX_MODEL_CALLS):
        started = time.time()
        response = ollama_chat(messages, settings)
        seconds = time.time() - started
        message = response.get("message", {})
        tool_calls = message.get("tool_calls") or []

        eval_count = response.get("eval_count", 0)
        eval_seconds = response.get("eval_duration", 0) / 1e9
        prompt_count = response.get("prompt_eval_count", 0)
        prompt_seconds = response.get("prompt_eval_duration", 0) / 1e9
        calls.append({
            "seconds": round(seconds, 2),
            "load_seconds": round(response.get("load_duration", 0) / 1e9, 2),
            "prompt_tokens": prompt_count,
            "prompt_tps": round(prompt_count / prompt_seconds, 1) if prompt_seconds else None,
            "eval_tokens": eval_count,
            "eval_tps": round(eval_count / eval_seconds, 1) if eval_seconds else None,
            "tool_calls": [call.get("function", {}).get("name") for call in tool_calls],
            "done_reason": response.get("done_reason"),
        })

        if response.get("done_reason") == "length" and not tool_calls:
            messages.append({"role": "assistant", "content": message.get("content", "")[:2000]})
            messages.append({"role": "user", "content": TOO_LONG_TEXT})
            continue

        assistant = {"role": "assistant", "content": message.get("content", "")}
        if tool_calls:
            assistant["tool_calls"] = tool_calls
            if message.get("thinking"):
                assistant["thinking"] = message["thinking"]
        messages.append(assistant)

        if tool_calls:
            screenshots = []
            for call in tool_calls:
                tool_name = call.get("function", {}).get("name", "")
                output = run_tool(fusion, call, screenshots, settings["prelude"])
                call_key = json.dumps(call.get("function", {}), sort_keys=True, ensure_ascii=False)
                if call_key == previous_call[0] and output == previous_call[1]:
                    output += "\n" + REPEAT_TEXT
                previous_call = (call_key, output)
                if settings.get("show_tool"):
                    settings["show_tool"](call, output)
                tool_message = {"role": "tool", "tool_name": tool_name, "content": output}
                if call.get("id"):
                    tool_message["tool_call_id"] = call["id"]
                messages.append(tool_message)

            is_bench = must(fusion.run_script(ACTIVE_IS_BENCH_SCRIPT, read_only=True), "active check").strip()
            if is_bench != "bench":
                status = "left_bench_document"
                break

            for shot in screenshots:
                messages.append({"role": "user", "content": "Screenshot (%s)." % shot["direction"],
                                 "images": [shot["image"]]})
            continue

        final_answer = message.get("content", "")
        current = signature(fusion)
        is_unchanged = current == start_signature
        if is_unchanged and nudges < MAX_NUDGES:
            nudges += 1
            strip_thinking(messages)
            messages.append({"role": "user", "content": NUDGE_TEXT})
            continue
        status = "answered_unchanged" if is_unchanged else "answered"
        break

    return {"status": status, "final_answer": final_answer, "nudges": nudges, "calls": calls}


def run_case(fusion, case, by_id, cache, settings, out_dir):
    print("==", case["id"], flush=True)
    started = time.time()
    expected = expected_signature(fusion, case, by_id, cache)

    build_reference_state(fusion, case, by_id, include_case_reference=False)
    record = {"id": case["id"], "level": case["level"], "prompt": case["prompt"], "expected": expected}
    try:
        start_signature = signature(fusion)
        record["start"] = start_signature
        record.update(run_agent(fusion, case, settings, start_signature))

        if record["status"] == "left_bench_document":
            record["problems"] = ["the agent left the bench document"]
        else:
            actual = signature(fusion)
            record["actual"] = actual
            record["problems"] = compare(expected, actual, case.get("ignore_extents", False))
            fusion.run_script(fit_view_script("iso-top-right"), read_only=True)
            image = fusion.screenshot(direction="current", width=1000, height=800, transparent_background=False)
            if image:
                with open(os.path.join(out_dir, case["id"] + ".png"), "wb") as file:
                    file.write(base64.b64decode(image))
    except Exception as error:
        record["status"] = "error"
        record["problems"] = ["runner error: %s" % error]
    finally:
        print(fusion.run_script(CLOSE_ALL_BENCH_DOCS_SCRIPT)[1].strip(), flush=True)

    record["passed"] = not record["problems"]
    record["seconds"] = round(time.time() - started, 1)
    llm_seconds = sum(call["seconds"] for call in record.get("calls", []))
    record["llm_seconds"] = round(llm_seconds, 1)
    with open(os.path.join(out_dir, case["id"] + ".json"), "w", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False, indent=1)
    print("   %s, %s, %d model calls, %.0f s" % (
        "PASS" if record["passed"] else "FAIL", record["status"], len(record.get("calls", [])), record["seconds"]),
        flush=True)
    return record


def write_summary(records, out_dir, args):
    lines = [
        "# %s" % args.tag,
        "",
        "Модель `%s`, промпт `%s`, функции CAD: %s, think=%s, num_ctx %d." % (
            MODEL, args.prompt, args.helpers, args.think, NUM_CTX),
        "",
        "| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for record in records:
        calls = record.get("calls", [])
        tool_count = sum(len(call["tool_calls"]) for call in calls)
        rates = [call["eval_tps"] for call in calls if call["eval_tps"] and call["eval_tokens"] >= 50]
        rate = "%.1f" % (sum(rates) / len(rates)) if rates else "—"
        lines.append("| %s | %s | %s | %d | %d | %d | %.0f | %.0f | %s |" % (
            record["id"], "✅" if record["passed"] else "❌", record["status"], len(calls), tool_count,
            record.get("nudges", 0), record["seconds"], record["llm_seconds"], rate))
    lines.append("")
    for record in records:
        if record["problems"]:
            lines.append("- **%s:** %s" % (record["id"], "; ".join(record["problems"])))
    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", type=int, help="run all cases of this level")
    parser.add_argument("--cases", help="comma-separated case ids")
    parser.add_argument("--all", action="store_true", help="run every case")
    parser.add_argument("--cases-file", default="cases.json", help="task file; cases.json is always loaded for start states")
    parser.add_argument("--prompt", default="raw", help="system prompt name in prompts/")
    parser.add_argument("--tag", required=True, help="results folder name")
    parser.add_argument("--helpers", action="store_true", help="prepend the CAD helper API to model scripts")
    parser.add_argument("--think", action="store_true")
    parser.add_argument("--attach-state", action="store_true", help="attach describe() of the design to the request")
    parser.add_argument("--num-gpu", type=int, help="Ollama num_gpu override")
    args = parser.parse_args()

    curriculum = json.load(open(os.path.join(HERE, "cases.json"), encoding="utf-8"))["cases"]
    cases = json.load(open(os.path.join(HERE, args.cases_file), encoding="utf-8"))["cases"]
    by_id = {case["id"]: case for case in curriculum + cases}
    if args.cases:
        selected = [by_id[case_id] for case_id in args.cases.split(",")]
    elif args.level:
        selected = [case for case in cases if case["level"] == args.level]
    elif args.all:
        selected = cases
    else:
        raise SystemExit("give --level, --cases or --all")

    options = {"num_ctx": NUM_CTX,
               "num_predict": MAX_REPLY_TOKENS_THINKING if args.think else MAX_REPLY_TOKENS}
    if args.num_gpu is not None:
        options["num_gpu"] = args.num_gpu
    settings = {
        "system_prompt": open(os.path.join(HERE, "prompts", args.prompt + ".md"), encoding="utf-8").read(),
        "tools": build_tools(args.helpers),
        "prelude": CAD_PRELUDE if args.helpers else None,
        "think": args.think,
        "options": options,
        "attach_state": args.attach_state,
    }

    out_dir = os.path.join(HERE, "results", args.tag)
    os.makedirs(out_dir, exist_ok=True)
    cache = {}
    if os.path.exists(EXPECTED_CACHE):
        cache = json.load(open(EXPECTED_CACHE, encoding="utf-8"))

    fusion = FusionMcp()
    records = []
    for case in selected:
        records.append(run_case(fusion, case, by_id, cache, settings, out_dir))
        write_summary(records, out_dir, args)


if __name__ == "__main__":
    main()
