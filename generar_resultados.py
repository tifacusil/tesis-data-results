#!/usr/bin/env python3
"""
generar_resultados.py — regenera las Figuras 2 a 5 y las cifras de las Tablas 7, 8 y 9
de la campaña definitiva (septiembre de 2026) a partir de los datos crudos.

Entradas (rutas configurables por argumento):
  --escalera-a / --escalera-b   carpetas con los JSON de Artillery vu-XXX-rN.json
  --prom-a / --prom-b           CSV por minuto de Prometheus de la escalera
                                (A-ladder-0917-timeseries.csv, B-ladder-0923-timeseries.csv)
  --nivel1-dir                  carpeta con A_nivel1_{cpu,mem}.json y B_nivel1_{cpu,mem}.json
                                (reextracción del nivel de 1 trama/s)
  --sat-b / --serie-b           CSV de la corrida de 12 h del Sistema B
                                (B-12h-0923-saturation.csv, B-12h-0923-timeseries.csv)
  --salida                      carpeta de salida

Método (declarado en 3.3 y 5.3 del manuscrito):
  - Ventana efectiva de cada corrida: periodos de 10 s 18 a 59 (descarta 3 min de calentamiento).
  - Valor de corrida: mediana de las 42 mediciones de su ventana efectiva.
  - Valor por nivel: mediana de las cinco corridas.
  - Contraste: Mann-Whitney exacto por permutación sobre las corridas (5 vs 5),
    Bonferroni sobre cuatro niveles; delta de Cliff sobre corridas;
    IC 95 % de la diferencia de medianas por remuestreo jerárquico (corridas, luego mediciones).

Uso:
  python3 generar_resultados.py --escalera-a "A - SPETIEMBRE 5 RUNS" --escalera-b "B - SEPTIEMBRE 5 RUNS V2" \
      --prom-a A-ladder-0917-timeseries.csv --prom-b B-ladder-0923-timeseries.csv \
      --nivel1-dir . --sat-b B-12h-0923-saturation.csv --serie-b B-12h-0923-timeseries.csv --salida salida
"""
import argparse, csv, glob, itertools, json, os, re, statistics as st
from datetime import datetime, timezone

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NIVELES = [1, 10, 50, 100]
CALENTAMIENTO, N_EFECTIVAS = 18, 42
SERVICIOS = ["data-receiving", "data-management", "early-warning",
             "data-analysis", "project-management", "user-management"]
COLOR = {"A": "#3B5B8A", "B": "#E8694A"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 14,
                     "axes.spines.top": False, "axes.spines.right": False})


