"""Per-replica breaker chronology for the 3 user-management delay runs (30/09/2026), from the
early-warning pod logs (raw/logs_ew). Writes cronologia_breaker_eventos.csv and cronologia_breaker_resumen.csv.

Breaker rules (go-early-warning@fd5a866, pkg/grpcx/grpcx.go:96-146; cmd/early-warning/main.go:127-131):
one Invoke = up to 3 attempts (MaxRetries 2), 5 s timeout each, backoff 1 s / 5 s; the breaker counts one
failure per failed Invoke, opens at 5 consecutive failures, goes half-open 30 s after opening, and one failed
half-open probe reopens it. A 'push_flow_failed' line with DeadlineExceeded is the end of a failed Invoke,
'grpcx: circuit open' is a rejected call, 'push_delivered' implies a successful Invoke.
"""
import csv, glob, json, os, re
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = [("1", "2026-09-30T03:33:12Z", "2026-09-30T03:35:08Z", "2026-09-30T03:37:16Z"),
        ("2", "2026-09-30T03:41:32Z", "2026-09-30T03:43:43Z", "2026-09-30T03:45:35Z"),
        ("3", "2026-09-30T03:49:53Z", "2026-09-30T03:51:56Z", "2026-09-30T03:53:56Z")]
ts = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
iso = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"

events = []
for log in sorted(glob.glob(os.path.join(HERE, "raw", "logs_ew", "**", "0.log"), recursive=True)):
    pod = re.search(r"early-warning-55859f5589-(\w+)_", log).group(1)
    for line in open(log, encoding="utf-8"):
        try:
            d = json.loads(line[line.index("{"):])
        except ValueError:
            continue
        kind = None
        if d["msg"] == "push_flow_failed":
            kind = "rechazada_circuit_open" if "circuit open" in d.get("err", "") else (
                "invocacion_agotada" if "DeadlineExceeded" in d.get("err", "") else "otro_error")
        elif d["msg"] == "push_delivered":
            kind = "invocacion_ok"
        if kind:
            events.append((ts(d["time"]), pod, kind, d.get("err", "")))
events.sort()

rows_ev, rows_sum = [], []
for run, inj, opened_poll, removed in RUNS:
    t_inj, t_rem = ts(inj), ts(removed)
    for pod in sorted({e[1] for e in events}):
        ev = [e for e in events if e[1] == pod and t_inj - 60 <= e[0] <= t_rem + 120]
        state, fails, opened_at, timeline = "closed", 0, None, []
        first_open = None
        for t, _, kind, err in ev:
            # half-open is only observable on the next call, as in grpcx.gate()
            if state == "open" and t - opened_at >= 30 and kind != "rechazada_circuit_open":
                state = "half_open"
            if kind == "invocacion_agotada":
                fails += 1
                note = "fallo %d" % fails
                if state == "half_open":
                    note = "sonda semiabierta fallida: reabre"
                if state == "half_open" or fails >= 5:
                    state, opened_at = "open", t
                    first_open = first_open or t
                    if note.startswith("fallo"):
                        note += ": abre" if fails == 5 else ": sigue abierto"
            elif kind == "invocacion_ok":
                note = "cierra" if state != "closed" else "ok"
                if state != "closed":
                    timeline.append(("cierre", t))
                state, fails = "closed", 0
            else:
                note = "rechazada"
            rows_ev.append([run, pod, iso(t), round(t - t_inj, 1), kind, note, state, err[:80]])
        agotadas = [e for e in ev if e[2] == "invocacion_agotada" and e[0] <= t_rem + 30]
        rech = [e for e in ev if e[2] == "rechazada_circuit_open"]
        cierre = next((t for k, t in timeline if t > t_rem), None)
        rows_sum.append([run, pod, inj, removed, len(agotadas), min(len(agotadas), 5), max(len(agotadas) - 5, 0),
                         iso(first_open) if first_open else "", round(first_open - t_inj, 1) if first_open else "",
                         len(rech), iso(cierre) if cierre else "", round(cierre - t_rem, 1) if cierre else ""])

with open(os.path.join(HERE, "cronologia_breaker_eventos.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["corrida", "pod", "hora_log_utc", "s_desde_inyeccion", "evento", "lectura", "estado_tras_evento", "err"])
    w.writerows(rows_ev)
with open(os.path.join(HERE, "cronologia_breaker_resumen.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["corrida", "pod", "inyeccion_utc", "retiro_utc", "invocaciones_agotadas", "de_apertura", "sondas_semiabiertas",
                "primera_apertura_utc", "apertura_s_desde_inyeccion", "rechazadas_circuit_open_en_log",
                "primer_ok_tras_retiro_utc", "cierre_s_desde_retiro"])
    w.writerows(rows_sum)
for r in rows_sum: print(r)
