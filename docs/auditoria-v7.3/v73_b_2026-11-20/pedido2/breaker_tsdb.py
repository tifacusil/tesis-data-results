"""Per-instance outbound calls and breaker state for the 3 runs, from raw/promql/api_log.json (restored TSDB).
Writes breaker_tsdb_por_instancia.csv."""
import csv, json, os
from datetime import datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
ts = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
iso = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%H:%M:%S")
POD = {"10.42.0.122:8080": "chqw5", "10.42.0.123:8080": "cgprm"}
RUNS = {"1": ("2026-09-30T03:33:12Z", "2026-09-30T03:37:36Z"), "2": ("2026-09-30T03:41:32Z", "2026-09-30T03:45:55Z"),
        "3": ("2026-09-30T03:49:53Z", "2026-09-30T03:54:16Z")}
log = json.load(open(os.path.join(HERE, "raw", "promql", "api_log.json"), encoding="utf-8"))
rows = []
for e in log:
    if not e["tipo"].startswith("breaker_corrida_"):
        continue
    run = e["tipo"][-1]; a, b = map(ts, RUNS[run])
    for s in e["respuesta"]["data"]["result"]:
        m = s["metric"]; v = [(float(t), float(x)) for t, x in s["values"]]
        if m["__name__"] == "ew_outbound_calls_total":
            before = [x for x in v if x[0] <= a]; inside = [x for x in v if a < x[0] <= b]
            start = before[-1] if before else (inside[0] if inside else None)
            if start is None:
                continue
            end = inside[-1] if inside else start
            born = not before
            rows.append([run, m["instance"], POD.get(m["instance"]), "ew_outbound_calls_total", m["outcome"], iso(start[0]), int(start[1]),
                         iso(end[0]), int(end[1]), int(end[1] - start[1]), born, int(end[1] - (0 if born else start[1]))])
        else:
            tr = [(iso(t), int(x)) for i, (t, x) in enumerate(v) if i == 0 or x != v[i - 1][1]]
            rows.append([run, m["instance"], POD.get(m["instance"]), "ew_circuit_breaker_state", "", "", "", "", "", "", "",
                         " ".join(f"{t}={x}" for t, x in tr)])
with open(os.path.join(HERE, "breaker_tsdb_por_instancia.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["corrida", "instance", "pod", "metrica", "outcome", "muestra_inicio_utc", "valor_inicio", "muestra_fin_utc", "valor_fin",
                "delta", "serie_nace_en_ventana", "delta_contando_desde_0_o_transiciones"])
    w.writerows(sorted(rows, key=lambda r: (r[0], r[3], r[2], r[4])))
for r in sorted(rows, key=lambda r: (r[0], r[3], r[2], r[4])): print(r)
