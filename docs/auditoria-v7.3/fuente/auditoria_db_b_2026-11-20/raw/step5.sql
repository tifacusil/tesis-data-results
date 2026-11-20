SET SESSION transaction_read_only = ON;
USE early_warning;
SELECT CURRENT_USER(), @@version, @@hostname, UTC_TIMESTAMP();
SHOW CREATE TABLE alerts\G
SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM alerts;
SELECT COUNT(*), COUNT(DISTINCT message_id), SUM(message_id IS NULL), MIN(created_at), MAX(created_at)
  FROM alerts WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21';
SELECT alert_level, COUNT(*) FROM alerts
  WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21' GROUP BY alert_level;
SELECT COUNT(*) FROM alerts WHERE created_at BETWEEN '2026-09-23 14:32:00' AND '2026-09-23 14:37:00';
SELECT DATE_FORMAT(created_at,'%Y-%m-%d %H:00') h, COUNT(*) FROM alerts
  WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21' GROUP BY h ORDER BY h;
SELECT DATE(created_at) d, COUNT(*) FROM alerts GROUP BY d ORDER BY d;
