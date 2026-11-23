# Read-only audit: ew_evaluations_total (System B early-warning), 12 h endurance test of 2026-09-23

Raw data only. No conclusions.

## Execution context

| Item | Value |
|---|---|
| Source | `respaldo-prometheus/B-prometheus-tsdb-20261014.tar.gz`, sha256 `7425191c484406224e51d576e87df158cd4dca7b6dd535229b683012bc561877` (matches the expected value) |
| Restore | Procedure from `tesis-data-results/docs/metrics-methodology.md` §9 (repo commit `51c1307`). Unpacked copy, container `prom-b`, port 9091, `--storage.tsdb.retention.time=100y`, config with no scrape jobs. |
| Prometheus | 3.5.4 (revision `9e1e3b5104fff654a84131b9854be18862569bb7`, go1.25.11), image `prom/prometheus:v3.5.4@sha256:a75c5a35bc21d7afe69551eefa3cb1e1fb1775fe759408007a66b54ec3de1f29` |
| Production | Steps 0–3: not touched. Step 4: one read-only MySQL session on `mysql-early-warning-0`, approved by the owner. |
| Execution time | Step 0: 2026-11-20T03:40:02Z. Steps 1–2: 2026-11-20T03:39:24.853Z – 2026-11-20T03:39:24.942Z. |
| Window | 2026-09-23T12:31:20Z – 2026-09-24T00:34:21Z (43,381 s); step 1 evaluated at `time=2026-09-24T00:34:21Z` |

## Step 0: verification

- sha256: matches.
- TSDB range: blocks 2026-09-15T16:47:50.624Z – 2026-10-14T00:00:00.000Z (17 blocks before start, all reported as `Found healthy block`), plus the WAL head 2026-10-14T00:00:00Z – 2026-10-14T02:08:45.971Z (`headStats`). The working copy was compacted by Prometheus after start; the archive is untouched. Current block list: `raw/blocks.tsv`.
- `ew_evaluations_total` sample range in the TSDB: 2026-09-15T17:59:56.304Z – 2026-10-14 (last sample 1791935994.508 = 2026-10-13T23:59:54.508Z).
- `ew_evaluations_total` exists on 23–24/09: 12 series. The labels are `app`, `instance`, `job`, `outcome`, `service`. **There is no `pod` label.** The two replicas differ by `instance` (`10.42.0.118:8080`, `10.42.0.119:8080`). Outcomes present: alert, fix_quality_not_rtk_fixed, gap_too_large_reset, none, previous_none, stale_reading_baseline_kept.
- Scrape interval: the backup holds no Prometheus configuration. Deduced from the raw sample timestamps of the 12 series in 12:25:00–00:40:00 (seconds: count of consecutive pairs): 14.969: 6, 14.973: 6, 14.987: 6, 14.988: 12, 14.989: 18, 14.99: 6, 14.991: 6, 14.992: 18, 14.993: 12, 14.994: 12, 14.995: 42, 14.996: 72, 14.997: 144, 14.998: 306, 14.999: 12, 15: 33936, 15.002: 282, 15.003: 144, 15.004: 72, 15.005: 54, 15.006: 12, 15.007: 12, 15.008: 18, 15.009: 6, 15.01: 6, 15.011: 18, 15.012: 12, 15.013: 6, 15.027: 6, 15.031: 6. No interval above 15.031 s.

Literal output (`raw/step0_output.txt`):

