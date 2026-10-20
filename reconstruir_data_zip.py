#!/usr/bin/env python3
"""
reconstruir_data_zip.py — identifica y verifica las consultas PromQL que generaron los CSV de data.zip.

Para cada columna de un CSV archivado, prueba consultas candidatas contra Prometheus en los mismos
instantes del CSV (mismo inicio, fin y paso) y se queda con la que reproduce los valores archivados.
Una consulta se da por "reproducida" solo si coincide en al menos el 99 % de las filas, dentro del
redondeo con que se escribió el CSV. Así lo que queda documentado es una consulta verificada, no supuesta.

Salidas, en --salida:
  <nombre>.csv             CSV reconstruido con la mejor consulta de cada columna
  <nombre>.consultas.md    columna -> consulta elegida -> coincidencia -> estado

Uso:
  python3 reconstruir_data_zip.py --prom http://localhost:31083 --sistema B \
      --csv B-ladder-0923-timeseries.csv B-12h-0923-timeseries.csv B-12h-0923-saturation.csv \
      --salida reconstruccion

  # Buscar nombres de métricas cuando ninguna candidata reproduce una columna:
  python3 reconstruir_data_zip.py --prom http://localhost:31083 --descubrir "rabbit|restarts|published"

  # Probar una consulta propia para una columna (se puede repetir):
  ... --candidato 'ew_publish_in_fps=sum(rate(mi_metrica_total[1m]))'

Solo usa la biblioteca estándar de Python 3.8+.
"""
import argparse, csv, json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone

SERVICIOS_JVM_A = {"data-management", "project-management", "user-management"}


def rates(expr_fn, ventanas=("1m", "5m")):
    return [expr_fn(v) for v in ventanas]


def candidatos(col, sistema):
    """Consultas candidatas para una columna. La etiqueta de servicio es 'service' en A y 'app' en B."""
    lbl = "service" if sistema == "A" else "app"
    c = []
    if col == "fps":
        c = rates(lambda w: f"sum(rate(data_receiving_frames_total[{w}]))")
    elif col == "node_cpu_pct":
        c = rates(lambda w: f'100 * (1 - avg(rate(node_cpu_seconds_total{{mode="idle"}}[{w}])))', ("1m", "2m", "5m"))
    elif col == "node_mem_used_mib":
        c = ["(sum(node_memory_MemTotal_bytes) - sum(node_memory_MemAvailable_bytes)) / 1048576",
             "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1048576"]
    elif col.startswith("mem_mib_"):
        s = col[len("mem_mib_"):]
        rss = f'process_resident_memory_bytes{{{lbl}="{s}"}}'
        c = [f"sum({rss}) / 1048576", f"max({rss}) / 1048576", f"avg({rss}) / 1048576"]
        if sistema == "A" and s in SERVICIOS_JVM_A:
            jvm = f'jvm_memory_used_bytes{{{lbl}="{s}"}}'
            c = [f"sum({jvm}) / 1048576",
                 f'sum(jvm_memory_used_bytes{{{lbl}="{s}",area="heap"}}) / 1048576'] + c
    elif col.startswith("cpu_pct_"):
        s = col[len("cpu_pct_"):]
        c = rates(lambda w: f'100 * sum(rate(process_cpu_seconds_total{{{lbl}="{s}"}}[{w}]))')
    elif col in ("q_ew_evaluate", "q_dm_persist", "q_dead_letter"):
        q = {"q_ew_evaluate": "early_warning.evaluate", "q_dm_persist": "data_management.persist",
             "q_dead_letter": "sensors.dead_letter"}[col]
        c = [f'sum(rabbitmq_queue_messages_ready{{queue="{q}"}})',
             f'sum(rabbitmq_queue_messages{{queue="{q}"}})',
             f'max(rabbitmq_queue_messages_ready{{queue="{q}"}})',
             f'max(rabbitmq_queue_messages{{queue="{q}"}})']
    elif col == "ew_consumed_fps":
        c = rates(lambda w: f"sum(rate(ew_messages_consumed_total[{w}]))")
    elif col == "ew_processed_fps":
        c = rates(lambda w: f"sum(rate(ew_messages_processed_total[{w}]))")
    elif col == "dr_published_fps":
        c = rates(lambda w: f"sum(rate(data_receiving_messages_published_total[{w}]))")
    elif col == "ew_publish_in_fps":
        c = (rates(lambda w: f'sum(rate(rabbitmq_queue_messages_published_total{{queue="early_warning.evaluate"}}[{w}]))')
             + rates(lambda w: f"sum(rate(data_receiving_messages_published_total[{w}]))")
             + rates(lambda w: f"sum(rate(rabbitmq_global_messages_received_total[{w}]))"))
    elif col == "ew_dropped_5m":
        c = ["sum(increase(ew_messages_dropped_total[5m]))"]
    elif col == "dr_dropped_5m":
        c = ["sum(increase(data_receiving_messages_dropped_total[5m]))"]
    elif col == "dm_dlq_5m":
        c = ["sum(increase(dm_messages_dlq_total[5m]))"]
    elif col == "redis_buffer_pending":
        c = ["sum(data_receiving_redis_buffer_pending)", "max(data_receiving_redis_buffer_pending)"]
    elif col == "pod_restarts":
        c = ['sum(kube_pod_container_status_restarts_total{namespace="landslide"})',
             "sum(kube_pod_container_status_restarts_total)"]
    elif col == "rabbit_up":
        c = ["max(rabbitmq_up)", 'max(up{job=~".*rabbit.*"})', 'min(up{job=~".*rabbit.*"})',
             "max(rabbitmq_identity_info)"]
    return c


