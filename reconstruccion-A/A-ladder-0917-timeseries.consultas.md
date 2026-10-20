# A-ladder-0917-timeseries

Prometheus: `http://204.168.203.32:9090` · sistema A · 2026-09-17 16:00 → 2026-09-17 19:00 UTC · paso 60 s

| Columna | Consulta | Coincidencia | Estado |
|---|---|---|---|
| `fps` | `sum(rate(data_receiving_frames_total[1m]))` | 181/181 (dif. máx. 0.004444) | REPRODUCIDA |
| `node_cpu_pct` | `100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))` | 181/181 (dif. máx. 0.004932) | REPRODUCIDA |
| `node_mem_used_mib` | `(sum(node_memory_MemTotal_bytes) - sum(node_memory_MemAvailable_bytes)) / 1048576` | 181/181 (dif. máx. 0.05) | REPRODUCIDA |
| `mem_mib_data-analysis` | `sum(process_resident_memory_bytes{service="data-analysis"}) / 1048576` | 181/181 (dif. máx. 0.04844) | REPRODUCIDA |
| `mem_mib_data-management` | `sum(jvm_memory_used_bytes{service="data-management"}) / 1048576` | 181/181 (dif. máx. 0.04992) | REPRODUCIDA |
| `mem_mib_data-receiving` | `sum(process_resident_memory_bytes{service="data-receiving"}) / 1048576` | 181/181 (dif. máx. 0.05) | REPRODUCIDA |
| `mem_mib_early-warning` | `sum(process_resident_memory_bytes{service="early-warning"}) / 1048576` | 181/181 (dif. máx. 0.04766) | REPRODUCIDA |
| `mem_mib_project-management` | `sum(jvm_memory_used_bytes{service="project-management"}) / 1048576` | 181/181 (dif. máx. 0.04993) | REPRODUCIDA |
| `mem_mib_user-management` | `sum(jvm_memory_used_bytes{service="user-management"}) / 1048576` | 181/181 (dif. máx. 0.04968) | REPRODUCIDA |
| `cpu_pct_data-analysis` | `100 * sum(rate(process_cpu_seconds_total{service="data-analysis"}[1m]))` | 181/181 (dif. máx. 0.004444) | REPRODUCIDA |
| `cpu_pct_data-receiving` | `100 * sum(rate(process_cpu_seconds_total{service="data-receiving"}[1m]))` | 181/181 (dif. máx. 0.004445) | REPRODUCIDA |
| `cpu_pct_early-warning` | `100 * sum(rate(process_cpu_seconds_total{service="early-warning"}[1m]))` | 181/181 (dif. máx. 0.004444) | REPRODUCIDA |

## Consultas que también reproducen la columna

Los datos de la ventana no permiten distinguirlas de la elegida (por ejemplo, series que valen 0).

- `node_mem_used_mib`
  - `(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1048576`
- `mem_mib_early-warning`
  - `max(process_resident_memory_bytes{service="early-warning"}) / 1048576`
  - `avg(process_resident_memory_bytes{service="early-warning"}) / 1048576`
