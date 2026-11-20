# Bloque 4 — Evaluaciones, buffer y circuit breaker

## 4.1 `ew_evaluations_total` por `outcome`

Fuente: muestras crudas de la auditoría 2 (`fuente/auditoria_ew_b_2026-11-20/ew_evaluations_samples.csv`, `source=raw`, exportadas de la TSDB restaurada con `ew_evaluations_total[44101s]` @ 2026-09-24T00:40:00Z). La etiqueta se llama `outcome`, no `result`. Cálculo: `derivar.py` → `outputs/b4_ew_evaluations_por_outcome.csv`. 0 reinicios en las 12 series.

| outcome | ventana del 20/11 | ventana común |
|---|---|---|
| `stale_reading_baseline_kept` | 3 592 828 | 3 593 634 |
| `fix_quality_not_rtk_fixed` | 432 125 | 432 238 |
| `none` | 299 255 | 299 311 |
| `alert` | 3 416 | 3 416 |
| `previous_none` | 96 | 100 |
| `gap_too_large_reset` | 81 | 81 |
| **total** | **4 327 801** | **4 328 780** |

- *Ventana del 20/11*: muestras con hora en (12:31:20, 00:34:21], diferencias entre la primera y la última. Es el cálculo «manual (window)» de `fuente/auditoria_ew_b_2026-11-20/report.md`, paso 3.
- *Ventana común*: regla de `docs/auditoria-resistencia-12h.md`, desde la última muestra ≤ @t0 (12:31:18.935 / 12:31:07.616) hasta la última ≤ @t1 = 00:39:21 (00:39:18.935 / 00:39:07.616).
- Las **177 «otras»** son `gap_too_large_reset` 81 + `previous_none` 96 en la ventana del 20/11 (181 en la ventana común).
- **Diferencia de 979** (4 328 780 − 4 327 801): la ventana del 20/11 empieza en la primera muestra *posterior* a 12:31:20 y termina a las 00:34:21, sin los 300 s de vaciado. Pierde las evaluaciones entre la muestra anterior a @t0 y la primera posterior (hasta 15 s por réplica) y las que ocurren entre 00:34:21 y el final del vaciado. Con la ventana común el total es 4 328 780, igual a los ACK de Artillery y a las filas de `gnss_readings`. También coincide con early-warning: consumidos 4 334 129 − duplicados omitidos 5 349 = 4 328 780 (`docs/auditoria-resistencia-12h.md` §3).

## 4.2 Buffer en la caída del broker

Código: `tifacusil/go-data-receiving@13ac6fe`.

| cifra | valor | métrica o log | definición | código |
|---|---|---|---|---|
| retenidas | **3 740** | líneas `rabbitmq publish failed; buffered in redis for retry` | tramas ya escritas en Redis cuya publicación falló; 3 740 `message_id` distintos, 14:32:24.446–14:33:01.805 (69b4v 1 486, 7rpf9 1 133, 8fgq2 1 121) | `internal/sink/rabbitmq.go:53-56` |
| máximo en la tabla | **3 752** | `data_receiving_redis_buffer_pending` (gauge), máximo por réplica 14:30–15:00 | número de claves del buffer en Redis contadas con `SCAN` al inicio de cada pase de reintento | `internal/buffer/retry_worker.go:61-64`, `internal/buffer/redis.go:111-126` |
| republicaciones | **9 077** | líneas `retry succeeded` | republicaciones confirmadas; 3 740 ids, 2 143 dos veces y 1 597 tres veces, 14:34:45.634–14:36:25.198 | `internal/buffer/retry_worker.go:78-92` |

Fuentes: `results/auditoria_resistencia/logs_b.json` (`publish_failed`, `retry_succeeded`, `reconciliacion`), `results/auditoria_resistencia/prometheus/B__buffer.json` → `outputs/b4_buffer_max_por_replica.csv` (10.42.0.90: 3 752 a las 14:33:50.624; 10.42.0.91: 3 743 a las 14:33:56.258; 10.42.0.92: 3 750 a las 14:33:45.971).

**¿Se persistieron las 3 740?** Sí: los 3 740 `message_id` de `publish failed` (tomados de los logs del repositorio) están en la exportación de `gnss_readings` de la ventana (`contar_message_id.py` → `outputs/b4_ids_de_logs_en_gnss_readings.csv`).

**Por qué 3 740 ≠ 3 752.** Las tres réplicas usan la misma instancia Redis, y `Count` cuenta todas las claves del prefijo, no solo las de su réplica: el gauge de cada réplica es el total compartido. Además, cada trama se escribe en Redis *antes* de publicarse y se borra después de la confirmación (`rabbitmq.go:47`, `:59`). El total incluye, por tanto, las tramas en vuelo de las tres réplicas, que en régimen oscilan entre 0 y 8 (`docs/auditoria-resistencia-12h.md` §3). Las 12 claves de más (3 752 − 3 740) nunca se republicaron: todos los ids con `retry succeeded` tienen antes un `publish failed` (`reconciliacion.retry_succeeded_sin_publish_failed = 0`). Se borraron por la vía normal tras la confirmación, es decir, eran tramas en vuelo. El log del pase de 69b4v de las 14:33:39.350 también registra `buffered` = 3 752 (`logs_b.json` → `retry_pass.max_buffered`).

