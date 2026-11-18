# Auditoría de la corrida de resistencia de 12 h (O06)

Informe de verificación. No contiene texto para el artículo. Todas las marcas temporales están en **UTC** salvo que se indique otra cosa. Los periodos de Artillery usan el reloj del PC cliente; Prometheus, los logs de los pods y el journal usan el reloj de cada servidor. No se midió el desfase entre ambos relojes.

## Fuentes y reproducción

| fuente | ubicación | integridad |
|---|---|---|
| Informes Artillery de la resistencia | `data/A - SPETIEMBRE 5 RUNS/sustained-12h.json`, `data/B - SEPTIEMBRE 5 RUNS V2/sustained-12h.json` | SHA-256 `dccf8eb0…0bb8` (A), `57fc9df4…5f50` (B); ambos en `SHA256SUMS.artillery` |
| TSDB de Prometheus A y B del 14/10/2026 | `respaldo-prometheus/{A,B}-prometheus-tsdb-20261014.tar.gz` (fuera del repo), restaurados con `scripts/restore_backups.sh` (A en :9092, B en :9091) | `sha256sum -c` OK sobre `SHA256SUMS.txt` del respaldo |
| Exportación cruda de Prometheus | `results/auditoria_resistencia/prometheus/*.json` | `manifiesto.json` (consulta, ventana, paso y SHA-256 de cada archivo) |
| Logs de data-receiving de B, instancia que terminó a las 14:33:02 | `data/data-receiving-logs-2026-09-23/*-previous.log` | SHA-256 en `docs/metrics-methodology.md` y en `logs_b.json` |
| Logs de data-receiving de B, instancia que arrancó a las 14:33:04 | `respaldo-logs-20261103/B-go-tesis-logs-20261103.tar.gz` (fuera del repo), miembros `var/log/pods/landslide_data-receiving-d9f59874f-{69b4v,7rpf9}_*/data-receiving/1098.log` y `…-8fgq2_*/data-receiving/1097.log` | tar: SHA-256 `be6e4d3f…a5891`; cada log, en `results/auditoria_resistencia/logs_b.json` |
| Journal del nodo de B (15/09–01/10) | mismo tar, `journal-B-2026-09-15_2026-10-01.txt` | — |
| Código | `go-tesis-infra` `c6732b0` (motor de carga y caos), `dtu-emulator` HEAD `4056311` (`transport.py` y `stream_mode.py` sin cambios desde `9e32f0c`, 22/07/2026), `go-data-receiving` `13ac6fe` (= `version` de los logs), `go-data-management` `3d960a5`, `data-receiving-module-csharp` `ef9d647` | — |

```bash
# 1. Prometheus restaurados (Docker)
scripts/restore_backups.sh <dir_respaldo_prometheus> <dir_trabajo>
# 2. Exportación cruda (solo GET a la API)
py -I scripts/auditoria_resistencia/exportar_prometheus.py --prom-a http://localhost:9092 --prom-b http://localhost:9091 \
   --out results/auditoria_resistencia/prometheus
# 3. Logs de data-receiving de B (los 3 *-previous.log del repo + los 3 logs del tar, extraídos a una copia)
py -I scripts/auditoria_resistencia/analizar_logs_b.py --out results/auditoria_resistencia/logs_b.json \
   data/data-receiving-logs-2026-09-23/*-previous.log <logs_extraidos>/landslide_data-receiving-*/data-receiving/{1098,1097}.log
# 4. Cálculo, CSV y PNG (necesita requirements.txt)
venv/Scripts/python.exe scripts/auditoria_resistencia/auditar.py
docker rm -f prom-a prom-b
# 5. Comprobar que las cifras de este informe coinciden con hallazgos.json y logs_b.json
py -I scripts/auditoria_resistencia/verificar_informe.py    # "145 cifras comprobadas, 0 no encontradas"
```

`auditar.py` escribe `results/auditoria_resistencia/hallazgos.json`, de donde sale cada cifra de este informe, y los archivos de `results/resistencia_memoria/`.

**Cómo se calculan los incrementos de contadores.** Se suman las diferencias entre muestras consecutivas de cada serie (scrape de 15 s), desde la última muestra anterior o igual al inicio de la ventana hasta la última anterior o igual al fin. Si el valor baja, se toma como reinicio del contador y se suma el valor nuevo. Es la semántica de `increase()` sin extrapolación. Los incrementos ocurridos entre el último scrape y la parada de un proceso no están en la TSDB y no se cuentan.

**Ventanas de las corridas** (`aggregate.firstMetricAt` / `lastMetricAt`): A 2026-09-18 05:17:31 – 17:20:32; B 2026-09-23 12:31:20 – 2026-09-24 00:34:21. Para contar mensajes en el servidor se usa [inicio, fin + 300 s], para incluir el vaciado del pipeline.

