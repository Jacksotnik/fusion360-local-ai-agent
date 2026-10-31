"""Pass rate and timing over result folders: python -I -X utf8 stats.py results/h3-v9-r1 results/h3-v9-r2 ..."""
import glob
import json
import os
import statistics
import sys


def main():
    folders = sys.argv[1:]
    records = []
    for folder in folders:
        for path in glob.glob(os.path.join(folder, "*.json")):
            record = json.load(open(path, encoding="utf-8"))
            if "passed" in record:
                records.append(record)
    if not records:
        print("no case records")
        return
    passed = sum(1 for record in records if record["passed"])
    seconds = sorted(record["seconds"] for record in records)
    calls = sorted(len(record.get("calls", [])) for record in records)
    p90 = seconds[min(len(seconds) - 1, int(round(0.9 * (len(seconds) - 1))))]
    print("cases %d, passed %d (%.0f%%)" % (len(records), passed, 100.0 * passed / len(records)))
    print("seconds per case: median %.0f, mean %.0f, p90 %.0f, max %.0f" % (
        statistics.median(seconds), statistics.mean(seconds), p90, seconds[-1]))
    print("model calls per case: median %.0f, max %d" % (statistics.median(calls), calls[-1]))
    under_15 = sum(1 for value in seconds if value <= 15)
    print("cases done within 15 s: %d of %d" % (under_15, len(seconds)))


if __name__ == "__main__":
    main()
