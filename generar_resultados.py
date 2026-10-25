#!/usr/bin/env python3
"""
generar_resultados.py: regenera las Figuras 2 a 5 y las cifras de las Tablas 7, 8 y 9
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
  - Latencia por corrida (--estimando agregado, por defecto): p50/p95/p99 de aggregate.summaries,
    el histograma de toda la corrida. El generador no expone percentiles sobre un subconjunto de
    ventanas, así que la latencia no descarta el calentamiento.
    Con --estimando ventanas: mediana de los percentiles de la ventana efectiva (Tabla 7 de la V3).
  - Procesador, memoria y rendimiento: mediana sobre la ventana efectiva, con cualquier estimando.
  - Valor por nivel: mediana de las cinco corridas.
  - Contraste: Mann-Whitney exacto por permutación sobre las corridas (5 vs 5),
    Bonferroni sobre cuatro niveles; delta de Cliff sobre corridas;
    IC 95 % de la diferencia de medianas por remuestreo de las corridas (agregado, 20 000 réplicas)
    o jerárquico, corridas y luego mediciones (ventanas, como en la V3).

Uso:
  python3 generar_resultados.py --escalera-a "A - SPETIEMBRE 5 RUNS" --escalera-b "B - SEPTIEMBRE 5 RUNS V2" \
      --prom-a A-ladder-0917-timeseries.csv --prom-b B-ladder-0923-timeseries.csv \
      --nivel1-dir . --sat-b B-12h-0923-saturation.csv --serie-b B-12h-0923-timeseries.csv --salida salida
"""
import argparse, csv, glob, itertools, json, os, re, statistics as st
from datetime import datetime, timezone

