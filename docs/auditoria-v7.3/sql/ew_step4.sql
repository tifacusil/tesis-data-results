SET SESSION transaction_read_only = ON;
USE early_warning;
SELECT CURRENT_USER(), @@version, @@hostname, UTC_TIMESTAMP() AS started_utc;
SHOW CREATE TABLE alerts;
SELECT COUNT(*) FROM (
  SELECT sensor_id, alert_timestamp, COUNT(*) c FROM alerts
  WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'
  GROUP BY sensor_id, alert_timestamp HAVING c > 1) t;
SELECT sensor_id, alert_timestamp, COUNT(*) c, MIN(created_at), MAX(created_at), GROUP_CONCAT(alert_level ORDER BY id) levels
  FROM alerts
  WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'
  GROUP BY sensor_id, alert_timestamp HAVING c > 1 ORDER BY MIN(created_at);
SELECT COUNT(*), COUNT(DISTINCT sensor_id, alert_timestamp), SUM(alert_timestamp IS NULL)
  FROM alerts WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21';
SELECT UTC_TIMESTAMP() AS finished_utc;
SELECT COUNT(*) FROM (
  SELECT sensor_id, timestamp, COUNT(*) c FROM alerts
  WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'
  GROUP BY sensor_id, timestamp HAVING c > 1) t;
