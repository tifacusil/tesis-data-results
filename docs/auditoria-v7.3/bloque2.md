# Bloque 2 — 105 «sink write failed» y 315 tramas sin ACK (C01)

## 2.1 Las 105 líneas «sink write failed»

`outputs/b2_sink_write_failed_105.csv` (columnas `timestamp_utc, pod, message_id, error`), extraído de `results/auditoria_resistencia/logs_b.json` → `sink_write_failed_detalle` (SHA-256 `95dd61cb…8e2a`). Ese JSON sale de los logs de data-receiving de B (`data/data-receiving-logs-2026-09-23/*-previous.log` y el tar `respaldo-logs-20261103`), procesados con `scripts/auditoria_resistencia/analizar_logs_b.py`.

- 105 líneas, 105 `message_id` distintos; 69b4v 42, 7rpf9 32, 8fgq2 31.
- Entre 2026-09-23 14:33:01.640 y 14:33:02.935 UTC (reloj del servidor).
- Error único: `buffer envelope <id>: context canceled`.

## 2.2 ¿Están en la tabla?

| consulta | instancia, base | ejecución UTC | resultado | archivo |
|---|---|---|---|---|
| `SELECT message_id, sensor_id, timestamp, received_at FROM gnss_readings WHERE message_id IN (<105 ids>)` (sin filtro de ventana) | pod `mysql-data-management-0` (vivo), `data_management` | 2026-11-20 03:12:31 | `Empty set`: 0 de 105 | `sql/db_s4.sql`, `fuente/auditoria_db_b_2026-11-20/raw/s4_out.txt` |
| los 105 ids contra la exportación de la ventana | exportación local | 2026-11-20 (auditoría 1) y 14:59:32 (V7.3) | 0 de 105 | `fuente/auditoria_db_b_2026-11-20/sink_ids_en_ventana.tsv`, `outputs/b4_ids_de_logs_en_gnss_readings.csv` |

## 2.3 ¿Se reintentaron o quedaron en el buffer?

- Logs de reintento: 0 de los 105 aparecen en `retry succeeded` ni en `rabbitmq publish failed` (`logs_b.json` → `reconciliacion.sink_write_failed_con_retry_succeeded = 0`, `sink_write_failed_con_publish_failed = 0`). `retry publish failed`, `retry delete failed` y `buffer delete after publish failed`: 0 líneas en toda la corrida.
- Buffer Redis: **no verificable**. No hay volcado de Redis del 23/09 y el estado actual no conserva aquel contenido (`FLUSHDB` antes de cada corrida, `experiment-manifest.json` → `etapas.escalera.reinicio_de_estado`). Por código (2.4), un «sink write failed» es justamente el fallo de la escritura en el buffer.

## 2.4 Código: sin ACK y sin buffer

`tifacusil/go-data-receiving`, commit `13ac6fe` (= `version` en los logs de la corrida):

- `internal/sink/rabbitmq.go:47-51`: `Write` escribe primero en Redis (`s.buffer.Set`). Si falla, devuelve `buffer envelope <id>: <err>` **sin publicar**. Nada queda en el buffer, así que el `RetryWorker` no puede republicarlo.
- `internal/tcp/server.go:162-170`: si `sink.Write` devuelve error, registra `sink write failed` con el `message_id` y hace `return`: no llega a `writeAck` (línea 175) y la conexión se cierra (`server.go:135-136`, `conn.Close()` en el `defer` de `handleConn`).
- `context canceled` es el contexto del servidor cancelado durante la parada (primera línea a las 14:33:01.640; `tcp server stopped` a las 14:33:02.641–02.936).

## 2.5 Filas por minuto

Consulta de la auditoría 1, recalculada sobre la exportación de la ventana (la versión en el servidor con funciones de ventana provocó el OOM; ver `README.md`):

```sql
-- equivalente local de:
SELECT DATE_FORMAT(received_at,'%Y-%m-%d %H:%i') minuto, COUNT(*)
FROM data_management.gnss_readings
WHERE received_at >= '2026-09-23 14:28:00' AND received_at < '2026-09-23 14:42:00'
GROUP BY minuto ORDER BY minuto;
```

`fuente/auditoria_db_b_2026-11-20/rows_per_minute_1428_1442.tsv`; tramo 14:30–14:39 en `outputs/b2_filas_por_minuto_1430_1440.csv`:

| minuto (UTC) | filas | − 6 000 |
|---|---|---|
| 14:30, 14:31, 14:32 | 6 000 c/u | 0 |
| **14:33** | 5 685 | **−315** |
| 14:34 | 5 875 | −125 |
| 14:35 | 5 993 | −7 |
| 14:36 | 6 132 | +132 |
| 14:37, 14:38, 14:39 | 6 000 c/u | 0 |

- 14:33 es **UTC del servidor**: `received_at` lo fija data-receiving con `time.Now().UTC()` (bloque 1).
- Ventana 14:33:00–14:36:59 (240 s, 24 000 tramas nominales a 100 tramas/s): 23 685 filas, déficit **315**. Todo el déficit está en el minuto 14:33; 14:34–14:36 suman 0 (−125 −7 +132): son tramas que llegaron más tarde, no tramas perdidas.
- Las 3 740 republicadas desde el buffer conservan su `received_at` original: están las 3 740 en la exportación, con `received_at` entre 14:32:24 y 14:33:01 (`outputs/b4_ids_de_logs_en_gnss_readings.csv`). Por eso 14:32 tiene 6 000 filas aunque se republicaron entre 14:34:45 y 14:36:25.

## 2.6 Artillery por periodos de 10 s (14:32–14:38)

`outputs/b2_artillery_10s_1432_1438.csv`, de `intermediate[]` de `data/B - SEPTIEMBRE 5 RUNS V2/sustained-12h.json` (SHA-256 `57fc9df4…5f50`). Periodos por su inicio, **reloj del PC cliente**.

| periodo | emitidas | OK (`frames_acked`) | `emulator_error` |
|---|---|---|---|
| 14:32:00 … 14:32:50 | 1 000 c/u | 1 000 c/u | 0 |
| **14:33:00** | 1 000 | **85** | **210** |
| **14:33:10** | 1 000 | 1 564 | **105** |
| 14:33:20 | 1 000 | 1 031 | 0 |
| 14:33:30 | 1 000 | 1 005 | 0 |
| 14:33:40 … 14:34:30 | 1 000 c/u | 1 000 c/u | 0 |
| 14:34:40 … 14:36:00 | 1 000 c/u | 842–1 379 | 0 |
| 14:36:10 … 14:37:50 | 1 000 c/u | 982–1 018 | 0 |

Las emitidas se cuentan en el periodo en que se crean; OK y fallidas, en el periodo en que terminan. Cuentas de 14:33:00–14:33:39: 4 000 emitidas = 3 685 OK (85 + 1 564 + 1 031 + 1 005) + 315 fallidas. Del periodo 14:33:00 quedaron 1 000 − 85 − 210 = 705 tramas abiertas; 105 fallaron en 14:33:10 y 600 terminaron con ACK en los tres periodos siguientes (564 + 31 + 5). Por eso un periodo tiene solo 85 confirmadas y no hay pérdida de 1 000.

**Sobre «20 s sin receptores».** Los 20 s son los dos periodos de Artillery con fallos (14:33:00 y 14:33:10). Según los logs del servidor, cada réplica de data-receiving dejó de escuchar entre 1,34 y 1,41 s (`tcp server stopped` 14:33:02.641/02.808/02.936 → `tcp server listening` 14:33:04.051/04.147/04.279). Con 100 tramas/s, la cantidad de fallos (315) corresponde a unos 3 s de tráfico. No se puede asignar cada fallo a una causa (rechazo de conexión, conexión cerrada con la trama en vuelo, o los 105 `sink write failed`) porque el generador no guarda el `message_id` (2.7), y el desfase de relojes no se midió (2.8).

## 2.7 ¿Artillery conservó los `message_id`?

No. El informe solo tiene contadores, tasas e histogramas por periodo (`aggregate.counters`: `dtu_tcp.frames_acked`, `errors.emulator_error`, `vusers.completed`, `vusers.created`, `vusers.created_by_name…`, `vusers.failed`). La cadena `message_id` no aparece en el archivo (0 coincidencias). Por eso no se puede comprobar por identificador si los 105 están entre los 315.

## 2.8 Zonas horarias y NTP

- Servidor B: MySQL con `@@system_time_zone = UTC` (20/11); logs y Prometheus en UTC.
- PC cliente: Artillery registra epoch en ms; la zona del PC no afecta a esos valores. Los logs de caos muestran la hora local como `HPS` (UTC−5).
- `timedatectl` y `chronyc tracking`: **no consultados** (requieren acceso al servidor; pendiente).
- **El desfase entre el reloj del PC cliente y el del servidor durante la campaña no se midió.** Las horas de Artillery (14:33:00–14:33:19) y las del servidor (14:33:01.6–14:33:04.3) no son comparables al segundo.
