# Bloque 3 — Alertas 3414 / 3416 (C03)

## Esquema y ajuste de nombres

`SHOW CREATE TABLE alerts` se ejecutó en producción (auditoría 2, paso 4, 2026-11-20 03:46:36 UTC, `fuente/auditoria_ew_b_2026-11-20/raw/step4_output.txt`):

```sql
CREATE TABLE `alerts` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime NOT NULL,
  `message_id` varchar(64) DEFAULT NULL,
  `project_id` varchar(64) NOT NULL,
  `sensor_id` varchar(64) NOT NULL,
  `alert_level` enum('blue','orange','red') NOT NULL,
  ...
  `alert_timestamp` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_alert_message` (`message_id`),
  KEY `idx_alerts_project_ts` (`project_id`,`alert_timestamp`)
) ENGINE=InnoDB AUTO_INCREMENT=4253 ...
```

| plantilla | columna real | nota |
|---|---|---|
| `<bd_early_warning>` | `early_warning` | pod `mysql-early-warning-0` |
| `<created_at>` | `created_at` | UTC, hora de inserción (`store.go:73`, `time.Now().UTC()`) |
| `<ts_lectura>` | `alert_timestamp` | `timestamp` no existe: `ERROR 1054 (42S22) ... Unknown column 'timestamp'` |
| `level` | `alert_level` | |

La tabla no se vació después: tiene 836 filas más del 29–30/09 (`step5_out.txt`). La ventana por `created_at` las excluye.

## Consultas SQL

| consulta (texto exacto en el archivo) | instancia, base | ejecución UTC | resultado | archivo |
|---|---|---|---|---|
| `SELECT COUNT(*), COUNT(DISTINCT message_id), SUM(message_id IS NULL), MIN(created_at), MAX(created_at) FROM alerts WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'` | `mysql-early-warning-0` (vivo), `early_warning` | 2026-11-20 02:29:57 | 3416, 3416, 0, 12:37:08, 00:34:07 | `sql/db_step5.sql`, `fuente/auditoria_db_b_2026-11-20/raw/step5_out.txt` |
| por `alert_level` | ídem | ídem | red 1777, blue 984, orange 655 | ídem |
| `SELECT COUNT(*), COUNT(DISTINCT sensor_id, alert_timestamp), SUM(alert_timestamp IS NULL) FROM alerts WHERE created_at BETWEEN ...` | ídem | 2026-11-20 03:46:36 | **3416 alertas, 3414 lecturas distintas**, 0 nulos | `sql/ew_step4.sql`, `fuente/auditoria_ew_b_2026-11-20/raw/step4_output.txt` |
| `SELECT sensor_id, alert_timestamp, COUNT(*) c, MIN(created_at), MAX(created_at), GROUP_CONCAT(alert_level ORDER BY id) ... GROUP BY sensor_id, alert_timestamp HAVING c > 1` | ídem | ídem | 2 grupos (abajo) | ídem |

| sensor | `alert_timestamp` | n | `created_at` | niveles |
|---|---|---|---|---|
| GXZM-DB050 | 2019-07-17 01:57:18 | 2 | 2026-09-23 14:33:27 (ambas) | red, red |
| GXZM-DB086 | 2019-09-03 13:33:47 | 2 | 2026-09-23 19:10:21 y 19:10:22 | blue, blue |

La variante pedida con `GROUP_CONCAT(CONCAT(id,'|',level,'|',created_at))` **no se ejecutó**: requiere `mysql-early-warning-0` (`sql/pendiente_v7.3.sql`). Las dos filas de cada grupo tienen `message_id` distintos (3416 `message_id` distintos en 3416 filas).

## PromQL, total y por réplica

Las series no tienen etiqueta `pod`; las dos réplicas se distinguen por `instance` (10.42.0.118:8080 y 10.42.0.119:8080). Fuente: TSDB restaurada del 14/10. Consultas exactas en `promql/consultas.md`. Incremento sin extrapolación en [@t0, @t1] (`derivar.py`).

