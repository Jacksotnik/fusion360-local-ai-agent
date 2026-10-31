"""Build the references of the photo tasks, save their renders as the task pictures, check their volumes."""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_ladder
from fusion_side import CLOSE_ALL_BENCH_DOCS_SCRIPT, fit_view_script
from mcp_client import FusionMcp

HERE = os.path.dirname(os.path.abspath(__file__))

HAND_VOLUMES = {
    "P-plate-holes": 24000 - 1884.956 - 678.584,
    "P-flange-8": 14137.167 - 1570.796 - 785.398,
    "P-angle-holes": 7920 - 3 * 78.540,
    "P-box-open": 47570.80 - 36148.9,
    "P-shaft-steps": 11733.85,
}


def main():
    cases = json.load(open(os.path.join(HERE, "cases_photo.json"), encoding="utf-8"))["cases"]
    by_id = {case["id"]: case for case in cases}
    os.makedirs(os.path.join(HERE, "photos"), exist_ok=True)
    fusion = FusionMcp()
    for case in cases:
        run_ladder.build_reference_state(fusion, case, by_id, include_case_reference=True)
        try:
            signature = run_ladder.signature(fusion)
            fusion.run_script(fit_view_script(case.get("view", "iso-top-right")), read_only=True)
            image = fusion.screenshot(direction="current", width=800, height=600, transparent_background=False)
            with open(os.path.join(HERE, case["image"]), "wb") as file:
                file.write(base64.b64decode(image))
            body = signature["bodies"][0]
            hand = HAND_VOLUMES[case["id"]]
            verdict = "OK" if abs(body["volume_mm3"] - hand) / hand < 0.001 and len(signature["bodies"]) == 1 else "MISMATCH"
            print(case["id"], verdict, body["volume_mm3"], "hand", round(hand, 3), body["extents_mm"],
                  body["cylinder_diameters_mm"], signature["unhealthy"])
        finally:
            fusion.run_script(CLOSE_ALL_BENCH_DOCS_SCRIPT)


if __name__ == "__main__":
    main()
