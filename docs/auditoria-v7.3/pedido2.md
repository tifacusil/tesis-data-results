# Pedido 2 — cifras pendientes de C01, C03 y bloque 4

Ejecución del 2026-11-20 (UTC). Todo el material está en `v73_b_2026-11-20/` (primera tanda: tramos de `gnss_readings` y duplicados de `alerts`) y `v73_b_2026-11-20/pedido2/` (esta tanda), cada carpeta con su `SHA256SUMS`. `received_at` y `created_at` están en UTC (`README.md`, zonas horarias).

## Ejecución

| fuente | usuario o acceso | cuándo (UTC) | salida cruda |
|---|---|---|---|
| `mysql-data-management-0` (vivo), MySQL 8.0.46 | `root@localhost`, `SET SESSION transaction_read_only = ON`, vía `kubectl exec` como `gotesis` | 15:37:13–15:37:16 (EXPLAIN), 15:37:27–15:38:02 (consultas) | `pedido2/raw/sql/p2_explain.*`, `p2_dm.*` |
| `restartCount` de `mysql-data-management-0` | `kubectl get pod … -o jsonpath='{.status.containerStatuses[0].restartCount}'` | antes y después de cada script | 1 → 1 y 1 → 1 (`pedido2/p2_ejecucion.csv`); el 1 es el OOM del paso 2 de la auditoría 1 (03:07:42) |
| TSDB `B-prometheus-tsdb-20261014.tar.gz` restaurada (Prometheus 3.5.4, Docker local, `:9091`) | API HTTP, solo GET | 15:39:41.52–15:39:41.79 | `pedido2/raw/promql/api_log.json` (35 consultas con su respuesta literal) |
| Logs de early-warning del 29/09 22:08 al 30/09 03:54 | `respaldo-logs-20261103/B-go-tesis-logs-20261103.tar.gz`, miembros `var/log/pods/landslide_early-warning-55859f5589-{cgprm,chqw5}_*/early-warning/0.log` | extraídos 2026-11-20 | `pedido2/raw/logs_ew/` |
| `~/breaker_recuperacion.json`, `~/breaker_inyeccion.json`, `~/alertas_12h.json` del servidor de B | `gotesis`, copia por `tar` | copiados 2026-11-20; generados el 29–30/09 | `pedido2/raw/servidor/` (SHA-256 iguales a los del servidor) |

Memoria del pod: el guardia lee `anon` y `memory.current` del cgroup cada 2 s y lanza `KILL QUERY` si `anon` ≥ 230 MiB. En esta tanda: `anon` 168–169 MiB y `memory.current` 314–318 MiB de 320 MiB. `memory.current` incluye la caché de archivos del recorrido completo (la tabla se lee con E/S con búfer, `innodb_flush_method = fsync`), que el kernel recupera antes de un OOM; el riesgo real es `anon`. El valor de 319 MiB del pedido corresponde a `memory.current`; `kubectl top` (conjunto de trabajo) marcó 295 MiB en la primera tanda.

## 1. C01 — 105 «sink write failed» y déficit de 315

**1.1** `pedido2/sink_write_failed_105.csv` (`archivo_log, linea, pod, timestamp_utc, message_id, error`), leído directamente de los logs de la instancia de data-receiving que se detuvo a las 14:33:02:

| archivo | líneas |
|---|---|
| `data/data-receiving-logs-2026-09-23/data-receiving-69b4v-previous.log` | 42 |
| `data/data-receiving-logs-2026-09-23/data-receiving-7rpf9-previous.log` | 32 |
| `data/data-receiving-logs-2026-09-23/data-receiving-8fgq2-previous.log` | 31 |
| total | 105 líneas, 105 `message_id` distintos, 14:33:01.640–14:33:02.935 |

Los mismos 105 ids que `outputs/b2_sink_write_failed_105.csv` y que el `IN (...)` de 1.2. Los logs de la instancia que arrancó a las 14:33:04 no tienen esa línea (`results/auditoria_resistencia/logs_b.json`).