```
# executed 2026-11-20T03:40:02Z against http://localhost:9091 (local restore)
## sha256sum B-prometheus-tsdb-20261014.tar.gz
7425191c484406224e51d576e87df158cd4dca7b6dd535229b683012bc561877 *~/Escritorio/TESIS/respaldo-prometheus/B-prometheus-tsdb-20261014.tar.gz
## GET /api/v1/status/buildinfo
{"status":"success","data":{"version":"3.5.4","revision":"9e1e3b5104fff654a84131b9854be18862569bb7","branch":"HEAD","buildUser":"root@dc5fbd8f9a0f","buildDate":"20260617-14:17:38","goVersion":"go1.25.11"}}
## docker image
prom/prometheus:v3.5.4@sha256:a75c5a35bc21d7afe69551eefa3cb1e1fb1775fe759408007a66b54ec3de1f29
## docker logs prom-b | grep -c 'Found healthy block'
17
## GET /api/v1/status/tsdb (headStats)
{"numSeries":10434,"numLabelPairs":2682,"chunkCount":52134,"minTime":1791936000000,"maxTime":1791943725971}
## query: timestamp(ew_evaluations_total) first/last over whole TSDB
{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1791936000,"1789495196.304"]}]}}
{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":[1791936000,"1791935994.508"]}]}}
## query (time=2026-09-24T00:34:21Z): count by (__name__) ({__name__=~"ew_.*"})
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"__name__":"ew_alert_delivery_latency_seconds_bucket"},"value":[1790210061,"22"]},{"metric":{"__name__":"ew_alert_delivery_latency_seconds_count"},"value":[1790210061,"2"]},{"metric":{"__name__":"ew_alert_delivery_latency_seconds_sum"},"value":[1790210061,"2"]},{"metric":{"__name__":"ew_alerts_published_total"},"value":[1790210061,"6"]},{"metric":{"__name__":"ew_circuit_breaker_state"},"value":[1790210061,"4"]},{"metric":{"__name__":"ew_duplicates_skipped_total"},"value":[1790210061,"2"]},{"metric":{"__name__":"ew_eval_duration_seconds_bucket"},"value":[1790210061,"26"]},{"metric":{"__name__":"ew_eval_duration_seconds_count"},"value":[1790210061,"2"]},{"metric":{"__name__":"ew_eval_duration_seconds_sum"},"value":[1790210061,"2"]},{"metric":{"__name__":"ew_evaluations_total"},"value":[1790210061,"12"]},{"metric":{"__name__":"ew_messages_consumed_total"},"value":[1790210061,"2"]},{"metric":{"__name__":"ew_messages_dropped_total"},"value":[1790210061,"2"]},{"metric":{"__name__":"ew_outbound_calls_total"},"value":[1790210061,"2"]}]}}
## query (time=2026-09-24T00:34:21Z): group by (outcome, pod, instance, job) (ew_evaluations_total)
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"instance":"10.42.0.118:8080","job":"microservices","outcome":"alert"},"value":[1790210061,"1"]},{"metric":{"instance":"10.42.0.118:8080","job":"microservices","outcome":"fix_quality_not_rtk_fixed"},"value":[1790210061,"1"]},{"metric":{"instance":"10.42.0.118:8080","job":"microservices","outcome":"gap_too_large_reset"},"value":[1790210061,"1"]},{"metric":{"instance":"10.42.0.118:8080","job":"microservices","outcome":"none"},"value":[1790210061,"1"]},{"metric":{"instance":"10.42.0.118:8080","job":"microservices","outcome":"previous_none"},"value":[1790210061,"1"]},{"metric":{"instance":"10.42.0.118:8080","job":"microservices","outcome":"stale_reading_baseline_kept"},"value":[1790210061,"1"]},{"metric":{"instance":"10.42.0.119:8080","job":"microservices","outcome":"alert"},"value":[1790210061,"1"]},{"metric":{"instance":"10.42.0.119:8080","job":"microservices","outcome":"fix_quality_not_rtk_fixed"},"value":[1790210061,"1"]},{"metric":{"instance":"10.42.0.119:8080","job":"microservices","outcome":"gap_too_large_reset"},"value":[1790210061,"1"]},{"metric":{"instance":"10.42.0.119:8080","job":"microservices","outcome":"none"},"value":[1790210061,"1"]},{"metric":{"instance":"10.42.0.119:8080","job":"microservices","outcome":"previous_none"},"value":[1790210061,"1"]},{"metric":{"instance":"10.42.0.119:8080","job":"microservices","outcome":"stale_reading_baseline_kept"},"value":[1790210061,"1"]}]}}
## GET /api/v1/series match[]=ew_evaluations_total start=2026-09-23T00:00:00Z end=2026-09-24T12:00:00Z
{"status":"success","data":[{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.118:8080","job":"microservices","outcome":"alert","service":"early-warning"},{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.118:8080","job":"microservices","outcome":"fix_quality_not_rtk_fixed","service":"early-warning"},{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.118:8080","job":"microservices","outcome":"gap_too_large_reset","service":"early-warning"},{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.118:8080","job":"microservices","outcome":"none","service":"early-warning"},{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.118:8080","job":"microservices","outcome":"previous_none","service":"early-warning"},{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.118:8080","job":"microservices","outcome":"stale_reading_baseline_kept","service":"early-warning"},{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.119:8080","job":"microservices","outcome":"alert","service":"early-warning"},{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.119:8080","job":"microservices","outcome":"fix_quality_not_rtk_fixed","service":"early-warning"},{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.119:8080","job":"microservices","outcome":"gap_too_large_reset","service":"early-warning"},{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.119:8080","job":"microservices","outcome":"none","service":"early-warning"},{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.119:8080","job":"microservices","outcome":"previous_none","service":"early-warning"},{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.119:8080","job":"microservices","outcome":"stale_reading_baseline_kept","service":"early-warning"}]}
## query (time=2026-09-23T18:00:00Z): ew_evaluations_total{outcome="none"}[2m]
{"status":"success","data":{"resultType":"matrix","result":[{"metric":{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.118:8080","job":"microservices","outcome":"none","service":"early-warning"},"values":[[1790186283.935,"85840"],[1790186298.935,"85884"],[1790186313.935,"85918"],[1790186328.935,"85956"],[1790186343.935,"85998"],[1790186358.935,"86040"],[1790186373.935,"86069"],[1790186388.935,"86113"]]},{"metric":{"__name__":"ew_evaluations_total","app":"early-warning","instance":"10.42.0.119:8080","job":"microservices","outcome":"none","service":"early-warning"},"values":[[1790186287.616,"85601"],[1790186302.616,"85661"],[1790186317.616,"85726"],[1790186332.616,"85784"],[1790186347.616,"85846"],[1790186362.616,"85909"],[1790186377.616,"85981"],[1790186392.616,"86046"]]}]}}
```

