# Bloque 1 — Filas en `gnss_readings` (C02)

Ventana: @t0 = 2026-09-23 12:31:20, @t1 = 2026-09-24 00:39:21 (UTC). Ver `README.md` para zonas horarias.

## Esquema y ajuste de nombres

`SHOW CREATE TABLE gnss_readings` **no se ejecutó en producción** (pendiente). DDL usado: reconstrucción local de AP8 (`mysqldump --no-data` tras aplicar las migraciones de `go-tesis-infra@c6732b0`), rama `verificacion-local-ap1-ap8`, `results/verificacion_ap1_ap8/ap8/dm/schema-B.sql`; el diff entre los esquemas de A y B es vacío.

```sql
CREATE TABLE `gnss_readings` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `message_id` varchar(64) ... DEFAULT NULL,
  `sensor_id` varchar(64) ... NOT NULL,
  `timestamp` datetime NOT NULL,
  `received_at` datetime NOT NULL,
  ...
  PRIMARY KEY (`id`,`timestamp`),
  UNIQUE KEY `uk_gnss_message` (`message_id`,`timestamp`),
  KEY `idx_gnss_sensor_ts` (`sensor_id`,`timestamp`),
  KEY `idx_gnss_project_ts` (`project_id`,`timestamp`)
) ... PARTITION BY RANGE (year(`timestamp`)) ...
```

| plantilla del pedido | columna real | nota |
|---|---|---|
| `data_management.gnss_readings` | `data_management.gnss_readings` | el encargo original de la auditoría 1 decía `data_management_db`, que no existe (`ERROR 1049`) |
| `<col_ingesta>` | `received_at` | **No hay columna de inserción** (sin `created_at` ni `DEFAULT CURRENT_TIMESTAMP`). `received_at` es la hora de recepción en data-receiving, en UTC, con resolución de 1 s (`go-data-receiving@13ac6fe:internal/parsing/parser.go:39`), y data-management la copia del sobre (`go-data-management@3d960a5:internal/persistence/repository.go:35`). Un mensaje republicado desde el buffer conserva su `received_at` original. |
| índice único | `uk_gnss_message (message_id, timestamp)` | no es único solo por `message_id`; por eso `COUNT(DISTINCT message_id)` se comprueba aparte |

## Consultas y resultados

| # | consulta (texto exacto) | instancia, base | ejecución UTC | resultado | archivo |
|---|---|---|---|---|---|
| 1.1 | `SELECT COUNT(*), MIN(received_at), MAX(received_at) FROM gnss_readings IGNORE INDEX (idx_gnss_sensor_ts, idx_gnss_project_ts, uk_gnss_message) WHERE received_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'` | pod `mysql-data-management-0` (vivo), MySQL 8.0.46, `data_management` | 2026-11-20 02:47:42–02:48:05 | 4 328 780 filas; mín 12:31:21, máx 00:34:23 | `sql/db_s0.sql`, `fuente/auditoria_db_b_2026-11-20/raw/s0_out.txt` |
| 1.2 | exportación `SELECT message_id, sensor_id, timestamp, received_at ... WHERE received_at BETWEEN ...` (streaming, `mysql --quick`) y recuento local de `message_id` distintos | mismo pod; recuento local en el PC | exportación 03:11:52–03:12:30; recuento 2026-11-20 14:59:32 | 4 328 780 filas, 4 328 780 `message_id` distintos, 0 repetidos, 0 nulos | `sql/db_export.sql`, `contar_message_id.py`, `outputs/b1_message_id_distintos.csv` |
| 1.3 | `mysql_global_status_innodb_row_ops_total{instance="mysqld-exporter-data-management:9104",operation="inserted"}[43982s]` @ 2026-09-24T00:39:22Z; incremento sin extrapolación | TSDB restaurada `B-prometheus-tsdb-20261014` | exportación de `docs/auditoria-resistencia-12h.md` (17/11); cálculo 20/11 | valor en @t0 (muestra 12:31:11.237) 4 815 603; en @t1 (muestra 00:39:11.237) 9 144 383; incremento **4 328 780**, 0 reinicios, 2 913 muestras | `results/auditoria_resistencia/prometheus/B__mysql_rows_inserted.json`, `outputs/b1_innodb_rows_inserted.csv` |

`IGNORE INDEX` no cambia el resultado: sin él, el recorrido por `idx_gnss_sensor_ts` tardó 27 min y se abortó (`fuente/auditoria_db_b_2026-11-20/report.md`, desviación 1). Las consultas 1.1 y la exportación son `SELECT` simples sin `GROUP BY` sobre la tabla completa.

El pedido pide `increase(...[12h])` evaluado en @t1. Se usa la misma regla de `docs/auditoria-resistencia-12h.md` (suma de diferencias entre muestras, sin extrapolación) sobre la ventana de 12 h 08 min; `increase()` de Prometheus extrapola a los extremos y no daría un entero.

## Comparación con los 4 328 780 ACK de Artillery

| fuente | valor | diferencia con ACK |
|---|---|---|
| `dtu_tcp.frames_acked` (Artillery) | 4 328 780 | — |
| `COUNT(*)` en `gnss_readings` por `received_at` | 4 328 780 | 0 |
| `COUNT(DISTINCT message_id)` | 4 328 780 | 0 |
| filas insertadas InnoDB (todas las tablas de la instancia) | 4 328 780 | 0 |

No hay diferencia. El contador InnoDB cuenta todas las tablas de la instancia; las otras cuatro tablas de lecturas tienen 0 filas según `information_schema.tables.TABLE_ROWS` (estimación de InnoDB, `s0_out.txt`), y el incremento coincide con el `COUNT(*)` de `gnss_readings`.