**1.2** Consulta pedida, texto exacto en `pedido2/raw/sql/p2_dm.sql`. `EXPLAIN` (`pedido2/p2_explain.csv`): `type = range`, `key = uk_gnss_message`, `partitions = p2024,p2025,p2026,p2027,pmax`, `rows = 105`, `Using index condition; Using MRR`. El índice sí se usa: `message_id` es el prefijo izquierdo de `(message_id, timestamp)` y cada partición tiene su índice local, así que no hace falta consultar por partición. Resultado a las 15:37:28: **`Empty set (0.01 sec)`**, 0 filas (`pedido2/p2_ids_105_en_gnss_readings.csv`, solo cabecera).

**1.3** Consulta pedida (por minuto, 14:30–14:40), 17,37 s, `pedido2/p2_filas_por_minuto_1430_1440.csv`:

| minuto | 14:30–14:32 | 14:33 | 14:34 | 14:35 | 14:36 | 14:37–14:39 |
|---|---|---|---|---|---|---|
| filas | 6 000 c/u | 5 685 | 5 875 | 5 993 | 6 132 | 6 000 c/u |

`COUNT(*)` con `received_at >= '2026-09-23 14:33:00' AND received_at < '2026-09-23 14:37:00'`: **23 685**; nominal 24 000; **déficit 315 = los 315 fallos de Artillery** (`pedido2/p2_deficit_1433_1436.csv`).

Por qué el tramo de 1 h (14:31:20–15:31:20) da −320 y no −315, desde la exportación de la ventana (`pedido2/tramo_1431_1531_por_minuto.csv`, `tramo_1431_1531.py`):

- 14:33–14:36 aportan −315.
- Fuera de la caída hay desvíos de ±1–2 filas por minuto: 14:42 −2, 14:45 −1, 15:10 −1, 15:11 +1, 15:13 −1, 15:14 −1. Suman −5. Los minutos de borde (14:31:20–14:31:59 y 15:31:00–15:31:19) no tienen desvío.
- Artillery, en los periodos de ese mismo tramo (reloj del cliente): 360 000 emitidas, **359 685 ACK**, 315 fallidas. Las filas (359 680) difieren de los ACK en 5: tramas confirmadas en ese tramo según el reloj del cliente con `received_at` (reloj del servidor) fuera de él, o al revés. No son pérdidas: en la ventana completa filas = ACK = 4 328 780. Las horas vecinas pierden −2 y −3 por la misma razón.

**1.4** Reintentos: 0 de los 105 en `retry succeeded`, `rabbitmq publish failed`, `retry publish failed`, `retry delete failed` en los 6 logs de data-receiving (`logs_b.json` → `reconciliacion`; ver `bloque2.md` §2.3). Buffer Redis: **NO DISPONIBLE**: no hay volcado de Redis del 23/09 y el contenido actual no sirve (`FLUSHDB` antes de cada corrida).

**1.5** `go-data-receiving@13ac6fe` (igual a `version` en los logs): `internal/sink/rabbitmq.go:47-51` (falla `buffer.Set`: devuelve error sin publicar y sin nada en Redis) y `internal/tcp/server.go:162-170` (registra `sink write failed`, `return` sin `writeAck`; la conexión se cierra en el `defer` de `server.go:135-136`). Detalle en `bloque2.md` §2.4.

## 2. C03 — `ew_alerts_published_total` = 3414

**2.1** PromQL en `time = 2026-09-24T00:39:21Z`, rango `[43681s]` (= 12:31:20–00:39:21). `pedido2/p2_promql_resultados.csv`.