## Step 1: increase per outcome over the window

`/api/v1/query`, `time=2026-09-24T00:34:21Z`.

```
sum by (outcome) (increase(ew_evaluations_total[43381s]))
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"outcome":"alert"},"value":[1790210061,"3417.260371267151"]},{"metric":{"outcome":"fix_quality_not_rtk_fixed"},"value":[1790210061,"432284.4373342558"]},{"metric":{"outcome":"gap_too_large_reset"},"value":[1790210061,"81.02988585264615"]},{"metric":{"outcome":"none"},"value":[1790210061,"299365.41346708173"]},{"metric":{"outcome":"previous_none"},"value":[1790210061,"96.03542026980284"]},{"metric":{"outcome":"stale_reading_baseline_kept"},"value":[1790210061,"3594153.6139282836"]}]}}

sum by (outcome, pod) (increase(ew_evaluations_total[43381s]))
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"outcome":"alert"},"value":[1790210061,"3417.260371267151"]},{"metric":{"outcome":"fix_quality_not_rtk_fixed"},"value":[1790210061,"432284.4373342558"]},{"metric":{"outcome":"gap_too_large_reset"},"value":[1790210061,"81.02988585264615"]},{"metric":{"outcome":"none"},"value":[1790210061,"299365.41346708173"]},{"metric":{"outcome":"previous_none"},"value":[1790210061,"96.03542026980284"]},{"metric":{"outcome":"stale_reading_baseline_kept"},"value":[1790210061,"3594153.6139282836"]}]}}
```

There is no `pod` label, so the per-replica query as specified returns the same groups as the first one. Adapted query (change: `pod` replaced by `instance`):

```
sum by (outcome, instance) (increase(ew_evaluations_total[43381s]))
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"instance":"10.42.0.118:8080","outcome":"alert"},"value":[1790210061,"1662.6132134209618"]},{"metric":{"instance":"10.42.0.118:8080","outcome":"fix_quality_not_rtk_fixed"},"value":[1790210061,"216071.69265536725"]},{"metric":{"instance":"10.42.0.118:8080","outcome":"gap_too_large_reset"},"value":[1790210061,"45.01660325147008"]},{"metric":{"instance":"10.42.0.118:8080","outcome":"none"},"value":[1790210061,"146942.1959644875"]},{"metric":{"instance":"10.42.0.118:8080","outcome":"previous_none"},"value":[1790210061,"44.0162342903263"]},{"metric":{"instance":"10.42.0.118:8080","outcome":"stale_reading_baseline_kept"},"value":[1790210061,"1799789.8075867635"]},{"metric":{"instance":"10.42.0.119:8080","outcome":"alert"},"value":[1790210061,"1754.6471578461894"]},{"metric":{"instance":"10.42.0.119:8080","outcome":"fix_quality_not_rtk_fixed"},"value":[1790210061,"216212.74467888853"]},{"metric":{"instance":"10.42.0.119:8080","outcome":"gap_too_large_reset"},"value":[1790210061,"36.013282601176066"]},{"metric":{"instance":"10.42.0.119:8080","outcome":"none"},"value":[1790210061,"152423.21750259426"]},{"metric":{"instance":"10.42.0.119:8080","outcome":"previous_none"},"value":[1790210061,"52.01918597947654"]},{"metric":{"instance":"10.42.0.119:8080","outcome":"stale_reading_baseline_kept"},"value":[1790210061,"1794363.8063415198"]}]}}
```

