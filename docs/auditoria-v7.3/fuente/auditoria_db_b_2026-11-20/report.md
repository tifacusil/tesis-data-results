# Read-only audit: data_management.gnss_readings (System B), 12 h endurance test of 2026-09-23

Raw data only. No conclusions.

## Execution context

| Item | Value |
|---|---|
| Server | 178.105.104.95 (host `go-tesis`), k3s, namespace `landslide` |
| Pod | `mysql-data-management-0`, image `mysql:8.0.46` |
| MySQL version | 8.0.46 (`@@version`) |
| MySQL user | `root@localhost`. A `revisor` user exists, but its password was not available; root was used with explicit owner approval. Every session ran `SET SESSION transaction_read_only = ON`. |
| Database | `data_management`. The brief says `data_management_db`; that schema does not exist (`ERROR 1049 (42000) at line 3: Unknown database 'data_management_db'`). |
| Window | `received_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'` |
| Execution date | 2026-11-20 (UTC); per-step times below |

### Deviations from the brief

1. **Index hint.** Steps 0, 1, 2 and 3 add `IGNORE INDEX (idx_gnss_sensor_ts, idx_gnss_project_ts, uk_gnss_message)`. Without it, step 1 ran for 27 min (about 3,400 rows/s through random lookups on `idx_gnss_sensor_ts`) and was aborted with `KILL QUERY` on its own connection. With the hint, step 1 took 32 s. The hint does not change the result set.
2. **Incident: the step 2 query OOM-killed MySQL.** The window-function query started on the server at 03:04:05 UTC. At 03:07:42 UTC the container was killed: `exitCode 137`, `reason: OOMKilled`, memory limit 320Mi. MySQL restarted and reported ready for connections at 03:07:46 UTC, after InnoDB crash recovery. The pod restart count went from 0 to 1. Steps 3 and 4 in that run failed with `ERROR 2002 (HY000)` while the server was down. See `raw/s2_out_OOM.txt`. An earlier server-side run of step 2 (02:49 UTC) finished, but its output was lost to a hung SSH pipe.
3. **Steps 1–3 recomputed from an export.** After the incident, and with owner approval, one streaming SELECT exported the window (`raw/export.sql`, `mysql --quick --batch --raw`). Steps 1, 2 and 3 were then recomputed locally with `raw/analyze.js`, which uses the same semantics as the SQL: per sensor, rows ordered by `timestamp`, LAG of `timestamp` and `received_at`, a gap when the difference is over 3600 s, `faltantes = d/3600 - 1`. The local step 1 counts match the server's step 1 output for all 100 sensors.
4. **Step 4** ran on the server exactly as specified, with no window filter.

## Step 0: preliminary check

Started 2026-11-20 02:47:42 UTC, finished 02:48:05 UTC. Literal output: `raw/s0_out.txt`.

```
SELECT @@global.time_zone, @@session.time_zone, @@system_time_zone, UTC_TIMESTAMP(), NOW()
--------------

+--------------------+---------------------+--------------------+---------------------+---------------------+
| @@global.time_zone | @@session.time_zone | @@system_time_zone | UTC_TIMESTAMP()     | NOW()               |
+--------------------+---------------------+--------------------+---------------------+---------------------+
| SYSTEM             | SYSTEM              | UTC                | 2026-11-20 02:47:42 | 2026-11-20 02:47:42 |
+--------------------+---------------------+--------------------+---------------------+---------------------+
1 row in set

--------------
SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema = DATABASE()
--------------

+----------------------------+------------+
| TABLE_NAME                 | TABLE_ROWS |
+----------------------------+------------+
| deep_displacement_readings |          0 |
| gnss_readings              |    8395288 |
| rainfall_readings          |          0 |
| soil_pressure_readings     |          0 |
| strain_readings            |          0 |
+----------------------------+------------+
5 rows in set

--------------
SELECT partition_name, table_rows FROM information_schema.partitions WHERE table_schema = DATABASE() AND table_name = 'gnss_readings'
--------------

+----------------+------------+
| PARTITION_NAME | TABLE_ROWS |
+----------------+------------+
| p2024          |    8393499 |
| p2025          |          0 |
| p2026          |       1789 |
| p2027          |          0 |
| pmax           |          0 |
+----------------+------------+
5 rows in set

--------------
SELECT COUNT(*), MIN(received_at), MAX(received_at) FROM gnss_readings IGNORE INDEX (idx_gnss_sensor_ts, idx_gnss_project_ts, uk_gnss_message) WHERE received_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'
--------------

+----------+---------------------+---------------------+
| COUNT(*) | MIN(received_at)    | MAX(received_at)    |
+----------+---------------------+---------------------+
|  4328780 | 2026-09-23 12:31:21 | 2026-09-24 00:34:23 |
+----------+---------------------+---------------------+
1 row in set
```

