#!/usr/bin/env python3
"""
generar_graficas.py — ejecuta, en orden, los scripts que regeneran data/output/
(Figuras 2–5, Tablas 7–9 y las CSV de CPU del cliente), igual que el paso
"Regenerate data/output" del workflow reproduce.

Para añadir otro script, agregue una entrada a SCRIPTS; {datos} y {salida}
se sustituyen por los valores de --datos y --salida.

Uso (desde cualquier carpeta; necesita requirements.txt):
  python3 generar_graficas.py                       # data/ -> data/output/
  python3 generar_graficas.py --datos data --salida /tmp/salida
"""
import argparse, os, subprocess, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__))
ESC_A, ESC_B = "{datos}/A - SPETIEMBRE 5 RUNS", "{datos}/B - SEPTIEMBRE 5 RUNS V2"

SCRIPTS = [
    ["client_cpu.py", "--sistema", "A", ESC_A, "--sistema", "B", ESC_B, "--out", "{salida}"],
    ["generar_resultados.py",
     "--escalera-a", ESC_A, "--escalera-b", ESC_B,
     "--prom-a", "{datos}/A-ladder-0917-timeseries.csv",
     "--prom-b", "{datos}/B-ladder-0923-timeseries.csv",
     "--nivel1-dir", "{datos}/nivel1",
     "--sat-b", "{datos}/B-12h-0923-saturation.csv",
     "--serie-b", "{datos}/B-12h-0923-timeseries.csv",
     "--salida", "{salida}"],
]


def main():
    ap = argparse.ArgumentParser(description="Ejecuta los scripts que generan las gráficas y tablas.")
    ap.add_argument("--datos", default=os.path.join(AQUI, "data"), help="carpeta de entradas (por defecto: data/)")
    ap.add_argument("--salida", default=None, help="carpeta de salida (por defecto: <datos>/output)")
    a = ap.parse_args()
    salida = a.salida or os.path.join(a.datos, "output")
    os.makedirs(salida, exist_ok=True)

    fallidos = []
    for script, *args in SCRIPTS:
        cmd = [sys.executable, os.path.join(AQUI, script)] + [x.format(datos=a.datos, salida=salida) for x in args]
        print(f"[{script}] ejecutando…", flush=True)
        t0 = time.time()
        if subprocess.run(cmd).returncode != 0:
            print(f"[{script}] FALLÓ", file=sys.stderr)
            fallidos.append(script)
        else:
            print(f"[{script}] ok ({time.time() - t0:.1f} s)", flush=True)

    if fallidos:
        sys.exit(f"Fallaron {len(fallidos)} de {len(SCRIPTS)} scripts: {', '.join(fallidos)}")
    print(f"Listo. Salida en: {os.path.abspath(salida)}")


if __name__ == "__main__":
    main()
