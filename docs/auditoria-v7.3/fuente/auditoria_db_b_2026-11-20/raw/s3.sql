SET SESSION transaction_read_only = ON;
USE data_management;
SELECT CURRENT_USER(), @@version, @@hostname, UTC_TIMESTAMP() AS started_utc;
SELECT sensor_id, timestamp, COUNT(*) c FROM gnss_readings IGNORE INDEX (idx_gnss_sensor_ts, idx_gnss_project_ts, uk_gnss_message)
WHERE received_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21' GROUP BY sensor_id, timestamp HAVING c > 1;
SELECT UTC_TIMESTAMP() AS finished_utc;