Earlier run (02:18:32 UTC), `SELECT user, host FROM mysql.user`: exporter@%, revisor@%, root@%, svc_data_mgmt@%, mysql.infoschema@localhost, mysql.session@localhost, mysql.sys@localhost, root@localhost.

`received_at` storage: the column type is `datetime`, which stores no time zone. `@@system_time_zone = UTC` and `@@global.time_zone = @@session.time_zone = SYSTEM`. That is the server setting today; the data cannot show whether the writer converted values before inserting.

## Step 1: rows per sensor

Server run: started 2026-11-20 02:48:17 UTC, finished 02:48:45 UTC. Literal output: `raw/s1_out.txt`. Local recomputation: `step1_local.tsv` (identical counts).

```
SELECT sensor_id, COUNT(*) AS n, MIN(timestamp), MAX(timestamp)
FROM gnss_readings IGNORE INDEX (idx_gnss_sensor_ts, idx_gnss_project_ts, uk_gnss_message) WHERE received_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'
GROUP BY sensor_id ORDER BY sensor_id
--------------

+------------+-------+---------------------+---------------------+
| sensor_id  | n     | MIN(timestamp)      | MAX(timestamp)      |
+------------+-------+---------------------+---------------------+
| GXZM-DB000 | 43296 | 2019-06-26 00:41:22 | 2019-10-30 06:41:22 |
| GXZM-DB001 | 43296 | 2019-06-26 00:49:01 | 2019-10-30 06:49:01 |
| GXZM-DB002 | 43297 | 2019-06-26 00:13:48 | 2019-10-30 06:13:48 |
| GXZM-DB003 | 43297 | 2019-06-26 00:48:43 | 2019-10-30 06:48:43 |
| GXZM-DB004 | 43297 | 2019-06-26 00:09:21 | 2019-10-30 06:09:21 |
| GXZM-DB005 | 43296 | 2019-06-26 00:40:59 | 2019-10-30 06:40:59 |
| GXZM-DB006 | 43295 | 2019-06-26 00:10:56 | 2019-10-30 06:10:56 |
| GXZM-DB007 | 43295 | 2019-06-26 00:36:51 | 2019-10-30 06:36:51 |
| GXZM-DB008 | 43295 | 2019-06-26 00:21:19 | 2019-10-30 06:21:19 |
| GXZM-DB009 | 43295 | 2019-06-26 00:17:30 | 2019-10-30 06:17:30 |
| GXZM-DB010 | 43295 | 2019-06-26 00:53:32 | 2019-10-30 06:53:32 |
| GXZM-DB011 | 43295 | 2019-06-26 00:19:52 | 2019-10-30 06:19:52 |
| GXZM-DB012 | 43295 | 2019-06-26 00:27:13 | 2019-10-30 06:27:13 |
| GXZM-DB013 | 43296 | 2019-06-26 00:55:41 | 2019-10-30 06:55:41 |
| GXZM-DB014 | 43295 | 2019-06-26 00:09:53 | 2019-10-30 06:09:53 |
| GXZM-DB015 | 43295 | 2019-06-26 00:17:16 | 2019-10-30 06:17:16 |
| GXZM-DB016 | 43295 | 2019-06-26 00:33:11 | 2019-10-30 06:33:11 |
| GXZM-DB017 | 43294 | 2019-06-26 00:14:02 | 2019-10-30 06:14:02 |
| GXZM-DB018 | 43293 | 2019-06-26 00:11:01 | 2019-10-30 06:11:01 |
| GXZM-DB019 | 43293 | 2019-06-26 00:20:33 | 2019-10-30 06:20:33 |
| GXZM-DB020 | 43293 | 2019-06-26 00:03:57 | 2019-10-30 06:03:57 |
| GXZM-DB021 | 43293 | 2019-06-26 00:09:58 | 2019-10-30 06:09:58 |
| GXZM-DB022 | 43293 | 2019-06-26 00:23:54 | 2019-10-30 06:23:54 |
| GXZM-DB023 | 43293 | 2019-06-26 00:11:40 | 2019-10-30 06:11:40 |
| GXZM-DB024 | 43293 | 2019-06-26 00:06:43 | 2019-10-30 06:06:43 |
| GXZM-DB025 | 43292 | 2019-06-26 00:48:41 | 2019-10-30 06:48:41 |
| GXZM-DB026 | 43292 | 2019-06-26 00:52:12 | 2019-10-30 06:52:12 |
| GXZM-DB027 | 43292 | 2019-06-26 00:18:52 | 2019-10-30 06:18:52 |
| GXZM-DB028 | 43292 | 2019-06-26 00:52:25 | 2019-10-30 06:52:25 |
| GXZM-DB029 | 43292 | 2019-06-26 00:13:04 | 2019-10-30 06:13:04 |
| GXZM-DB030 | 43291 | 2019-06-26 00:22:45 | 2019-10-30 06:22:45 |
| GXZM-DB031 | 43290 | 2019-06-26 00:07:30 | 2019-10-30 06:07:30 |
| GXZM-DB032 | 43290 | 2019-06-26 00:06:44 | 2019-10-30 06:06:44 |
| GXZM-DB033 | 43290 | 2019-06-26 00:21:18 | 2019-10-30 06:21:18 |
| GXZM-DB034 | 43290 | 2019-06-26 00:25:45 | 2019-10-30 06:25:45 |
| GXZM-DB035 | 43291 | 2019-06-26 00:48:35 | 2019-10-30 06:48:35 |
| GXZM-DB036 | 43289 | 2019-06-26 00:03:57 | 2019-10-30 06:03:57 |
| GXZM-DB037 | 43289 | 2019-06-26 00:57:03 | 2019-10-30 06:57:03 |
| GXZM-DB038 | 43289 | 2019-06-26 00:54:45 | 2019-10-30 06:54:45 |
| GXZM-DB039 | 43290 | 2019-06-26 00:55:25 | 2019-10-30 06:55:25 |
| GXZM-DB040 | 43289 | 2019-06-26 00:31:34 | 2019-10-30 06:31:34 |
| GXZM-DB041 | 43289 | 2019-06-26 00:42:02 | 2019-10-30 06:42:02 |
| GXZM-DB042 | 43289 | 2019-06-26 00:31:46 | 2019-10-30 06:31:46 |
| GXZM-DB043 | 43288 | 2019-06-26 00:23:58 | 2019-10-30 06:23:58 |
| GXZM-DB044 | 43288 | 2019-06-26 00:03:05 | 2019-10-30 06:03:05 |
| GXZM-DB045 | 43288 | 2019-06-26 00:50:03 | 2019-10-30 06:50:03 |
| GXZM-DB046 | 43287 | 2019-06-26 00:58:20 | 2019-10-30 06:58:20 |
| GXZM-DB047 | 43287 | 2019-06-26 00:25:17 | 2019-10-30 06:25:17 |
| GXZM-DB048 | 43288 | 2019-06-26 00:41:11 | 2019-10-30 06:41:11 |
| GXZM-DB049 | 43287 | 2019-06-26 00:20:33 | 2019-10-30 06:20:33 |
| GXZM-DB050 | 43287 | 2019-06-26 00:57:18 | 2019-10-30 06:57:18 |
| GXZM-DB051 | 43287 | 2019-06-26 00:25:07 | 2019-10-30 06:25:07 |
| GXZM-DB052 | 43287 | 2019-06-26 00:37:33 | 2019-10-30 06:37:33 |
| GXZM-DB053 | 43287 | 2019-06-26 00:32:16 | 2019-10-30 06:32:16 |
| GXZM-DB054 | 43287 | 2019-06-26 00:18:43 | 2019-10-30 06:18:43 |
| GXZM-DB055 | 43286 | 2019-06-26 00:12:26 | 2019-10-30 06:12:26 |
| GXZM-DB056 | 43286 | 2019-06-26 00:53:32 | 2019-10-30 06:53:32 |
| GXZM-DB057 | 43286 | 2019-06-26 00:52:18 | 2019-10-30 06:52:18 |
| GXZM-DB058 | 43285 | 2019-06-26 00:24:54 | 2019-10-30 06:24:54 |
| GXZM-DB059 | 43285 | 2019-06-26 00:56:00 | 2019-10-30 06:56:00 |
| GXZM-DB060 | 43285 | 2019-06-26 00:38:42 | 2019-10-30 06:38:42 |
| GXZM-DB061 | 43286 | 2019-06-26 00:11:04 | 2019-10-30 06:11:04 |
| GXZM-DB062 | 43286 | 2019-06-26 00:44:21 | 2019-10-30 06:44:21 |
| GXZM-DB063 | 43286 | 2019-06-26 00:56:13 | 2019-10-30 06:56:13 |
| GXZM-DB064 | 43286 | 2019-06-26 00:00:49 | 2019-10-30 06:00:49 |
| GXZM-DB065 | 43286 | 2019-06-26 00:39:39 | 2019-10-30 06:39:39 |
| GXZM-DB066 | 43285 | 2019-06-26 00:21:05 | 2019-10-30 06:21:05 |
| GXZM-DB067 | 43285 | 2019-06-26 00:27:31 | 2019-10-30 06:27:31 |
| GXZM-DB068 | 43283 | 2019-06-26 00:10:30 | 2019-10-30 06:10:30 |
| GXZM-DB069 | 43283 | 2019-06-26 00:30:57 | 2019-10-30 06:30:57 |
| GXZM-DB070 | 43283 | 2019-06-26 00:59:44 | 2019-10-30 06:59:44 |
| GXZM-DB071 | 43283 | 2019-06-26 00:36:54 | 2019-10-30 06:36:54 |
| GXZM-DB072 | 43283 | 2019-06-26 00:41:28 | 2019-10-30 06:41:28 |
| GXZM-DB073 | 43284 | 2019-06-26 00:15:34 | 2019-10-30 06:15:34 |
| GXZM-DB074 | 43284 | 2019-06-26 00:46:21 | 2019-10-30 06:46:21 |
| GXZM-DB075 | 43284 | 2019-06-26 00:41:42 | 2019-10-30 06:41:42 |
| GXZM-DB076 | 43284 | 2019-06-26 00:36:58 | 2019-10-30 06:36:58 |
| GXZM-DB077 | 43284 | 2019-06-26 00:53:46 | 2019-10-30 06:53:46 |
| GXZM-DB078 | 43284 | 2019-06-26 00:04:01 | 2019-10-30 06:04:01 |
| GXZM-DB079 | 43284 | 2019-06-26 00:30:35 | 2019-10-30 06:30:35 |
| GXZM-DB080 | 43282 | 2019-06-26 00:16:27 | 2019-10-30 06:16:27 |
| GXZM-DB081 | 43281 | 2019-06-26 00:49:55 | 2019-10-30 06:49:55 |
| GXZM-DB082 | 43281 | 2019-06-26 00:54:22 | 2019-10-30 06:54:22 |
| GXZM-DB083 | 43281 | 2019-06-26 00:03:05 | 2019-10-30 06:03:05 |
| GXZM-DB084 | 43281 | 2019-06-26 00:24:44 | 2019-10-30 06:24:44 |
| GXZM-DB085 | 43281 | 2019-06-26 00:47:29 | 2019-10-30 06:47:29 |
| GXZM-DB086 | 43281 | 2019-06-26 00:33:47 | 2019-10-30 06:33:47 |
| GXZM-DB087 | 43282 | 2019-06-26 00:52:03 | 2019-10-30 06:52:03 |
| GXZM-DB088 | 43282 | 2019-06-26 00:18:02 | 2019-10-30 06:18:02 |
| GXZM-DB089 | 43282 | 2019-06-26 00:44:07 | 2019-10-30 06:44:07 |
| GXZM-DB090 | 43282 | 2019-06-26 00:48:37 | 2019-10-30 06:48:37 |
| GXZM-DB091 | 43283 | 2019-06-26 00:43:20 | 2019-10-30 06:43:20 |
| GXZM-DB092 | 43281 | 2019-06-26 00:38:07 | 2019-10-30 06:38:07 |
| GXZM-DB093 | 43280 | 2019-06-26 00:15:55 | 2019-10-30 05:15:55 |
| GXZM-DB094 | 43280 | 2019-06-26 00:25:05 | 2019-10-30 05:25:05 |
| GXZM-DB095 | 43280 | 2019-06-26 00:50:57 | 2019-10-30 05:50:57 |
| GXZM-DB096 | 43280 | 2019-06-26 00:08:29 | 2019-10-30 05:08:29 |
| GXZM-DB097 | 43280 | 2019-06-26 00:33:09 | 2019-10-30 05:33:09 |
| GXZM-DB098 | 43280 | 2019-06-26 00:40:59 | 2019-10-30 05:40:59 |
| GXZM-DB099 | 43280 | 2019-06-26 00:50:50 | 2019-10-30 05:50:50 |
+------------+-------+---------------------+---------------------+
100 rows in set
```

