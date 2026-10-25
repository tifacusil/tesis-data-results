"""Regresión de generar_resultados.py contra los valores publicados (V3) y los del re-análisis.
Uso: python test_generar_resultados.py"""
import csv, filecmp, os, subprocess, sys, tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
ARGS = ["--escalera-a", "data/A - SPETIEMBRE 5 RUNS", "--escalera-b", "data/B - SEPTIEMBRE 5 RUNS V2",
        "--prom-a", "data/A-ladder-0917-timeseries.csv", "--prom-b", "data/B-ladder-0923-timeseries.csv",
        "--nivel1-dir", "data/nivel1", "--sat-b", "data/B-12h-0923-saturation.csv", "--serie-b", "data/B-12h-0923-timeseries.csv"]

# Tabla 7 de Articulo_v3.docx (12 celdas, 24 valores): p50 A/B, p95 A/B, p99 A/B con el estimando de ventanas
V3 = {1: (198.4, 188.7, 198.4, 190.6, 198.4, 190.6), 10: (198.4, 186.8, 198.4, 194.4, 198.4, 194.4),
      50: (198.4, 186.8, 202.4, 198.4, 206.5, 202.4), 100: (198.4, 186.8, 206.5, 206.5, 210.6, 219.2)}
# Tablas 7 y 8 nuevas: p50 A/B, p95 A/B, p99 A/B, dif, IC, Cliff, p
NUEVA = {1: (198.4, 190.6, 198.4, 194.4, 202.4, 198.4, -4.0, -8.0, -4.0, -1.0, 0.0079),
         10: (198.4, 186.8, 198.4, 194.4, 202.4, 198.4, -4.0, -4.0, -4.0, -1.0, 0.0079),
         50: (198.4, 186.8, 206.5, 198.4, 210.6, 206.5, -8.1, -12.1, -4.0, -1.0, 0.0079),
         100: (198.4, 186.8, 206.5, 206.5, 210.6, 232.8, 0.0, 0.0, 8.4, 0.4, 0.4444)}

# Tabla 9 con la ventana efectiva filtrada (sin ventanas vacías): CPU A/B %, memoria A/B MiB
TABLA9 = {1: (5.7, 24.8, 3328.5, 2826.9), 10: (13.3, 35.3, 3334.1, 2832.9),
          50: (39.7, 61.3, 3338.3, 2864.4), 100: (68.0, 80.7, 3388.5, 2886.4)}


def correr(salida, *extra):
    subprocess.run([sys.executable, "generar_resultados.py", *ARGS, "--salida", salida, *extra], cwd=AQUI, check=True)
    return {int(r["tramas_s"]): r for r in csv.DictReader(open(os.path.join(salida, "tabla7_tabla8.csv"), encoding="utf-8"))}


with tempfile.TemporaryDirectory() as t:
    viejo = correr(os.path.join(t, "v"), "--estimando", "ventanas")
    for l, esperado in V3.items():
        assert tuple(float(viejo[l][k]) for k in ("p50_A", "p50_B", "p95_A", "p95_B", "p99_A", "p99_B")) == esperado, (l, viejo[l])

    nuevo = correr(os.path.join(t, "n1"))
    cols = ["p50_A", "p50_B", "p95_A", "p95_B", "p99_A", "p99_B", "dif_p95_B_menos_A", "ic95_inf", "ic95_sup", "delta_cliff", "p_exacto"]
    for l, esperado in NUEVA.items():
        assert tuple(float(nuevo[l][k]) for k in cols) == esperado, (l, nuevo[l])
        assert nuevo[l]["significativo_0.0125"] == str(l != 100)

    for r in csv.DictReader(open(os.path.join(t, "n1", "tabla9.csv"), encoding="utf-8")):
        assert tuple(float(r[k]) for k in ("cpu_A", "cpu_B", "mem_ocupada_A_MiB", "mem_ocupada_B_MiB")) == TABLA9[int(r["tramas_s"])], r

    correr(os.path.join(t, "n2"))
    c = filecmp.dircmp(os.path.join(t, "n1"), os.path.join(t, "n2"))
    assert not c.diff_files and not c.left_only and not c.right_only, c.diff_files
    assert all(filecmp.cmp(os.path.join(t, "n1", f), os.path.join(t, "n2", f), shallow=False) for f in c.same_files)
print("OK")
