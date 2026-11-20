"""Checks on the 2026-11-20 export of gnss_readings (not in the repository: 122 MB).

    py -I docs/auditoria-v7.3/contar_message_id.py <path>/export.tsv.gz

Counts rows and distinct message_id, and looks up the message_id of the
"rabbitmq publish failed" (3740) and "sink write failed" (105) log lines of
data-receiving (from this repository) in the export. Writes
outputs/b1_message_id_distintos.csv and outputs/b4_ids_de_logs_en_gnss_readings.csv.
"""
import csv
import glob
import gzip
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "auditoria-v7.3", "outputs")

export = sys.argv[1]
gz_sha = hashlib.sha256(open(export, "rb").read()).hexdigest()
tsv_sha = hashlib.sha256()
rows = {}  # message_id -> received_at
dup = 0
with gzip.open(export, "rb") as f:
    header = f.readline()
    tsv_sha.update(header)
    assert header == b"message_id\tsensor_id\ttimestamp\treceived_at\n", header
    for line in f:
        tsv_sha.update(line)
        mid, _, _, received_at = line.rstrip(b"\n").split(b"\t")
        if mid in rows:
            dup += 1
        rows[mid] = received_at
n = len(rows) + dup
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

with open(os.path.join(OUT, "b1_message_id_distintos.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["archivo", "sha256_gz", "sha256_tsv_descomprimido", "filas", "message_id_distintos",
                "message_id_repetidos", "ejecutado_utc"])
    w.writerow(["auditoria_db_b_2026-11-20/raw/export.tsv.gz (fuera del repo)", gz_sha, tsv_sha.hexdigest(),
                n, len(rows), dup, now])

publish_failed = set()
for log in sorted(glob.glob(os.path.join(ROOT, "data", "data-receiving-logs-2026-09-23", "*-previous.log"))):
    for line in open(log, encoding="utf-8"):
        if '"rabbitmq publish failed' in line:
            publish_failed.add(json.loads(line)["message_id"].encode())
logs = json.load(open(os.path.join(ROOT, "results", "auditoria_resistencia", "logs_b.json"), encoding="utf-8"))
sink_failed = {x[2].encode() for x in logs["sink_write_failed_detalle"]}

with open(os.path.join(OUT, "b4_ids_de_logs_en_gnss_readings.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["linea_de_log", "message_id_distintos", "en_exportacion", "min_received_at", "max_received_at"])
    for name, ids in (("rabbitmq publish failed", publish_failed), ("sink write failed", sink_failed)):
        found = sorted(rows[i].decode() for i in ids if i in rows)
        w.writerow([name, len(ids), len(found), found[0] if found else "", found[-1] if found else ""])

print(f"filas={n} distintos={len(rows)} repetidos={dup} sha256_gz={gz_sha} sha256_tsv={tsv_sha.hexdigest()}")
print(f"publish_failed={len(publish_failed)} en_export={sum(i in rows for i in publish_failed)}")
print(f"sink_write_failed={len(sink_failed)} en_export={sum(i in rows for i in sink_failed)}")
