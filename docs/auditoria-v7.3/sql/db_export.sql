SET SESSION transaction_read_only = ON;
USE data_management;
SELECT message_id, sensor_id, timestamp, received_at
FROM gnss_readings IGNORE INDEX (idx_gnss_sensor_ts, idx_gnss_project_ts, uk_gnss_message)
WHERE received_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21';