# ---------------------------------------------------------------- Prometheus
def prom_get(base, path, params):
    url = base.rstrip("/") + path + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as r:
        d = json.load(r)
    if d.get("status") != "success":
        raise RuntimeError(d.get("error", "respuesta sin éxito"))
    return d["data"]


def serie(base, expr, start, end, step):
    """Devuelve ({epoch: valor}, None) o (None, motivo)."""
    try:
        res = prom_get(base, "/api/v1/query_range",
                       {"query": expr, "start": start, "end": end, "step": step})["result"]
    except Exception as e:
        return None, f"error: {e}"
    if not res:
        return None, "sin datos"
    if len(res) > 1:
        return None, f"devuelve {len(res)} series"
    return {int(round(float(t))): float(v) for t, v in res[0]["values"]}, None


# ---------------------------------------------------------------- CSV archivado
def epoch(iso):
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp())


def decimales(txt):
    return len(txt.split(".")[1]) if "." in txt else 0


def cargar(ruta):
    filas = list(csv.DictReader(open(ruta, encoding="utf-8")))
    ts = [epoch(f["time"]) for f in filas]
    pasos = {b - a for a, b in zip(ts, ts[1:])}
    if len(pasos) != 1:
        sys.exit(f"{ruta}: el paso entre filas no es constante ({sorted(pasos)[:5]})")
    return filas, ts, pasos.pop()


def comparar(filas, ts, col, valores):
    n = ok = 0
    dif_max = 0.0
    for f, t in zip(filas, ts):
        a = f.get(col, "")
        if a in ("", "NaN"):
            continue
        n += 1
        v = valores.get(t)
        if v is None:
            continue
        d = abs(v - float(a))
        dif_max = max(dif_max, d)
        if d <= 0.5 * 10 ** -decimales(a) * 1.01 + 1e-9:
            ok += 1
    return ok, n, dif_max


