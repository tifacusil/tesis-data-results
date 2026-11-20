SET SESSION transaction_read_only = ON;
USE data_management;
SELECT CURRENT_USER(), @@version, @@hostname, UTC_TIMESTAMP() AS started_utc;
SELECT @@global.time_zone, @@session.time_zone, @@system_time_zone, UTC_TIMESTAMP(), NOW();
SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema = DATABASE();
SELECT partition_name, table_rows FROM information_schema.partitions WHERE table_schema = DATABASE() AND table_name = 'gnss_readings';
SELECT COUNT(*), MIN(received_at), MAX(received_at) FROM gnss_readings IGNORE INDEX (idx_gnss_sensor_ts, idx_gnss_project_ts, uk_gnss_message) WHERE received_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21';
SELECT UTC_TIMESTAMP() AS finished_utc;
