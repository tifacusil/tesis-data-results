"""V7.5 item 1: the SQL window of E4 (gnss_readings, 12 h run of B) against the
generator interval.

Reads only repository files, plus, optionally, the unpublished export of the
window (`raw/export.tsv.gz`, SHA-256 in docs/auditoria-v7.3/README.md). Run
from the repository root:

    py -I docs/auditoria-v7.3/v75_2026-11-21/ventana_e4.py [--export PATH]

Writes, next to this script:
- ventana_e4_fases.csv: Artillery phases of sustained-12h.json (nominal
  limits from the scenario, frames from the 10 s periods of the report).
- ventana_e4_tramos.csv: the 37 chunks of dm_tramos_completo.csv with the
  predicate each one ran with (from raw/dm.sql and raw/dm2/dm2.sql) and the
  contiguity check.
- ventana_e4_corridas_b.csv: every Artillery report and chaos file of B in
  the repository, with its time span and whether it falls inside the window.
- ventana_e4_bordes_por_segundo.csv (needs --export): rows per second of
  received_at in the first and last 15 s that hold rows, with the sensor
  set of each second.
- ventana_e4_resumen.csv (needs --export): one row per figure quoted in
  pedido5.md. Without --export the other three files are still rewritten and
  must not change (git diff).

All times are UTC. Artillery uses the client PC clock; received_at uses the
clock of data-receiving on the server of B. The offset between them was not
measured.
"""
import argparse
import csv
import glob
import gzip
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B = os.path.join(ROOT, "data", "B - SEPTIEMBRE 5 RUNS V2")
V73 = os.path.join(ROOT, "docs", "auditoria-v7.3", "v73_b_2026-11-20")
EXPORT_SHA = "28cee4f9eb7450af162cd4cd80e53369a5268c03df1c20a5a11a40439fed0f05"

T0 = datetime(2026, 9, 23, 12, 31, 20)  # @t0 of the SQL window
T1 = datetime(2026, 9, 24, 0, 39, 21)  # @t1 = lastMetricAt (truncated) + 300 s
RAMP_S, STEADY_S, RATE = 180, 43200, 100  # go-tesis-infra@c6732b0 load-tests/scenarios/vu-sustained-12h.yml
GENERATOR_SENSORS = re.compile(r"^GXZM-DB\d{3}$")  # dtu-emulator contract example


def utc(ms):
    return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).replace(tzinfo=None)


def fmt(t):
    return t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def write(name, rows):
    with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerows(rows)