| métrica | 10.42.0.118 | 10.42.0.119 | total | archivo |
|---|---|---|---|---|
| `ew_alerts_published_total` (suma de `level`), regla de incremento | 1 661 | 1 753 | **3 414** | `outputs/b3_ew_alertas_por_serie.csv` |
| ídem, contando el valor inicial de las series que nacen en la ventana | 1 662 | 1 754 | **3 416** | ídem |
| `ew_alert_delivery_latency_seconds_count` | 1 662 | 1 754 | **3 416** | ídem |
| `ew_evaluations_total{outcome="alert"}` | 1 662 | 1 754 | **3 416** | `outputs/b4_ew_evaluations_por_outcome.csv` |

## Código

`tifacusil/go-early-warning`, clon local en `fd5a866`. El commit de la imagen del 23/09 (`sha256:94bdbcf8…`, construida 2026-09-23T05:15:40Z) no está registrado; estas líneas son del clon local.

| contador o escritura | definición | dónde se incrementa |
|---|---|---|
| `ew_evaluations_total{outcome}` | `pkg/metrics/metrics.go:125` | `internal/earlywarning/consumer/consumer.go:335`, una vez por evaluación |
| `ew_alert_delivery_latency_seconds` (histograma sin etiquetas) | `metrics.go:134-135` | `consumer.go:405`, solo si `PublishPush` entrega el multicast (`consumer.go:402`) |
| `INSERT IGNORE INTO alerts` | `internal/earlywarning/store/store.go:67-76` | llamado desde `consumer.go:419` (`recordAlert`) |
| `ew_alerts_published_total{level}` | `metrics.go:107-108` (`CounterVec` por `level`) | `consumer.go:424`, después de que `recordAlert` termina sin error |

## 3414 publicadas frente a 3416 en `alerts` y 3416 push: **conciliada**

1. Por código, cada alerta pasa por push (`:405`), `INSERT` (`:419`) y `AlertsPublished.Inc()` (`:424`) en ese orden. No hubo fallos de `INSERT` en la corrida: al final, en cada réplica, la suma de `ew_alerts_published_total` por nivel es igual a `ew_alert_delivery_latency_seconds_count` (118: 498 + 333 + 1 023 = 1 854; 119: 535 + 322 + 1 092 = 1 949).
2. `ew_alerts_published_total` es un `CounterVec`: la serie de un nivel se crea con el primer `Inc()`. Las series `level="orange"` de las dos réplicas no existían en @t0 y aparecen con valor 1 en 12:55:03.935 (118) y 12:54:52.616 (119). La regla de incremento empieza en la primera muestra y no cuenta ese 1. Faltan 2 alertas: 3 414 + 2 = 3 416.
3. El histograma de entrega no tiene etiquetas y existe desde el arranque, así que cuenta todas: 3 416.

El valor correcto de alertas publicadas en la ventana es **3 416** = filas en `alerts` = envíos push aceptados = evaluaciones con `outcome="alert"`.

## Las dos lecturas con dos alertas

El generador envía cada lectura 10–15 veces con `message_id` distintos (bloque 1: grupos de 10–15 filas por `(sensor_id, timestamp)`). early-warning lee la última lectura del sensor en Redis antes de evaluar (`consumer.go:324-329`) y la escribe después con compare-and-set (`consumer.go:344-354`). Hipótesis, **no verificada con logs**: las dos réplicas evaluaron a la vez dos copias de la misma lectura nueva, leyeron la misma línea base y alertaron las dos; la segunda escritura de la base se rechazó (`baseline_write_superseded`).

Réplica que generó cada alerta: **no determinada**. Requiere los logs de early-warning del 23/09 (`alert_emitted` con `sensor_id`), que no están en el repositorio. Indicio compatible con una alerta por réplica: `ew_alerts_published_total{level="red"}` sube en 118 entre las muestras 14:33:18 y 14:33:33 (+1) y en 119 entre 14:33:22 y 14:33:37 (+4); `level="blue"` sube en 118 entre 19:10:18 y 19:10:33 (+1) y en 119 entre 19:10:07 y 19:10:22 (+1). No es concluyente: en esos intervalos hubo otras alertas.
