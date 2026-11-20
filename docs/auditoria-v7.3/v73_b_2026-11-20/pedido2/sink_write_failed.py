"""The 105 'sink write failed' lines straight from the data-receiving logs in the repository.
Usage: py -I sink_write_failed.py <repo>/data/data-receiving-logs-2026-09-23  -> sink_write_failed_105.csv"""
import csv, glob, hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
for log in sorted(glob.glob(os.path.join(sys.argv[1], "*-previous.log"))):
    for n, line in enumerate(open(log, encoding="utf-8"), 1):
        if '"sink write failed"' in line:
            d = json.loads(line)
            rows.append([os.path.basename(log), n, d["instance_id"], d["time"], d["message_id"], d["error"]])
with open(os.path.join(HERE, "sink_write_failed_105.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, lineterminator="\n"); w.writerow(["archivo_log", "linea", "pod", "timestamp_utc", "message_id", "error"]); w.writerows(rows)
print(len(rows), len({r[4] for r in rows}), {k: sum(r[0] == k for r in rows) for k in sorted({r[0] for r in rows})})
