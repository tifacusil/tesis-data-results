#!/usr/bin/env python3
"""Compute every figure of docs/auditoria-resistencia-12h.md from frozen files.

Inputs (all read-only):
  - data/<A|B>/sustained-12h.json            Artillery reports of the 12 h runs
  - results/auditoria_resistencia/prometheus  raw exports (exportar_prometheus.py)
  - results/auditoria_resistencia/logs_b.json B log reconciliation (analizar_logs_b.py)

Outputs:
  - results/auditoria_resistencia/hallazgos.json   every value cited in the report
  - results/resistencia_memoria/memoria_nodo_{A,B}.csv, memoria_servicio_B.csv
  - results/resistencia_memoria/memoria_12h.png

  venv/Scripts/python.exe scripts/auditoria_resistencia/auditar.py

Needs NumPy and Matplotlib (requirements.txt). All times are UTC.
Counters: increases are summed per series from consecutive raw samples; a drop
is taken as a counter reset and the new value is added (Prometheus increase()
semantics without extrapolation). Increments between the last scrape before a
process restart and the restart itself are not in the TSDB and are not counted.
"""
import json
import pathlib
from datetime import datetime, timezone

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROM = ROOT / "results/auditoria_resistencia/prometheus"
OUT = ROOT / "results/auditoria_resistencia"
MEM = ROOT / "results/resistencia_memoria"
ART = {"A": ROOT / "data/A - SPETIEMBRE 5 RUNS/sustained-12h.json",
       "B": ROOT / "data/B - SEPTIEMBRE 5 RUNS V2/sustained-12h.json"}


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Perturbation intervals (UTC).
# B: exact times of the chaos commands in the node journal (journal-B-2026-09-15_2026-10-01.txt,
#    sudo lines): kubectl delete pod rabbitmq 14:32:23.61; kill -STOP 18:32:29.65 / kill -CONT 18:33:59.82;
#    tc netem add 22:32:28.17 / first tc qdisc del 22:35:37.84 (second pod). Broker end = first
#    kube-state-metrics sample with the new rabbitmq-0 Ready=1 (14:33:00, 15 s resolution).
# A: no journal for 18/09; the bounds are the pre/post chaos snapshots (capture times, not injection times).
INJ = {
    "A": [
        ("caida_broker", ts("2026-09-18T07:18:20Z"), ts("2026-09-18T07:19:10Z")),
        ("pausa_dm", ts("2026-09-18T11:18:19Z"), ts("2026-09-18T11:20:01Z")),
    ],
    "B": [
        ("caida_broker", ts("2026-09-23T14:32:23.61Z"), ts("2026-09-23T14:33:00Z")),
        ("pausa_dm", ts("2026-09-23T18:32:29.65Z"), ts("2026-09-23T18:33:59.82Z")),
        ("netem_da", ts("2026-09-23T22:32:28.17Z"), ts("2026-09-23T22:35:37.84Z")),
    ],
}
EXCL_AFTER = 600  # memory: each injection is excluded from its start to 10 min after its end


def load(system, name):
    return json.loads((PROM / f"{system}__{name}.json").read_text())["data"]["result"]


def samples(series):
    return [(float(t), float(v)) for t, v in series.get("values", [])]


def increase(series, t0, t1):
    """Increase from the last sample at or before t0 to the last sample at or before t1."""
    allp = [p for p in samples(series) if p[0] <= t1]
    before = [i for i, p in enumerate(allp) if p[0] <= t0]
    pts = allp[before[-1]:] if before else allp
    inc = 0.0
    for (_, a), (_, b) in zip(pts, pts[1:]):
        inc += b - a if b >= a else b
    return inc, pts[0][0] if pts else None, pts[-1][0] if pts else None


def total_increase(result, t0, t1, flt=lambda m: True):
    return sum(increase(s, t0, t1)[0] for s in result if flt(s["metric"]))