# ---------------------------------------------------------------- principal
def reconstruir(base, sistema, ruta, salida, extra):
    filas, ts, paso = cargar(ruta)
    nombre = os.path.splitext(os.path.basename(ruta))[0]
    cols = [c for c in filas[0].keys() if c != "time"]
    print(f"\n== {nombre}: {len(filas)} filas, paso {paso}s, {len(cols)} columnas")
    elegidas, informe = {}, []
    for col in cols:
        cands = extra.get(col, []) + candidatos(col, sistema)
        mejor = None
        notas = []
        reproducen = []
        for expr in cands:
            vals, motivo = serie(base, expr, ts[0], ts[-1], f"{paso}s")
            if vals is None:
                notas.append(f"`{expr}`: {motivo}")
                continue
            ok, n, dmax = comparar(filas, ts, col, vals)
            if n and ok / n >= 0.99:
                reproducen.append(expr)
            clave = (ok / n if n else 0, -dmax)
            if mejor is None or clave > mejor[0]:
                mejor = (clave, expr, vals, ok, n, dmax)
        if mejor is None:
            estado, expr, txt = "SIN CANDIDATA", "—", "0/0"
            if not cands:
                notas.append("no hay candidatas: usar --candidato o --descubrir")
        else:
            (frac, _), expr, vals, ok, n, dmax = mejor
            elegidas[col] = (vals, expr)
            estado = "REPRODUCIDA" if n and frac >= 0.99 else "NO REPRODUCIDA"
            txt = f"{ok}/{n} (dif. máx. {dmax:.4g})"
        empates = [e for e in reproducen if e != expr]
        print(f"  {col:32} {estado:15} {txt}" + (f"  (+{len(empates)} equivalentes)" if empates else ""))
        informe.append((col, expr, txt, estado, notas, empates))

    os.makedirs(salida, exist_ok=True)
    dec = {c: max((decimales(f[c]) for f in filas if f[c] not in ("", "NaN")), default=2) for c in cols}
    with open(os.path.join(salida, nombre + ".csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["time"] + cols)
        for f, t in zip(filas, ts):
            fila = [f["time"]]
            for c in cols:
                v = elegidas.get(c, ({}, ""))[0].get(t)
                fila.append("" if v is None else f"{v:.{dec[c]}f}")
            w.writerow(fila)
    with open(os.path.join(salida, nombre + ".consultas.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# {nombre}\n\nPrometheus: `{base}` · sistema {sistema} · "
                 f"{datetime.fromtimestamp(ts[0], timezone.utc):%Y-%m-%d %H:%M} → "
                 f"{datetime.fromtimestamp(ts[-1], timezone.utc):%Y-%m-%d %H:%M} UTC · paso {paso} s\n\n"
                 "| Columna | Consulta | Coincidencia | Estado |\n|---|---|---|---|\n")
        esc = lambda x: x.replace('|', chr(92) + '|')
        for col, expr, txt, estado, _, _ in informe:
            fh.write(f"| `{col}` | `{esc(expr)}` | {txt} | {estado} |\n")
        emp = [(c, e) for c, _, _, _, _, e in informe if e]
        if emp:
            fh.write("\n## Consultas que también reproducen la columna\n\n"
                     "Los datos de la ventana no permiten distinguirlas de la elegida (por ejemplo, series que valen 0).\n\n")
            for c, e in emp:
                fh.write(f"- `{c}`\n" + "".join(f"  - `{x}`\n" for x in e))
        pend = [(c, n) for c, _, _, e, n, _ in informe if e != "REPRODUCIDA" and n]
        if pend:
            fh.write("\n## Candidatas descartadas\n\n")
            for c, n in pend:
                fh.write(f"- `{c}`\n" + "".join(f"  - {x}\n" for x in n))
    return sum(1 for r in informe if r[3] == "REPRODUCIDA"), len(cols)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prom", required=True, help="URL de Prometheus, p. ej. http://localhost:31083")
    ap.add_argument("--sistema", choices=["A", "B"])
    ap.add_argument("--csv", nargs="+", help="CSV archivados de data.zip")
    ap.add_argument("--salida", default="reconstruccion")
    ap.add_argument("--candidato", action="append", default=[], metavar="COL=EXPR")
    ap.add_argument("--descubrir", metavar="REGEX", help="lista los nombres de métricas que coinciden")
    a = ap.parse_args()

    if a.descubrir:
        nombres = prom_get(a.prom, "/api/v1/label/__name__/values", {})
        for n in sorted(x for x in nombres if re.search(a.descubrir, x)):
            print(n)
        return
    if not (a.sistema and a.csv):
        ap.error("--sistema y --csv son obligatorios salvo con --descubrir")

    extra = {}
    for c in a.candidato:
        col, _, expr = c.partition("=")
        extra.setdefault(col.strip(), []).append(expr.strip())

    total_ok = total = 0
    for ruta in a.csv:
        ok, n = reconstruir(a.prom, a.sistema, ruta, a.salida, extra)
        total_ok += ok
        total += n
    print(f"\nColumnas reproducidas: {total_ok}/{total}. Informe y CSV en {a.salida}/")


if __name__ == "__main__":
    main()