# ---------------------------------------------------------------- escalera (Artillery)
def cargar_escalera(carpeta):
    corridas = {}
    for f in glob.glob(os.path.join(carpeta, "vu-*-r*.json")):
        m = re.search(r"vu-(\d+)-r(\d+)\.json$", f)
        if not m:
            continue
        d = json.load(open(f, encoding="utf-8"))
        periodos = sorted(d["intermediate"], key=lambda p: int(p["period"]))
        ef = periodos[CALENTAMIENTO:CALENTAMIENTO + N_EFECTIVAS]
        rtt = lambda k: [p["summaries"]["dtu_tcp.round_trip_ms"][k] for p in ef]
        corridas[(int(m[1]), int(m[2]))] = {
            "p50": rtt("p50"), "p95": rtt("p95"), "p99": rtt("p99"),
            "confirmadas": sum(p["counters"].get("dtu_tcp.frames_acked", 0) for p in ef),
            "fallos": sum(p["counters"].get("vusers.failed", 0) for p in ef),
            "n": len(ef),
            "ventana": (int(ef[0]["period"]) // 1000, int(ef[-1]["period"]) // 1000 + 10),
        }
    return corridas


def valores_corrida(E, nivel, k):
    return [st.median(E[(nivel, r)][k]) for r in sorted(r for (l, r) in E if l == nivel)]


def p_permutacion(a, b):
    todos, n = a + b, len(a)
    U = lambda x, y: sum((xi > yi) + 0.5 * (xi == yi) for xi in x for yi in y)
    mu = n * len(b) / 2
    obs = abs(U(b, a) - mu)
    extremos = total = 0
    for idx in itertools.combinations(range(len(todos)), n):
        bb = [todos[i] for i in idx]
        aa = [todos[i] for i in range(len(todos)) if i not in idx]
        total += 1
        extremos += abs(U(bb, aa) - mu) >= obs - 1e-12
    return extremos / total


def delta_cliff(b, a):
    return sum((x > y) - (x < y) for x in b for y in a) / (len(a) * len(b))


def ic_jerarquico(EA, EB, nivel, k, B=10000, semilla=7):
    rng = np.random.default_rng(semilla)
    arr = {s: [np.array(E[(nivel, r)][k]) for r in sorted(r for (l, r) in E if l == nivel)]
           for s, E in (("A", EA), ("B", EB))}
    dif = np.empty(B)
    for i in range(B):
        med = {}
        for s in "AB":
            idx = rng.integers(0, len(arr[s]), len(arr[s]))
            med[s] = np.median([np.median(rng.choice(arr[s][j], size=len(arr[s][j]))) for j in idx])
        dif[i] = med["B"] - med["A"]
    return np.percentile(dif, [2.5, 97.5])


# ---------------------------------------------------------------- recursos (Prometheus)
def cargar_serie(csv_path):
    filas = []
    for r in csv.DictReader(open(csv_path, encoding="utf-8")):
        t = datetime.fromisoformat(r["time"].replace("Z", "+00:00")).timestamp()
        filas.append((t, r))
    return filas


def recursos_corrida(serie, E, nivel, columna, nivel1=None):
    if nivel == 1 and nivel1 is not None:
        return nivel1[columna]
    vals = []
    for r in sorted(r for (l, r) in E if l == nivel):
        a, b = E[(nivel, r)]["ventana"]
        v = [float(f[columna]) for t, f in serie if a <= t < b and f.get(columna) not in (None, "")]
        if v:
            vals.append(st.median(v))
    return vals


def cargar_nivel1(carpeta, sistema, E):
    def serie(nombre):
        return json.load(open(os.path.join(carpeta, f"{sistema}_nivel1_{nombre}.json")))["data"]["result"][0]["values"]
    cpu, mem = serie("cpu"), serie("mem")
    out = {"node_cpu_pct": [], "node_mem_used_mib": []}
    for r in sorted(r for (l, r) in E if l == 1):
        a, b = E[(1, r)]["ventana"]
        out["node_cpu_pct"].append(st.median(float(v) for t, v in cpu if a <= t < b))
        out["node_mem_used_mib"].append(st.median(float(v) for t, v in mem if a <= t < b))
    return out


# ---------------------------------------------------------------- figuras
def puntos_por_corrida(ax, x, vals, off, color):
    j = np.linspace(-0.05, 0.05, len(vals)) if len(vals) > 1 else np.array([0.0])
    ax.scatter(x + off + j, vals, s=22, facecolors="none", edgecolors=color, lw=1.1, zorder=2)


def figura2(EA, EB, salida):
    with plt.rc_context({"font.size": 15}):
        _figura2(EA, EB, salida)


def _figura2(EA, EB, salida):
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.6))
    x = np.arange(len(NIVELES))
    for ax, k, titulo in zip(axs, ["p50", "p95", "p99"], ["Percentil 50", "Percentil 95", "Percentil 99"]):
        for s, E, off in (("A", EA, -0.08), ("B", EB, 0.08)):
            ax.plot(x, [st.median(valores_corrida(E, l, k)) for l in NIVELES], "-o",
                    color=COLOR[s], lw=2.6, ms=8, label="Sistema " + s, zorder=3)
            for i, l in enumerate(NIVELES):
                puntos_por_corrida(ax, x[i], valores_corrida(E, l, k), off, COLOR[s])
        ax.set_title(titulo); ax.set_xticks(x); ax.set_xticklabels(NIVELES)
        ax.set_xlabel("tramas por segundo"); ax.set_ylim(180, 225)
        ax.grid(axis="y", color="#e3e3e3"); ax.set_axisbelow(True)
    axs[0].set_ylabel("Latencia (ms)"); axs[0].legend(frameon=False, loc="upper left")
    fig.tight_layout(); fig.savefig(os.path.join(salida, "figura2_latencia.png"), dpi=300); plt.close(fig)


