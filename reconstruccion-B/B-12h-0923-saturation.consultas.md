# B-12h-0923-saturation

Prometheus: `http://178.105.104.95:31083` · sistema B · 2026-09-23 12:35 → 2026-09-24 00:30 UTC · paso 300 s

| Columna | Consulta | Coincidencia | Estado |
|---|---|---|---|
| `fps` | `sum(rate(data_receiving_frames_total[1m]))` | 144/144 (dif. máx. 0.004444) | REPRODUCIDA |
| `q_ew_evaluate` | `sum(rabbitmq_queue_messages{queue="early_warning.evaluate"})` | 144/144 (dif. máx. 0) | REPRODUCIDA |
| `q_dm_persist` | `sum(rabbitmq_queue_messages{queue="data_management.persist"})` | 144/144 (dif. máx. 0) | REPRODUCIDA |
| `q_dead_letter` | `sum(rabbitmq_queue_messages_ready{queue="sensors.dead_letter"})` | 144/144 (dif. máx. 0) | REPRODUCIDA |
| `ew_consumed_fps` | `sum(rate(ew_messages_consumed_total[5m]))` | 144/144 (dif. máx. 0.004561) | REPRODUCIDA |
| `ew_publish_in_fps` | `sum(rate(rabbitmq_queue_messages_published_total{queue="early_warning.evaluate"}[5m]))` | 144/144 (dif. máx. 0.004912) | REPRODUCIDA |
| `ew_dropped_5m` | `sum(increase(ew_messages_dropped_total[5m]))` | 144/144 (dif. máx. 0) | REPRODUCIDA |
| `dr_dropped_5m` | `sum(increase(data_receiving_messages_dropped_total[5m]))` | 144/144 (dif. máx. 0) | REPRODUCIDA |
| `dm_dlq_5m` | `sum(increase(dm_messages_dlq_total[5m]))` | 144/144 (dif. máx. 0) | REPRODUCIDA |
| `redis_buffer_pending` | `sum(data_receiving_redis_buffer_pending)` | 144/144 (dif. máx. 0) | REPRODUCIDA |
| `pod_restarts` | `sum(kube_pod_container_status_restarts_total{namespace="landslide"})` | 144/144 (dif. máx. 0) | REPRODUCIDA |
| `rabbit_up` | `max(rabbitmq_up)` | 144/144 (dif. máx. 0) | REPRODUCIDA |

## Consultas que también reproducen la columna

Los datos de la ventana no permiten distinguirlas de la elegida (por ejemplo, series que valen 0).

- `q_ew_evaluate`
  - `max(rabbitmq_queue_messages{queue="early_warning.evaluate"})`
- `q_dm_persist`
  - `max(rabbitmq_queue_messages{queue="data_management.persist"})`
- `q_dead_letter`
  - `sum(rabbitmq_queue_messages{queue="sensors.dead_letter"})`
  - `max(rabbitmq_queue_messages_ready{queue="sensors.dead_letter"})`
  - `max(rabbitmq_queue_messages{queue="sensors.dead_letter"})`
- `pod_restarts`
  - `sum(kube_pod_container_status_restarts_total)`
- `rabbit_up`
  - `max(up{job=~".*rabbit.*"})`
  - `min(up{job=~".*rabbit.*"})`
