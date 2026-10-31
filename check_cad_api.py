"""Solve every case with the CAD helper API and compare with the reference signatures (checks the helpers)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_ladder
from cad_api import CAD_PRELUDE
from fusion_side import CLOSE_ALL_BENCH_DOCS_SCRIPT
from mcp_client import FusionMcp

SOLUTIONS = {
    "L1-cube": "sk = new_sketch('XY')\nrect(sk, 0, 0, 20, 20)\nextrude(sk, 20)",
    "L1-cylinder": "sk = new_sketch('XY')\ncircle(sk, 0, 0, 30)\nextrude(sk, 10)",
    "L1-plate": "sk = new_sketch('XY')\nrect_center(sk, 0, 0, 60, 40)\nextrude(sk, -5)",
    "L2-plate-center-hole": "sk = new_sketch('XY')\nrect(sk, 0, 0, 60, 40)\ncircle(sk, 30, 20, 12)\nextrude(sk, 5)",
    "L2-plate-4-holes": ("sk = new_sketch('XY')\nrect(sk, 0, 0, 60, 40)\nextrude(sk, 5)\n"
                         "holes([(8, 8), (52, 8), (8, 32), (52, 32)], 5)"),
    "L2-bushing": "sk = new_sketch('XZ', offset=7)\ncircle(sk, 0, 0, 20)\ncircle(sk, 0, 0, 10)\nextrude(sk, 15)",
    "L3-bigger-holes": "for c in find_circles(diameter=5):\n    set_diameter(c, 6)",
    "L3-round-corners": "fillet(find_edges(parallel_to='Z'), 5)",
    "L3-chamfer": "chamfer(find_edges(kind='circle', diameter=20, z=15), 1)",
    "L4-flange": ("sk = new_sketch('XY')\ncircle(sk, 0, 0, 60)\ncircle(sk, 0, 0, 20)\nextrude(sk, 6)\n"
                  "hole = holes([(22.5, 0)], 6)\ncircular_pattern(hole, 6)"),
    "L4-revolve-knob": ("sk = new_sketch('XZ')\npolygon(sk, [(0, 0), (10, 0), (10, 10), (6, 10), (6, 25), (0, 25)])\n"
                        "revolve(sk, 'Z')"),
}


def main():
    cases = json.load(open(os.path.join(run_ladder.HERE, "cases.json"), encoding="utf-8"))["cases"]
    by_id = {case["id"]: case for case in cases}
    cache = json.load(open(run_ladder.EXPECTED_CACHE, encoding="utf-8"))
    fusion = FusionMcp()
    for case in cases:
        expected = run_ladder.expected_signature(fusion, case, by_id, cache)
        run_ladder.build_reference_state(fusion, case, by_id, include_case_reference=False)
        try:
            body = SOLUTIONS[case["id"]] + "\ndescribe()"
            is_success, text = fusion.run_script(run_ladder.wrap_script(body, CAD_PRELUDE))
            if not is_success:
                print(case["id"], "SCRIPT ERROR", text)
                continue
            problems = run_ladder.compare(expected, run_ladder.signature(fusion))
            print(case["id"], "OK" if not problems else problems)
            print(text)
        finally:
            fusion.run_script(CLOSE_ALL_BENCH_DOCS_SCRIPT)


if __name__ == "__main__":
    main()
