#!/usr/bin/env python3
"""
generar_graficas.py — ejecuta, en orden, los scripts que generan las gráficas.

Cada entrada de SCRIPTS indica el script y sus argumentos; las rutas se resuelven
respecto a --datos (carpeta con los datos crudos, ver README §2 y §7).
Para añadir otro script de gráficas, agregue una entrada a SCRIPTS.

Uso:
  python3 generar_graficas.py --datos <carpeta_datos> --salida salida
"""
import argparse, os, subprocess, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__))

# (script, [(argumento, ruta relativa a --datos)])
SCRIPTS = [
    ("generar_resultados.py", [
        ("--escalera-a", "A - SPETIEMBRE 5 RUNS"),
        ("--escalera-b", "B - SEPTIEMBRE 5 RUNS V2"),
        ("--prom-a", "A-ladder-0917-timeseries.csv"),
        ("--prom-b", "B-ladder-0923-timeseries.csv"),
        ("--nivel1-dir", "nivel1"),
        ("--sat-b", "B-12h-0923-saturation.csv"),
        ("--serie-b", "B-12h-0923-timeseries.csv"),
    ]),
]


def main():
    ap = argparse.ArgumentParser(description="Ejecuta todos los scripts que generan las gráficas.")
    ap.add_argument("--datos", default=".", help="carpeta con los datos crudos (por defecto: .)")
    ap.add_argument("--salida", default="salida", help="carpeta de salida (por defecto: salida)")
    a = ap.parse_args()

    fallidos = []
    for script, entradas in SCRIPTS:
        rutas = [(arg, os.path.join(a.datos, rel)) for arg, rel in entradas]
        faltan = [r for _, r in rutas if not os.path.exists(r)]
        if faltan:
            print(f"[{script}] OMITIDO, faltan entradas:\n  " + "\n  ".join(faltan), file=sys.stderr)
            fallidos.append(script)
            continue
        cmd = [sys.executable, os.path.join(AQUI, script)]
        for arg, r in rutas:
            cmd += [arg, r]
        cmd += ["--salida", a.salida]
        print(f"[{script}] ejecutando…")
        t0 = time.time()
        if subprocess.run(cmd).returncode != 0:
            print(f"[{script}] FALLÓ", file=sys.stderr)
            fallidos.append(script)
        else:
            print(f"[{script}] ok ({time.time() - t0:.1f} s)")

    if fallidos:
        sys.exit(f"Fallaron {len(fallidos)} de {len(SCRIPTS)} scripts: {', '.join(fallidos)}")
    print(f"Todas las gráficas generadas en: {os.path.abspath(a.salida)}")


if __name__ == "__main__":
    main()