def resets(series):
    pts = samples(series)
    return [(iso(b[0]), a[1], b[1]) for a, b in zip(pts, pts[1:]) if b[1] < a[1]]


def label(m):
    return ",".join(f"{k}={v}" for k, v in sorted(m.items()) if k not in ("__name__", "job"))


def artillery(system):
    d = json.loads(ART[system].read_text())
    ag = d["aggregate"]
    c = ag["counters"]
    periods = []
    for p in d["intermediate"]:
        s = p["summaries"].get("dtu_tcp.round_trip_ms", {})
        errs = {k: v for k, v in p["counters"].items() if k.startswith("errors.")}
        periods.append({"t": int(p["period"]) / 1000, "failed": p["counters"].get("vusers.failed", 0),
                        "acked": p["counters"].get("dtu_tcp.frames_acked", 0), "errors": errs,
                        "p95": s.get("p95"), "max": s.get("max")})
    periods.sort(key=lambda r: r["t"])
    emitted, acked, failed = c["vusers.created"], c["dtu_tcp.frames_acked"], c.get("vusers.failed", 0)
    return {
        "archivo": str(ART[system].relative_to(ROOT)).replace("\\", "/"),
        "inicio": iso(ag["firstMetricAt"] / 1000), "fin": iso(ag["lastMetricAt"] / 1000),
        "inicio_epoch": ag["firstMetricAt"] / 1000, "fin_epoch": ag["lastMetricAt"] / 1000,
        "contadores": c,
        "emitidas": emitted, "confirmadas": acked, "fallidas": failed,
        "cuadra": emitted == acked + failed,
        "no_confirmadas_pct": 100 * (emitted - acked) / emitted,
        "p95_agregado": ag["summaries"]["dtu_tcp.round_trip_ms"]["p95"],
        "periodos_con_fallos": [{"periodo": iso(p["t"]), "fallidas": p["failed"], "errores": p["errors"]}
                                for p in periods if p["failed"]],
        "_periods": periods,
    }


def p95_runs(periods, thr=1000.0):
    runs, cur = [], None
    for p in periods:
        hi = p["p95"] is not None and p["p95"] > thr
        if hi and cur is None:
            cur = [p["t"], p["t"] + 10, p["p95"]]
        elif hi:
            cur[1] = p["t"] + 10
            cur[2] = max(cur[2], p["p95"])
        elif cur is not None:
            runs.append(cur)
            cur = None
    if cur:
        runs.append(cur)
    return runs


def restarts_b(t0, t1):
    out = []
    for s in load("B", "restarts"):
        m = s["metric"]
        pts = [p for p in samples(s) if t0 <= p[0] <= t1]
        for a, b in zip(pts, pts[1:]):
            if b[1] > a[1]:
                out.append({"pod": m.get("pod"), "container": m.get("container"),
                            "entre": [iso(a[0]), iso(b[0])], "de": a[1], "a": b[1]})
    return sorted(out, key=lambda r: r["entre"][1])


def not_ready_b(t0, t1, pod_prefix):
    out = []
    for s in load("B", "ready"):
        m = s["metric"]
        if not m.get("pod", "").startswith(pod_prefix):
            continue
        pts = [p for p in samples(s) if t0 <= p[0] <= t1]
        zero = [p[0] for p in pts if p[1] == 0]
        if zero:
            out.append({"pod": m["pod"], "container": m.get("container"), "ready_0_desde": iso(min(zero)),
                        "ready_0_hasta": iso(max(zero)), "muestras_0": len(zero)})
    return out


def restarts_a(t0, t1):
    out = []
    for s in load("A", "process_start"):
        vals = sorted({p[1] for p in samples(s) if t0 <= p[0] <= t1})
        if len(vals) > 1:
            out.append({"serie": label(s["metric"]), "inicios": [iso(v) for v in vals]})
    return out


