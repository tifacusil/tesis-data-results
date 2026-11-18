#!/usr/bin/env python3
"""Export the raw Prometheus series used by the 12 h endurance audit.

Run against the restored 14/10/2026 TSDB backups (scripts/restore_backups.sh:
A on :9092, B on :9091). Read-only: it only issues GET /api/v1/query and
/api/v1/query_range. Each query is written verbatim to its own JSON file, and
manifiesto.json records query, type, time/start/end/step and SHA-256.

  py -I scripts/auditoria_resistencia/exportar_prometheus.py \
     --prom-a http://localhost:9092 --prom-b http://localhost:9091 \
     --out results/auditoria_resistencia/prometheus

"raw" queries are instant queries over a range selector, evaluated at the end
of the export window: they return every scrape sample (15 s), with no
extrapolation. "range" queries use /api/v1/query_range with a 60 s step.
All times are UTC.
"""
import argparse
import hashlib
import json
import pathlib
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# Run windows from aggregate.firstMetricAt / lastMetricAt of each sustained-12h.json
# (epoch ms): A 1789708651024-1789752032403, B 1790166680398-1790210061989.
# Exported with 5 min of margin on each side.
WINDOWS = {
    "A": (1789708651 - 300, 1789752033 + 300),
    "B": (1790166680 - 300, 1790210062 + 300),
}

DM = 'instance="mysqld-exporter-data-management:9104"'
Q_B = 'queue=~"data_management.persist|early_warning.evaluate|sensors.dead_letter"'
MEM_NODE = "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes"

QUERIES = {
    "B": [
        ("raw", "frames", "data_receiving_frames_total"),
        ("raw", "published", "data_receiving_messages_published_total"),
        ("raw", "dr_dropped", "data_receiving_messages_dropped_total"),
        ("raw", "buffer", "data_receiving_redis_buffer_pending"),
        ("raw", "dm_processed", "dm_messages_processed_total"),
        ("raw", "dm_dlq", "dm_messages_dlq_total"),
        ("raw", "dm_retried", "dm_messages_retried_total"),
        ("raw", "dm_invalid", "dm_messages_invalid_total"),
        ("raw", "ew_dropped", "ew_messages_dropped_total"),
        ("raw", "ew_consumed", "ew_messages_consumed_total"),
        ("raw", "ew_alerts", "ew_alerts_published_total"),
        ("raw", "ew_duplicates", "ew_duplicates_skipped_total"),
        ("raw", "ew_alert_delivery_count", "ew_alert_delivery_latency_seconds_count"),
        ("raw", "mysql_rows_inserted", f'mysql_global_status_innodb_row_ops_total{{{DM},operation="inserted"}}'),
        ("raw", "mysql_insert_cmds", f'mysql_global_status_commands_total{{{DM},command="insert"}}'),
        ("raw", "queues", f"rabbitmq_queue_messages{{{Q_B}}}"),
        ("raw", "queue_published", f"rabbitmq_queue_messages_published_total{{{Q_B}}}"),
        ("raw", "rabbit_up", "rabbitmq_up"),
        ("raw", "restarts", 'kube_pod_container_status_restarts_total{namespace="landslide"}'),
        ("raw", "ready", 'kube_pod_container_status_ready{namespace="landslide"}'),
        ("range", "mem_node", MEM_NODE),
        ("range", "mem_rss_app", 'sum by (app) (process_resident_memory_bytes{app!=""})'),
        ("range", "mem_rss_instance", 'process_resident_memory_bytes{app!=""}'),
    ],
    "A": [
        ("raw", "frames", "data_receiving_frames_total"),
        ("raw", "published", "data_receiving_messages_published_total"),
        ("raw", "dr_dropped", "data_receiving_messages_dropped_total"),
        ("raw", "dm_processed", "dm_messages_processed_total"),
        ("raw", "dm_rabbit_acked", 'rabbitmq_acknowledged_total{service="data-management"}'),
        ("raw", "ew_processed", "ew_messages_processed_total"),
        ("raw", "mysql_rows_inserted", 'mysql_global_status_innodb_row_ops_total{operation="inserted"}'),
        ("raw", "up", 'up{job="microservices"}'),
        ("raw", "process_start", 'process_start_time_seconds{job="microservices"}'),
        ("raw", "dm_rabbit_connections", 'rabbitmq_connections{service="data-management"}'),
        ("raw", "dr_outgoing_connections", 'system_net_sockets_outgoing_connections_established{service="data-receiving"}'),
        ("raw", "redis_up", "redis_up"),
        ("range", "mem_node", MEM_NODE),
        ("range", "mem_rss_service", 'sum by (service) (process_resident_memory_bytes{service!=""})'),
        ("range", "mem_jvm_service", 'sum by (service) (jvm_memory_used_bytes{service!=""})'),
    ],
}


def get(base, path, params):
    url = f"{base}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=300) as r:
        body = r.read()
    doc = json.loads(body)
    if doc.get("status") != "success":
        sys.exit(f"query failed: {url}: {doc}")
    if not doc["data"]["result"]:
        sys.exit(f"empty result, refusing to write an empty file: {params}")
    return body


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prom-a", required=True)
    ap.add_argument("--prom-b", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"prometheus": {"A": a.prom_a, "B": a.prom_b}, "zona_horaria": "UTC", "archivos": []}
    for system, base in (("A", a.prom_a), ("B", a.prom_b)):
        start, end = WINDOWS[system]
        for kind, name, expr in QUERIES[system]:
            if kind == "raw":
                q = f"{expr}[{end - start}s]"
                params = {"query": q, "time": end}
                body = get(base, "/api/v1/query", params)
                entry = {"consulta": q, "api": "/api/v1/query", "time": iso(end)}
            else:
                params = {"query": expr, "start": start, "end": end, "step": "60s"}
                body = get(base, "/api/v1/query_range", params)
                entry = {"consulta": expr, "api": "/api/v1/query_range",
                         "start": iso(start), "end": iso(end), "step": "60s"}
            f = out / f"{system}__{name}.json"
            f.write_bytes(body)
            entry.update(archivo=f.name, sistema=system, sha256=hashlib.sha256(body).hexdigest())
            manifest["archivos"].append(entry)
            print(f"{f.name}: {len(body)} B")
    (out / "manifiesto.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
