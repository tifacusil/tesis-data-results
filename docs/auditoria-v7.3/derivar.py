"""Derive the V7.3 audit CSVs from files already in this repository.

Reads only repository files (no database, no TSDB, no network) and writes
docs/auditoria-v7.3/outputs/*.csv. Run from the repository root:

    py -I docs/auditoria-v7.3/derivar.py

Every counter increase uses the same rule as docs/auditoria-resistencia-12h.md:
sum of differences between consecutive samples, from the last sample at or
before the window start to the last sample at or before the window end; a drop
is a counter reset and the new value is added. A series that does not exist at
the window start starts from its first sample. Column `incremento_con_nacimiento`
also counts that first value, i.e. it assumes the counter was created at 0.
"""
import csv
import glob
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, "docs", "auditoria-v7.3")
OUT = os.path.join(HERE, "outputs")
PROM = os.path.join(ROOT, "results", "auditoria_resistencia", "prometheus")
EW = os.path.join(HERE, "fuente", "auditoria_ew_b_2026-11-20")
DB = os.path.join(HERE, "fuente", "auditoria_db_b_2026-11-20")
CHAOS = os.path.join(ROOT, "data", "B - SEPTIEMBRE 5 RUNS V2", "chaos")
ARTILLERY_B = os.path.join(ROOT, "data", "B - SEPTIEMBRE 5 RUNS V2", "sustained-12h.json")


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def utc(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# Window of docs/auditoria-resistencia-12h.md, section 3 (B): [start, end of Artillery + 300 s].
T0 = ts("2026-09-23T12:31:20Z")
T1 = ts("2026-09-24T00:39:21Z")
# Window used by the 20/11 TSDB audit (end of Artillery, no drain margin).
T1_ARTILLERY = ts("2026-09-24T00:34:21Z")


def increase(samples, t0, t1):
    """samples: sorted [(t, v)]. Returns dict with the window samples and increases."""
    before = [s for s in samples if s[0] <= t0]
    inside = [s for s in samples if t0 < s[0] <= t1]
    start = before[-1] if before else (inside[0] if inside else None)
    if start is None:
        return None
    seq = [start] + [s for s in inside if s is not start]
    inc, resets = 0.0, 0
    for (_, a), (_, b) in zip(seq, seq[1:]):
        if b < a:
            resets += 1
            inc += b
        else:
            inc += b - a
    born = not before
    return {
        "muestra_inicio_utc": utc(start[0]), "valor_inicio": start[1],
        "muestra_fin_utc": utc(seq[-1][0]), "valor_fin": seq[-1][1],
        "nace_en_ventana": born, "incremento": inc,
        "incremento_con_nacimiento": inc + (start[1] if born else 0),
        "reinicios": resets, "muestras": len(seq),
    }


def prom_series(name):
    d = json.load(open(os.path.join(PROM, name), encoding="utf-8"))
    for s in d["data"]["result"]:
        yield s["metric"], [(float(t), float(v)) for t, v in s["values"]]


def write(name, header, rows):
    path = os.path.join(OUT, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    print(f"{name}: {len(rows)} filas")


def num(x):
    return int(x) if float(x).is_integer() else round(x, 6)


def bloque1():
    rows = []
    for m, v in prom_series("B__mysql_rows_inserted.json"):
        r = increase(v, T0, T1)
        rows.append([m["instance"], m["operation"], r["muestra_inicio_utc"], num(r["valor_inicio"]),
                     r["muestra_fin_utc"], num(r["valor_fin"]), num(r["incremento"]), r["reinicios"], r["muestras"]])
    write("b1_innodb_rows_inserted.csv",
          ["instance", "operation", "muestra_t0_utc", "valor_t0", "muestra_t1_utc", "valor_t1",
           "incremento", "reinicios", "muestras"], rows)


def bloque2():
    logs = json.load(open(os.path.join(ROOT, "results", "auditoria_resistencia", "logs_b.json"), encoding="utf-8"))
    write("b2_sink_write_failed_105.csv", ["timestamp_utc", "pod", "message_id", "error"],
          [list(x) for x in logs["sink_write_failed_detalle"]])

    rows = []
    for line in open(os.path.join(DB, "rows_per_minute_1428_1442.tsv"), encoding="utf-8"):
        minute, n = line.rstrip("\n").split("\t")
        if "2026-09-23 14:30" <= minute <= "2026-09-23 14:39":
            rows.append([minute, int(n), 6000, int(n) - 6000])
    write("b2_filas_por_minuto_1430_1440.csv",
          ["minuto_received_at_utc", "filas", "nominal_100_tramas_s", "diferencia"], rows)

    art = json.load(open(ARTILLERY_B, encoding="utf-8"))
    rows = []
    for p in art["intermediate"]:
        t = int(p["period"]) / 1000
        if ts("2026-09-23T14:32:00Z") <= t < ts("2026-09-23T14:38:00Z"):
            c = p["counters"]
            p95 = p["summaries"].get("dtu_tcp.round_trip_ms", {}).get("p95", "")
            rows.append([utc(t), c.get("vusers.created", 0), c.get("dtu_tcp.frames_acked", 0),
                         c.get("errors.emulator_error", 0), c.get("vusers.failed", 0),
                         c.get("vusers.completed", 0), p95])
    write("b2_artillery_10s_1432_1438.csv",
          ["periodo_inicio_reloj_cliente", "emitidas_vusers_created", "ok_frames_acked",
           "errors_emulator_error", "vusers_failed", "vusers_completed", "p95_round_trip_ms"], rows)


def bloque3():
    rows = []
    for fname, metric in (("B__ew_alerts.json", "ew_alerts_published_total"),
                          ("B__ew_alert_delivery_count.json", "ew_alert_delivery_latency_seconds_count")):
        for m, v in prom_series(fname):
            r = increase(v, T0, T1)
            rows.append([metric, m["instance"], m.get("level", ""), utc(v[0][0]), num(v[0][1]),
                         r["muestra_inicio_utc"], num(r["valor_inicio"]), r["muestra_fin_utc"], num(r["valor_fin"]),
                         r["nace_en_ventana"], num(r["incremento"]), num(r["incremento_con_nacimiento"]),
                         r["reinicios"]])
    write("b3_ew_alertas_por_serie.csv",
          ["metrica", "instance", "level", "primera_muestra_tsdb_utc", "valor_primera_muestra",
           "muestra_inicio_utc", "valor_inicio", "muestra_fin_utc", "valor_fin", "nace_en_ventana",
           "incremento", "incremento_con_nacimiento", "reinicios"], rows)


def bloque4():
    series = {}
    with open(os.path.join(EW, "ew_evaluations_samples.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["source"] == "raw":
                series.setdefault((r["outcome"], r["instance"]), []).append(
                    (float(r["timestamp_unix"]), float(r["value"])))
    rows = []
    for (outcome, inst), v in sorted(series.items()):
        v.sort()
        # 20/11 method: samples strictly after 12:31:20 up to 00:34:21.
        w = [s for s in v if T0 < s[0] <= T1_ARTILLERY]
        a = sum(b - x if b >= x else b for (_, x), (_, b) in zip(w, w[1:]))
        r = increase(v, T0, T1)
        rows.append([outcome, inst, num(a), r["muestra_inicio_utc"], r["muestra_fin_utc"],
                     num(r["incremento"]), r["reinicios"]])
    rows.append(["TOTAL", "", sum(x[2] for x in rows), "", "", sum(x[5] for x in rows), ""])
    write("b4_ew_evaluations_por_outcome.csv",
          ["outcome", "instance", "incremento_ventana_20_11", "muestra_inicio_utc", "muestra_fin_utc",
           "incremento_ventana_alineada", "reinicios"], rows)

    rows = []
    for m, v in prom_series("B__buffer.json"):
        w = [s for s in v if ts("2026-09-23T14:30:00Z") <= s[0] <= ts("2026-09-23T15:00:00Z")]
        top = max(w, key=lambda s: s[1])
        rows.append([m.get("instance", ""), m.get("pod", ""), num(top[1]), utc(top[0])])
    write("b4_buffer_max_por_replica.csv",
          ["instance", "pod", "max_data_receiving_redis_buffer_pending_1430_1500", "primera_muestra_con_max_utc"],
          rows)

    rows = []
    for f in sorted(glob.glob(os.path.join(CHAOS, "netem-delay-ew-um-summary-*.env"))):
        env = dict(line.strip().split("=", 1) for line in open(f, encoding="utf-8") if "=" in line)
        with open(os.path.join(CHAOS, env["samples_csv"]), encoding="utf-8") as g:
            s = list(csv.DictReader(g))

        def delta(k):
            vals = [float(x[k]) for x in s if x[k] != "NaN"]
            return num(vals[-1] - vals[0]), num(vals[-1])

        co_delta, co_last = delta("calls_circuit_open")
        first_co = next(x for x in s if x["calls_circuit_open"] != "NaN")
        open_samples = [x["iso_utc"] for x in s if x["breaker_state"] == "1"]
        rows.append([env["fail_start_utc"], env["breaker_opened_after_s"], env["recovery_s"],
                     open_samples[0] if open_samples else "", open_samples[-1] if open_samples else "",
                     "".join(x["breaker_state"] for x in s),
                     s[0]["calls_circuit_open"], first_co["iso_utc"], first_co["calls_circuit_open"], co_last, co_delta,
                     env["calls_circuit_open"], delta("alerts_published")[0], env["alerts_while_open"],
                     env["degraded_alerts"], env["samples_csv"]])
    write("b4_circuit_breaker_por_corrida.csv",
          ["fail_start_utc", "breaker_opened_after_s", "recovery_s", "primera_muestra_abierto_utc",
           "ultima_muestra_abierto_utc", "breaker_state_por_muestra", "calls_circuit_open_primera_muestra",
           "primera_muestra_no_nan_utc", "calls_circuit_open_primera_no_nan", "calls_circuit_open_ultima",
           "delta_calls_circuit_open_desde_primera_no_nan", "calls_circuit_open_summary",
           "delta_alerts_published_ventana_muestreo", "alerts_while_open_summary", "degraded_alerts_summary",
           "samples_csv"], rows)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    bloque1()
    bloque2()
    bloque3()
    bloque4()