def down_a(t0, t1):
    out = []
    for s in load("A", "up"):
        z = [p[0] for p in samples(s) if t0 <= p[0] <= t1 and p[1] == 0]
        if z:
            out.append({"serie": label(s["metric"]), "up_0_desde": iso(min(z)), "up_0_hasta": iso(max(z)), "muestras": len(z)})
    return out


def transitions(result, t0, t1):
    """Per series: every raw sample where the value changes, with the previous sample's time."""
    out = []
    for s in result:
        pts = [p for p in samples(s) if t0 <= p[0] <= t1]
        ch = [{"antes": iso(x[0]), "despues": iso(y[0]), "de": x[1], "a": y[1]} for x, y in zip(pts, pts[1:]) if y[1] != x[1]]
        if ch:
            out.append({"serie": label(s["metric"]), "cambios": ch})
    return out


def max_by_time(result, flt=lambda m: True):
    """max() over series at each scrape timestamp (raw samples share scrape times only per target; bucket to 15 s)."""
    buckets = {}
    for s in result:
        if not flt(s["metric"]):
            continue
        for t, v in samples(s):
            k = round(t / 15) * 15
            buckets[k] = max(buckets.get(k, v), v)
    return sorted(buckets.items())


def series_minmax(result, t0, t1):
    rows = []
    for s in result:
        v = [p[1] for p in samples(s) if t0 <= p[0] <= t1]
        rows.append({"serie": label(s["metric"]), "min": min(v), "max": max(v), "muestras": len(v)})
    return rows


def memory(system, art):
    t_ramp = art["inicio_epoch"] + 180
    t_end = art["fin_epoch"]
    res = load(system, "mem_node")
    assert len(res) == 1, "expected one node_exporter series"
    pts = [(t, v / 1048576) for t, v in samples(res[0]) if t_ramp <= t <= t_end]
    win = [(n, a, b) for n, a, b in INJ[system]]

    def excluded(t):
        return any(a <= t <= b + EXCL_AFTER for _, a, b in win)

    def stats(p):
        t = np.array([x[0] for x in p])
        v = np.array([x[1] for x in p])
        slope = np.polyfit((t - t[0]) / 3600, v, 1)[0]
        return {"muestras": len(p), "inicial_MiB": round(v[0], 1), "inicial_t": iso(t[0]),
                "final_MiB": round(v[-1], 1), "final_t": iso(t[-1]),
                "min_MiB": round(v.min(), 1), "min_t": iso(t[v.argmin()]),
                "max_MiB": round(v.max(), 1), "max_t": iso(t[v.argmax()]),
                "pendiente_MiB_h": round(float(slope), 2)}

    keep = [p for p in pts if not excluded(p[0])]
    by_win = {}
    for n, a, b in win:
        w = [p for p in pts if a <= p[0] <= b + EXCL_AFTER]
        v = [x[1] for x in w]
        by_win[n] = {"desde": iso(a), "hasta": iso(b + EXCL_AFTER), "muestras": len(w),
                     "min_MiB": round(min(v), 1), "max_MiB": round(max(v), 1)}
    MEM.mkdir(parents=True, exist_ok=True)
    with open(MEM / f"memoria_nodo_{system}.csv", "w", newline="") as f:
        f.write("time_utc,node_mem_used_mib,excluida_inyeccion\n")
        for t, v in pts:
            f.write(f"{iso(t)},{v:.1f},{int(excluded(t))}\n")
    return {"consulta": "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes", "paso": "60s",
            "ventana": [iso(t_ramp), iso(t_end)], "exclusion": f"[inicio, fin + {EXCL_AFTER} s] de cada inyeccion",
            "todo": stats(pts), "sin_inyecciones": stats(keep), "ventanas_inyeccion": by_win, "_pts": pts}