## Step 2: check without extrapolation

Exports, both evaluated against the restore:

- `/api/v1/query_range?query=ew_evaluations_total&start=2026-09-23T12:25:00Z&end=2026-09-24T00:40:00Z&step=15s` (as specified).
- Raw samples: `/api/v1/query?query=ew_evaluations_total[44101s]&time=2026-09-24T00:40:00Z` (range selector; returns the stored samples without step alignment; 44101 s so that 12:25:00 is included).

CSV of both: `ew_evaluations_samples.csv` (`source,outcome,instance,timestamp_unix,timestamp_utc,value`). Manual method: sum of consecutive differences; when the counter drops, the new value is added (restart from 0).

Columns:
- *increase*: step 1, per `(outcome, instance)`.
- *window*: raw samples with timestamp in (12:31:20Z, 00:34:21Z].
- *export range*: raw samples in [12:25:00Z, 00:40:00Z].
- *query_range*: query_range samples, same export range.

| outcome | instance | increase | first raw sample in window | last raw sample in window | manual (window) | resets | samples | manual (export range) | resets | samples | manual (query_range) | resets | samples |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| alert | 10.42.0.118:8080 | 1662.613213 | 192 @ 2026-09-23T12:31:33.935Z | 1854 @ 2026-09-24T00:34:18.935Z | 1662 | 0 | 2892 | 1662 | 0 | 2940 | 1662 | 0 | 2941 |
| alert | 10.42.0.119:8080 | 1754.647158 | 195 @ 2026-09-23T12:31:22.616Z | 1949 @ 2026-09-24T00:34:07.616Z | 1754 | 0 | 2892 | 1754 | 0 | 2940 | 1754 | 0 | 2941 |
| fix_quality_not_rtk_fixed | 10.42.0.118:8080 | 216071.692655 | 24303 @ 2026-09-23T12:31:33.935Z | 240295 @ 2026-09-24T00:34:18.935Z | 215992 | 0 | 2892 | 216225 | 0 | 2940 | 216225 | 0 | 2941 |
| fix_quality_not_rtk_fixed | 10.42.0.119:8080 | 216212.744679 | 23981 @ 2026-09-23T12:31:22.616Z | 240114 @ 2026-09-24T00:34:07.616Z | 216133 | 0 | 2892 | 216403 | 0 | 2940 | 216403 | 0 | 2941 |
| gap_too_large_reset | 10.42.0.118:8080 | 45.016603 | 11 @ 2026-09-23T12:31:33.935Z | 56 @ 2026-09-24T00:34:18.935Z | 45 | 0 | 2892 | 45 | 0 | 2940 | 45 | 0 | 2941 |
| gap_too_large_reset | 10.42.0.119:8080 | 36.013283 | 5 @ 2026-09-23T12:31:22.616Z | 41 @ 2026-09-24T00:34:07.616Z | 36 | 0 | 2892 | 36 | 0 | 2940 | 36 | 0 | 2941 |
| none | 10.42.0.118:8080 | 146942.195964 | 21901 @ 2026-09-23T12:31:33.935Z | 168789 @ 2026-09-24T00:34:18.935Z | 146888 | 0 | 2892 | 147002 | 0 | 2940 | 147002 | 0 | 2941 |
| none | 10.42.0.119:8080 | 152423.217503 | 14782 @ 2026-09-23T12:31:22.616Z | 167149 @ 2026-09-24T00:34:07.616Z | 152367 | 0 | 2892 | 152536 | 0 | 2940 | 152536 | 0 | 2941 |
| previous_none | 10.42.0.118:8080 | 44.016234 | 1345 @ 2026-09-23T12:31:33.935Z | 1389 @ 2026-09-24T00:34:18.935Z | 44 | 0 | 2892 | 100 | 0 | 2940 | 100 | 0 | 2941 |
| previous_none | 10.42.0.119:8080 | 52.019186 | 759 @ 2026-09-23T12:31:22.616Z | 811 @ 2026-09-24T00:34:07.616Z | 52 | 0 | 2892 | 100 | 0 | 2940 | 100 | 0 | 2941 |
| stale_reading_baseline_kept | 10.42.0.118:8080 | 1799789.807587 | 195764 @ 2026-09-23T12:31:33.935Z | 1994890 @ 2026-09-24T00:34:18.935Z | 1799126 | 0 | 2892 | 1800955 | 0 | 2940 | 1800955 | 0 | 2941 |
| stale_reading_baseline_kept | 10.42.0.119:8080 | 1794363.806342 | 203813 @ 2026-09-23T12:31:22.616Z | 1997515 @ 2026-09-24T00:34:07.616Z | 1793702 | 0 | 2892 | 1795986 | 0 | 2940 | 1795986 | 0 | 2941 |

