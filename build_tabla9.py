#!/usr/bin/env python3
"""build_tabla9.py - rebuild Table 9 (node CPU % and node memory used MiB per load level, A vs B)
from raw Prometheus range-query JSON and the Artillery reports.

Usage (from the root of this repo):
  python3 build_tabla9.py --out <dir> [--prom-dir tabla9/prometheus]

Inputs:
  data/A - SPETIEMBRE 5 RUNS, data/B - SEPTIEMBRE 5 RUNS V2   Artillery reports (run windows)
  <prom-dir>/{A,B}_nivel1_{cpu,mem}.json   level 1 frame/s   (scripts/export_prometheus.sh, step 60 s)
  <prom-dir>/{A,B}_ladder_{cpu,mem}.json   levels 10/50/100  (scripts/export_prometheus.sh, step 60 s)

Method: the one in generar_resultados.py, whose functions are imported, not copied.
  Run window = 10 s Artillery periods 18..59 after dropping empty periods (3 min warm-up excluded).
  Run value  = median of the Prometheus samples with window_start <= t < window_end.
  Level value = median of the 5 run values, rounded to 0.1.

Outputs (in --out): tabla9.csv (same columns as generar_resultados.py) and tabla9_por_corrida.csv
(one row per run: window in UTC, number of samples, run medians).
Read-only on its inputs. Exits non-zero (AssertionError/exception) if anything is missing or inconsistent.
See docs/tabla9-replication.md.
"""
import argparse, csv, json, os, statistics as st, sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--prom-dir", default=os.path.join(REPO, "tabla9", "prometheus"))
ap.add_argument("--out", required=True)
a = ap.parse_args()
sys.path.insert(0, REPO)          # python -I does not add the script's folder
sys.dont_write_bytecode = True    # leave no __pycache__ in the repo
import generar_resultados as g  # noqa: E402  (needs numpy/scipy/matplotlib from requirements.txt)

ESCALERA = {"A": "A - SPETIEMBRE 5 RUNS", "B": "B - SEPTIEMBRE 5 RUNS V2"}
COLS = {"cpu": "node_cpu_pct", "mem": "node_mem_used_mib"}
iso = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def serie(sistema, tramo, nombre):
    res = json.load(open(os.path.join(a.prom_dir, f"{sistema}_{tramo}_{nombre}.json"), encoding="utf-8"))["data"]["result"]
    assert len(res) == 1, (sistema, tramo, nombre, len(res))  # one node per system
    return [(float(t), float(v)) for t, v in res[0]["values"]]


os.makedirs(a.out, exist_ok=True)
por_corrida, tabla = [], {}
for s in "AB":
    E = g.cargar_escalera(os.path.join(REPO, "data", ESCALERA[s]))
    assert len(E) == 20, (s, len(E))
    for l in g.NIVELES:
        tramo = "nivel1" if l == 1 else "ladder"
        datos = {k: serie(s, tramo, k) for k in COLS}
        for r in sorted(r for (ll, r) in E if ll == l):
            ini, fin = E[(l, r)]["ventana"]
            v = {k: [x for t, x in datos[k] if ini <= t < fin] for k in COLS}
            assert v["cpu"] and len(v["cpu"]) == len(v["mem"]), (s, l, r)  # window must be covered by the export
            por_corrida.append([s, l, r, iso(ini), iso(fin), len(v["cpu"]), st.median(v["cpu"]), st.median(v["mem"])])
        filas = [f for f in por_corrida if f[0] == s and f[1] == l]
        tabla[(s, l)] = (round(st.median(f[6] for f in filas), 1), round(st.median(f[7] for f in filas), 1), len(filas))

with open(os.path.join(a.out, "tabla9_por_corrida.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["sistema", "tramas_s", "corrida", "ventana_inicio_utc", "ventana_fin_utc", "muestras", "cpu_pct", "mem_ocupada_MiB"])
    w.writerows(por_corrida)
with open(os.path.join(a.out, "tabla9.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["tramas_s", "cpu_A", "cpu_B", "mem_ocupada_A_MiB", "mem_ocupada_B_MiB", "corridas_A", "corridas_B"])
    for l in g.NIVELES:
        w.writerow([l, tabla[("A", l)][0], tabla[("B", l)][0], tabla[("A", l)][1], tabla[("B", l)][1], tabla[("A", l)][2], tabla[("B", l)][2]])
print("tabla9.csv, tabla9_por_corrida.csv ->", a.out)
