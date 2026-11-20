SET SESSION transaction_read_only = ON;
USE early_warning;
SELECT CURRENT_USER(), @@version, @@hostname, @@system_time_zone, UTC_TIMESTAMP() AS started_utc;
SHOW CREATE TABLE alerts\G
SET @t0 = '2026-09-23 12:31:20', @t1 = '2026-09-24 00:39:21';
SELECT COUNT(*) alertas, COUNT(DISTINCT sensor_id, alert_timestamp) lecturas_distintas FROM alerts WHERE created_at >= @t0 AND created_at < @t1;
SELECT sensor_id, alert_timestamp, COUNT(*) n,
       GROUP_CONCAT(CONCAT(id, '|', alert_level, '|', created_at, '|', message_id) ORDER BY id SEPARATOR ' ; ') filas
FROM alerts
WHERE created_at >= @t0 AND created_at < @t1
GROUP BY sensor_id, alert_timestamp HAVING n > 1;
SELECT UTC_TIMESTAMP() AS finished_utc;