def figura3(rec, salida):
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.6))
    x = np.arange(len(NIVELES))
    for ax, col, titulo, eje in ((axs[0], "node_cpu_pct", "Procesador del nodo", "Utilización (%)"),
                                 (axs[1], "node_mem_used_mib", "Memoria ocupada del nodo", "MiB")):
        for s, off in (("A", -0.08), ("B", 0.08)):
            ax.plot(x, [st.median(rec[s][l][col]) for l in NIVELES], "-o", color=COLOR[s],
                    lw=2.6, ms=8, label="Sistema " + s, zorder=3)
            for i, l in enumerate(NIVELES):
                puntos_por_corrida(ax, x[i], rec[s][l][col], off, COLOR[s])
        ax.set_title(titulo); ax.set_xticks(x); ax.set_xticklabels(NIVELES)
        ax.set_xlabel("tramas por segundo"); ax.set_ylabel(eje)
        ax.grid(axis="y", color="#e3e3e3"); ax.set_axisbelow(True)
    axs[0].set_ylim(0, 100); axs[1].set_ylim(2600, 3600); axs[0].legend(frameon=False, loc="upper left")
    fig.tight_layout(); fig.savefig(os.path.join(salida, "figura3_recursos.png"), dpi=300); plt.close(fig)


def figura4(mem, salida):
    a = [mem["A"][s] for s in SERVICIOS]; b = [mem["B"][s] for s in SERVICIOS]
    fig, ax = plt.subplots(figsize=(12, 5)); y = np.arange(len(SERVICIOS)); h = 0.38
    ax.barh(y - h / 2, a, h, color=COLOR["A"], label="Sistema A")
    ax.barh(y + h / 2, b, h, color=COLOR["B"], label="Sistema B")
    for yi, (va, vb) in enumerate(zip(a, b)):
        ax.text(va + 4, yi - h / 2, f"{va:.0f}", va="center", fontsize=12)
        ax.text(vb + 4, yi + h / 2, f"{vb:.0f}", va="center", fontsize=12)
    marca = {"data-management": " *", "project-management": " *", "user-management": " *", "early-warning": " †"}
    ax.set_yticks(y); ax.set_yticklabels([s + marca.get(s, "") for s in SERVICIOS]); ax.invert_yaxis()
    ax.set_xlabel("Memoria (MiB)"); ax.set_xlim(0, max(a + b) * 1.12)
    ax.grid(axis="x", color="#e3e3e3"); ax.set_axisbelow(True); ax.legend(frameon=False, loc="lower right")
    fig.tight_layout(); fig.savefig(os.path.join(salida, "figura4_memoria_servicio.png"), dpi=300); plt.close(fig)


def figura5(sat_csv, serie_csv, inicio_utc, salida):
    t0 = datetime.fromisoformat(inicio_utc).replace(tzinfo=timezone.utc).timestamp()
    S = list(csv.DictReader(open(sat_csv, encoding="utf-8")))
    T = list(csv.DictReader(open(serie_csv, encoding="utf-8")))
    hr = lambda r: (datetime.fromisoformat(r["time"].replace("Z", "+00:00")).timestamp() - t0) / 3600
    fig, axs = plt.subplots(1, 2, figsize=(14, 4.8))
    ax = axs[0]
    ax.plot([hr(r) for r in S], [float(r["q_ew_evaluate"]) for r in S], color=COLOR["B"], lw=1.8, label="cola de evaluación")
    ax.plot([hr(r) for r in S], [float(r["q_dm_persist"]) for r in S], color=COLOR["A"], lw=1.8, label="cola de persistencia")
    ax.plot([hr(r) for r in S], [float(r["q_dead_letter"]) for r in S], color="#888888", lw=1.8, ls="--", label="dead letter queue")
    ax.set_ylim(-1, 30); ax.set_ylabel("mensajes en cola"); ax.set_title("Colas del broker")
    ax2 = axs[1]
    ax2.plot([hr(r) for r in T], [float(r["fps"]) for r in T], color="#9BBCD6", lw=1.4, label="recepción")
    ax2.plot([hr(r) for r in S], [float(r["ew_consumed_fps"]) for r in S], color=COLOR["B"], lw=2, label="consumo de early-warning")
    ax2.set_ylim(0, 150); ax2.set_ylabel("tramas por segundo"); ax2.set_title("Tasas por componente")
    for a in axs:
        for hh, et in ((2, "broker"), (6, "réplica"), (10, "retardo")):
            a.axvline(hh, color="#555555", ls=":", lw=1.2)
            a.text(hh + 0.1, a.get_ylim()[1] * 0.93, et, fontsize=11, color="#555555")
        a.set_xlabel("horas de corrida"); a.set_xlim(0, 12.2)
        a.grid(axis="y", color="#e3e3e3"); a.set_axisbelow(True)
        a.legend(frameon=False, loc="lower right" if a is ax2 else "center right", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(salida, "figura5_resistencia_B.png"), dpi=300); plt.close(fig)


