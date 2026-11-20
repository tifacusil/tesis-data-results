-- NOT EXECUTED. Pending queries for V7.3; each needs the owner's confirmation and
-- access to System B. Read-only session; no GROUP BY over the full table
-- (the 320 MiB limit of the MySQL pod was exceeded on 2026-11-20).
-- Record for each run: exact text, pod, database, UTC start/end, output file and its SHA-256.

-- 1. mysql-data-management-0, database data_management
SET SESSION transaction_read_only = ON;
USE data_management;
SELECT CURRENT_USER(), @@version, @@hostname, @@system_time_zone, UTC_TIMESTAMP() AS started_utc;
SHOW CREATE TABLE gnss_readings;
-- Half-open window as requested (the 2026-11-20 run used BETWEEN; same result there).
SET @t0 = '2026-09-23 12:31:20', @t1 = '2026-09-24 00:39:21';  -- UTC, received_at
SELECT COUNT(*) AS filas, COUNT(DISTINCT message_id) AS ids
FROM gnss_readings IGNORE INDEX (idx_gnss_sensor_ts, idx_gnss_project_ts, uk_gnss_message)
WHERE received_at >= @t0 AND received_at < @t1;
SELECT UTC_TIMESTAMP() AS finished_utc;

-- 2. mysql-early-warning-0, database early_warning
SET SESSION transaction_read_only = ON;
USE early_warning;
SELECT CURRENT_USER(), @@version, @@hostname, @@system_time_zone, UTC_TIMESTAMP() AS started_utc;
SET @t0 = '2026-09-23 12:31:20', @t1 = '2026-09-24 00:39:21';  -- UTC, created_at
SELECT sensor_id, alert_timestamp, COUNT(*) n,
       GROUP_CONCAT(CONCAT(id, '|', alert_level, '|', created_at, '|', message_id) ORDER BY id SEPARATOR ' ; ') filas
FROM alerts
WHERE created_at >= @t0 AND created_at < @t1
GROUP BY sensor_id, alert_timestamp HAVING n > 1;
SELECT UTC_TIMESTAMP() AS finished_utc;
