# A-12h-0918-saturation

Prometheus: `http://204.168.203.32:9090` · sistema A · 2026-09-18 05:25 → 2026-09-18 17:20 UTC · paso 300 s

| Columna | Consulta | Coincidencia | Estado |
|---|---|---|---|
| `fps` | `sum(rate(data_receiving_frames_total[1m]))` | 144/144 (dif. máx. 0.004819) | REPRODUCIDA |
| `dr_published_fps` | `sum(rate(data_receiving_messages_published_total[5m]))` | 144/144 (dif. máx. 0.004269) | REPRODUCIDA |
| `ew_processed_fps` | `sum(rate(ew_messages_processed_total[5m]))` | 144/144 (dif. máx. 0.004561) | REPRODUCIDA |
| `dr_dropped_5m` | `sum(increase(data_receiving_messages_dropped_total[5m]))` | 144/144 (dif. máx. 0) | REPRODUCIDA |
