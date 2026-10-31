"""Chat with Gemma 4 12B in Fusion: type requests in Russian, the model builds and edits the part.

It opens a new design document and works only in it; saving the document is up to you.

Usage:
    python -I -X utf8 fusion_chat.py [--prompt cad9] [--quiet]
Type an empty line or "выход" to quit.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_ladder
from cad_api import CAD_PRELUDE
from fusion_side import NEW_DOCUMENT_SCRIPT
from mcp_client import FusionMcp

HERE = os.path.dirname(os.path.abspath(__file__))


def show_tool(call, output):
    arguments = call.get("function", {}).get("arguments") or {}
    script = arguments.get("script") if isinstance(arguments, dict) else None
    if script:
        print("  скрипт:")
        for line in script.strip().splitlines():
            print("    " + line)
    first_lines = output.strip().splitlines()[:3]
    print("  результат: " + " | ".join(first_lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="cad12")
    parser.add_argument("--quiet", action="store_true", help="do not print the scripts")
    parser.add_argument("--think", action="store_true",
                        help="slow, more accurate mode for parts made of many operations")
    args = parser.parse_args()

    reply_cap = run_ladder.MAX_REPLY_TOKENS_THINKING if args.think else run_ladder.MAX_REPLY_TOKENS
    settings = {
        "system_prompt": open(os.path.join(HERE, "prompts", args.prompt + ".md"), encoding="utf-8").read(),
        "tools": run_ladder.build_tools(True),
        "prelude": CAD_PRELUDE,
        "think": args.think,
        "options": {"num_ctx": run_ladder.NUM_CTX, "num_predict": reply_cap},
        "attach_state": True,
        "show_tool": None if args.quiet else show_tool,
    }
    fusion = FusionMcp()
    name = run_ladder.must(fusion.run_script(NEW_DOCUMENT_SCRIPT), "new document").strip()
    print("Открыт новый документ Fusion: %s. Модель %s. Пустая строка - выход." % (name, run_ladder.MODEL))

    messages = [{"role": "system", "content": settings["system_prompt"]}]
    while True:
        try:
            request = input("\n> ").strip()
        except EOFError:
            break
        if not request or request.lower() in ("выход", "exit", "quit"):
            break
        run_ladder.strip_thinking(messages)
        start_signature = run_ladder.signature(fusion)
        messages.append({"role": "user", "content": run_ladder.user_message(fusion, request, settings)})
        started = time.time()
        result = run_ladder.agent_turn(fusion, messages, settings, start_signature)
        print("\n%s\n(%.0f с, вызовов модели: %d)" % (result["final_answer"].strip(), time.time() - started,
                                                   len(result["calls"])))
        if result["status"] == "left_bench_document":
            print("Активным стал другой документ - остановка, чтобы не трогать чужие документы.")
            break
    print("Документ остаётся открытым; сохранить его или закрыть - на твоё усмотрение.")


if __name__ == "__main__":
    main()
