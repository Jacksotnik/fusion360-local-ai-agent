"""Scan the Fusion 360 Gallery reconstruction data on Hugging Face (harrisonxliang/Fusion360Dataset) into the
file tools/gallery_cases.py reads: a list of designs {id, image (a URL), code (the Gallery JSON)}.

It pages through the datasets-server rows API (no download of the parquet files). The image URLs it writes are
signed and expire within hours: run gallery_cases.py right after the scan.

    .venv\\Scripts\\python -X utf8 tools\\gallery_scan.py test scanned_test.json
    .venv\\Scripts\\python -X utf8 tools\\gallery_scan.py test scanned_test.json --ids ids.txt

--ids keeps only the designs listed in the file (one id per line, "G-" prefixes allowed): the way to rebuild a
set that was measured before, e.g. from the case file names of an earlier results folder.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

DATASET = "harrisonxliang/Fusion360Dataset"
ROWS_URL = "https://datasets-server.huggingface.co/rows?dataset=%s&config=default&split=%s&offset=%d&length=%d"
PAGE = 100
RETRIES = 4


def fetch_page(split, offset):
    url = ROWS_URL % (DATASET, split, offset, PAGE)
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == RETRIES - 1:
                raise
            print("offset %d: %s, retrying" % (offset, error), file=sys.stderr)
            time.sleep(10 * (attempt + 1))
    return None


def read_ids(path):
    ids = set()
    with open(path, encoding="utf-8") as file:
        for line in file:
            name = line.strip()
            if not name:
                continue
            if name.startswith("G-"):
                name = name[2:]
            if name.endswith(".json"):
                name = name[:-5]
            ids.add(name)
    return ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("split", choices=["train", "test"])
    parser.add_argument("output")
    parser.add_argument("--ids", help="file with the design ids to keep, one per line")
    args = parser.parse_args()

    wanted = read_ids(args.ids) if args.ids else None
    designs = []
    offset = 0
    total = None
    while total is None or offset < total:
        page = fetch_page(args.split, offset)
        total = int(page.get("num_rows_total", 0))
        rows = page.get("rows", [])
        if not rows:
            break
        for item in rows:
            row = item.get("row", {})
            design_id = str(row.get("id", ""))
            if wanted is not None and design_id not in wanted:
                continue
            image = row.get("image") or {}
            try:
                code = json.loads(row.get("code") or "{}")
            except ValueError:
                print("%s: the code is not JSON, skipped" % design_id, file=sys.stderr)
                continue
            designs.append({"id": design_id, "image": image.get("src", ""), "code": code})

        offset += len(rows)
        print("%s: %d of %d rows read, %d designs kept" % (args.split, offset, total, len(designs)), flush=True)

    if wanted is not None:
        missing = sorted(wanted - set(design["id"] for design in designs))
        if missing:
            print("not found: %s" % ", ".join(missing), file=sys.stderr)
    with open(args.output, "w", encoding="utf-8") as file:
        json.dump(designs, file)
    print("%d designs -> %s" % (len(designs), args.output))


if __name__ == "__main__":
    main()
