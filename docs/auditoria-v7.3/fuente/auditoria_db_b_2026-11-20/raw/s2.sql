SET SESSION transaction_read_only = ON;
USE data_management;
SELECT CURRENT_USER(), @@version, @@hostname, UTC_TIMESTAMP() AS started_utc;
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
SELECT UTC_TIMESTAMP() AS finished_utc;