import numpy as np
from scipy.stats import spearmanr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NIVELES = [1, 10, 50, 100]
CALENTAMIENTO, N_EFECTIVAS = 18, 42
M = "dtu_tcp.round_trip_ms"
CONTEO_AGREGADO = {1: 600, 10: 6000, 50: 30000, 100: 60000}
VENTANA_EFECTIVA = {1: (420, 420), 10: (4193, 4200), 50: (20998, 21001), 100: (41990, 42001)}
ESTIMANDO = "agregado"  # lo fija --estimando
YLIM_FIG2 = (180, 270)
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
        todos = sorted(d["intermediate"], key=lambda p: int(p["period"]))
        # Las ventanas sin mediciones se descartan antes de contar el calentamiento, o el recorte se desplaza
        periodos = [p for p in todos if p["summaries"].get(M, {}).get("count", 0) > 0]
        ef = periodos[CALENTAMIENTO:CALENTAMIENTO + N_EFECTIVAS]
        rtt = lambda k: [p["summaries"][M][k] for p in ef]
        agg = d["aggregate"]["summaries"][M]
        n_ef = sum(p["summaries"][M]["count"] for p in ef)
        nivel = int(m[1])
        # El agregado es un percentil sobre todas las observaciones de la corrida (5.2 del brief)
        assert agg["count"] == sum(p["summaries"].get(M, {}).get("count", 0) for p in periodos) \
            == d["aggregate"]["counters"]["dtu_tcp.frames_acked"], f
        assert agg["count"] == CONTEO_AGREGADO[nivel] and VENTANA_EFECTIVA[nivel][0] <= n_ef <= VENTANA_EFECTIVA[nivel][1], f
        corridas[(nivel, int(m[2]))] = {
            "p50": rtt("p50"), "p95": rtt("p95"), "p99": rtt("p99"),
            "agregado": {k: agg[k] for k in ("p50", "p95", "p99")}, "n_agregado": agg["count"], "n_efectivo": n_ef,
            "inicio": int(todos[0]["period"]) // 1000,
            # p95 de cada ventana (None si la ventana no tiene mediciones), para la contribución del calentamiento
            "p95_ventanas": [p["summaries"].get(M, {}).get("p95") for p in periodos[:CALENTAMIENTO + N_EFECTIVAS]],
            "confirmadas": sum(p["counters"].get("dtu_tcp.frames_acked", 0) for p in ef),
            "fallos": sum(p["counters"].get("vusers.failed", 0) for p in ef),
            "n": len(ef),
            "ventana": (int(ef[0]["period"]) // 1000, int(ef[-1]["period"]) // 1000 + 10),
        }
    return corridas


def valor_corrida(c, k):
    # "agregado": percentil del histograma de toda la corrida; "ventanas": mediana de los percentiles de la ventana efectiva
    return c["agregado"][k] if ESTIMANDO == "agregado" else st.median(c[k])


def valores_corrida(E, nivel, k):
    return [valor_corrida(E[(nivel, r)], k) for r in sorted(r for (l, r) in E if l == nivel)]


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


def ic_corridas(a, b, B=20000, semilla=7):
    # Con el estimando agregado no hay segundo nivel: se remuestrean solo las corridas
    rng = np.random.default_rng(semilla)
    a, b = np.array(a), np.array(b)
    dif = (np.median(rng.choice(b, (B, len(b))), axis=1) - np.median(rng.choice(a, (B, len(a))), axis=1))
    return np.percentile(dif, [2.5, 97.5])


def ic(EA, EB, nivel, k):
    if ESTIMANDO == "agregado":
        return ic_corridas(valores_corrida(EA, nivel, k), valores_corrida(EB, nivel, k))
    return ic_jerarquico(EA, EB, nivel, k)


def contraste(EA, EB, l, k):
    ra, rb = valores_corrida(EA, l, k), valores_corrida(EB, l, k)
    lo, hi = ic(EA, EB, l, k); p = p_permutacion(ra, rb)
    return [round(st.median(rb) - st.median(ra), 1), round(lo, 1), round(hi, 1),
            round(delta_cliff(rb, ra), 2), round(p, 4), p < 0.0125]


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
    graficados = [v for E in (EA, EB) for k in ("p50", "p95", "p99") for l in NIVELES for v in valores_corrida(E, l, k)]
    assert YLIM_FIG2[0] <= min(graficados) and max(graficados) <= YLIM_FIG2[1], (min(graficados), max(graficados))
    for ax, k, titulo in zip(axs, ["p50", "p95", "p99"], ["50th percentile", "95th percentile", "99th percentile"]):
        for s, E, off in (("A", EA, -0.08), ("B", EB, 0.08)):
            ax.plot(x, [st.median(valores_corrida(E, l, k)) for l in NIVELES], "-o",
                    color=COLOR[s], lw=2.6, ms=8, label="System " + s, zorder=3)
            for i, l in enumerate(NIVELES):
                puntos_por_corrida(ax, x[i], valores_corrida(E, l, k), off, COLOR[s])
        ax.set_title(titulo); ax.set_xticks(x); ax.set_xticklabels(NIVELES)
        ax.set_xlabel("frames per second"); ax.set_ylim(*YLIM_FIG2)
        ax.grid(axis="y", color="#e3e3e3"); ax.set_axisbelow(True)
    axs[0].set_ylabel("Latency (ms)"); axs[0].legend(frameon=False, loc="upper left")
    fig.tight_layout(); fig.savefig(os.path.join(salida, "figura2_latencia.png"), dpi=300); plt.close(fig)
    # Debe reemplazar word/media/image2.png sin alterar la maquetación (6,27 × 1,92 in)
    assert plt.imread(os.path.join(salida, "figura2_latencia.png")).shape[:2] == (1380, 4500)


def figura3(rec, salida):
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.6))
    x = np.arange(len(NIVELES))
    for ax, col, titulo, eje in ((axs[0], "node_cpu_pct", "Node CPU", "Utilization (%)"),
                                 (axs[1], "node_mem_used_mib", "Node memory used", "MiB")):
        for s, off in (("A", -0.08), ("B", 0.08)):
            ax.plot(x, [st.median(rec[s][l][col]) for l in NIVELES], "-o", color=COLOR[s],
                    lw=2.6, ms=8, label="System " + s, zorder=3)
            for i, l in enumerate(NIVELES):
                puntos_por_corrida(ax, x[i], rec[s][l][col], off, COLOR[s])
        ax.set_title(titulo); ax.set_xticks(x); ax.set_xticklabels(NIVELES)
        ax.set_xlabel("frames per second"); ax.set_ylabel(eje)
        ax.grid(axis="y", color="#e3e3e3"); ax.set_axisbelow(True)
    axs[0].set_ylim(0, 100); axs[1].set_ylim(2600, 3600); axs[0].legend(frameon=False, loc="upper left")
    fig.tight_layout(); fig.savefig(os.path.join(salida, "figura3_recursos.png"), dpi=300); plt.close(fig)