Resets detected: 0 in every series, in every method.

## Step 3: coherence

| Method | Sum of all outcomes | outcome="alert" | none + alert |
|---|---|---|---|
| increase | 4329397.790407 | 3417.260371 | 302782.673838 |
| manual_raw_window | 4327801 | 3416 | 302671 |
| manual_raw_export_range | 4332804 | 3416 | 302954 |
| manual_query_range_export_range | 4332804 | 3416 | 302954 |

By outcome and method:

| outcome | increase | manual_raw_window | manual_raw_export_range | manual_query_range_export_range |
|---|---|---|---|---|
| alert | 3417.260371 | 3416 | 3416 | 3416 |
| fix_quality_not_rtk_fixed | 432284.437334 | 432125 | 432628 | 432628 |
| gap_too_large_reset | 81.029886 | 81 | 81 | 81 |
| none | 299365.413467 | 299255 | 299538 | 299538 |
| previous_none | 96.035420 | 96 | 200 | 200 |
| stale_reading_baseline_kept | 3594153.613928 | 3592828 | 3596941 | 3596941 |

Reference values from the brief: 4,328,780 confirmed frames; 3,416 rows in `alerts`; 3,414 from the publication counter; 303,093 distinct timestamps in `gnss_readings`.

| Item | Value | Reference | Difference |
|---|---|---|---|
| Sum of all outcomes, increase | 4329397.790407 | 4328780 | 617.790407 |
| Sum of all outcomes, manual (window) | 4327801 | 4328780 | -979 |
| Sum of all outcomes, manual (export range) | 4332804 | 4328780 | 4024 |
| alert, increase | 3417.260371 | 3416 / 3414 | 1.260371 / 3.260371 |
| alert, manual (window) | 3416 | 3416 / 3414 | 0 / 2 |
| none + alert, increase | 302782.673838 | 303093 | -310.326162 |
| none + alert, manual (window) | 302671 | 303093 | -422 |
| none + alert, manual (export range) | 302954 | 303093 | -139 |

## Step 4: duplicate alerts per reading (production MySQL)

Run on `mysql-early-warning-0` (production) with explicit owner approval, overriding the "nothing on production" restriction for this step only. MySQL 8.0.46, user `root@localhost` (the `revisor` password was not available), `SET SESSION transaction_read_only = ON`. Finished 2026-11-20 03:46:36 UTC. Pod before and after: `Running`, 0 restarts, 173Mi.

Schema change: `alerts` has no `timestamp` column (literal error below). The adapted query uses `alert_timestamp`. The original query was also run, last, to record its error. Full script: `raw/step4.sql`. Literal output: `raw/step4_output.txt` (stderr is interleaved with stdout in that file; the `ERROR 1054` line belongs to the last query).

```
mysql-early-warning-0   16m   173Mi   
rc=1
--------------
SET SESSION transaction_read_only = ON
--------------

Query OK, 0 rows affected

--------------
SELECT CURRENT_USER(), @@version, @@hostname, UTC_TIMESTAMP() AS started_utc
--------------

+----------------+-----------+-----------------------+---------------------+
| CURRENT_USER() | @@version | @@hostname            | started_utc         |
+----------------+-----------+-----------------------+---------------------+
| root@localhost | 8.0.46    | mysql-early-warning-0 | 2026-11-20 03:46:36 |
+----------------+-----------+-----------------------+---------------------+
1 row in set

--------------
SHOW CREATE TABLE alerts
--------------

+--------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Table  | Create Table                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
+--------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| alerts | CREATE TABLE `alerts` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime NOT NULL,
  `message_id` varchar(64) DEFAULT NULL,
  `project_id` varchar(64) NOT NULL,
  `sensor_id` varchar(64) NOT NULL,
  `alert_level` enum('blue','orange','red') NOT NULL,
  `deformation_speed_mm_day` double DEFAULT NULL,
  `threshold_mm_day` double DEFAULT NULL,
  `alert_timestamp` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_alert_message` (`message_id`),
  KEY `idx_alerts_project_ts` (`project_id`,`alert_timestamp`)
) ENGINE=InnoDB AUTO_INCREMENT=4253 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci |
+--------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
1 row in set

