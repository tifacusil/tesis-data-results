# Auditoría V7.3: respaldo publicado de las cifras del artículo

Auditoría post hoc del 20/11/2026 sobre la corrida de resistencia de 12 h de B (23–24/09/2026) y las pruebas dirigidas del 30/09/2026. Completa `docs/auditoria-resistencia-12h.md`, que todavía marcaba como NO DISPONIBLE el recuento SQL de `gnss_readings`, la tabla `alerts` y `ew_evaluations_total`.

Todas las horas están en **UTC** salvo que se indique otra cosa.

## Procedencia

| parte | origen | cuándo |
|---|---|---|
| `fuente/auditoria_db_b_2026-11-20/` | Auditoría 1: SQL de solo lectura sobre `data_management.gnss_readings` (`mysql-data-management-0`) y `early_warning.alerts` (`mysql-early-warning-0`), **instancias vivas** de B en `178.105.104.95`. Copia byte a byte de la carpeta local del autor, sin `raw/export.tsv.gz` (122 MB, ver abajo). | 2026-11-20 02:18–03:12 UTC |
| `fuente/auditoria_ew_b_2026-11-20/` | Auditoría 2: `ew_evaluations_total` sobre la **TSDB restaurada** `B-prometheus-tsdb-20261014.tar.gz` (Prometheus 3.5.4 en Docker, puerto 9091), más un paso SQL sobre `mysql-early-warning-0` vivo. Copia byte a byte. | 2026-11-20 03:39–03:46 UTC |
| `outputs/` | Derivado en esta sesión (V7.3) de archivos del repositorio con `derivar.py`. `b1_message_id_distintos.csv` y `b4_ids_de_logs_en_gnss_readings.csv` salen de `contar_message_id.py` sobre la exportación no publicada (abajo). | 2026-11-20, sesión V7.3 |

Las dos auditorías usaron `root@localhost` con `SET SESSION transaction_read_only = ON`, con aprobación del propietario (el usuario `revisor` no tenía contraseña disponible). La consulta del paso 2 de la auditoría 1 agotó la memoria del pod MySQL (límite 320 MiB, `OOMKilled`, reinicio 0→1 a las 03:07:42). Los pasos 1–3 se recalcularon después sobre una exportación de la ventana.

Archivo no publicado: `auditoria_db_b_2026-11-20/raw/export.tsv.gz` (exportación de `message_id, sensor_id, timestamp, received_at` de la ventana; 4 328 780 filas). SHA-256 del `.gz`: `28cee4f9eb7450af162cd4cd80e53369a5268c03df1c20a5a11a40439fed0f05`; del TSV descomprimido: `faf0f99ee8cdc71d22dec2c448703632e0e924d379025a40fb7a05f354b4d4a3` (igual al que registra `fuente/auditoria_db_b_2026-11-20/report.md`). Supera el límite de 100 MB de GitHub; se entrega a solicitud, como los respaldos de la TSDB.

## Ventana y zonas horarias

- **@t0 = 2026-09-23 12:31:20**, **@t1 = 2026-09-24 00:39:21** (UTC): inicio de Artillery y fin + 300 s, igual que `docs/auditoria-resistencia-12h.md` §3.
- La auditoría 1 usó `BETWEEN @t0 AND @t1` (intervalo cerrado), no `>= @t0 AND < @t1`. El resultado es el mismo: `MIN(received_at)` = 12:31:21 y `MAX(received_at)` = 00:34:23, lejos de los dos extremos.
- La auditoría 2 evaluó `ew_evaluations_total` en 12:31:20–00:34:21 (sin el margen de 300 s). El bloque 4 la recalcula con la ventana común.