def memory_services_b(art):
    t_ramp, t_end = art["inicio_epoch"] + 180, art["fin_epoch"]
    win = INJ["B"]

    def excluded(t):
        return any(a <= t <= b + EXCL_AFTER for _, a, b in win)

    rows, cols = {}, {}
    for s in load("B", "mem_rss_app"):
        app = s["metric"]["app"]
        pts = [(t, v / 1048576) for t, v in samples(s) if t_ramp <= t <= t_end]
        cols[app] = dict(pts)
        keep = [p for p in pts if not excluded(p[0])]
        t = np.array([p[0] for p in keep])
        v = np.array([p[1] for p in keep])
        allv = np.array([p[1] for p in pts])
        rows[app] = {"inicial_MiB": round(pts[0][1], 1), "final_MiB": round(pts[-1][1], 1),
                     "min_MiB": round(allv.min(), 1), "max_MiB": round(allv.max(), 1),
                     "pendiente_sin_inyecciones_MiB_h": round(float(np.polyfit((t - t[0]) / 3600, v, 1)[0]), 2),
                     "pendiente_todo_MiB_h": round(float(np.polyfit((np.array([p[0] for p in pts]) - pts[0][0]) / 3600, allv, 1)[0]), 2),
                     "muestras": len(pts)}
    times = sorted({t for c in cols.values() for t in c})
    apps = sorted(cols)
    with open(MEM / "memoria_servicio_B.csv", "w", newline="") as f:
        f.write("time_utc," + ",".join(f"rss_mib_{a}" for a in apps) + ",excluida_inyeccion\n")
        for t in times:
            f.write(iso(t) + "," + ",".join(f"{cols[a][t]:.1f}" if t in cols[a] else "" for a in apps) + f",{int(excluded(t))}\n")
    return {"consulta": 'sum by (app) (process_resident_memory_bytes{app!=""})', "paso": "60s", "servicios": rows}


def plot(mem, arts):
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
    for ax, system in zip(axes, ("A", "B")):
        pts = mem[system]["_pts"]
        t0 = arts[system]["inicio_epoch"]
        x = [(t - t0) / 3600 for t, _ in pts]
        ax.plot(x, [v for _, v in pts], lw=1, color="#3b6ea5")
        for n, a, b in INJ[system]:
            ax.axvline((a - t0) / 3600, color="#c0392b", lw=1, ls="--")
            ax.text((a - t0) / 3600, ax.get_ylim()[1], f" {n}", color="#c0392b", fontsize=8, va="top")
        s = mem[system]["sin_inyecciones"]
        ax.set_title(f"Sistema {system}: memoria usada del nodo (MemTotal − MemAvailable), "
                     f"pendiente sin inyecciones {s['pendiente_MiB_h']} MiB/h")
        ax.set_ylabel("MiB")
        ax.set_xlabel(f"horas desde el inicio de Artillery ({arts[system]['inicio']} UTC)")
        ax.grid(alpha=0.3)
    fig.savefig(MEM / "memoria_12h.png", dpi=120)