def figura4(mem, salida):
    a = [mem["A"][s] for s in SERVICIOS]; b = [mem["B"][s] for s in SERVICIOS]
    fig, ax = plt.subplots(figsize=(12, 5)); y = np.arange(len(SERVICIOS)); h = 0.38
    ax.barh(y - h / 2, a, h, color=COLOR["A"], label="System A")
    ax.barh(y + h / 2, b, h, color=COLOR["B"], label="System B")
    for yi, (va, vb) in enumerate(zip(a, b)):
        ax.text(va + 4, yi - h / 2, f"{va:.0f}", va="center", fontsize=12)
        ax.text(vb + 4, yi + h / 2, f"{vb:.0f}", va="center", fontsize=12)
    # Notas en superíndice: a = memoria utilizada por la JVM en el Sistema A; b = una de dos instancias en el Sistema A
    marca = {"data-management": r"$^{\mathrm{a}}$", "project-management": r"$^{\mathrm{a}}$",
             "user-management": r"$^{\mathrm{a}}$", "early-warning": r"$^{\mathrm{b}}$"}
    ax.set_yticks(y); ax.set_yticklabels([s + marca.get(s, "") for s in SERVICIOS]); ax.invert_yaxis()
    ax.set_xlabel("Memory (MiB)"); ax.set_xlim(0, max(a + b) * 1.12)
    ax.grid(axis="x", color="#e3e3e3"); ax.set_axisbelow(True); ax.legend(frameon=False, loc="lower right")
    fig.tight_layout(); fig.savefig(os.path.join(salida, "figura4_memoria_servicio.png"), dpi=300); plt.close(fig)


