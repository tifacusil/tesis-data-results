#!/usr/bin/env python3
"""Reconcile B's data-receiving logs around the broker kill (23/09/2026, UTC).

Inputs: the data-receiving container logs of the three replicas, both the
instance that ended at 14:33:02 (data/data-receiving-logs-2026-09-23/*-previous.log)
and the instance that started at 14:33:04 (pod logs from
respaldo-logs-20261103/B-go-tesis-logs-20261103.tar.gz, members
var/log/pods/landslide_data-receiving-d9f59874f-<pod>_*/data-receiving/<n>.log).
Lines may carry the CRI prefix ("<ts> stdout F "); it is stripped.

  py -I scripts/auditoria_resistencia/analizar_logs_b.py --out results/auditoria_resistencia/logs_b.json LOG [LOG ...]

Only reads the logs. Writes one JSON with counts, message_id sets and their
intersections, and the buffer value reported by each "retry pass" line.
All timestamps are the "time" field of each JSON log line (UTC).
"""
import argparse
import collections
import hashlib
import json
import pathlib
import re

POD = re.compile(r"data-receiving-d9f59874f-([a-z0-9]{5})")
KEEP = {
    "rabbitmq publish failed; buffered in redis for retry": "publish_failed",
    "sink write failed": "sink_write_failed",
    "retry succeeded": "retry_succeeded",
    "retry publish failed": "retry_publish_failed",
    "retry delete failed": "retry_delete_failed",
    "buffer delete after publish failed; RetryWorker may republish": "buffer_delete_failed",
}


def lines(path):
    with open(path, encoding="utf-8") as f:
        for raw in f:
            i = raw.find("{")
            if i < 0:
                continue
            try:
                yield json.loads(raw[i:])
            except json.JSONDecodeError:
                continue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("logs", nargs="+")
    a = ap.parse_args()

    files = []
    ids = collections.defaultdict(list)          # kind -> [(time, pod, message_id, error)]
    retry_pass = []                               # (time, pod, buffered)
    lifecycle = []                                # (time, pod, msg)
    read_errors = collections.Counter()           # (pod, minute) -> count
    for p in a.logs:
        pth = pathlib.Path(p)
        counts = collections.Counter()
        first = last = None
        for rec in lines(pth):
            t, msg = rec.get("time"), rec.get("msg")
            pod = POD.search(rec.get("instance_id", "")).group(1)
            counts[msg] += 1
            first = first or t
            last = t
            if msg in KEEP:
                ids[KEEP[msg]].append((t, pod, rec.get("message_id"), rec.get("error")))
            elif msg == "retry pass":
                retry_pass.append((t, pod, rec.get("buffered")))
            elif msg in ("starting", "stopped", "tcp server stopped", "tcp server listening", "closing amqp connection"):
                lifecycle.append((t, pod, msg))
            elif msg == "error reading frame":
                read_errors[(pod, t[:16])] += 1
        files.append({"archivo": "/".join(pth.parts[-3:]), "sha256": hashlib.sha256(pth.read_bytes()).hexdigest(),
                      "primera_linea": first, "ultima_linea": last, "mensajes": dict(counts)})

    def summary(kind):
        rows = ids[kind]
        u = {r[2] for r in rows}
        per_pod = collections.Counter(r[1] for r in rows)
        errs = collections.Counter(re.sub(r"[0-9a-f-]{36}", "<id>", r[3] or "") for r in rows)
        return {"lineas": len(rows), "message_id_unicos": len(u), "por_pod": dict(per_pod),
                "primera": min((r[0] for r in rows), default=None),
                "ultima": max((r[0] for r in rows), default=None), "errores": dict(errs)}, u

    out = {"zona_horaria": "UTC", "archivos": files}
    sets = {}
    for kind in KEEP.values():
        out[kind], sets[kind] = summary(kind)

    failed, sinkf, retried = sets["publish_failed"], sets["sink_write_failed"], sets["retry_succeeded"]
    per_id = collections.Counter(r[2] for r in ids["retry_succeeded"])
    out["reconciliacion"] = {
        "publish_failed_con_retry_succeeded": len(failed & retried),
        "publish_failed_sin_retry_succeeded": len(failed - retried),
        "retry_succeeded_sin_publish_failed": len(retried - failed),
        "sink_write_failed_con_retry_succeeded": len(sinkf & retried),
        "sink_write_failed_con_publish_failed": len(sinkf & failed),
        "retry_succeeded_lineas_por_id": dict(collections.Counter(per_id.values())),
        "retry_succeeded_primera": out["retry_succeeded"]["primera"],
        "retry_succeeded_ultima": out["retry_succeeded"]["ultima"],
    }
    retry_pass.sort()
    nz = [r for r in retry_pass if r[2]]
    out["retry_pass"] = {
        "lineas": len(retry_pass),
        "max_buffered": max(retry_pass, key=lambda r: r[2]) if retry_pass else None,
        "primera_tras_reinicio": next((r for r in retry_pass if r[0] >= "2026-09-23T14:33:03"), None),
        "ultima_con_buffered": nz[-1] if nz else None,
        "por_minuto_max": {},
    }
    # The worker logs "retry pass" only when buffered > 0, so the last line is the last non-zero value seen.
    m = collections.defaultdict(int)
    for t, pod, b in retry_pass:
        m[t[:16]] = max(m[t[:16]], b)
    out["retry_pass"]["por_minuto_max"] = dict(sorted(m.items()))
    out["ciclo_de_vida"] = sorted(lifecycle)
    out["error_reading_frame_por_minuto"] = {f"{k[1]} {k[0]}": v for k, v in sorted(read_errors.items(), key=lambda kv: kv[0][1])}
    out["sink_write_failed_detalle"] = sorted(ids["sink_write_failed"])
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("publish_failed", "sink_write_failed", "retry_succeeded", "reconciliacion")}, indent=1))


if __name__ == "__main__":
    main()
