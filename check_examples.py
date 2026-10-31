"""Run every example script of a system prompt in Fusion (examples on an existing design get their start part)."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_ladder
from cad_api import CAD_PRELUDE
from fusion_side import CLOSE_ALL_BENCH_DOCS_SCRIPT, NEW_DOCUMENT_SCRIPT
from mcp_client import FusionMcp

HERE = os.path.dirname(os.path.abspath(__file__))

# Start parts for the examples that edit an existing design, keyed by a phrase of the example text.
START_PARTS = {
    "box 40 x 40 x 10": "box(40, 40, 10, corner=(0, 0, 0))",
    "plate 60 x 40": "sk = new_sketch('XY')\nrect(sk, 0, 0, 60, 40)\ncircle(sk, 30, 20, 8)\nextrude(sk, 5)",
}


def main():
    prompt_name = sys.argv[1] if len(sys.argv) > 1 else "cad5"
    text = open(os.path.join(HERE, "prompts", prompt_name + ".md"), encoding="utf-8").read()
    examples = text[text.index("## Examples"):]
    pieces = re.split(r"```\n(.*?)```", examples, flags=re.S)
    fusion = FusionMcp()
    for index in range(1, len(pieces), 2):
        lead = pieces[index - 1].strip().splitlines()[-1]
        block = pieces[index]
        run_ladder.must(fusion.run_script(NEW_DOCUMENT_SCRIPT), "new document")
        try:
            for phrase, start in START_PARTS.items():
                if phrase in lead:
                    run_ladder.must(fusion.run_script(run_ladder.wrap_script(start, CAD_PRELUDE)), "start part")
            is_success, output = fusion.run_script(run_ladder.wrap_script(block, CAD_PRELUDE))
            print("==", lead[:70], "OK" if is_success else "SCRIPT ERROR")
            print(output.strip())
        finally:
            fusion.run_script(CLOSE_ALL_BENCH_DOCS_SCRIPT)


if __name__ == "__main__":
    main()