**Definiciones usadas en las tablas** (etapas de O06):

- *Falta de ACK*: trama emitida por el generador (etapa 1) sin ACK de data-receiving (etapa 2). Se mide con Artillery: `vusers.created − dtu_tcp.frames_acked`.
- *Descarte*: mensaje que un servicio descarta de forma explícita y cuenta. Se mide con `data_receiving_messages_dropped_total`, `ew_messages_dropped_total`, `dm_messages_dlq_total` y la cola `sensors.dead_letter`.
- *Pérdida*: trama confirmada (etapa 2) que no llega a persistirse (etapa 3). Se mide comparando filas insertadas en MySQL de data-management con tramas confirmadas.

## 1. Denominador de la falta de ACK

| dato | valor | fuente | sistema | estado |
|---|---|---|---|---|
| Tramas emitidas | 4 329 095 | `sustained-12h.json`, `aggregate.counters["vusers.created"]` | A | OBTENIDO |
| Tramas confirmadas (ACK) | 4 329 095 | `aggregate.counters["dtu_tcp.frames_acked"]` | A | OBTENIDO |
| Tramas fallidas | 0 | `aggregate.counters["vusers.failed"]` | A | OBTENIDO |
| Tipo de error | ninguno (no hay claves `errors.*`) | `aggregate.counters` | A | OBTENIDO |
| emitidas = confirmadas + fallidas | sí (4 329 095 = 4 329 095 + 0) | cálculo | A | OBTENIDO |
| No confirmadas / emitidas | 0 % | cálculo | A | OBTENIDO |
| p95 agregado | 202,4 ms | `aggregate.summaries["dtu_tcp.round_trip_ms"].p95` | A | OBTENIDO |
| Tramas emitidas | 4 329 095 | `aggregate.counters["vusers.created"]` | B | OBTENIDO |
| Tramas confirmadas (ACK) | 4 328 780 | `aggregate.counters["dtu_tcp.frames_acked"]` | B | OBTENIDO |
| Tramas fallidas | 315 | `aggregate.counters["vusers.failed"]` | B | OBTENIDO |
| Tipo de error (código) | `errors.emulator_error`: 315 | `aggregate.counters["errors.emulator_error"]` | B | OBTENIDO |
| Mensaje de error de cada fallo | NO DISPONIBLE. El motor emite solo el código `emulator_error` y descarta el texto (`msg.error` va al callback, no al informe). Haría falta registrar `msg.error` por trama en el motor o guardar el stderr de Artillery. | `go-tesis-infra@c6732b0:load-tests/artillery-engine-dtu-tcp/index.js:509-511`; `dtu-emulator/src/sender/modes/stream_mode.py:107` | B | NO DISPONIBLE |
| Fallos por periodo de 10 s | 210 en el periodo 14:33:00; 105 en el periodo 14:33:10 (reloj del cliente) | `intermediate[].counters["vusers.failed"]` | B | OBTENIDO |
| emitidas = confirmadas + fallidas | sí (4 329 095 = 4 328 780 + 315) | cálculo | B | OBTENIDO |
| No confirmadas / emitidas | 315 / 4 329 095 = 0,0073 % | cálculo | B | OBTENIDO |
| p95 agregado | 242,3 ms | `aggregate.summaries["dtu_tcp.round_trip_ms"].p95` | B | OBTENIDO |
| ¿El generador reintenta? | No. Cada worker se lanza con `--no-retry`; con esa opción `send_with_retry` relanza la excepción sin reconectar ni reenviar, y la trama se cuenta como fallida. | `index.js:265` (`'--no-retry'`); `dtu-emulator/src/sender/transport.py:65-83` (`if self.no_retry: raise`) | A y B | OBTENIDO |
| Timeout de ACK por trama | 5 s | `index.js:47` (`ACK_TIMEOUT_MS = 5000`), pasado como `--ack-timeout` en `index.js:264` | A y B | OBTENIDO |
| Timeout total por `send` en el motor | 120 000 ms (por defecto; `DTU_ENGINE_SEND_TIMEOUT_MS` no consta en la configuración) | `index.js:59-62` | A y B | OBTENIDO |

## 2. Estado final de las 315 tramas no confirmadas de B

