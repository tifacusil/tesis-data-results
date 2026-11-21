"""V7.4 items 6, 7 and A09: breaker rejections and post-closure alerts from the
early-warning logs of 2026-09-30, and the window of `degraded_alerts`.

Reads only repository files. Run from the repository root:

    py -I docs/auditoria-v7.3/v74_2026-11-21/calcular_v74.py

Writes, next to this script:
- rechazos_y_alertas_tras_cierre.csv: per run and pod, `grpcx: circuit open`
  rejections from injection to removal (both inclusive), from removal to
  closure, and in total; alerts logged between closure (first OK call after
  removal, from cronologia_breaker_resumen.csv) and the last log event of the
  run's driver, split by push_path.
- a09_degraded_alerts.csv: the sampler window behind `degraded_alerts`
  (go-tesis-infra chaos/netem-delay-ew-um.sh:563) next to log counts.

An alert is counted from its `alert_emitted` line, which consumer.go writes only
after recordAlert succeeds (go-early-warning@fd5a866 consumer.go:419-436).
"""
import csv
import glob
import json
import os
from collections import Counter
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
P2 = os.path.join(ROOT, "docs", "auditoria-v7.3", "v73_b_2026-11-20", "pedido2")
CHAOS = os.path.join(ROOT, "data", "B - SEPTIEMBRE 5 RUNS V2", "chaos")
# driver start epoch (trace_id prefix) -> run; sampler/summary files per run
RUNS = {"1790739123": 1, "1790739623": 2, "1790740124": 3}
SAMPLES = {1: "1790739192", 2: "1790739691", 3: "1790740192"}
SUMMARY = {1: "1790739192", 2: "1790739692", 3: "1790740193"}


def ts(s):
    s = s.rstrip("Z")
    a, _, b = s.partition(".")
    return datetime.strptime(a + "." + (b[:6] or "0"), "%Y-%m-%dT%H:%M:%S.%f").replace(
        tzinfo=timezone.utc).timestamp()


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def write(name, rows):
    with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


res = {(int(r["corrida"]), r["pod"]): r
       for r in csv.DictReader(open(os.path.join(P2, "cronologia_breaker_resumen.csv"), encoding="utf-8"))}

ev = []  # (run, pod, epoch, msg, record)
for f in sorted(glob.glob(os.path.join(P2, "raw", "logs_ew", "var", "log", "pods", "*", "early-warning", "0.log"))):
    pod = "cgprm" if "cgprm" in f else "chqw5"
    for line in open(f, encoding="utf-8"):
        j = json.loads(line.split(" ", 3)[3])
        tr = j.get("trace_id", "")
        run = RUNS.get(tr.split("-")[2]) if tr.startswith("chaos-um-") else None
        if run:
            ev.append((run, pod, ts(j["time"]), j["msg"], j))

rows = []
for run in (1, 2, 3):
    end = max(e[2] for e in ev if e[0] == run)
    for pod in ("cgprm", "chqw5"):
        r = res[(run, pod)]
        inj, ret, close = ts(r["inyeccion_utc"]), ts(r["retiro_utc"]), ts(r["primer_ok_tras_retiro_utc"])
        e = [x for x in ev if x[0] == run and x[1] == pod]
        co = [x[2] for x in e if x[3] == "push_flow_failed" and x[4].get("err") == "grpcx: circuit open"]
        after = [x for x in e if x[3] == "alert_emitted" and close <= x[2] <= end]
        pp = Counter(x[4].get("push_path") for x in after)
        # Removal to closure: each `circuit open` rejection belongs to one alert stored without push.
        gap = [x for x in e if x[3] == "alert_emitted" and ret < x[2] <= close]
        rej_traces = [x[4]["trace_id"] for x in e if x[3] == "push_flow_failed"
                      and x[4].get("err") == "grpcx: circuit open" and ret < x[2] <= close]
        gap_rf = {x[4]["trace_id"] for x in gap if x[4].get("push_path") == "resolve_failed"}
        assert all(t in gap_rf for t in rej_traces), (run, pod)
        rows.append({
            "corrida": run, "pod": pod,
            "inyeccion_utc": r["inyeccion_utc"], "retiro_utc": r["retiro_utc"],
            "ventana_inyeccion_retiro_s": round(ret - inj, 3),
            "rechazos_inyeccion_retiro": sum(inj <= t <= ret for t in co),
            "rechazos_retiro_cierre": sum(ret < t <= close for t in co),
            "rechazos_total_corrida": len(co),
            "alertas_retiro_cierre": len(gap),
            "sin_push_retiro_cierre": len(gap_rf),
            "primera_alerta_retiro_cierre_utc": iso(min(x[2] for x in gap)) if gap else "",
            "ultima_alerta_retiro_cierre_utc": iso(max(x[2] for x in gap)) if gap else "",
            "cierre_utc": iso(close), "fin_registro_utc": iso(end),
            "ventana_cierre_fin_s": round(end - close, 3),
            "alertas_registradas_tras_cierre": len(after),
            "notificadas_delivered": pp.get("delivered", 0),
            "sin_push_resolve_failed": pp.get("resolve_failed", 0),
            "otro_push_path": len(after) - pp.get("delivered", 0) - pp.get("resolve_failed", 0),
            "db_record_failed_tras_cierre": sum(1 for x in e if x[3] == "db_record_failed" and close <= x[2] <= end),
        })