--------------
SELECT COUNT(*) FROM (
  SELECT sensor_id, alert_timestamp, COUNT(*) c FROM alerts
  WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'
  GROUP BY sensor_id, alert_timestamp HAVING c > 1) t
--------------

+----------+
|ERROR 1054 (42S22) at line 16: Unknown column 'timestamp' in 'field list'
 COUNT(*) |
+----------+
|        2 |
+----------+
1 row in set

--------------
SELECT sensor_id, alert_timestamp, COUNT(*) c, MIN(created_at), MAX(created_at), GROUP_CONCAT(alert_level ORDER BY id) levels
  FROM alerts
  WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'
  GROUP BY sensor_id, alert_timestamp HAVING c > 1 ORDER BY MIN(created_at)
--------------

+------------+---------------------+---+---------------------+---------------------+-----------+
| sensor_id  | alert_timestamp     | c | MIN(created_at)     | MAX(created_at)     | levels    |
+------------+---------------------+---+---------------------+---------------------+-----------+
| GXZM-DB050 | 2019-07-17 01:57:18 | 2 | 2026-09-23 14:33:27 | 2026-09-23 14:33:27 | red,red   |
| GXZM-DB086 | 2019-09-03 13:33:47 | 2 | 2026-09-23 19:10:21 | 2026-09-23 19:10:22 | blue,blue |
+------------+---------------------+---+---------------------+---------------------+-----------+
2 rows in set

--------------
SELECT COUNT(*), COUNT(DISTINCT sensor_id, alert_timestamp), SUM(alert_timestamp IS NULL)
  FROM alerts WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'
--------------

+----------+--------------------------------------------+------------------------------+
| COUNT(*) | COUNT(DISTINCT sensor_id, alert_timestamp) | SUM(alert_timestamp IS NULL) |
+----------+--------------------------------------------+------------------------------+
|     3416 |                                       3414 |                            0 |
+----------+--------------------------------------------+------------------------------+
1 row in set

--------------
SELECT UTC_TIMESTAMP() AS finished_utc
--------------

+---------------------+
| finished_utc        |
+---------------------+
| 2026-11-20 03:46:36 |
+---------------------+
1 row in set

--------------
SELECT COUNT(*) FROM (
  SELECT sensor_id, timestamp, COUNT(*) c FROM alerts
  WHERE created_at BETWEEN '2026-09-23 12:31:20' AND '2026-09-24 00:39:21'
  GROUP BY sensor_id, timestamp HAVING c > 1) t
--------------

Bye
command terminated with exit code 1
mysql-early-warning-0   1/1   Running   0     65d
```

| Item | Value |
|---|---|
| (`sensor_id`, `alert_timestamp`) groups with `c > 1` | 2 |
| GXZM-DB050, 2019-07-17 01:57:18 | 2 rows, red,red, created 2026-09-23 14:33:27 (both) |
| GXZM-DB086, 2019-09-03 13:33:47 | 2 rows, blue,blue, created 2026-09-23 19:10:21 and 19:10:22 |
| Rows in window / distinct (`sensor_id`, `alert_timestamp`) | 3416 / 3414 |
| Original query (`timestamp`) | `ERROR 1054 (42S22) at line 16: Unknown column 'timestamp' in 'field list'` |

## Files

| File | Content |
|---|---|
| `ew_evaluations_samples.csv` | Step 2 samples (raw and query_range) |
| `ew_result.json` | Step 1–3 results |
| `raw/ew_api_log.json` | Every API request of steps 1–2 with its literal response and UTC time |
| `raw/step0_output.txt` | Step 0 literal output |
| `raw/step4.sql`, `raw/step4_output.txt` | Step 4 script and literal output |
| `raw/blocks.tsv` | Block list of the working copy after start |
| `raw/audit_ew.js` | Script for steps 1–2 (`node audit_ew.js <outdir>`) |