| dato | valor | fuente | sistema | estado |
|---|---|---|---|---|
| Identificador por trama en el generador | Sí existe en la trama: `message_id` = `uuid4()` aleatorio, más `sensor_id` y `timestamp` derivados de `reading_index`. No se conserva: el informe de Artillery solo guarda contadores e histogramas por periodo. | `dtu-emulator/src/sender/field.py:233`; `index.js` (`assignReading`, `request.sensor_id`, `request.reading_index`) | B | OBTENIDO |
| Identificador en data-receiving | `message_id` leído de la cabecera de la trama. Se registra solo en las líneas de fallo (`rabbitmq publish failed`, `sink write failed`, `retry succeeded`); el éxito se registra en nivel DEBUG, que no estaba activo. | `go-data-receiving/internal/sink/rabbitmq.go:53-67`; logs | B | OBTENIDO |
| Identificador en data-management | `gnss_readings.message_id` (`INSERT IGNORE` por `message_id`) | `go-data-management/internal/persistence/repository.go:29` | B | OBTENIDO |
| Reconciliación de las 315 por identificador | NO DISPONIBLE. No hay `message_id` de las tramas fallidas en el lado del generador. Haría falta que el motor registrara `message_id` (o `sensor_id` + `reading_index`) y el error de cada trama fallida. | — | B | NO DISPONIBLE |
| Clasificación (no recibida / recibida sin persistir / persistida sin ACK) | NO DISPONIBLE por trama, por la fila anterior. | — | B | NO DISPONIBLE |
| Base de datos de data-management del 23/09 | NO DISPONIBLE en este repo ni en los respaldos locales (los respaldos son de Prometheus y de logs, no de MySQL). Si la tabla sigue en el servidor: `SELECT COUNT(*) FROM gnss_readings WHERE message_id IN (<105 ids de logs_b.json>)` y `SELECT COUNT(*) FROM gnss_readings WHERE received_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'` en `mysql-data-management-0`. | — | B | NO DISPONIBLE |
| Evidencia existente: tramas recibidas por data-receiving y no escritas en Redis | 105 líneas `sink write failed` con 105 `message_id` distintos, error `buffer envelope <id>: context canceled`, entre 14:33:01.640 y 14:33:02.935 (69b4v 42, 7rpf9 32, 8fgq2 31). Por código, en ese caso no se publica ni se envía ACK y se cierra la conexión. | `logs_b.json` → `sink_write_failed`; `rabbitmq.go:47-51`; `server.go:162-170` | B | OBTENIDO |
| ¿Esos 105 ids se republicaron después? | No: 0 de los 105 aparecen en `retry succeeded` ni en `rabbitmq publish failed` | `logs_b.json` → `reconciliacion.sink_write_failed_con_retry_succeeded = 0`, `sink_write_failed_con_publish_failed = 0` | B | OBTENIDO |
| ¿Los 105 están entre las 315? | NO DISPONIBLE (sin identificador en el generador) | — | B | NO DISPONIBLE |
| Evidencia existente: parada y arranque de data-receiving | `tcp server stopped` 14:33:02.641 (69b4v), 14:33:02.808 (7rpf9), 14:33:02.936 (8fgq2); `tcp server listening` 14:33:04.051, 14:33:04.147, 14:33:04.279 | `logs_b.json` → `ciclo_de_vida` | B | OBTENIDO |
| Evidencia existente: réplicas listas | Las tres réplicas con `Ready=0` en las muestras 14:33:00 y 14:33:15; `Ready=1` en 14:33:30 | `kube_pod_container_status_ready{namespace="landslide"}` (`B__ready.json`) | B | OBTENIDO |
| Evidencia existente: errores de lectura TCP en data-receiving a las 14:33 | 0 líneas `error reading frame` el 23/09 entre 14:30 y 14:39 | `logs_b.json` → `error_reading_frame_por_minuto` | B | OBTENIDO |

## 3. Durabilidad durante toda la resistencia

### B