## Step 2: gaps in each sensor series

Query as specified (with the index hint). Server execution: OOM, see deviations. Result recomputed locally from the export (exported 2026-11-20 03:11:52–03:12:30 UTC, 4328780 rows, sha256 `faf0f99ee8cdc71d22dec2c448703632e0e924d379025a40fb7a05f354b4d4a3`).

```sql
WITH w AS (
  SELECT sensor_id, timestamp, received_at,
         LAG(timestamp)   OVER (PARTITION BY sensor_id ORDER BY timestamp) AS prev_ts,
         LAG(received_at) OVER (PARTITION BY sensor_id ORDER BY timestamp) AS prev_recv
  FROM gnss_readings IGNORE INDEX (idx_gnss_sensor_ts, idx_gnss_project_ts, uk_gnss_message) WHERE received_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21')
SELECT sensor_id, prev_ts, timestamp, prev_recv, received_at,
       TIMESTAMPDIFF(SECOND, prev_ts, timestamp)/3600 - 1 AS faltantes
FROM w WHERE TIMESTAMPDIFF(SECOND, prev_ts, timestamp) > 3600
ORDER BY received_at;
WITH w AS (
  SELECT sensor_id, timestamp, received_at,
         LAG(timestamp)   OVER (PARTITION BY sensor_id ORDER BY timestamp) AS prev_ts,
         LAG(received_at) OVER (PARTITION BY sensor_id ORDER BY timestamp) AS prev_recv
  FROM gnss_readings IGNORE INDEX (idx_gnss_sensor_ts, idx_gnss_project_ts, uk_gnss_message) WHERE received_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'),
g AS (SELECT *, TIMESTAMPDIFF(SECOND, prev_ts, timestamp) AS d,
   (prev_recv BETWEEN '2026-09-23 14:32:00' AND '2026-09-23 14:37:00'
    OR received_at BETWEEN '2026-09-23 14:32:00' AND '2026-09-23 14:37:00') AS in_outage
  FROM w WHERE prev_ts IS NOT NULL)
SELECT SUM(CASE WHEN d > 3600 THEN d/3600 - 1 END)                  AS a_total_faltantes,
       SUM(CASE WHEN d > 3600 AND in_outage THEN d/3600 - 1 END)     AS b_faltantes_1432_1437,
       SUM(CASE WHEN d > 3600 AND NOT in_outage THEN d/3600 - 1 END) AS c_faltantes_fuera,
       COUNT(*)                                                      AS d_pares_consecutivos,
       SUM(d = 3600)                                                 AS d_espaciado_3600,
       SUM(d < 3600)                                                 AS d_espaciado_menor_3600,
       SUM(d > 3600)                                                 AS d_espaciado_mayor_3600,
       SUM(d > 3600 AND MOD(d, 3600) <> 0)                           AS d_huecos_no_multiplo_3600,
       MIN(d) AS d_min, MAX(d) AS d_max
FROM g;
```

