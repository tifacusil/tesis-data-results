"""Pedido 3: per run and pod, alerts between injection and removal of the user-management delay (30/09),
split by breaker state at dispatch. Joins each 'alert_emitted' with the 'push_flow_failed' of the same
trace_id in the same pod (early-warning logs in raw/logs_ew). DeadlineExceeded invocations 1-5 of each run
are dispatched with the breaker closed (the 5th opens it); later ones are failed half-open probes (see
cronologia_breaker_eventos.csv, whose 'lectura' column is checked here). Writes alertas_sin_push_por_estado.csv."""
import collections, csv, glob, json, os, re
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__))
ts = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
RUNS = {"1": ("2026-09-30T03:33:12Z", "2026-09-30T03:37:16Z"), "2": ("2026-09-30T03:41:32Z", "2026-09-30T03:45:35Z"),
        "3": ("2026-09-30T03:49:53Z", "2026-09-30T03:53:56Z")}
fails, alerts = {}, []
for log in glob.glob(os.path.join(HERE, "raw", "logs_ew", "**", "0.log"), recursive=True):
    pod = re.search(r"55859f5589-(\w+)_", log).group(1)
    for line in open(log, encoding="utf-8"):
        if '"push_flow_failed"' in line or '"alert_emitted"' in line:
            d = json.loads(line[line.index("{"):])
            if d["msg"] == "push_flow_failed":
                fails[(pod, d["trace_id"])] = (ts(d["time"]), d["err"])
            else:
                alerts.append((ts(d["time"]), pod, d["trace_id"], d["push_path"]))
alerts.sort()
lectura = {(r["corrida"], r["pod"]): [x for x in []] for r in []}
cron = collections.defaultdict(list)
for r in csv.DictReader(open(os.path.join(HERE, "cronologia_breaker_eventos.csv"), encoding="utf-8")):
    if r["evento"] == "invocacion_agotada":
        cron[(r["corrida"], r["pod"])].append(r["lectura"])
rows, check = [], []
for run, (a, b) in RUNS.items():
    for pod in ("cgprm", "chqw5"):
        c = collections.Counter(); n_de = 0
        for t, p, tid, pp in alerts:
            if p != pod or not ts(a) <= t <= ts(b):
                continue
            if pp == "delivered":
                c["push_entregado"] += 1; continue
            if pp != "resolve_failed":
                c["otro_" + pp] += 1; continue
            err = fails[(pod, tid)][1]
            if "circuit open" in err:
                c["b_abierto_circuit_open"] += 1
            elif "DeadlineExceeded" in err:
                n_de += 1
                c["a_cerrado_deadline_exceeded" if n_de <= 5 else "c_semiabierto_sonda_fallida"] += 1
            else:
                c["otro_error"] += 1
        sin_push = c["a_cerrado_deadline_exceeded"] + c["b_abierto_circuit_open"] + c["c_semiabierto_sonda_fallida"]
        # cross-check against the chronology: first 5 readings are 'fallo n', the rest 'sonda semiabierta fallida'
        lect = cron[(run, pod)]
        check.append(sum(x.startswith("fallo") for x in lect) == c["a_cerrado_deadline_exceeded"]
                     and sum(x.startswith("sonda") for x in lect) == c["c_semiabierto_sonda_fallida"])
        rows.append([run, pod, a, b, c["a_cerrado_deadline_exceeded"], c["b_abierto_circuit_open"],
                     c["c_semiabierto_sonda_fallida"], sin_push, c["push_entregado"], c["otro_error"]])
    tot = [sum(r[i] for r in rows[-2:]) for i in range(4, 10)]
    rows.append([run, "total", a, b] + tot)
with open(os.path.join(HERE, "alertas_sin_push_por_estado.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["corrida", "pod", "inyeccion_utc", "retiro_utc", "a_cerrado_deadline_exceeded", "b_abierto_circuit_open",
                "c_semiabierto_sonda_fallida", "sin_push_resolve_failed", "push_entregado", "otro_error"])
    w.writerows(rows)
for r in rows: print(r)
print("coincide con cronologia:", all(check))