**Por qué 9 077 > 3 740.** Cada réplica tiene su propio `RetryWorker` (cada 30 s, edad mínima 2 min; `internal/config/config.go:34-35`). Cada pase lee con `SCAN` todas las claves antiguas del Redis compartido (`ScanOld`), las republica y después las borra (`retry_worker.go:71-90`). No hay bloqueo ni reparto entre réplicas, así que dos o tres réplicas republican el mismo mensaje antes de que alguna lo borre. Las tres lo hicieron: `retry succeeded` por pod 69b4v 3 723, 7rpf9 1 614, 8fgq2 3 740. Las 9 077 − 3 740 = 5 337 republicaciones de más llegan con el mismo `message_id`; en toda la corrida, `INSERT IGNORE` dejó 5 342 sentencias sin fila nueva y early-warning omitió 5 349 duplicados (`docs/auditoria-resistencia-12h.md` §3).

## 4.3 Circuit breaker (retardo de 9 000 ms hacia user-management, 3 repeticiones, 30/09/2026)

Fuentes: `data/B - SEPTIEMBRE 5 RUNS V2/chaos/netem-delay-ew-um-{summary,samples,run}-*`. Script: `go-tesis-infra/chaos/netem-delay-ew-um.sh` y `chaos/lib/{sampler,capture}.sh` (clon local en `654d9a6`; no se comprobó que sea idéntico a la versión usada el 30/09). Cálculo: `outputs/b4_circuit_breaker_por_corrida.csv`.

| | corrida 1 | corrida 2 | corrida 3 |
|---|---|---|---|
| inicio del retardo (`fail_start`) | 03:33:12 | 03:41:32 | 03:49:53 |
| `breaker_opened_after_s` («Apertura») | 116 | 131 | 123 |
| primera / última muestra con breaker abierto | 03:35:07 / 03:37:36 | 03:43:43 / 03:45:39 | 03:52:04 / 03:54:16 |
| `calls_circuit_open`: primera muestra no vacía → última | 57 → 190 | 190 → 364 | 364 → 547 |
| Δ rechazadas («Llamadas rechazadas») | 133 | 174 | 183 |
| Δ `alerts_published` en el muestreo («Alertas publicadas») | 229 | 205 | 211 |
| `alerts_while_open` («Alertas sin push») | 117 | 94 | 104 |
| `degraded_alerts` (alertas con `push_path="resolve_failed"`) | 191 | 171 | 181 |
| `recovery_s` | 0 | 0 | 0 |

Definiciones (del script):

- **Apertura**: segundos desde `fail_start` (`date +%s` justo antes de `tc qdisc add`, `netem-delay-ew-um.sh:471`) hasta la primera consulta de `max(ew_circuit_breaker_state{target="user-management"})` = 1 en el bucle de sondeo (`:501-509`). El sondeo se repite cada 7–8 s (log `run`), así que la resolución es de unos 8 s. `max()` toma la primera réplica que abre; no es la apertura de cada réplica.
- **Llamadas rechazadas**: `sum(ew_outbound_calls_total{target="user-management",outcome="circuit_open"})` (`lib/sampler.sh:32`), última muestra menos primera muestra numérica del CSV. El contador es acumulado desde el arranque de los pods. En la corrida 1 la serie no existía al empezar (NaN hasta 03:35:07, primera muestra 57), así que 133 omite los 57 rechazos anteriores a esa muestra; contando desde 0 son 190. **133 no es comparable con 174 y 183**, que sí parten de un valor previo.
- **Alertas publicadas**: Δ `sum(ew_alerts_published_total)` (`lib/sampler.sh:34`) entre la primera y la última muestra del CSV (≈264 s, desde `fail_start` hasta el fin del muestreo).
- **Alertas sin push**: `alerts_while_open` = Δ `sum(ew_alerts_published_total)` entre la apertura y la última muestra con breaker abierto (`netem-delay-ew-um.sh:572-577`). Son alertas **registradas con el breaker abierto**; el script las llama «alertas registradas con el breaker abierto» (`run` log: «Continuidad operativa»). Por código, con el breaker abierto `TokensFor` falla y no hay push (`go-early-warning` `consumer.go:387-395`). Las alertas sin push de todo el fallo, incluidas las del tramo con el breaker cerrado y user-management lento, son `degraded_alerts` = 191 / 171 / 181 (`netem-delay-ew-um.sh:563`).
- **Cierre (17–29 s)**: **sin fuente en el repositorio.** `recovery_s` vale 0 en las tres corridas y no mide el cierre: `wait_for_breaker_closed` (`lib/capture.sh:139-150`) consulta `ew_circuit_breaker_state{target=...}` sin `max()` y `prom_query` devuelve solo `result[0]` (`capture.sh:121`). Con dos réplicas, basta con que la primera serie devuelta valga 0. En el CSV, solo la corrida 2 muestra el breaker cerrado de nuevo (03:45:55); las corridas 1 y 3 terminan el muestreo con el breaker abierto.

**Cronología por réplica** (invocaciones agotadas, primera apertura de cada réplica, sondas semiabiertas, apertura sostenida, cierre): **no disponible**. El CSV guarda `max()` sobre las réplicas y el log `run` no tiene eventos por réplica. Requiere los logs de early-warning del 30/09 o `ew_circuit_breaker_state` y `ew_outbound_calls_total` por `instance` en la TSDB del 14/10 (pendiente).