| Item | Value |
|---|---|
| Gap rows (`d > 3600`) | 0 |
| (a) total `faltantes` | 0 |
| (b) `faltantes` with `prev_recv` or `received_at` in 14:32:00–14:37:00 | 0 |
| (c) `faltantes` outside that interval | 0 |
| (d) consecutive pairs (rows with non-NULL `prev_ts`) | 4328680 |
| (d) pairs with `d = 3600` | 302993 |
| (d) pairs with `d < 3600` | 4025687 |
| (d) pairs with `d > 3600` | 0 |
| (d) gaps where `d` is not a multiple of 3600 | 0 |
| (d) min `d` / max `d` (s) | 0 / 3600 |

Spacing histogram (seconds: pairs): `0: 4025687`, `3600: 302993`. No other values occur.

CSV of all gaps: `huecos_paso2.csv`. It has the header only, 0 rows.

### Supporting data for step 2 (no interpretation)

- Distinct `timestamp` values per sensor: min 3030, max 3031, total 303,093. Rows: 4328780.
- Rows per (`sensor_id`, `timestamp`), as size: number of groups: `1:13, 2:12, 3:13, 4:12, 5:13, 6:13, 7:12, 8:13, 9:12, 10:43212, 11:11, 12:11, 13:121, 14:104, 15:259521`.
- Example: GXZM-DB000 at `timestamp = 2019-06-26 00:41:22` has 15 rows, each with a different `message_id`. Their `received_at` values run from 2026-09-23 12:31:21 to 12:31:48.
- There are 360 groups whose size is not 10 or 15 (`groups_size_not_10_15.tsv`). By hour of first `received_at`: 2026-09-23 14h: 204; 22h: 43; 2026-09-24 00h: 113. 204 of them overlap 14:32:00–14:37:00.
- Rows per minute of `received_at`, 14:28–14:41 UTC (`rows_per_minute_1428_1442.tsv`):