| consulta | total | 10.42.0.118 | 10.42.0.119 |
|---|---|---|---|
| `increase(ew_alerts_published_total[43681s])` | 3415,25 | 1661,56 | 1753,68 |
| `increase(ew_alert_delivery_latency_seconds_count[43681s])` | 3417,25 | 1662,61 | 1754,64 |
| `increase(ew_evaluations_total{result="alert"}[43681s])` | sin series: la etiqueta es `outcome` | — | — |
| `increase(ew_evaluations_total{outcome="alert"}[43681s])` | 3417,25 | 1662,61 | 1754,64 |
| `resets(...)` de las tres métricas | 0 | 0 | 0 |

`increase()` extrapola a los extremos y no da enteros. Valores crudos (consulta instantánea en @t0 y @t1):

| métrica | 118 en @t0 → @t1 | 119 en @t0 → @t1 | incremento entero |
|---|---|---|---|
| `ew_alerts_published_total` | blue 22 → 498, red 170 → 1 023, **orange sin serie** → 333 | blue 27 → 535, red 168 → 1 092, **orange sin serie** → 322 | 3 414 sin contar el valor inicial de `orange`; **3 416** contándolo |
| `ew_alert_delivery_latency_seconds_count` | 192 → 1 854 | 195 → 1 949 | 3 416 |
| `ew_evaluations_total{outcome="alert"}` | 192 → 1 854 | 195 → 1 949 | 3 416 |

Pod de cada instancia (`kube_pod_info` @ 2026-09-23T18:00Z): 10.42.0.118 = `early-warning-697ddb9db5-zjxkk`, 10.42.0.119 = `early-warning-697ddb9db5-zvxgk`.

**2.2** Código (`go-early-warning@fd5a866`; el commit de la imagen del 23/09 no está registrado): `ew_evaluations_total` se incrementa en `internal/earlywarning/consumer/consumer.go:335`; el histograma de entrega en `:405` (solo si el push se entrega); `INSERT IGNORE INTO alerts` en `internal/earlywarning/store/store.go:67-76`, llamado desde `consumer.go:419`; `ew_alerts_published_total{level}` en `consumer.go:424`, después del `INSERT`. **Conciliada**: las series `level="orange"` no existen en @t0, aparecen con valor 1 (12:55:03.935 en 118, 12:54:52.616 en 119) y el incremento desde la primera muestra no cuenta ese 1. 3 414 + 2 = 3 416 = filas en `alerts` = envíos push = evaluaciones `alert`. Detalle en `bloque3.md`.

**2.3** Réplica que generó cada duplicada: **NO DISPONIBLE**. Las réplicas del 23/09 (`697ddb9db5-zjxkk` y `-zvxgk`) se reemplazaron el 2026-09-29 a las 22:08:49 y 22:09:07 por `55859f5589-chqw5` y `-cgprm` (`kubectl get pods`, `startTime`). Sus logs no se conservan: el tar del 03/11 solo trae los de los pods de `55859f5589`, desde el 29/09.

| id | sensor | `created_at` | `message_id` | ¿publicada? | ¿push aceptado? |
|---|---|---|---|---|---|
| 535 | GXZM-DB050 | 14:33:27 | `777a378d-ef96-426f-9746-b861173e9fab` | sí | sí (inferido) |
| 536 | GXZM-DB050 | 14:33:27 | `d34afd7d-fedc-4774-8284-d529f2233d8e` | sí | sí (inferido) |
| 1840 | GXZM-DB086 | 19:10:21 | `4e7ef7ef-054d-4777-a381-f4d8d491dfd4` | sí | sí (inferido) |
| 1841 | GXZM-DB086 | 19:10:22 | `f8b1e81c-56cd-435f-8d8f-a89b37f6b672` | sí | sí (inferido) |

- *Publicada*: la fila existe, así que `recordAlert` terminó sin error y `consumer.go:424` incrementó `ew_alerts_published_total`.
- *Push aceptado*: inferido por recuento, no por id. Cada alerta observa el histograma de entrega como máximo una vez y solo si el multicast se acepta (`consumer.go:402-406`). En la ventana hubo 3 416 observaciones para 3 416 alertas, así que se aceptaron todas.
- Indicio por réplica (no concluyente): `level="red"` sube en 118 entre 14:33:18 y 14:33:33 y en 119 entre 14:33:22 y 14:33:37; `level="blue"` sube en ambas alrededor de 19:10:21–22 (`bloque3.md`).