| columna o fuente | zona | evidencia |
|---|---|---|
| `gnss_readings.received_at` (`DATETIME`) | UTC. Es la hora de **recepción en data-receiving** (no la de inserción en MySQL), con resolución de 1 s. | `go-data-receiving@13ac6fe:internal/parsing/parser.go:39` (`p.now().UTC()`); `go-data-management@3d960a5:internal/persistence/repository.go:26,35` (`utc(e.ReceivedAt)`) |
| `gnss_readings.timestamp` | UTC; marca virtual de la lectura (conjunto de 2019) | ídem, `utc(e.Timestamp)` |
| `alerts.created_at` (`DATETIME`) | UTC; hora de inserción | `go-early-warning@fd5a866:internal/earlywarning/store/store.go:73` (`time.Now().UTC()`) |
| `alerts.alert_timestamp` | UTC; marca virtual de la lectura | ídem |
| Servidor MySQL de B | `@@system_time_zone = UTC`, `@@global.time_zone = SYSTEM` el 20/11 | `fuente/auditoria_db_b_2026-11-20/raw/s0_out.txt` |
| Prometheus, logs de pods | epoch Unix / RFC 3339 con `Z` | exportaciones; `logs_b.json` → `zona_horaria` |
| Periodos de Artillery | reloj del PC cliente (epoch ms) | `sustained-12h.json` |
| Logs `netem-delay-ew-um-run-*` | muestran hora local `HPS` (UTC−5) y UTC | los propios logs |

No se midió el desfase entre el reloj del PC cliente y el del servidor durante la campaña. El estado actual de NTP no se consultó (requiere acceso, ver Pendientes).

## Paso 0: inventario

«Aquí» = este repositorio, la carpeta de las auditorías del 20/11 y los clones locales del código (solo lectura de archivos).

| ítem | estado | fuente o acceso que falta |
|---|---|---|
| B1 `COUNT(*)` en la ventana | disponible aquí (auditoría 1, ejecutado en la instancia viva) | `fuente/auditoria_db_b_2026-11-20/raw/s0_out.txt` |
| B1 `COUNT(DISTINCT message_id)` | calculado aquí sobre la exportación de la auditoría 1 | `outputs/b1_message_id_distintos.csv` |
| B1 `SHOW CREATE TABLE gnss_readings` en producción | **requiere MySQL de B**. Se usa el DDL de la reconstrucción local de AP8 (`mysqldump --no-data` de las migraciones de c6732b0) | rama `verificacion-local-ap1-ap8`, `results/verificacion_ap1_ap8/ap8/dm/schema-B.sql` |
| B1 PromQL InnoDB en @t0 y @t1 | disponible aquí | `results/auditoria_resistencia/prometheus/B__mysql_rows_inserted.json` |
| B2.1 105 «sink write failed» | disponible aquí | `results/auditoria_resistencia/logs_b.json` |
| B2.2 105 ids en la tabla | disponible aquí (auditoría 1) | `fuente/auditoria_db_b_2026-11-20/raw/s4_out.txt` |
| B2.3 105 ids en reintentos | disponible aquí | `logs_b.json` → `reconciliacion` |
| B2.3 105 ids en el buffer Redis | **no verificable**: no existe volcado de Redis del 23/09 y el estado actual no sirve (`FLUSHDB` entre corridas) | — |
| B2.4 código de data-receiving | disponible aquí (clon local en `13ac6fe` = versión de los logs) | `go-data-receiving` |
| B2.5 filas por minuto | disponible aquí (auditoría 1, recalculado sobre la exportación) | `rows_per_minute_1428_1442.tsv` |
| B2.6–7 Artillery por periodo, `message_id` | disponible aquí | `sustained-12h.json` |
| B2.8 zona horaria y NTP actuales | **requiere el servidor de B** (`timedatectl`, `chronyc tracking`) y el PC cliente | — |
| B3 SQL de `alerts` | disponible aquí (auditoría 1 paso 5 y auditoría 2 paso 4), salvo `GROUP_CONCAT(id,'|',level,'|',created_at)`: **requiere MySQL de early-warning** | `step5_out.txt`, `step4_output.txt` |
| B3 PromQL por réplica | disponible aquí | `B__ew_alerts.json`, `B__ew_alert_delivery_count.json`, `ew_evaluations_samples.csv` |
| B3 código de early-warning | disponible aquí (clon local en `fd5a866`; el commit de la imagen del 23/09 no está registrado) | `go-early-warning` |
| B3 logs de early-warning de DB050 y DB086 | **requiere logs de early-warning del 23/09** (no están en el repo; podrían estar en `respaldo-logs-20261103`, sin abrir) | — |
| B4.1 `ew_evaluations_total` por outcome | disponible aquí | `ew_evaluations_samples.csv` |
| B4.2 buffer en la caída del broker | disponible aquí; persistencia de las 3740 comprobada sobre la exportación | `logs_b.json`, `B__buffer.json`, `go-data-receiving`, `export.tsv.gz` |
| B4.3 cifras del circuit breaker | disponible aquí | `data/B - SEPTIEMBRE 5 RUNS V2/chaos/netem-delay-ew-um-*` |
| B4.3 cronología por réplica y cierre | **requiere logs de early-warning del 30/09 o la TSDB del 14/10** (`ew_circuit_breaker_state` por `instance`) | — |