| dato | valor | fuente | sistema | estado |
|---|---|---|---|---|
| Ventana de conteo | 2026-09-23 12:31:20 – 2026-09-24 00:39:21 | `hallazgos.json` → `durabilidad.B.ventana` | B | OBTENIDO |
| Tráfico previo a la corrida (excluido) | 4 024 tramas entre 12:28:26 y 12:30:35, antes del primer envío de Artillery; ninguna entre 12:30:35 y 12:31:26 | `data_receiving_frames_total` (`B__frames.json`) | B | OBTENIDO |
| Filas insertadas en MySQL de data-management | 4 328 780 | `mysql_global_status_innodb_row_ops_total{instance="mysqld-exporter-data-management:9104",operation="inserted"}`; sin reinicios del contador; incremento 0 en las 2 h previas (`increase(...[2h])` a las 12:00) | B | OBTENIDO |
| Tramas confirmadas por el generador | 4 328 780 | sección 1 | B | OBTENIDO |
| Diferencia filas − confirmadas | 0 (0 %) | cálculo | B | OBTENIDO |
| Recuento de filas por SQL (`gnss_readings`) | NO DISPONIBLE (ver sección 2). El contador InnoDB cuenta filas insertadas en todas las tablas de esa instancia MySQL; no distingue tablas. | — | B | NO DISPONIBLE |
| Sentencias INSERT ejecutadas | 4 334 122 (5 342 más que filas: `INSERT IGNORE` sobre `message_id` ya existente) | `mysql_global_status_commands_total{instance="mysqld-exporter-data-management:9104",command="insert"}` | B | OBTENIDO |
| Mensajes procesados por data-management | 4 333 397 (+4 617, +0,1067 % sobre confirmadas). Cuenta también los `INSERT IGNORE` sin fila nueva. Un reinicio del contador en 10.42.0.88 a las 18:33:45. | `dm_messages_processed_total`; `go-data-management/internal/consumer/processor.go:116-118` | B | OBTENIDO |
| Tramas `result="ok"` en data-receiving | 4 328 151 (−629 frente a confirmadas). Los contadores se reinician con los contenedores (14:33:05–14:33:26); se pierden los incrementos previos a la parada. | `data_receiving_frames_total` | B | OBTENIDO |
| Publicaciones en `data_management.persist` / `early_warning.evaluate` | 4 333 427 / 4 333 427 | `rabbitmq_queue_messages_published_total{queue=...}` | B | OBTENIDO |
| Consumidos por early-warning / duplicados omitidos | 4 334 129 / 5 349 | `ew_messages_consumed_total`, `ew_duplicates_skipped_total` | B | OBTENIDO |
| Etapa 4: alertas publicadas / entregas aceptadas por FCM | 3 414 / 3 416. La métrica de entrega mide «umbral cruzado → multicast FCM aceptado», no la recepción en el dispositivo; la recepción en el suscriptor es NO DISPONIBLE. | `ew_alerts_published_total`, `ew_alert_delivery_latency_seconds_count`; `go-early-warning/pkg/metrics/metrics.go:134-136` | B | OBTENIDO |
| `data_receiving_messages_dropped_total` | mín 0, máx 0 (3 series, 2 932–2 933 muestras) | `data_receiving_messages_dropped_total[43982s]` @ 2026-09-24T00:39:22Z (`/api/v1/query`; igual para las filas siguientes, ver `manifiesto.json`) | B | OBTENIDO |
| `dm_messages_dlq_total` | mín 0, máx 0 (2 series) | `dm_messages_dlq_total[...]` | B | OBTENIDO |
| `dm_messages_retried_total`, `dm_messages_invalid_total` | mín 0, máx 0 | ídem | B | OBTENIDO |
| `ew_messages_dropped_total` | mín 0, máx 0 (2 series) | ídem | B | OBTENIDO |
| Cola `sensors.dead_letter` | mín 0, máx 0 | `rabbitmq_queue_messages{queue="sensors.dead_letter"}` | B | OBTENIDO |
| Buffer Redis, máximo con `max()` | 3 752 (primera muestra 14:33:50, réplica 10.42.0.90). Otras réplicas: 3 743 (14:33:56), 3 750 (14:33:45). | `max(data_receiving_redis_buffer_pending)` calculado sobre `B__buffer.json` | B | OBTENIDO |
| Buffer Redis, nivel previo | ≤ 5 en los 20 min anteriores a la caída | ídem | B | OBTENIDO |
| Buffer Redis, vuelve al nivel previo | todas las réplicas ≤ 5 desde 14:36:41 | ídem | B | OBTENIDO |
| Buffer Redis, vuelve a 0 | primera muestra con `max()` = 0: intervalo de 14:51:45 (en régimen el valor oscila entre 0 y 8) | ídem | B | OBTENIDO |
| Buffer entre la parada y el primer pase de reintento | Las tres réplicas publican 0 entre 14:33:05 y 14:33:41: valor inicial del gauge en el proceso nuevo, que solo se actualiza en cada pase de reintento (cada 30 s) | `B__buffer.json`; `go-data-receiving/internal/buffer/retry_worker.go:58-65`; `config.go:34-35` | B | OBTENIDO |
| ¿El contenido sobrevivió al reinicio de 14:33:02? | Sí. Primer pase tras el arranque, 14:33:38.98 (8fgq2): `buffered` 3 750. Los 3 740 `message_id` de `publish failed` (instancia anterior) aparecen en `retry succeeded` (instancia nueva). `redis-0` sin reinicios. | `logs_b.json` → `retry_pass.primera_tras_reinicio`, `reconciliacion`; `kube_pod_container_status_restarts_total{pod="redis-0"}` = 0 | B | OBTENIDO |
| Publicaciones fallidas durante la caída | 3 740 líneas, 3 740 `message_id` distintos (69b4v 1 486, 7rpf9 1 133, 8fgq2 1 121), 14:32:24.446 – 14:33:01.805. Errores: `Exception (504) … channel/connection is not open` (3 739) y `broker nacked message` (1). | `logs_b.json` → `publish_failed` | B | OBTENIDO |
| ¿Se publicaron todas después? | Sí: 3 740 de 3 740 tienen `retry succeeded`, entre 14:34:45.634 y 14:36:25.198 | `logs_b.json` → `reconciliacion.publish_failed_con_retry_succeeded = 3740` | B | OBTENIDO |
| Republicaciones por mensaje | 9 077 líneas `retry succeeded` para 3 740 ids: 2 143 ids republicados 2 veces y 1 597 ids 3 veces (69b4v 3 723, 7rpf9 1 614, 8fgq2 3 740) | `logs_b.json` → `retry_succeeded`, `reconciliacion.retry_succeeded_lineas_por_id` | B | OBTENIDO |
| ¿Se persistieron las 3 740? | Por identificador: NO DISPONIBLE (requiere la consulta SQL por `message_id` de la sección 2). En agregado: filas insertadas = confirmadas (fila «Diferencia filas − confirmadas»). | — | B | NO DISPONIBLE |