```
2026-09-23 14:28	6000
2026-09-23 14:29	6000
2026-09-23 14:30	6000
2026-09-23 14:31	6000
2026-09-23 14:32	6000
2026-09-23 14:33	5685
2026-09-23 14:34	5875
2026-09-23 14:35	5993
2026-09-23 14:36	6132
2026-09-23 14:37	6000
2026-09-23 14:38	6000
2026-09-23 14:39	6000
2026-09-23 14:40	6000
2026-09-23 14:41	6000
```

  Sum for 14:33–14:36: 5685 + 5875 + 5993 + 6132 = 23,685 (4 × 6000 = 24,000).

## Step 3: duplicates

Query as specified (with the index hint). Recomputed locally from the export.

```sql
SELECT sensor_id, timestamp, COUNT(*) c FROM gnss_readings IGNORE INDEX (idx_gnss_sensor_ts, idx_gnss_project_ts, uk_gnss_message)
WHERE received_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21' GROUP BY sensor_id, timestamp HAVING c > 1;
```

Result: 303080 rows, i.e. (`sensor_id`, `timestamp`) groups with `c > 1`. Full list: `duplicados_paso3.tsv`. The size distribution is in step 2 above.

## Step 4: the 105 "sink write failed" message_id

Source: `tifacusil/tesis-data-results`, `results/auditoria_resistencia/logs_b.json`, key `sink_write_failed_detalle`, element [2] of each entry. 105 entries, 105 distinct IDs (`raw/sink_ids.txt`). First entry: `2026-09-23T14:33:01.640070801Z`, pod `69b4v`, `34f9a2c7-ad41-4e70-8b29-7e699ae2c64f`, `buffer envelope 34f9a2c7-ad41-4e70-8b29-7e699ae2c64f: context canceled`.