def figura5(sat_csv, serie_csv, inicio_utc, salida):
    t0 = datetime.fromisoformat(inicio_utc).replace(tzinfo=timezone.utc).timestamp()
    S = list(csv.DictReader(open(sat_csv, encoding="utf-8")))
    T = list(csv.DictReader(open(serie_csv, encoding="utf-8")))
    hr = lambda r: (datetime.fromisoformat(r["time"].replace("Z", "+00:00")).timestamp() - t0) / 3600
    fig, axs = plt.subplots(1, 2, figsize=(14, 4.8))
    ax = axs[0]
    ax.plot([hr(r) for r in S], [float(r["q_ew_evaluate"]) for r in S], color=COLOR["B"], lw=1.8, label="evaluation queue")
    ax.plot([hr(r) for r in S], [float(r["q_dm_persist"]) for r in S], color=COLOR["A"], lw=1.8, label="persistence queue")
    ax.plot([hr(r) for r in S], [float(r["q_dead_letter"]) for r in S], color="#888888", lw=1.8, ls="--", label="dead letter queue")
    ax.set_ylim(-1, 30); ax.set_ylabel("queued messages"); ax.set_title("Broker queues")
    ax2 = axs[1]
    ax2.plot([hr(r) for r in T], [float(r["fps"]) for r in T], color="#9BBCD6", lw=1.4, label="reception")
    ax2.plot([hr(r) for r in S], [float(r["ew_consumed_fps"]) for r in S], color=COLOR["B"], lw=2, label="early-warning consumption")
    ax2.set_ylim(0, 150); ax2.set_ylabel("frames per second"); ax2.set_title("Rates by component")
    for a in axs:
        for hh, et in ((2, "broker"), (6, "replica"), (10, "delay")):
            a.axvline(hh, color="#555555", ls=":", lw=1.2)
            a.text(hh + 0.1, a.get_ylim()[1] * 0.93, et, fontsize=11, color="#555555")
        a.set_xlabel("run time (hours)"); a.set_xlim(0, 12.2)
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
    ap.add_argument("--estimando", choices=["agregado", "ventanas"], default="agregado",
                    help="latencia por corrida: percentil del agregado (defecto) o mediana de las ventanas 18-59 (V3)")
    a = ap.parse_args()
    global ESTIMANDO
    ESTIMANDO = a.estimando
    os.makedirs(a.salida, exist_ok=True)

    EA, EB = cargar_escalera(a.escalera_a), cargar_escalera(a.escalera_b)
    E = {"A": EA, "B": EB}
    assert len(EA) == len(EB) == 20

    # Tabla 7 y Tabla 8
    with open(os.path.join(a.salida, "tabla7_tabla8.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tramas_s", "p50_A", "p50_B", "p95_A", "p95_B", "p99_A", "p99_B",
                    "dif_p95_B_menos_A", "ic95_inf", "ic95_sup", "delta_cliff", "p_exacto", "significativo_0.0125"])
        for l in NIVELES:
            med = {(s, k): st.median(valores_corrida(E[s], l, k)) for s in "AB" for k in ("p50", "p95", "p99")}
            w.writerow([l, med[("A", "p50")], med[("B", "p50")], med[("A", "p95")], med[("B", "p95")],
                        med[("A", "p99")], med[("B", "p99")]] + contraste(EA, EB, l, "p95"))

    # Contraste opcional del p99 a 100 tramas/s (sección 7 del brief)
    with open(os.path.join(a.salida, "contraste_p99_100.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tramas_s", "dif_p99_B_menos_A", "ic95_inf", "ic95_sup", "delta_cliff", "p_exacto", "significativo_0.0125"])
        w.writerow([100] + contraste(EA, EB, 100, "p99"))

    # Latencia por corrida, en orden real de ejecución (3.4 del manuscrito)
    orden = sorted(((c["inicio"], s, l, r) for s in "AB" for (l, r), c in E[s].items()))
    iso = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(a.salida, "latencia_por_corrida.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["orden", "sistema", "tramas_s", "corrida", "inicio_utc", "p50_agregado", "p95_agregado",
                    "p99_agregado", "p95_mediana_ventanas", "conteo_agregado", "conteo_ventana_efectiva"])
        for i, (t, s, l, r) in enumerate(orden, 1):
            c = E[s][(l, r)]
            w.writerow([i, s, l, r, iso(t), c["agregado"]["p50"], c["agregado"]["p95"], c["agregado"]["p99"],
                        st.median(c["p95"]), c["n_agregado"], c["n_efectivo"]])

    # Deriva: Spearman entre orden de ejecución y valor de corrida, dentro de cada celda sistema × nivel
    with open(os.path.join(a.salida, "deriva_spearman.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tramas_s", "sistema", "rho", "p"])
        for l in NIVELES:
            for s in "AB":
                rs = sorted((r for (ll, r) in E[s] if ll == l), key=lambda r: E[s][(l, r)]["inicio"])
                v = [valor_corrida(E[s][(l, r)], "p95") for r in rs]
                if len(set(v)) == 1:
                    w.writerow([l, s, "constante", ""])
                else:
                    rho, p = spearmanr(range(len(v)), v)
                    w.writerow([l, s, round(rho, 2), round(p, 2)])

    # Proporción de ventanas cuyo p95 supera el p95 agregado de su corrida
    with open(os.path.join(a.salida, "calentamiento_cola.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tramas_s", "sistema", "pct_calentamiento", "pct_medicion"])
        for l in NIVELES:
            for s in "AB":
                cs = [c for (ll, r), c in E[s].items() if ll == l]
                pct = lambda tramo: round(100 * st.mean(v is not None and v > c["agregado"]["p95"]
                                                        for c in cs for v in tramo(c["p95_ventanas"])), 1)
                w.writerow([l, s, pct(lambda x: x[:CALENTAMIENTO]), pct(lambda x: x[CALENTAMIENTO:])])

    # Corridas de resistencia de 12 h
    with open(os.path.join(a.salida, "resistencia_12h.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sistema", "confirmadas", "fallos", "p95_agregado", "ventanas_p95_mayor_1s", "ventanas"])
        for s, carpeta in (("A", a.escalera_a), ("B", a.escalera_b)):
            d = json.load(open(os.path.join(carpeta, "sustained-12h.json"), encoding="utf-8"))
            v = [p["summaries"].get(M, {}).get("p95") for p in d["intermediate"]]
            assert d["aggregate"]["summaries"][M]["count"] == d["aggregate"]["counters"]["dtu_tcp.frames_acked"]
            w.writerow([s, d["aggregate"]["counters"]["dtu_tcp.frames_acked"], d["aggregate"]["counters"].get("vusers.failed", 0),
                        d["aggregate"]["summaries"][M]["p95"], sum(x is not None and x > 1000 for x in v), len(v)])

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