def fases():
    rep = json.load(open(os.path.join(B, "sustained-12h.json"), encoding="utf-8"))
    agg, per = rep["aggregate"], rep["intermediate"]
    first, last = utc(agg["firstCounterAt"]), utc(agg["lastCounterAt"])
    created = [(utc(p["period"]), p["counters"].get("vusers.created", 0)) for p in per]
    assert sum(c for _, c in created) == agg["counters"]["vusers.created"] == 4329095
    ramp_end = first + timedelta(seconds=RAMP_S)
    steady_end = ramp_end + timedelta(seconds=STEADY_S)
    # 10 s periods that start before the nominal end of the ramp hold ramp frames;
    # the period starting at 12:34:20.000 also holds the last 0.398 s of the ramp.
    ramp_periods = [c for t, c in created if t + timedelta(seconds=10) <= ramp_end]
    steady_periods = [c for t, c in created if t + timedelta(seconds=10) > ramp_end]
    full = [c for t, c in created if ramp_end <= t and t + timedelta(seconds=10) <= steady_end]
    tail = [c for t, c in created if t + timedelta(seconds=10) > steady_end]
    rows = [
        ["fase", "inicio_nominal_utc", "fin_nominal_utc", "duracion_nominal_s",
         "periodos_10s", "primer_periodo_utc", "ultimo_periodo_utc", "tramas_creadas", "tramas_nominales"],
        ["ramp-up (1 -> 100/s)", fmt(first), fmt(ramp_end), RAMP_S, len(ramp_periods),
         fmt(created[0][0]), fmt(created[len(ramp_periods) - 1][0]), sum(ramp_periods), (1 + RATE) * RAMP_S // 2],
        ["sustained-load-12h (100/s)", fmt(ramp_end), fmt(steady_end), STEADY_S, len(steady_periods),
         fmt(created[len(ramp_periods)][0]), fmt(created[-1][0]), sum(steady_periods), RATE * STEADY_S],
        ["total", fmt(first), fmt(last), round((last - first).total_seconds(), 3), len(created),
         fmt(created[0][0]), fmt(created[-1][0]), sum(c for _, c in created), (1 + RATE) * RAMP_S // 2 + RATE * STEADY_S],
    ]
    write("ventana_e4_fases.csv", rows)
    return {
        "first": first, "last": last, "ramp_end": ramp_end, "steady_end": steady_end,
        "ramp": sum(ramp_periods), "steady": sum(steady_periods),
        "full_min": min(full), "full_max": max(full), "full_n": len(full),
        "tail_created": tail[-1], "acked": agg["counters"]["dtu_tcp.frames_acked"],
        "created": agg["counters"]["vusers.created"],
    }


def tramos():
    pred = re.compile(r"received_at (>=|>|BETWEEN) '([^']+)' (?:AND received_at (<|<=) )?(?:AND )?'([^']+)'")
    sql = {}
    for f in ("raw/dm.sql", "raw/dm2/dm2.sql"):
        for m in pred.finditer(open(os.path.join(V73, f), encoding="utf-8").read()):
            sql[(m.group(2), m.group(4))] = (f, f"{m.group(1)} / {m.group(3)}")
    rows = list(csv.DictReader(open(os.path.join(V73, "dm_tramos_completo.csv"), encoding="utf-8")))
    out = [["n", "desde_utc", "hasta_utc", "duracion_s", "filas", "ids_distintos", "predicado", "sql",
            "contiguo_con_el_siguiente"]]
    for i, r in enumerate(rows):
        a, b = r["desde_utc"], r["hasta_utc"]
        f, p = sql[(a, b)]
        assert p == ">= / <", (a, b, p)
        nxt = "fin" if i == len(rows) - 1 else ("si" if rows[i + 1]["desde_utc"] == b else "no")
        dur = (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()
        out.append([i + 1, a, b, int(dur), r["filas"], r["ids_distintos"], "received_at >= desde AND received_at < hasta", f, nxt])
    assert len(rows) == 37 and all(o[-1] in ("si", "fin") for o in out[1:])
    assert rows[0]["desde_utc"] == str(T0) and rows[-1]["hasta_utc"] == str(T1)
    write("ventana_e4_tramos.csv", out)
    return {"n": len(rows), "filas": sum(int(r["filas"]) for r in rows),
            "ids": sum(int(r["ids_distintos"]) for r in rows)}


def corridas():
    out = [["archivo", "tipo", "inicio_utc", "fin_utc", "fuente_del_tiempo", "dentro_de_la_ventana"]]
    inside = []
    for p in sorted(glob.glob(os.path.join(B, "*.json"))):
        a = json.load(open(p, encoding="utf-8"))["aggregate"]
        s, e = utc(a["firstMetricAt"]), utc(a["lastMetricAt"])
        name = os.path.basename(p)
        hit = "generador de E4" if name == "sustained-12h.json" else ("si" if s < T1 and e >= T0 else "no")
        out.append([name, "Artillery", fmt(s), fmt(e), "aggregate.firstMetricAt / lastMetricAt", hit])
    for p in sorted(os.listdir(os.path.join(B, "chaos"))):
        for m in re.findall(r"-(17\d{8})", p):
            t = utc(int(m) * 1000)
            hit = "si" if T0 <= t < T1 else "no"
            if hit == "si":
                inside.append(p)
            out.append([f"chaos/{p}", p.split("-1")[0], fmt(t), "", "epoch del nombre del archivo", hit])
    write("ventana_e4_corridas_b.csv", out)
    return inside, sum(1 for o in out[1:] if o[1] == "Artillery" and o[-1] == "si")


def bordes(path):
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    assert h == EXPORT_SHA, h
    per_s, sensors = Counter(), defaultdict(set)
    ids, other = set(), Counter()
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        r = csv.reader(f, delimiter="\t")
        assert next(r) == ["message_id", "sensor_id", "timestamp", "received_at"]
        for mid, sensor, _, rec in r:
            per_s[rec] += 1
            sensors[rec].add(sensor)
            ids.add(mid)
            if not GENERATOR_SENSORS.match(sensor):
                other[sensor] += 1
    secs = sorted(per_s)
    out = [["received_at_utc", "filas", "sensores_distintos", "posicion"]]
    for s in secs[:15]:
        out.append([s, per_s[s], len(sensors[s]), "inicio"])
    for s in secs[-15:]:
        out.append([s, per_s[s], len(sensors[s]), "final"])
    write("ventana_e4_bordes_por_segundo.csv", out)
    return {"filas": sum(per_s.values()), "ids": len(ids), "min": secs[0], "max": secs[-1],
            "otros_sensores": sum(other.values()), "sensores": len({x for v in sensors.values() for x in v}),
            "per_s": per_s}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", help="raw/export.tsv.gz of audit 1 (not published)")
    args = ap.parse_args()
    fa, tr = fases(), tramos()
    chaos_in, artillery_in = corridas()
    assert artillery_in == 0
    res = [["item", "valor", "fuente"]]
    add = lambda i, v, s: res.append([i, v, s])
    add("1 primer evento del generador (firstCounterAt)", fmt(fa["first"]), "sustained-12h.json aggregate")
    add("1 ultimo evento del generador (lastCounterAt, ultimo ACK)", fmt(fa["last"]), "sustained-12h.json aggregate")
    add("1 duracion primer-ultimo evento (s)", round((fa["last"] - fa["first"]).total_seconds(), 3), "calculo")
    add("1 fin nominal de la rampa", fmt(fa["ramp_end"]), "first + 180 s")
    add("1 fin nominal de la fase de 12 h", fmt(fa["steady_end"]), "first + 180 s + 43200 s")
    add("1 tramas creadas en el ultimo periodo (desde 00:34:20.000)", fa["tail_created"], "intermediate[-1]")
    add("2 tramos", tr["n"], "dm_tramos_completo.csv")
    add("2 predicado de cada tramo", "received_at >= desde AND received_at < hasta (semiabierto, contiguos)", "raw/dm.sql, raw/dm2/dm2.sql")
    add("2 filas en los 37 tramos", tr["filas"], "dm_tramos_completo.csv")
    add("6 tramas creadas", fa["created"], "aggregate.counters")
    add("6 tramas en periodos de la rampa (12:31:20-12:34:20)", fa["ramp"], "intermediate")
    add("6 tramas en periodos de la fase de 12 h (12:34:20-00:34:21.989)", fa["steady"], "intermediate")
    add("6 excedente sobre 4320000", fa["created"] - RATE * STEADY_S, "calculo")
    add("6 periodos completos de la fase de 12 h: min / max por 10 s",
        f'{fa["full_min"]} / {fa["full_max"]} ({fa["full_n"]} periodos)', "intermediate")
    add("5 informes Artillery de B dentro de la ventana (sin contar E4)", artillery_in, "ventana_e4_corridas_b.csv")
    add("5 archivos de caos de B dentro de la ventana", "; ".join(chaos_in), "ventana_e4_corridas_b.csv")
    if args.export:
        bo = bordes(args.export)
        assert bo["filas"] == bo["ids"] == tr["filas"] == fa["acked"]
        last_s = fa["last"].replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        after = sum(n for s, n in bo["per_s"].items() if s > last_s)
        add("4 MIN(received_at) / MAX(received_at)", f'{bo["min"]} / {bo["max"]}', "export.tsv.gz")
        add("4 filas con received_at < 12:31:20 (antes del primer envio)", sum(n for s, n in bo["per_s"].items() if s < "2026-09-23 12:31:20"), "export.tsv.gz")
        add("4 filas con received_at > 00:34:21 (segundo del ultimo evento del cliente)", after, "export.tsv.gz")
        add("4 filas en el margen de vaciado 00:34:24-00:39:21", sum(n for s, n in bo["per_s"].items() if s >= "2026-09-24 00:34:24"), "export.tsv.gz")
        add("5 filas = ids distintos = ACK de Artillery", f'{bo["filas"]} = {bo["ids"]} = {fa["acked"]}', "export.tsv.gz, aggregate")
        add("5 filas con sensor_id fuera de GXZM-DB000..999", bo["otros_sensores"], "export.tsv.gz")
        add("5 sensores distintos en la ventana", bo["sensores"], "export.tsv.gz")
        # The summary quotes export rows, so it is only rewritten when the export is given.
        write("ventana_e4_resumen.csv", res)
    for r in res[1:]:
        print(" | ".join(map(str, r)))


if __name__ == "__main__":
    main()