Server run, no window filter: started 2026-11-20 03:12:31 UTC. Full query with all 105 IDs: `raw/s4.sql`. Literal output: `raw/s4_out.txt`.

```
SELECT message_id, sensor_id, timestamp, received_at FROM gnss_readings
WHERE message_id IN (<105 ids>)
--------------

Empty set
```

Found: 0 of 105. Cross-check: 0 of the 105 IDs occur in the window export (`sink_ids_en_ventana.tsv`).

## Step 5: alerts (early_warning)

Pod `mysql-early-warning-0`, MySQL 8.0.46, database `early_warning`, table `alerts` (UNIQUE `message_id`). Run 2026-11-20 02:29:57 UTC. Literal output: `raw/step5_out.txt`. The column used for the window is `created_at`.

```
SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM alerts
--------------

+----------+---------------------+---------------------+
| COUNT(*) | MIN(created_at)     | MAX(created_at)     |
+----------+---------------------+---------------------+
|     4252 | 2026-09-23 12:37:08 | 2026-09-30 03:54:24 |
+----------+---------------------+---------------------+
1 row in set

--------------
SELECT COUNT(*), COUNT(DISTINCT message_id), SUM(message_id IS NULL), MIN(created_at), MAX(created_at)
  FROM alerts WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'
--------------

+----------+----------------------------+-------------------------+---------------------+---------------------+
| COUNT(*) | COUNT(DISTINCT message_id) | SUM(message_id IS NULL) | MIN(created_at)     | MAX(created_at)     |
+----------+----------------------------+-------------------------+---------------------+---------------------+
|     3416 |                       3416 |                       0 | 2026-09-23 12:37:08 | 2026-09-24 00:34:07 |
+----------+----------------------------+-------------------------+---------------------+---------------------+
1 row in set

--------------
SELECT alert_level, COUNT(*) FROM alerts
  WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21' GROUP BY alert_level
--------------

+-------------+----------+
| alert_level | COUNT(*) |
+-------------+----------+
| red         |     1777 |
| blue        |      984 |
| orange      |      655 |
+-------------+----------+
3 rows in set

--------------
SELECT COUNT(*) FROM alerts WHERE created_at BETWEEN '2026-09-23 14:32:00' AND '2026-09-23 14:37:00'
--------------

+----------+
| COUNT(*) |
+----------+
|       28 |
+----------+
1 row in set

--------------
SELECT DATE_FORMAT(created_at,'%Y-%m-%d %H:00') h, COUNT(*) FROM alerts
  WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21' GROUP BY h ORDER BY h
--------------

+------------------+----------+
| h                | COUNT(*) |
+------------------+----------+
| 2026-09-23 12:00 |       80 |
| 2026-09-23 13:00 |      325 |
| 2026-09-23 14:00 |      293 |
| 2026-09-23 15:00 |      171 |
| 2026-09-23 16:00 |      338 |
| 2026-09-23 17:00 |      356 |
| 2026-09-23 18:00 |      218 |
| 2026-09-23 19:00 |      341 |
| 2026-09-23 20:00 |      308 |
| 2026-09-23 21:00 |      248 |
| 2026-09-23 22:00 |      209 |
| 2026-09-23 23:00 |      316 |
| 2026-09-24 00:00 |      213 |
+------------------+----------+
13 rows in set

--------------
SELECT DATE(created_at) d, COUNT(*) FROM alerts GROUP BY d ORDER BY d
--------------

+------------+----------+
| d          | COUNT(*) |
+------------+----------+
| 2026-09-23 |     3203 |
| 2026-09-24 |      213 |
| 2026-09-29 |        7 |
| 2026-09-30 |      829 |
+------------+----------+
4 rows in set
```

The table was not emptied by later runs: 836 more rows have `created_at` on 2026-09-29 and 2026-09-30. Reference values from the brief: 3414 alerts published, 3416 accepted by the push service.

## Files

| File | Content |
|---|---|
| `huecos_paso2.csv` | Step 2 gaps (0 rows) |
| `duplicados_paso3.tsv` | Step 3 duplicate groups |
| `groups_size_not_10_15.tsv` | Groups with size not 10 or 15, with `received_at` range |
| `rows_per_minute_1428_1442.tsv` | Rows per minute around the broker outage |
| `step1_local.tsv`, `summary.json` | Local recomputation |
| `raw/*.sql`, `raw/*_out.txt` | Exact queries and literal outputs |
| `raw/export.tsv.gz` | Window export (message_id, sensor_id, timestamp, received_at) |
| `raw/analyze.js` | Local recomputation script (`node analyze.js export.tsv sink_ids.txt outdir`) |