write("rechazos_y_alertas_tras_cierre.csv", rows)

a09 = []
for run in (1, 2, 3):
    env = dict(l.rstrip("\n").split("=", 1) for l in open(
        os.path.join(CHAOS, f"netem-delay-ew-um-summary-{SUMMARY[run]}.env"), encoding="utf-8") if "=" in l)
    fs = int(env["fail_start"])
    ret = ts(res[(run, "cgprm")]["retiro_utc"])
    s = [x for x in csv.DictReader(open(os.path.join(CHAOS, f"netem-delay-ew-um-samples-{SAMPLES[run]}.csv"),
                                        encoding="utf-8"))
         if fs <= int(x["epoch"]) <= ret and x["dispatch_degraded_count"] not in ("", "NaN")]
    first, last = s[0], s[-1]
    rf = [x[2] for x in ev if x[0] == run and x[3] == "alert_emitted" and x[4].get("push_path") == "resolve_failed"]
    a09.append({
        "corrida": run, "fail_start_utc": env["fail_start_utc"], "retiro_utc": iso(ret),
        "primera_muestra_utc": first["iso_utc"], "ultima_muestra_utc": last["iso_utc"],
        "dispatch_degraded_count_primera": first["dispatch_degraded_count"],
        "dispatch_degraded_count_ultima": last["dispatch_degraded_count"],
        "delta_prometheus": f"{float(last['dispatch_degraded_count']) - float(first['dispatch_degraded_count']):g}",
        "degraded_alerts_env": env["degraded_alerts"],
        "logs_sin_push_inyeccion_retiro": sum(fs <= t <= ret for t in rf),
        "logs_sin_push_inyeccion_ultima_muestra": sum(fs <= t <= int(last["epoch"]) for t in rf),
        "logs_sin_push_ultima_muestra_retiro": sum(int(last["epoch"]) < t <= ret for t in rf),
    })
write("a09_degraded_alerts.csv", a09)

# Self-check against the figures already published in pedido2.md / pedido3.md.
tot = {k: sum(r["rechazos_total_corrida"] for r in rows if r["corrida"] == k) for k in (1, 2, 3)}
win = {k: sum(r["rechazos_inyeccion_retiro"] for r in rows if r["corrida"] == k) for k in (1, 2, 3)}
assert tot == {1: 190, 2: 174, 3: 183}, tot
assert win == {1: 185, 2: 169, 3: 178}, win
assert [a["degraded_alerts_env"] for a in a09] == ["191", "171", "181"]
assert [a["delta_prometheus"] for a in a09] == ["191", "171", "181"]
assert [a["logs_sin_push_inyeccion_retiro"] for a in a09] == [199, 183, 192]
gap = {k: sum(r["sin_push_retiro_cierre"] for r in rows if r["corrida"] == k) for k in (1, 2, 3)}
assert gap == {1: 5, 2: 5, 3: 5}, gap
assert all(r["alertas_retiro_cierre"] == r["sin_push_retiro_cierre"] for r in rows)
# Every alert without push of the run = injection-removal + removal-closure (pedido2.md: 204 / 188 / 197).
allrf = {k: sum(1 for x in ev if x[0] == k and x[3] == "alert_emitted" and x[4].get("push_path") == "resolve_failed")
         for k in (1, 2, 3)}
assert allrf == {1: 204, 2: 188, 3: 197}, allrf
print("ok")