## Bloques

- [Bloque 1 — filas en `gnss_readings` (C02)](bloque1.md)
- [Bloque 2 — 105 «sink write failed» y 315 tramas sin ACK (C01)](bloque2.md)
- [Bloque 3 — alertas 3414 / 3416 (C03)](bloque3.md)
- [Bloque 4 — evaluaciones, buffer y circuit breaker](bloque4.md)
- [Pedido 2 — consultas en B del 20/11 15:08–15:39 UTC, PromQL con `increase()`, cronología del breaker por réplica](pedido2.md): actualiza las filas de cierre, llamadas rechazadas y alertas sin push de la tabla de abajo, y cierra los pendientes 1, 2 y 5 y la parte del 30/09 del 4 (los logs de early-warning del 23/09 son NO DISPONIBLE)

Consultas: `sql/` (texto exacto ejecutado, copiado de `fuente/`; `sql/pendiente_v7.3.sql` no se ejecutó) y `promql/consultas.md`.

## Cifras del artículo

| cifra del artículo | archivo | valor | ¿coincide? |
|---|---|---|---|
| 4 328 780 tramas confirmadas (B) | `data/B - SEPTIEMBRE 5 RUNS V2/sustained-12h.json` | 4 328 780 | sí |
| filas en `gnss_readings` | `fuente/auditoria_db_b_2026-11-20/raw/s0_out.txt` | 4 328 780 | sí |
| `message_id` distintos | `outputs/b1_message_id_distintos.csv` | 4 328 780 | sí |
| filas insertadas (InnoDB) | `outputs/b1_innodb_rows_inserted.csv` | 4 328 780 | sí |
| 105 «sink write failed» | `outputs/b2_sink_write_failed_105.csv` | 105 (105 ids distintos) | sí |
| 105 ids en `gnss_readings` | `fuente/auditoria_db_b_2026-11-20/raw/s4_out.txt` | 0 | sí (esperado 0) |
| 315 tramas sin ACK | `outputs/b2_artillery_10s_1432_1438.csv` | 210 + 105 = 315 | sí |
| 85 confirmadas en un periodo | ídem, periodo 14:33:00 | 85 | sí |
| déficit 14:33:00–14:36:59, 24 000 nominales | `outputs/b2_filas_por_minuto_1430_1440.csv` | 23 685 filas (−315), todo en el minuto 14:33 | sí |
| «20 s sin receptores» | `logs_b.json` → `ciclo_de_vida` | data-receiving sin escuchar entre `tcp server stopped` y `tcp server listening`: 1,41 / 1,34 / 1,34 s por réplica (14:33:02,641–14:33:04,279). Los 20 s son los dos periodos de Artillery con fallos | **no** como duración sin receptores |
| 3416 filas en `alerts` | `fuente/auditoria_db_b_2026-11-20/raw/step5_out.txt` | 3416 (3416 `message_id` distintos) | sí |
| 3414 lecturas distintas en `alerts` | `fuente/auditoria_ew_b_2026-11-20/raw/step4_output.txt` | 3414 (2 lecturas con 2 alertas) | sí |
| 3414 alertas publicadas | `outputs/b3_ew_alertas_por_serie.csv` | 3414 con la regla de incremento; 3416 contando el valor inicial de las 2 series `level="orange"` | conciliada: el valor real es **3416** |
| 3416 envíos push | ídem, `ew_alert_delivery_latency_seconds_count` | 3416 | sí |
| `ew_evaluations_total{outcome="alert"}` | `outputs/b4_ew_evaluations_por_outcome.csv` | 3416 | sí |
| 4 327 801 evaluadas | ídem, ventana del 20/11 | 4 327 801 (ventana común: 4 328 780) | sí |
| 177 «otras» | ídem | `gap_too_large_reset` 81 + `previous_none` 96 | sí (ventana del 20/11) |
| diferencia de 979 | ídem | 4 328 780 − 4 327 801; alineación de las muestras en los extremos | sí, explicada |
| 3740 retenidas | `logs_b.json` → `publish_failed` | 3740 | sí |
| 3740 persistidas | `outputs/b4_ids_de_logs_en_gnss_readings.csv` | 3740 de 3740 en `gnss_readings` | sí |
| 3752 como máximo | `outputs/b4_buffer_max_por_replica.csv` | 3752 (10.42.0.90, 14:33:50) | sí |
| 9077 republicaciones | `logs_b.json` → `retry_succeeded` | 9077 | sí |
| Apertura 116 / 131 / 123 s | `outputs/b4_circuit_breaker_por_corrida.csv` | 116 / 131 / 123 | sí |
| Cierre 17–29 s | — | sin fuente en el repositorio; `recovery_s` = 0 / 0 / 0 y no mide el cierre | **no** |
| Llamadas rechazadas 133 / 174 / 183 | ídem | 133 / 174 / 183 (corrida 1 desde la primera muestra no vacía; contando desde 0, 190) | sí con ese método; corrida 1 **no comparable** con 2 y 3 |
| Alertas publicadas 229 / 205 / 211 | ídem | 229 / 205 / 211 | sí |
| Alertas sin push 117 / 94 / 104 | ídem, `alerts_while_open` | 117 / 94 / 104 son alertas registradas **con el breaker abierto**; las alertas sin push en todo el fallo son 191 / 171 / 181 | valor sí; **definición no** |

## Pendientes (requieren acceso externo; no se intentaron)

1. `SHOW CREATE TABLE gnss_readings` y `SHOW CREATE TABLE alerts` (este último ya está en `step4_output.txt`) en las instancias vivas.
2. `sql/pendiente_v7.3.sql` en `mysql-early-warning-0`: ids, nivel y `created_at` de las 4 filas duplicadas.
3. `timedatectl` y `chronyc tracking` en el servidor de B; zona horaria del PC cliente.
4. Logs de early-warning del 23/09 (DB050 14:33:27, DB086 19:10:21–22) y del 30/09 (cronología del breaker).
5. TSDB del 14/10 restaurada: `ew_circuit_breaker_state{target="user-management"}` por `instance` el 30/09 03:32–03:56, para medir el cierre.

## Reproducción

```bash
py -I docs/auditoria-v7.3/derivar.py                                 # outputs/b1_innodb…, b2_*, b3_*, b4_ew…, b4_buffer…, b4_circuit…
py -I docs/auditoria-v7.3/contar_message_id.py <ruta>/export.tsv.gz  # outputs/b1_message_id_distintos.csv, b4_ids_de_logs…
(cd docs/auditoria-v7.3 && sha256sum -c SHA256SUMS)
```
