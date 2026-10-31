"""Build every reference result in Fusion and print its signature, to check the references themselves."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fusion_side import CLOSE_BENCH_DOC_SCRIPT, NEW_DOCUMENT_SCRIPT, SIGNATURE_SCRIPT, reference_script
from mcp_client import FusionMcp
from reference_prelude import REFERENCE_PRELUDE

HERE = os.path.dirname(os.path.abspath(__file__))


def must(result, what):
    is_success, text = result
    if not is_success:
        raise RuntimeError(what + " failed: " + text)
    return text


def main():
    cases = json.load(open(os.path.join(HERE, "cases.json"), encoding="utf-8"))["cases"]
    by_id = {case["id"]: case for case in cases}
    fusion = FusionMcp()
    for case in cases:
        must(fusion.run_script(NEW_DOCUMENT_SCRIPT), "new document")
        try:
            if case["start"]:
                must(fusion.run_script(reference_script(REFERENCE_PRELUDE, by_id[case["start"]]["reference"])), "start reference")
            must(fusion.run_script(reference_script(REFERENCE_PRELUDE, case["reference"])), "reference")
            signature = json.loads(must(fusion.run_script(SIGNATURE_SCRIPT, read_only=True), "signature"))
            print(case["id"], json.dumps(signature, ensure_ascii=False), flush=True)
        except Exception as error:
            print(case["id"], "ERROR", error, flush=True)
        finally:
            must(fusion.run_script(CLOSE_BENCH_DOC_SCRIPT), "close")


if __name__ == "__main__":
    main()
