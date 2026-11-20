"""Per-minute and per-second rows of gnss_readings by received_at (UTC), 14:31:20-15:31:20, from the
2026-11-20 window export (export.tsv.gz, sha256 28cee4f9...). Usage: py -I tramo_1431_1531.py <export.tsv.gz>"""
import collections, csv, gzip, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sec = collections.Counter()
with gzip.open(sys.argv[1], "rt", encoding="utf-8") as f:
    next(f)
    for line in f:
        r = line.rstrip("\n").split("\t")[3]
        if "2026-09-23 14:31:00" <= r < "2026-09-23 15:32:00":
            sec[r] += 1
minute = collections.Counter()
for k, v in sec.items():
    if "2026-09-23 14:31:20" <= k < "2026-09-23 15:31:20":
        minute[k[:16]] += v
with open(os.path.join(HERE, "tramo_1431_1531_por_minuto.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, lineterminator="\n"); w.writerow(["minuto_utc", "filas_en_tramo", "segundos_en_tramo", "nominal", "diferencia"])
    for m in sorted(minute):
        secs = 40 if m.endswith("14:31") else 20 if m.endswith("15:31") else 60
        w.writerow([m, minute[m], secs, secs * 100, minute[m] - secs * 100])
with open(os.path.join(HERE, "tramo_1431_1531_bordes_por_segundo.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, lineterminator="\n"); w.writerow(["segundo_utc", "filas"])
    for k in sorted(sec):
        if k[11:16] in ("14:31", "15:31"):
            w.writerow([k, sec[k]])
tot = sum(minute.values())
print("total", tot, "dif", tot - 360000)
for m in sorted(minute):
    secs = 40 if m.endswith("14:31") else 20 if m.endswith("15:31") else 60
    d = minute[m] - secs * 100
    if d: print(m, minute[m], d)
