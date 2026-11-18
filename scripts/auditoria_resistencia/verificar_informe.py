#!/usr/bin/env python3
"""Check that the figures in docs/auditoria-resistencia-12h.md match the generated JSON.

The report was written by hand from results/auditoria_resistencia/hallazgos.json and
logs_b.json. This script looks up each figure, formatted as the report writes it
(thousands separated by a space, decimal comma, minus sign "−"), in the report text.
It prints one line per missing figure and exits with code 1 if any is missing.

  py -I scripts/auditoria_resistencia/verificar_informe.py

Values taken from manual commands (journal times, last_terminated_*, per-sample
transitions written as times) are not covered: see the report, section 5.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
H = json.loads((ROOT / "results/auditoria_resistencia/hallazgos.json").read_text(encoding="utf-8"))
L = json.loads((ROOT / "results/auditoria_resistencia/logs_b.json").read_text(encoding="utf-8"))
MD = (ROOT / "docs/auditoria-resistencia-12h.md").read_text(encoding="utf-8")


def fmt(v, dec=None):
    if dec is None:
        dec = 0 if float(v).is_integer() else 1
    s = f"{abs(v):,.{dec}f}".replace(",", " ").replace(".", ",")
    return ("−" if v < 0 else "") + s


def main():
    checks = []  # (label, value, decimals, text the value must appear in)

    def add(label, v, dec=None, where=MD):
        checks.append((label, v, dec, where))

    for s in "AB":
        a = H[f"artillery_{s}"]
        for k in ("emitidas", "confirmadas", "fallidas"):
            add(f"{s} {k}", a[k])
        add(f"{s} p95", a["p95_agregado"])
        d = H["durabilidad"][s]
        add(f"{s} trafico previo", d["trafico_previo_frames"]["frames"])
        for k in ("frames_ok", "dm_processed"):
            add(f"{s} {k}", d[k])
        add(f"{s} dm - confirmadas", d["dif_dm_processed_vs_confirmadas"]["abs"])
        add(f"{s} dm - confirmadas %", d["dif_dm_processed_vs_confirmadas"]["pct"], 4)
        m = H["memoria_nodo"][s]
        for k in ("todo", "sin_inyecciones"):
            for f in ("inicial_MiB", "final_MiB", "min_MiB", "max_MiB"):
                add(f"{s} memoria {k} {f}", m[k][f], 1)
            add(f"{s} memoria {k} pendiente", m[k]["pendiente_MiB_h"], 2)
        for n, w in m["ventanas_inyeccion"].items():
            add(f"{s} memoria {n} min", w["min_MiB"], 1)
            add(f"{s} memoria {n} max", w["max_MiB"], 1)
    add("B no confirmadas %", H["artillery_B"]["no_confirmadas_pct"], 4)
    for p in H["artillery_B"]["periodos_con_fallos"]:
        add(f"B fallos {p['periodo']}", p["fallidas"])

    b = H["durabilidad"]["B"]
    for k in ("mysql_rows_inserted", "mysql_insert_cmds", "ew_consumed", "ew_duplicates", "ew_alerts", "ew_alert_delivery_count"):
        add(f"B {k}", b[k])
    add("B insert - filas", b["mysql_insert_cmds"] - b["mysql_rows_inserted"])
    add("B frames - confirmadas", b["dif_frames_ok_vs_confirmadas"]["abs"])
    add("B persist publicados", b["queue_published"]["data_management.persist"])
    buf = b["buffer_caida_broker"]
    add("B buffer max", buf["max"])
    for r in buf["por_replica_max"]:
        add(f"B buffer {r['serie']}", r["max"])
        add(f"B buffer t {r['serie']}", r["primera_muestra_con_max"][11:19])

    a = H["durabilidad"]["A"]
    add("A ew_processed", a["ew_processed"])
    for w in a["dm_menos_frames_por_ventana"]:
        row = next((l for l in MD.splitlines() if "dm_menos_frames_por_ventana" in l), "")
        add(f"A dm-frames {w['desde']}", w["dm_menos_frames"], where=row)
        if abs(w["dm_menos_frames"]) > 1000:
            add(f"A frames {w['desde']}", w["frames"], where=row)
            add(f"A dm {w['desde']}", w["dm_processed"], where=row)

    for app, r in H["memoria_servicio_B"]["servicios"].items():
        row = next(l for l in MD.splitlines() if l.startswith(f"| {app} |"))
        for f in ("inicial_MiB", "final_MiB", "min_MiB", "max_MiB"):
            add(f"{app} {f}", r[f], 1, row)
        for f in ("pendiente_todo_MiB_h", "pendiente_sin_inyecciones_MiB_h"):
            add(f"{app} {f}", r[f], 2, row)

    for e in H["incidencias"]["B"]["todos_los_periodos_p95_mayor_1s"]:
        add(f"B p95>1s {e['desde']}", e["p95_max_ms"])
        add(f"B p95>1s desde {e['desde']}", e["desde"][11:19])

    for k in ("publish_failed", "sink_write_failed", "retry_succeeded"):
        add(f"logs {k}", L[k]["lineas"])
        for pod, n in L[k]["por_pod"].items():
            add(f"logs {k} {pod}", n)
    for times, n in L["reconciliacion"]["retry_succeeded_lineas_por_id"].items():
        add(f"logs ids republicados {times} veces", n)

    missing = []
    for lab, v, dec, where in checks:
        s = v if isinstance(v, str) else fmt(v, dec)
        if s not in where:
            missing.append((lab, v, s))
    for lab, v, s in missing:
        print(f'FALTA {lab}: {v} (buscado como "{s}")')
    print(f"{len(checks)} cifras comprobadas, {len(missing)} no encontradas")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