def main():
    H = {"zona_horaria": "UTC"}
    arts = {s: artillery(s) for s in ("A", "B")}
    for s in ("A", "B"):
        H[f"artillery_{s}"] = {k: v for k, v in arts[s].items() if not k.startswith("_")}

    # Section 5: incident intervals.
    inc = {}
    for s in ("A", "B"):
        per = arts[s]["_periods"]
        runs = p95_runs(per)
        rows = []
        for n, a, b in INJ[s]:
            lo, hi = a - 600, b + 1800
            fails = [p for p in per if p["failed"] and lo <= p["t"] <= hi]
            r = [x for x in runs if lo <= x[0] <= hi]
            row = {"evento": n, "inicio": iso(a), "fin": iso(b),
                   "primer_periodo_con_fallo": iso(fails[0]["t"]) if fails else None,
                   "ultimo_periodo_con_fallo": iso(fails[-1]["t"]) if fails else None,
                   "fallos": sum(p["failed"] for p in fails),
                   "p95_mayor_1s": [{"desde": iso(x[0]), "hasta": iso(x[1]), "p95_max_ms": x[2]} for x in r]}
            if s == "B":
                row["reinicios"] = restarts_b(a - 300, b + 1800)
                row["ready_0"] = (not_ready_b(a - 300, b + 1800, "rabbitmq") if n == "caida_broker" else
                                  not_ready_b(a - 300, b + 1800, "data-management") if n == "pausa_dm" else
                                  not_ready_b(a - 300, b + 1800, "data-analysis"))
            else:
                row["reinicios_process_start"] = restarts_a(a - 300, b + 1800)
                row["up_0"] = down_a(a - 300, b + 1800)
                row["dm_rabbitmq_connections"] = transitions(load("A", "dm_rabbit_connections"), a - 300, b + 600)
                row["dr_outgoing_connections"] = transitions(load("A", "dr_outgoing_connections"), a - 300, b + 600)
            rows.append(row)
        inc[s] = {"eventos": rows, "todos_los_periodos_p95_mayor_1s": [
            {"desde": iso(x[0]), "hasta": iso(x[1]), "p95_max_ms": x[2]} for x in runs]}
    H["incidencias"] = inc
    H["reinicios_B_corrida"] = restarts_b(arts["B"]["inicio_epoch"], arts["B"]["fin_epoch"] + 300)
    H["reinicios_A_corrida"] = restarts_a(arts["A"]["inicio_epoch"], arts["A"]["fin_epoch"] + 300)

    # Section 3: durability.
    dur = {}
    for s in ("A", "B"):
        # From the last scrape before Artillery's first frame to 5 min after its last one (pipeline drain).
        t0, t1 = arts[s]["inicio_epoch"], arts[s]["fin_epoch"] + 300
        pre0 = arts[s]["inicio_epoch"] - 300
        d = {"ventana": [iso(t0), iso(t1)],
             "trafico_previo_frames": {"ventana": [iso(pre0), iso(t0)], "frames": total_increase(load(s, "frames"), pre0, t0)},
             "frames_ok": total_increase(load(s, "frames"), t0, t1, lambda m: m.get("result") == "ok"),
             "frames_no_ok": total_increase(load(s, "frames"), t0, t1, lambda m: m.get("result") != "ok"),
             "published": total_increase(load(s, "published"), t0, t1),
             "dm_processed": total_increase(load(s, "dm_processed"), t0, t1),
             "mysql_rows_inserted": total_increase(load(s, "mysql_rows_inserted"), t0, t1),
             "resets": {n: [{"serie": label(x["metric"]), "resets": resets(x)} for x in load(s, n) if resets(x)]
                        for n in ("frames", "published", "dm_processed", "mysql_rows_inserted")}}
        if s == "B":
            d["mysql_insert_cmds"] = total_increase(load(s, "mysql_insert_cmds"), t0, t1)
            d["ew_consumed"] = total_increase(load(s, "ew_consumed"), t0, t1)
            d["ew_duplicates"] = total_increase(load(s, "ew_duplicates"), t0, t1)
            d["ew_alerts"] = total_increase(load(s, "ew_alerts"), t0, t1)
            d["ew_alert_delivery_count"] = total_increase(load(s, "ew_alert_delivery_count"), t0, t1)
            d["queue_published"] = {x["metric"]["queue"]: increase(x, t0, t1)[0] for x in load(s, "queue_published")}
            d["contadores_cero"] = {n: series_minmax(load(s, n), t0, t1) for n in
                                    ("dr_dropped", "dm_dlq", "dm_retried", "dm_invalid", "ew_dropped")}
            d["dead_letter_queue"] = series_minmax([x for x in load(s, "queues") if x["metric"]["queue"] == "sensors.dead_letter"], t0, t1)
            buf = max_by_time(load(s, "buffer"))
            ev0, ev1 = ts("2026-09-23T14:20:00Z"), ts("2026-09-23T15:00:00Z")
            b_ev = [p for p in buf if ev0 <= p[0] <= ev1]
            bmax = max(b_ev, key=lambda p: p[1])
            back0 = next((p for p in b_ev if p[0] > bmax[0] and p[1] == 0), None)
            # Steady-state level: max() over the 20 min before the kill (in-flight entries, never 0 for long).
            base = max(v for t, v in buf if INJ["B"][0][1] - 1200 <= t < INJ["B"][0][1])
            back_base = next((p for p in b_ev if p[0] > bmax[0] and p[1] <= base), None)
            d["buffer_caida_broker"] = {
                "agregacion": "max() entre replicas, muestras agrupadas en intervalos de 15 s",
                "max": bmax[1], "max_t": iso(bmax[0]),
                "linea_base_20min_previos": base,
                "vuelve_a_linea_base": iso(back_base[0]) if back_base else None,
                "vuelve_a_0": iso(back0[0]) if back0 else None,
                "muestras_14_32_30_a_14_36_30": [(iso(t), v) for t, v in b_ev if ts("2026-09-23T14:32:30Z") <= t <= ts("2026-09-23T14:36:30Z")],
                "por_replica_max": [{"serie": label(x["metric"]),
                                     "max": max(v for t, v in samples(x) if ev0 <= t <= ev1),
                                     "primera_muestra_con_max": iso(min(t for t, v in samples(x) if ev0 <= t <= ev1 and v == max(
                                         w for u, w in samples(x) if ev0 <= u <= ev1)))} for x in load(s, "buffer")]}
            d["buffer_corrida_max"] = max(buf, key=lambda p: p[1] if t0 <= p[0] <= t1 else -1)
            d["buffer_corrida_max"] = [iso(d["buffer_corrida_max"][0]), d["buffer_corrida_max"][1]]
        else:
            d["dr_dropped"] = series_minmax(load(s, "dr_dropped"), t0, t1)
            d["dm_rabbit_acked"] = total_increase(load(s, "dm_rabbit_acked"), t0, t1)
            d["ew_processed"] = total_increase(load(s, "ew_processed"), t0, t1)
            # dm_processed - frames per window: where the surplus over received frames appears.
            cuts = [t0, ts("2026-09-18T07:18:00Z"), ts("2026-09-18T07:30:00Z"),
                    ts("2026-09-18T11:18:00Z"), ts("2026-09-18T11:30:00Z"), t1]
            d["dm_menos_frames_por_ventana"] = [
                {"desde": iso(x), "hasta": iso(y),
                 "frames": total_increase(load(s, "frames"), x, y),
                 "dm_processed": total_increase(load(s, "dm_processed"), x, y),
                 "dm_menos_frames": total_increase(load(s, "dm_processed"), x, y) - total_increase(load(s, "frames"), x, y)}
                for x, y in zip(cuts, cuts[1:])]
            d["redis_up"] = series_minmax(load(s, "redis_up"), t0, t1)
        acked = arts[s]["confirmadas"]
        for k in ("mysql_rows_inserted", "dm_processed", "frames_ok"):
            if d.get(k):
                d[f"dif_{k}_vs_confirmadas"] = {"abs": d[k] - acked, "pct": round(100 * (d[k] - acked) / acked, 4)}
        dur[s] = d
    H["durabilidad"] = dur
    H["logs_b"] = json.loads((OUT / "logs_b.json").read_text())["reconciliacion"]

    # Section 4: memory.
    mem = {s: memory(s, arts[s]) for s in ("A", "B")}
    H["memoria_nodo"] = {s: {k: v for k, v in m.items() if not k.startswith("_")} for s, m in mem.items()}
    H["memoria_servicio_B"] = memory_services_b(arts["B"])
    plot(mem, arts)

    (OUT / "hallazgos.json").write_text(json.dumps(H, indent=1, ensure_ascii=False, default=float) + "\n", encoding="utf-8")
    print(json.dumps({k: H[k] for k in ("durabilidad", "memoria_nodo", "memoria_servicio_B")}, indent=1, default=float)[:20000])


if __name__ == "__main__":
    main()
