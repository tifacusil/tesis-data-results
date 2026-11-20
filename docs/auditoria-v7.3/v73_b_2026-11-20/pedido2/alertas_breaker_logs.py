"""alert_emitted lines by push_path per run and pod (early-warning logs, 30/09), in two windows:
[injection, removal] and the sampler window [first, last sample]. Writes alertas_breaker_por_push_path.csv."""
import collections, csv, glob, json, os, re
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__))
ts = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
RUNS = {"1": ("2026-09-30T03:33:12Z", "2026-09-30T03:37:16Z", "2026-09-30T03:35:08Z", "2026-09-30T03:37:36Z"),
        "2": ("2026-09-30T03:41:32Z", "2026-09-30T03:45:35Z", "2026-09-30T03:43:43Z", "2026-09-30T03:45:55Z"),
        "3": ("2026-09-30T03:49:53Z", "2026-09-30T03:53:56Z", "2026-09-30T03:51:56Z", "2026-09-30T03:54:16Z")}
ev = []
for log in glob.glob(os.path.join(HERE, "raw", "logs_ew", "**", "0.log"), recursive=True):
    pod = re.search(r"55859f5589-(\w+)_", log).group(1)
    for line in open(log, encoding="utf-8"):
        if '"alert_emitted"' in line:
            d = json.loads(line[line.index("{"):]); ev.append((ts(d["time"]), pod, d["push_path"]))
rows = []
for run, (inj, rem, first_open_poll, last_sample) in RUNS.items():
    for wname, a, b in (("inyeccion_a_retiro", inj, rem), ("ventana_muestreo", inj, last_sample)):
        c = collections.Counter((p, pp) for t, p, pp in ev if ts(a) <= t <= ts(b))
        for (pod, pp), n in sorted(c.items()):
            rows.append([run, wname, a, b, pod, pp, n])
        rows.append([run, wname, a, b, "total", "todas", sum(c.values())])
        rows.append([run, wname, a, b, "total", "sin_push(resolve_failed)", sum(n for (p, pp), n in c.items() if pp == "resolve_failed")])
with open(os.path.join(HERE, "alertas_breaker_por_push_path.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, lineterminator="\n"); w.writerow(["corrida", "ventana", "desde_utc", "hasta_utc", "pod", "push_path", "alertas"]); w.writerows(rows)
for r in rows:
    if r[4] == "total": print(r)