# ---------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escalera-a", required=True); ap.add_argument("--escalera-b", required=True)
    ap.add_argument("--prom-a", required=True); ap.add_argument("--prom-b", required=True)
    ap.add_argument("--nivel1-dir", required=True)
    ap.add_argument("--sat-b", required=True); ap.add_argument("--serie-b", required=True)
    ap.add_argument("--inicio-12h-b", default="2026-09-23T12:30:00")
    ap.add_argument("--salida", default="salida")
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)

    EA, EB = cargar_escalera(a.escalera_a), cargar_escalera(a.escalera_b)
    E = {"A": EA, "B": EB}

    # Tabla 7 y Tabla 8
    with open(os.path.join(a.salida, "tabla7_tabla8.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tramas_s", "p50_A", "p50_B", "p95_A", "p95_B", "p99_A", "p99_B",
                    "dif_p95_B_menos_A", "ic95_inf", "ic95_sup", "delta_cliff", "p_exacto", "significativo_0.0125"])
        for l in NIVELES:
            med = {(s, k): st.median(valores_corrida(E[s], l, k)) for s in "AB" for k in ("p50", "p95", "p99")}
            ra, rb = valores_corrida(EA, l, "p95"), valores_corrida(EB, l, "p95")
            ic = ic_jerarquico(EA, EB, l, "p95"); p = p_permutacion(ra, rb)
            w.writerow([l, med[("A", "p50")], med[("B", "p50")], med[("A", "p95")], med[("B", "p95")],
                        med[("A", "p99")], med[("B", "p99")], round(med[("B", "p95")] - med[("A", "p95")], 1),
                        round(ic[0], 1), round(ic[1], 1), round(delta_cliff(rb, ra), 2), round(p, 4), p < 0.0125])

    # Valores por corrida (latencia y rendimiento)
    with open(os.path.join(a.salida, "valores_por_corrida.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sistema", "tramas_s", "corrida", "mediciones", "p50_ms", "p95_ms", "p99_ms",
                    "tramas_confirmadas", "fallos", "rendimiento_tramas_s"])
        for s in "AB":
            for (l, r) in sorted(E[s]):
                v = E[s][(l, r)]
                w.writerow([s, l, r, v["n"], st.median(v["p50"]), st.median(v["p95"]), st.median(v["p99"]),
                            v["confirmadas"], v["fallos"], round(v["confirmadas"] / (v["n"] * 10), 2)])

    # Recursos (Tabla 9, Figuras 3 y 4)
    serie = {"A": cargar_serie(a.prom_a), "B": cargar_serie(a.prom_b)}
    n1 = {s: cargar_nivel1(a.nivel1_dir, s, E[s]) for s in "AB"}
    rec = {s: {l: {c: recursos_corrida(serie[s], E[s], l, c, n1[s] if l == 1 else None)
                   for c in ("node_cpu_pct", "node_mem_used_mib")} for l in NIVELES} for s in "AB"}
    with open(os.path.join(a.salida, "tabla9.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tramas_s", "cpu_A", "cpu_B", "mem_ocupada_A_MiB", "mem_ocupada_B_MiB", "corridas_A", "corridas_B"])
        for l in NIVELES:
            w.writerow([l] + [round(st.median(rec[s][l]["node_cpu_pct"]), 1) for s in "AB"]
                       + [round(st.median(rec[s][l]["node_mem_used_mib"]), 1) for s in "AB"]
                       + [len(rec[s][l]["node_cpu_pct"]) for s in "AB"])
    mem = {s: {sv: st.median(recursos_corrida(serie[s], E[s], 100, "mem_mib_" + sv)) for sv in SERVICIOS} for s in "AB"}

    figura2(EA, EB, a.salida)
    figura3(rec, a.salida)
    figura4(mem, a.salida)
    figura5(a.sat_b, a.serie_b, a.inicio_12h_b, a.salida)
    print("Listo:", ", ".join(sorted(os.listdir(a.salida))))


if __name__ == "__main__":
    main()
