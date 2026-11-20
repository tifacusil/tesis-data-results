# Consultas PromQL

Todas sobre la TSDB restaurada `B-prometheus-tsdb-20261014.tar.gz` (SHA-256 `7425191c484406224e51d576e87df158cd4dca7b6dd535229b683012bc561877`), Prometheus en Docker en `:9091`. Ninguna sobre el Prometheus de producción. Los incrementos no usan `increase()`: se calculan sobre las muestras crudas con `derivar.py` (regla de `docs/auditoria-resistencia-12h.md`), para obtener enteros sin extrapolación.

## Ejecutadas

| consulta | API, `time` | ejecutada | archivo crudo | usada en |
|---|---|---|---|---|
| `mysql_global_status_innodb_row_ops_total{instance="mysqld-exporter-data-management:9104",operation="inserted"}[43982s]` | `/api/v1/query`, 2026-09-24T00:39:22Z | exportación de `docs/auditoria-resistencia-12h.md` (17/11/2026) | `results/auditoria_resistencia/prometheus/B__mysql_rows_inserted.json` | bloque 1 |
| `ew_alerts_published_total[43982s]` | ídem | ídem | `…/B__ew_alerts.json` | bloque 3 |
| `ew_alert_delivery_latency_seconds_count[43982s]` | ídem | ídem | `…/B__ew_alert_delivery_count.json` | bloque 3 |
| `data_receiving_redis_buffer_pending[43982s]` | ídem | ídem | `…/B__buffer.json` | bloque 4.2 |
| `ew_evaluations_total[44101s]` | `/api/v1/query`, 2026-09-24T00:40:00Z | 2026-11-20 03:39:24 UTC (auditoría 2) | `fuente/auditoria_ew_b_2026-11-20/ew_evaluations_samples.csv` (`source=raw`), `raw/ew_api_log.json` | bloques 3 y 4.1 |
| `query_range` `ew_evaluations_total`, 12:25:00–00:40:00, paso 15 s | `/api/v1/query_range` | ídem | ídem (`source=query_range_15s`) | comprobación |
| `sum by (outcome) (increase(ew_evaluations_total[43381s]))`, `sum by (outcome, instance) (...)` | `/api/v1/query`, 2026-09-24T00:34:21Z | ídem | `fuente/auditoria_ew_b_2026-11-20/report.md`, paso 1 | referencia (extrapola) |

SHA-256 de las exportaciones del 17/11: `results/auditoria_resistencia/prometheus/manifiesto.json`.

Equivalencias con el pedido:

- `increase(mysql_global_status_innodb_row_ops_total{operation="inserted",…}[12h])` @ @t1 → incremento sin extrapolación sobre `B__mysql_rows_inserted.json`, con los valores crudos en @t0 y @t1 en `outputs/b1_innodb_rows_inserted.csv`.
- `increase(ew_alerts_published_total[12h])`, `increase(ew_alert_delivery_latency_seconds_count[12h])`, `increase(ew_evaluations_total{result="alert"}[12h])`, total y por pod → `outputs/b3_ew_alertas_por_serie.csv` y `outputs/b4_ew_evaluations_por_outcome.csv`. No existe etiqueta `pod` ni `result`: las réplicas se separan por `instance` y la etiqueta es `outcome`.

## Pendientes (no ejecutadas)

```promql
# 30/09/2026 03:32–03:56 UTC, por réplica, para la cronología y el cierre del breaker
ew_circuit_breaker_state{target="user-management"}
ew_outbound_calls_total{target="user-management"}
```