## 3. Bloque 4

**3.1 Evaluaciones.** La etiqueta es `outcome` (no `result`); 6 valores en las 2 réplicas, sin reinicios. `outputs/b4_ew_evaluations_por_outcome.csv` (enteros) y `pedido2/p2_promql_resultados.csv` (`increase()` por `outcome`).

| outcome | ventana del 20/11 (12:31:20–00:34:21) | ventana común (12:31:20–00:39:21) | `increase()` |
|---|---|---|---|
| `stale_reading_baseline_kept` | 3 592 828 | 3 593 634 | 3 594 932,8 |
| `fix_quality_not_rtk_fixed` | 432 125 | 432 238 | 432 391,4 |
| `none` | 299 255 | 299 311 | 299 420,7 |
| `alert` | 3 416 | 3 416 | 3 417,3 |
| `previous_none` | 96 | 100 | 96,0 |
| `gap_too_large_reset` | 81 | 81 | 81,0 |
| total | **4 327 801** | **4 328 780** | 4 330 339,2 |

Las **177 «otras»** = `gap_too_large_reset` 81 + `previous_none` 96. La **diferencia de 979** es de alineación: la cifra de 4 327 801 empieza en la primera muestra *posterior* a 12:31:20 (12:31:33.935 en 118, 12:31:22.616 en 119) y termina en la última anterior a 00:34:21, sin los 300 s de vaciado. Con la muestra anterior o igual a 12:31:20 (12:31:18.935 / 12:31:07.616) y la última anterior o igual a 00:39:21 (00:39:18.935 / 00:39:07.616), el total es 4 328 780 = filas = ACK (`bloque4.md` §4.1).

**3.2 Buffer.** Sin cambios respecto a `bloque4.md` §4.2: 3 740 = líneas `rabbitmq publish failed; buffered in redis for retry` (`rabbitmq.go:53-56`); 3 752 = máximo de `data_receiving_redis_buffer_pending` (`retry_worker.go:61-64`, `redis.go:111-126`, `SCAN` del Redis compartido); 9 077 = líneas `retry succeeded` (`retry_worker.go:78-92`). 3 752 − 3 740 = 12 tramas en vuelo; 9 077 > 3 740 porque tres `RetryWorker` sin coordinación republican las mismas claves.

**3.3 Circuit breaker (retardo de 9 000 ms hacia user-management).** Reglas del código (`go-early-warning@fd5a866`, la versión de los pods del 30/09 según sus logs): `cmd/early-warning/main.go:127-131` (timeout 5 000 ms, `MaxRetries` 2, umbral 5, `OpenFor` 30 000 ms) y `pkg/grpcx/grpcx.go:96-146`. Una invocación son hasta 3 intentos de 5 s con esperas de 1 s y 5 s (≈ 21 s); el breaker cuenta un fallo por invocación, abre con 5 fallos seguidos, pasa a semiabierto 30 s después y una sonda fallida lo reabre. `grpcx` no registra los cambios de estado. La cronología sale de los logs (`push_flow_failed` con `DeadlineExceeded` = invocación agotada; `grpcx: circuit open` = rechazo; `push_delivered` = invocación correcta) y se contrasta con la TSDB por `instance`.

Archivos: `pedido2/cronologia_breaker_eventos.csv` (cada evento por réplica), `cronologia_breaker_resumen.csv`, `breaker_tsdb_por_instancia.csv`, `alertas_breaker_por_push_path.csv`.

Invocaciones agotadas, en segundos desde la inyección (iguales en las dos réplicas ± 0,1 s):