### A

| dato | valor | fuente | sistema | estado |
|---|---|---|---|---|
| Ventana de conteo | 2026-09-18 05:17:31 – 17:25:32 | `durabilidad.A.ventana` | A | OBTENIDO |
| Tráfico previo a la corrida (excluido) | 1 666 tramas en las muestras de 05:15:45 a 05:17:30, antes del primer envío de Artillery (05:17:31) | `data_receiving_frames_total` (`A__frames.json`) | A | OBTENIDO |
| Tramas `result="ok"` en data-receiving / publicadas | 4 329 095 / 4 329 095 (diferencia 0 con confirmadas) | `data_receiving_frames_total`, `data_receiving_messages_published_total` | A | OBTENIDO |
| `data_receiving_messages_dropped_total` | mín 0, máx 0 (3 series, 2 932 muestras) | `data_receiving_messages_dropped_total[43982s]` @ 2026-09-18T17:25:33Z | A | OBTENIDO |
| Mensajes procesados por data-management | 4 332 014 (+2 919, +0,0674 % sobre confirmadas). `rabbitmq_acknowledged_total{service="data-management"}` da el mismo valor. | `dm_messages_processed_total` (2 instancias, :8082 y :8086) | A | OBTENIDO |
| Procesados por data-management menos tramas recibidas, por ventana | 05:17:31–07:18:00: +272; **07:18:00–07:30:00: +2 918** (72 000 tramas, 74 918 procesados); 07:30:00–11:18:00: +3; 11:18:00–11:30:00: −4; 11:30:00–17:25:32: −270. Los cortes de ventana están fijados a mano en `auditar.py`. | `dm_messages_processed_total`, `data_receiving_frames_total`; `hallazgos.json` → `durabilidad.A.dm_menos_frames_por_ventana` | A | OBTENIDO |
| Procesados por early-warning | 2 166 025 (solo la instancia :8092; Prometheus de A no raspa :8088) | `ew_messages_processed_total` | A | OBTENIDO |
| Filas persistidas en MySQL | NO DISPONIBLE. El único mysqld-exporter de A (`localhost:9104`) da 0 filas insertadas en toda la corrida: no apunta a la base de data-management. Haría falta el exporter sobre esa instancia o `SELECT COUNT(*)` sobre la tabla de lecturas. | `mysql_global_status_innodb_row_ops_total{operation="inserted"}` | A | NO DISPONIBLE |
| DLQ, cola dead-letter, contadores de descarte de DM/EW | NO DISPONIBLE: Prometheus de A no raspa RabbitMQ y los servicios de A no exponen esas métricas | `docs/metrics-methodology.md` §4 (limitaciones de `RESUMEN.md`) | A | NO DISPONIBLE |
| Buffer Redis de data-receiving | NO DISPONIBLE: A no expone la métrica (snapshots: `redis_buffer_pending=n/a`), y el redis_exporter de A da `redis_up` = 0 en toda la corrida (2 912 muestras), así que tampoco hay recuento de claves | `data/A - SPETIEMBRE 5 RUNS/chaos/kill-rabbitmq-*.snapshot`; `redis_up{instance="localhost:9121"}` (`A__redis_up.json`) | A | NO DISPONIBLE |
| Retenidas, republicadas y duplicadas en la caída del broker | NO DISPONIBLE. data-receiving (C#) las registra solo en logs (`rabbitmq publish failed`, `retry succeeded`), que van a journald; el journal conservado de A empieza el 2026-10-30 14:57:31. `data_receiving_messages_published_total` coincide con `frames_total`, así que no separa republicaciones. | `respaldo-logs-20261103/A-concurso-logs-20261103.tar.gz` (`journal-A-all.txt`, primera línea); `data-receiving-module-csharp/src/DataReceiving/Sinks/RabbitMqSink.cs:37`, `Buffer/RetryWorker.cs:51` | A | NO DISPONIBLE |

## 4. Memoria durante las 12 h

Consulta: `node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes`, `query_range` con paso 60 s, en MiB. Ventana: fin de la rampa (inicio + 180 s) hasta el fin de Artillery. Exclusión: de cada inyección, desde su inicio (sección 5) hasta 10 min después de su fin. Pendiente: regresión lineal por mínimos cuadrados (`numpy.polyfit`, grado 1) sobre las horas transcurridas.

| dato | valor | fuente | sistema | estado |
|---|---|---|---|---|
| Inicial (05:21:31) / final (17:20:31) | 3 404,3 / 3 459,4 MiB | `results/resistencia_memoria/memoria_nodo_A.csv` | A | OBTENIDO |
| Mínimo / máximo | 3 400,7 (05:23:31) / 3 532,1 MiB (17:01:31) | ídem | A | OBTENIDO |
| Pendiente, serie completa (720 muestras) | 4,00 MiB/h | ídem | A | OBTENIDO |
| Pendiente sin inyecciones (697 muestras) | 4,02 MiB/h | ídem | A | OBTENIDO |
| Ventana caída del broker (07:18:20–07:29:10) | mín 3 422,6, máx 3 448,5 MiB | ídem | A | OBTENIDO |
| Ventana pausa de data-management (11:18:19–11:30:01) | mín 3 446,1, máx 3 476,2 MiB | ídem | A | OBTENIDO |
| Inicial (12:35:20) / final (00:34:20) | 2 871,9 / 2 941,2 MiB | `memoria_nodo_B.csv` | B | OBTENIDO |
| Mínimo / máximo | 2 871,9 (12:35:20) / 3 038,1 MiB (17:00:20) | ídem | B | OBTENIDO |
| Pendiente, serie completa (720 muestras) | 2,17 MiB/h | ídem | B | OBTENIDO |
| Pendiente sin inyecciones (686 muestras) | 2,25 MiB/h | ídem | B | OBTENIDO |
| Ventana caída del broker (14:32:23–14:43:00) | mín 2 924,5, máx 2 984,5 MiB | ídem | B | OBTENIDO |
| Ventana pausa de data-management (18:32:29–18:43:59) | mín 2 962,7, máx 2 991,9 MiB | ídem | B | OBTENIDO |
| Ventana retardo hacia data-analysis (22:32:28–22:45:37) | mín 2 918,8, máx 2 991,9 MiB | ídem | B | OBTENIDO |
| Memoria por contenedor (cAdvisor, `container_memory_*`) | NO DISPONIBLE: Prometheus de B no tiene esas series. Se usa RSS por servicio. | lista de métricas de la TSDB restaurada | B | NO DISPONIBLE |
| Figura | `results/resistencia_memoria/memoria_12h.png` (una por sistema, líneas verticales en el inicio de cada inyección) | `auditar.py` → `plot` | A y B | OBTENIDO |

RSS por servicio en B: `sum by (app) (process_resident_memory_bytes{app!=""})`, paso 60 s, misma ventana y exclusión. Serie en `results/resistencia_memoria/memoria_servicio_B.csv`. Suma de las réplicas de cada servicio.

| servicio | inicial (MiB) | final (MiB) | mín (MiB) | máx (MiB) | pendiente completa (MiB/h) | pendiente sin inyecciones (MiB/h) | estado |
|---|---|---|---|---|---|---|---|
| data-analysis | 260,6 | 279,8 | 255,2 | 284,4 | 1,74 | 1,70 | OBTENIDO |
| data-management | 40,4 | 41,5 | 19,3 | 42,3 | −0,01 | −0,02 | OBTENIDO |
| data-receiving | 42,5 | 44,1 | 39,8 | 51,9 | −0,20 | −0,19 | OBTENIDO |
| early-warning | 79,3 | 54,2 | 48,9 | 82,9 | −2,93 | −2,93 | OBTENIDO |
| project-management | 14,2 | 13,9 | 13,3 | 15,4 | −0,07 | −0,07 | OBTENIDO |
| user-management | 18,8 | 16,9 | 16,4 | 20,2 | −0,20 | −0,19 | OBTENIDO |

En A, Prometheus tiene `process_resident_memory_bytes` para data-receiving, data-analysis y early-warning (:8092), y `jvm_memory_used_bytes` (no RSS) para los servicios Java. `exportar_prometheus.py` los exporta (`A__mem_rss_service.json`, `A__mem_jvm_service.json`), pero esta auditoría no los tabula porque el encargo pide la tabla por servicio solo para B.

## 5. Intervalos de cada incidencia

Los periodos de Artillery son de 10 s y se nombran por su inicio (reloj del cliente). «p95 > 1 s» lista los periodos consecutivos cuyo `summaries["dtu_tcp.round_trip_ms"].p95` supera 1 000 ms, buscados entre 10 min antes y 30 min después de cada inyección. Los reinicios salen de `kube_pod_container_status_restarts_total{namespace="landslide"}` (resolución 15 s: el incremento ocurre entre las dos muestras indicadas).

| dato | valor | fuente | sistema | estado |
|---|---|---|---|---|
| **Caída del broker**: inicio | 14:32:23.610 (`kubectl delete pod -l app=rabbitmq --force --grace-period=0`) | journal de B, línea `sudo[4040027]` | B | OBTENIDO |
| fin | nuevo `rabbitmq-0` con `Ready=1` en la muestra 14:33:00 (0 en 14:32:45); `rabbitmq_up` = 0 en las muestras 14:32:36–14:32:51 y 1 desde 14:33:06 | `kube_pod_container_status_ready{pod="rabbitmq-0"}`, `rabbitmq_up` | B | OBTENIDO |
| primer / último fallo del generador | periodo 14:33:00 (210) / periodo 14:33:10 (105) | `intermediate[].counters["vusers.failed"]` | B | OBTENIDO |
| p95 > 1 s | 14:34:50 – 14:36:00 (máx 2 059,5 ms) | `intermediate[].summaries` | B | OBTENIDO |
| reinicios | data-receiving 69b4v (1097→1098), 7rpf9 (1097→1098), 8fgq2 (1096→1097), entre las muestras 14:33:00 y 14:33:15; logs: parada 14:33:02.641–14:33:02.936, arranque 14:33:04.002–14:33:04.226. `last_terminated_reason="Completed"`, `exitcode=0`. | `kube_pod_container_status_restarts_total`; `logs_b.json` → `ciclo_de_vida`; `kube_pod_container_status_last_terminated_{reason,exitcode}` @ 19:00 | B | OBTENIDO |
| otros cambios de `Ready` | data-receiving ×3: 0 en 14:33:00–14:33:15, 1 en 14:33:30. data-management ×2: 0 en 14:33:00, 1 en 14:33:15 (sin reinicio) | `kube_pod_container_status_ready` | B | OBTENIDO |
| **Pausa de data-management**: inicio / fin | `kill -STOP 2056637` 18:32:29.652 / `kill -CONT` 18:33:59.821 | journal de B, `sudo[102139]`, `sudo[103946]` | B | OBTENIDO |
| primer / último fallo del generador | ninguno | `intermediate` | B | OBTENIDO |
| p95 > 1 s | 18:32:10 – 18:32:30 (máx 2 231 ms) | `intermediate[].summaries` | B | OBTENIDO |
| reinicios | data-management-5c98d7c987-zmctz (4→5) entre 18:33:30 y 18:33:45; `last_terminated_reason="Error"`, `exitcode=137`. `Ready=0` de 18:33:00 a 18:33:45. | `kube_pod_container_status_restarts_total`, `..._ready`, `..._last_terminated_*` | B | OBTENIDO |
| **Retardo hacia data-analysis** (netem 8 000 ms, puerto 50051): inicio / fin | `tc qdisc add … netem delay 8000ms` 22:32:28.174 y 22:32:30.824 (dos pods) / primer `tc qdisc del` por pod 22:35:35.229 y 22:35:37.837 (borrados repetidos hasta 22:36:32) | journal de B | B | OBTENIDO |
| primer / último fallo del generador | ninguno | `intermediate` | B | OBTENIDO |
| p95 > 1 s | 22:34:10–22:34:30 (1 200,1 ms); 22:35:00–22:35:20 (1 326,4 ms); 22:35:30–22:35:50 (1 863,5 ms); 22:36:00–22:39:20 (2 101,1 ms) | `intermediate[].summaries` | B | OBTENIDO |
| reinicios | ninguno | `kube_pod_container_status_restarts_total` | B | OBTENIDO |
| p95 > 1 s fuera de las inyecciones | 16:55:30–16:56:00 (1 587,9 ms); 17:00:00–17:00:10 (1 085,9 ms); 19:31:20–19:31:30 (1 620 ms); 00:00:00–00:00:10 (1 224,4 ms) | `hallazgos.json` → `incidencias.B.todos_los_periodos_p95_mayor_1s` | B | OBTENIDO |
| Reinicios en toda la corrida | solo los 4 anteriores (3 data-receiving, 1 data-management) | `reinicios_B_corrida` | B | OBTENIDO |
| **Caída del broker**: inicio / fin exactos | NO DISPONIBLE: no hay journal de A del 18/09 y Prometheus de A no raspa RabbitMQ. Cotas: snapshots pre 07:18:20 y post 07:19:10 (horas de captura, no de inyección). | `kill-rabbitmq-{pre-1789715900,post-1789715950}.snapshot` | A | NO DISPONIBLE |
| Caída del broker vista por los clientes | Conexión AMQP de data-management: :8086 pasa a 0 entre 07:18:14 y 07:18:29 y vuelve a 1 entre 07:18:44 y 07:18:59; :8082 pasa a 0 entre 07:18:17 y 07:18:32 y vuelve a 1 entre 07:18:47 y 07:19:02. data-receiving abre una conexión saliente nueva (4→5) entre 07:18:39 y 07:19:04 en las tres instancias. | `rabbitmq_connections{service="data-management"}`, `system_net_sockets_outgoing_connections_established{service="data-receiving"}` (`A__dm_rabbit_connections.json`, `A__dr_outgoing_connections.json`) | A | OBTENIDO |
| primer / último fallo; p95 > 1 s | ninguno; ningún periodo con p95 > 1 s en toda la corrida | `intermediate` | A | OBTENIDO |
| reinicios | ninguno en los servicios raspados (`process_start_time_seconds{job="microservices"}` sin cambios). El reinicio de `rabbitmq-server` no es observable (no raspado). | `A__process_start.json` | A | OBTENIDO |
| **Pausa de data-management**: inicio / fin | cotas: snapshots pre 11:18:19 y post 11:20:01. `up{instance="localhost:8082",service="data-management"}` = 0 de 11:18:32 a 11:19:32 (5 muestras). | `pause-data-management-{pre-1789730299,post-1789730401}.snapshot`; `A__up.json` | A | OBTENIDO |
| primer / último fallo; p95 > 1 s | ninguno; ninguno | `intermediate` | A | OBTENIDO |
| reinicios | ninguno (`process_start_time_seconds` sin cambios) | `A__process_start.json` | A | OBTENIDO |
| **Retardo hacia data-analysis** | no se inyectó en A (`run-during-endurance.sh` lo omite: A no tiene circuit breaker) | `docs/metrics-methodology.md` §3 | A | NO DISPONIBLE |

## Discrepancias con el artículo

| cifra del contexto | valor encontrado | fuente |
|---|---|---|
| B: 315 fallos «concentrados entre 14:33:00 y 14:33:19 UTC» | Coincide con los periodos de Artillery 14:33:00 (210) y 14:33:10 (105). Esas horas son del reloj del PC cliente, no del servidor. | sección 1 |
| B: «las tres réplicas de data-receiving se reiniciaron a las 14:33:01» | Parada a las 14:33:02.641, 14:33:02.808 y 14:33:02.936; arranque a las 14:33:04.002, 14:33:04.098 y 14:33:04.226. A las 14:33:01.640 empiezan las 105 escrituras canceladas (`sink write failed`). | `logs_b.json` |
| B: 3 740 publicaciones fallidas «todas retenidas en el buffer y confirmadas» | Retenidas y republicadas: sí, las 3 740. «Confirmadas» no es verificable por trama (sin identificador en el generador). | secciones 2 y 3 |
| B: buffer de 3 752 por réplica, máximo y no suma | Coincide: `max()` = 3 752 (10.42.0.90, primera muestra 14:33:50). | sección 3 |
| B: DLQ en 0 y contadores de descarte en 0 | Coincide: todas las series con mín 0 y máx 0 en la ventana. | sección 3 |
| A: 2 015 tramas retenidas | NO DISPONIBLE en ninguna fuente conservada. | sección 3, A |
| A: 4 933 republicadas | NO DISPONIBLE en ninguna fuente conservada. | sección 3, A |
| A: unas 2 900 duplicadas en el broker | NO DISPONIBLE como duplicados en el broker. Dato más cercano: data-management procesó 4 332 014 mensajes, 2 919 más que las tramas confirmadas, y 2 918 de ese excedente aparecen entre 07:18:00 y 07:30:00, la ventana de la caída del broker. | sección 3, A |

Las cifras de A (4 329 095 confirmadas, 0 fallos, p95 202,4 ms) y de B (4 328 780 confirmadas, p95 242,3 ms) coinciden con los informes de Artillery.

Cifras halladas que el contexto no menciona:

- Republicaciones duplicadas en B: 9 077 republicaciones para 3 740 mensajes. Además, 5 349 duplicados omitidos por early-warning y 5 342 `INSERT IGNORE` sin fila nueva.
- Tráfico previo a ambas corridas, excluido de los conteos: 1 666 tramas en A y 4 024 en B.
- La serie de memoria (sección 4).
