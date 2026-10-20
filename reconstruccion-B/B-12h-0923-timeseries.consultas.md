# B-12h-0923-timeseries

Prometheus: `http://178.105.104.95:31083` · sistema B · 2026-09-23 12:35 → 2026-09-24 00:30 UTC · paso 60 s

| Columna | Consulta | Coincidencia | Estado |
|---|---|---|---|
| `fps` | `sum(rate(data_receiving_frames_total[1m]))` | 716/716 (dif. máx. 0.004987) | REPRODUCIDA |
| `node_cpu_pct` | `100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))` | 716/716 (dif. máx. 0.004983) | REPRODUCIDA |
| `node_mem_used_mib` | `(sum(node_memory_MemTotal_bytes) - sum(node_memory_MemAvailable_bytes)) / 1048576` | 716/716 (dif. máx. 0.05) | REPRODUCIDA |
| `mem_mib_data-analysis` | `sum(process_resident_memory_bytes{app="data-analysis"}) / 1048576` | 716/716 (dif. máx. 0.05) | REPRODUCIDA |
| `mem_mib_data-management` | `sum(process_resident_memory_bytes{app="data-management"}) / 1048576` | 716/716 (dif. máx. 0.05) | REPRODUCIDA |
| `mem_mib_data-receiving` | `sum(process_resident_memory_bytes{app="data-receiving"}) / 1048576` | 716/716 (dif. máx. 0.05) | REPRODUCIDA |
| `mem_mib_early-warning` | `sum(process_resident_memory_bytes{app="early-warning"}) / 1048576` | 716/716 (dif. máx. 0.05) | REPRODUCIDA |
| `mem_mib_project-management` | `sum(process_resident_memory_bytes{app="project-management"}) / 1048576` | 716/716 (dif. máx. 0.05) | REPRODUCIDA |
| `mem_mib_user-management` | `sum(process_resident_memory_bytes{app="user-management"}) / 1048576` | 716/716 (dif. máx. 0.05) | REPRODUCIDA |
| `cpu_pct_data-analysis` | `100 * sum(rate(process_cpu_seconds_total{app="data-analysis"}[1m]))` | 716/716 (dif. máx. 0.004477) | REPRODUCIDA |
| `cpu_pct_data-management` | `100 * sum(rate(process_cpu_seconds_total{app="data-management"}[1m]))` | 716/716 (dif. máx. 0.004929) | REPRODUCIDA |
| `cpu_pct_data-receiving` | `100 * sum(rate(process_cpu_seconds_total{app="data-receiving"}[1m]))` | 716/716 (dif. máx. 0.00499) | REPRODUCIDA |
| `cpu_pct_early-warning` | `100 * sum(rate(process_cpu_seconds_total{app="early-warning"}[1m]))` | 716/716 (dif. máx. 0.004711) | REPRODUCIDA |
| `cpu_pct_project-management` | `100 * sum(rate(process_cpu_seconds_total{app="project-management"}[1m]))` | 716/716 (dif. máx. 0.004461) | REPRODUCIDA |
| `cpu_pct_user-management` | `100 * sum(rate(process_cpu_seconds_total{app="user-management"}[1m]))` | 716/716 (dif. máx. 0.004465) | REPRODUCIDA |

## Consultas que también reproducen la columna

Los datos de la ventana no permiten distinguirlas de la elegida (por ejemplo, series que valen 0).

- `node_mem_used_mib`
  - `(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1048576`
- `mem_mib_project-management`
  - `max(process_resident_memory_bytes{app="project-management"}) / 1048576`
  - `avg(process_resident_memory_bytes{app="project-management"}) / 1048576`
- `mem_mib_user-management`
  - `max(process_resident_memory_bytes{app="user-management"}) / 1048576`
  - `avg(process_resident_memory_bytes{app="user-management"}) / 1048576`