| corrida | fallos 1–5 (el 5.º abre) | sondas semiabiertas fallidas | primer OK tras el retiro (cierre) |
|---|---|---|---|
| 1 (inyección 03:33:12, retiro 03:37:16) | 30,2 / 51,2 / 72,2 / 93,3 / **114,3** | 168,9 / 220,3 | 03:37:29,0 (**13,0 s** tras el retiro) |
| 2 (03:41:32, retiro 03:45:35) | 29,6 / 50,6 / 71,7 / 92,7 / **113,8** | 168,4 / 219,8 | 03:45:48,6 (**13,6 s**) |
| 3 (03:49:53, retiro 03:53:56) | 29,3 / 50,3 / 71,3 / 92,3 / **113,3** | 168,1 / 219,4 | 03:54:09,1 (**13,1 s**) |

- Primera apertura de cada réplica: en el 5.º fallo, 113,3–114,3 s tras la inyección; las dos réplicas a la vez (cgprm = 10.42.0.123, chqw5 = 10.42.0.122). Apertura sostenida: cada sonda se lanza a los ≈ 30 s de reabrir, falla ≈ 21 s después y vuelve a abrir. La primera sonda tras el retiro (≈ 250 s) sale bien y cierra.
- **«14 invocaciones agotadas»**: cada corrida tiene 7 por réplica, 14 en total = 10 de apertura (5 por réplica) + 4 sondas semiabiertas (2 por réplica). La apertura ocurre **después de las 10 primeras y antes de las 4 sondas**, no después de las 14. El log `run` ve `breaker=1` a los 116 s con `timeouts=9` porque las métricas llegan con el retraso del scrape (15 s).

Definiciones y valores:

| cifra | definición (script `go-tesis-infra/chaos/netem-delay-ew-um.sh`) | valor en el artículo | reconstruido |
|---|---|---|---|
| Apertura | `fail_start` (antes de `tc qdisc add`, `:471`) hasta la primera consulta de `max(ew_circuit_breaker_state)` = 1 (`:501-509`), cada 7–8 s; el gauge solo se actualiza al terminar cada llamada (`subs.go:107-109`) y Prometheus lo lee cada 15 s | 116 / 131 / 123 s | apertura real (logs): 114,3 / 113,8 / 113,4 s; en la TSDB, primera muestra abierta: 03:35:06 (114 s), 03:43:36 (124 s), 03:51:51 (118 s) |
| Cierre | sin definición en el script: `recovery_s` = 0 (`wait_for_breaker_closed` toma `result[0]` sin `max()`, `lib/capture.sh:121,146`) | 17–29 s | logs: 13,0 / 13,6 / 13,1 s (ambas réplicas). TSDB (scrape 15 s): 20 y 23 s, 16 y 19 s, 13 y 25 s. `breaker_recuperacion.json` (servidor, `query_range` con paso 1 s): 21 y 24 s, 17 y 20 s, 26 y 14 s. Ninguna fuente da 17–29 |
| Llamadas rechazadas | Δ `sum(ew_outbound_calls_total{target="user-management",outcome="circuit_open"})` entre la primera y la última muestra numérica del CSV (`lib/sampler.sh:32`) | 133 / 174 / 183 | por réplica (TSDB): 92 + 98 = **190**, 88 + 86 = 174, 97 + 86 = 183; logs: los mismos recuentos. En la corrida 1 las series nacen durante la prueba (primer valor 40 y 17) y 133 omite esos 57 |
| Alertas publicadas | Δ `sum(ew_alerts_published_total)` entre la primera y la última muestra del CSV (`lib/sampler.sh:34`), ≈ 264 s | 229 / 205 / 211 | logs, `alert_emitted` en la misma ventana: 222 / 206 / 215 (las muestras del CSV llevan hasta 15 s de retraso de scrape en cada extremo) |
| Alertas sin push | `alerts_while_open`: Δ `sum(ew_alerts_published_total)` entre la primera y la última muestra con el breaker abierto (`:572-577`) | 117 / 94 / 104 | son alertas **registradas con el breaker abierto**. Alertas sin push (`push_path = resolve_failed`) en los logs: 204 / 188 / 197 en la ventana de muestreo (= Δ `dispatch_degraded_count` del CSV), 199 / 183 / 192 entre la inyección y el retiro |

