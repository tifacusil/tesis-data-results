#!/usr/bin/env python3
"""
Utilización de procesador del cliente generador por corrida, nivel y sistema.

Entrada, por cada sistema, una carpeta con los pares de cada corrida de la escalera:
    vu-<nivel>-r<n>.json             reporte de Artillery (se usa el inicio de 'intermediate')
    vu-<nivel>-r<n>.client-cpu.csv   unix_ts,cpu_percent,node_percent,python_percent

Ventana: desde el inicio del reporte de Artillery + calentamiento (180 s por defecto)
hasta el inicio + duración (600 s por defecto), igual que la ventana efectiva del artículo.

Columnas del CSV:
    cpu_percent     utilización total de la máquina (0-100 %)
    node_percent    proceso de Artillery (Node.js), % de un procesador lógico (puede superar 100)
    python_percent  procesos emuladores de DTU en Python, % de un procesador lógico

Salidas:
    <out>/client-cpu-por-corrida.csv   una fila por corrida (mediana y media en la ventana)
    <out>/client-cpu-resumen.csv       por sistema y nivel: mediana de las medianas de corrida y rango
    y la tabla de resumen por pantalla.

Uso:
    python client_cpu.py --sistema A "A - SPETIEMBRE 5 RUNS" --sistema B "B - SEPTIEMBRE 5 RUNS V2" --out salida
"""
import argparse
import csv
import json
import os
import re
import statistics as st
import sys

METRICAS = ("cpu_percent", "node_percent", "python_percent")
PATRON = re.compile(r"^vu-(\d+)-r(\d+)\.client-cpu\.csv$")


def inicio_artillery(ruta_json):
    """Marca de tiempo (s) del primer periodo del reporte de Artillery."""
    with open(ruta_json, encoding="utf-8") as f:
        rep = json.load(f)
    periodos = []
    for p in rep.get("intermediate", []):
        v = p.get("period") or p.get("firstMetricAt")
        if v is None:
            continue
        v = int(v)
        periodos.append(v // 1000 if v > 10**11 else v)  # ms -> s
    if not periodos:
        raise ValueError(f"sin periodos en {ruta_json}")
    return min(periodos)


def leer_csv(ruta):
    filas = []
    with open(ruta, encoding="utf-8") as f:
        for x in csv.DictReader(f):
            filas.append({"ts": int(float(x["unix_ts"])), **{m: float(x[m]) for m in METRICAS}})
    filas.sort(key=lambda r: r["ts"])
    return filas


def corridas(carpeta, sistema, calentamiento, duracion):
    salida = []
    for nombre in sorted(os.listdir(carpeta)):
        m = PATRON.match(nombre)
        if not m:
            continue
        nivel, rep = int(m.group(1)), int(m.group(2))
        ruta_csv = os.path.join(carpeta, nombre)
        ruta_json = os.path.join(carpeta, f"vu-{m.group(1)}-r{m.group(2)}.json")
        if not os.path.exists(ruta_json):
            print(f"aviso: falta {ruta_json}; se omite la corrida", file=sys.stderr)
            continue
        t0 = inicio_artillery(ruta_json)
        filas = leer_csv(ruta_csv)
        vent = [r for r in filas if t0 + calentamiento <= r["ts"] <= t0 + duracion]
        if not vent:
            print(f"aviso: ventana vacía en {ruta_csv}", file=sys.stderr)
            continue
        huecos = sum(1 for a, b in zip(filas, filas[1:]) if b["ts"] - a["ts"] > 8)
        fila = {
            "sistema": sistema, "nivel": nivel, "corrida": rep,
            "inicio_artillery_unix": t0,
            "desfase_csv_s": filas[0]["ts"] - t0,
            "muestras_ventana": len(vent),
            "huecos_mayores_8s": huecos,
        }
        for met in METRICAS:
            vals = [r[met] for r in vent]
            fila[f"{met}_mediana"] = st.median(vals)
            fila[f"{met}_media"] = round(st.mean(vals), 2)
            fila[f"{met}_max"] = max(vals)
        salida.append(fila)
    return salida


def resumir(filas):
    grupos = {}
    for f in filas:
        grupos.setdefault((f["sistema"], f["nivel"]), []).append(f)
    resumen = []
    for (sis, niv), g in sorted(grupos.items(), key=lambda k: (k[0][1], k[0][0])):
        r = {"sistema": sis, "nivel": niv, "corridas": len(g)}
        for met in METRICAS:
            meds = [x[f"{met}_mediana"] for x in g]
            r[f"{met}_mediana"] = st.median(meds)
            r[f"{met}_min_corrida"] = min(meds)
            r[f"{met}_max_corrida"] = max(meds)
        resumen.append(r)
    return resumen


def escribir(ruta, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sistema", nargs=2, action="append", metavar=("ETIQUETA", "CARPETA"), required=True)
    ap.add_argument("--calentamiento", type=int, default=180, help="segundos descartados (180)")
    ap.add_argument("--duracion", type=int, default=600, help="duración de la corrida en s (600)")
    ap.add_argument("--out", default="salida-client-cpu")
    a = ap.parse_args()

    filas = []
    for etiqueta, carpeta in a.sistema:
        filas += corridas(carpeta, etiqueta, a.calentamiento, a.duracion)
    if not filas:
        sys.exit("no se encontraron corridas")
    resumen = resumir(filas)

    os.makedirs(a.out, exist_ok=True)
    escribir(os.path.join(a.out, "client-cpu-por-corrida.csv"), filas)
    escribir(os.path.join(a.out, "client-cpu-resumen.csv"), resumen)

    print(f"Ventana: inicio de Artillery + {a.calentamiento} s hasta + {a.duracion} s; "
          "mediana de las medianas de corrida [rango entre corridas]\n")
    print(f"{'Tramas/s':>8} {'Sist':>4}  {'Máquina %':>18}  {'Artillery % lógico':>20}  {'Python % lógico':>16}")
    for r in resumen:
        def c(m):
            return f"{r[m+'_mediana']:g} [{r[m+'_min_corrida']:g}–{r[m+'_max_corrida']:g}]"
        print(f"{r['nivel']:>8} {r['sistema']:>4}  {c('cpu_percent'):>18}  {c('node_percent'):>20}  {c('python_percent'):>16}")
    print(f"\nArchivos en {os.path.abspath(a.out)}")


if __name__ == "__main__":
    main()