## Cifras del artículo

| cifra del artículo | archivo | valor obtenido | ¿coincide? |
|---|---|---|---|
| 105 «sink write failed» | `pedido2/sink_write_failed_105.csv` | 105 (42 + 32 + 31) | sí |
| 105 ids en `gnss_readings` | `pedido2/raw/sql/p2_dm.out.txt`, `p2_ids_105_en_gnss_readings.csv` | 0 filas | sí (esperado 0) |
| 23 685 filas 14:33–14:36 | `pedido2/p2_deficit_1433_1436.csv` | 23 685 | sí |
| 24 000 nominales | ídem | 24 000 | sí |
| déficit 315 | ídem | 315 | sí |
| −320 en el tramo de 1 h | `pedido2/tramo_1431_1531_por_minuto.csv` | −315 en la caída, −5 de borde entre relojes (ACK del tramo = 359 685) | explicado |
| 3414 publicadas | `pedido2/p2_promql_resultados.csv` | `increase()` 3 415,25; entero 3 414 sin las series nacidas, 3 416 con ellas | conciliada (3 416) |
| 3416 filas en `alerts` | `v73_b_2026-11-20/ew_count_ventana.csv` | 3 416 | sí |
| 3416 envíos push | `pedido2/p2_promql_resultados.csv` | entero 3 416 (`increase()` 3 417,25) | sí |
| réplica de 535/536 y 1840/1841 | — | NO DISPONIBLE: logs de los pods del 23/09 no conservados | — |
| 535/536 y 1840/1841 publicadas y con push | `v73_b_2026-11-20/ew_alertas_duplicadas.csv` | publicadas sí; push sí (inferido por recuento) | sí |
| 4 327 801 evaluadas | `outputs/b4_ew_evaluations_por_outcome.csv` | 4 327 801 (ventana del 20/11) | sí |
| 177 otras | ídem | 81 + 96 | sí |
| 979 | ídem | 4 328 780 − 4 327 801, alineación de muestras | sí, explicada |
| 3740 / 3752 / 9077 | `bloque4.md` §4.2 | 3 740 / 3 752 / 9 077 | sí |
| Apertura 116 / 131 / 123 s | `pedido2/cronologia_breaker_resumen.csv` | sondeo: 116 / 131 / 123; real: 114,3 / 113,8 / 113,4 | el valor sí; **no** es el instante real de apertura |
| Cierre 17–29 s | `pedido2/cronologia_breaker_resumen.csv`, `breaker_tsdb_por_instancia.csv`, `raw/servidor/breaker_recuperacion.json` | 13–14 s (logs); 13–25 s (TSDB); 14–26 s (`query_range` 1 s) | **no** |
| Llamadas rechazadas 133 / 174 / 183 | `pedido2/breaker_tsdb_por_instancia.csv` | 190 / 174 / 183 | **no** en la corrida 1 |
| Alertas publicadas 229 / 205 / 211 | `outputs/b4_circuit_breaker_por_corrida.csv` | 229 / 205 / 211 (logs: 222 / 206 / 215) | sí con esa métrica |
| Alertas sin push 117 / 94 / 104 | ídem, `pedido2/alertas_breaker_por_push_path.csv` | 117 / 94 / 104 son alertas con el breaker abierto; sin push: 204 / 188 / 197 | valor sí; **definición no** |
| 14 invocaciones agotadas (10 + 4) | `pedido2/cronologia_breaker_eventos.csv` | 14 por corrida = 10 + 4 | sí; la apertura va tras las 10, antes de las 4 |
