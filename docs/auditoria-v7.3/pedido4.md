# Pedido 4 — the seven [FALTA] marks of V7.4

Run on 2026-11-21 (UTC). All times are UTC. Material in `v74_2026-11-21/`; every file is listed in `SHA256SUMS`. Repository files were only read; the server of B was only read (`kubectl get`, `crictl inspecti`, `grep` of the containerd log), with the `gotesis` key and, for the containerd log, `sudo`.

## 1. Early-warning image digests

Source: containerd log of the node of B (`/var/lib/rancher/k3s/agent/containerd/containerd.log`, SHA-256 on the server `69ea2e173f672d754e668fe030d196d61d91b4ffbfd59bcf065590ed2f262224`), excerpt in `v74_2026-11-21/raw/servidor/containerd_early_warning.txt` (with the log line numbers), and `kubectl get pods` of 2026-11-21 05:49 in `raw/servidor/kubectl_early_warning.txt`.

| run | pods | pulled (containerd) | repo digest | image id |
|---|---|---|---|---|
| 12 h (23/09) | `early-warning-697ddb9db5-zjxkk`, `-zvxgk` | 05:17:54.747, 05:18:07.826 | `sha256:94bdbcf8b255cae290d6897b213cd57e209a253af507d1e7a11ed1edf0bb48a2` | `sha256:1fdabdb3ce8362b6431e8adee337ff2f844f6cdabd92f430fdbeec1a9a227a31` |
| directed tests (29–30/09) | `early-warning-55859f5589-chqw5`, `-cgprm` | 2026-09-29 22:08:53.713, 22:09:09.274 | `sha256:d5bae3eeaf58c5e0aaf962f00ce987e470bf12a91d85a19dfe1fd9d6d41026ad` | `sha256:2db1d66556f1789e47584da4f14d4f9f36b8e7eb5bf7b8abe4a8afbd36cb2efe` |

- `697ddb9db5-zjxkk` and `-zvxgk` are the two replicas of the 12 h run (`pedido2.md` §2.1, `kube_pod_info`). The previous ReplicaSet `b46bf9db6` (05:15:20) still pulled the older `sha256:b10580a2…`; it was replaced before the first run of B (05:23:18).
- The `55859f5589` pods still run `d5bae3ee…` (0 restarts); `crictl inspecti` gives `created` 2026-09-29T22:08:19.578856911Z.
- `94bdbcf8…` is no longer in the node's store: containerd logged `ImageDelete` for it on 2026-11-20 02:57:50 (line 169737). Its log lines from 23/09 are the remaining evidence.
- **`d5bae3ee…` was built from `fd5a866`.** The CD workflow builds with `VERSION=<commit verified by CI>` and links it into `main.version` (`go-early-warning@fd5a866` `.github/workflows/cd.yml:47-58`, `Dockerfile:14-16`); the two pods that run `d5bae3ee…` log `version=fd5a866db21bfcb08066ded89b5ad51ab3b82b22` at start-up (`v73_b_2026-11-20/pedido2/raw/logs_ew/…/0.log`, first line). Commit 22:02:40Z, image 22:08:19Z, pull 22:08:53Z.
- **Commit of `94bdbcf8…`: not recorded.** The logs of the 23/09 pods are not kept and the image is gone. The only merge to `main` between `d734f7f` (2026-09-15T15:21:31Z) and `fd5a866` is `e31b2b8` (2026-09-23T05:09:10Z); the image was built at 05:15:40Z. Candidate, not verified.
- **Registry: private.** The Deployment pulls with `imagePullSecrets: ghcr`. On 2026-11-21, without credentials, GHCR refused an anonymous pull token for all six images of B (`UNAUTHORIZED: authentication required`), and both early-warning digests returned `403`. Controls: a public image (`github/super-linter`) got a token; a nonexistent name under the same account got `DENIED`, so `UNAUTHORIZED` means the images exist and are private. A digest is a content hash: it does not name the account and does not resolve without credentials; the image reference `ghcr.io/<account>/…` does name it. Repeated at 2026-11-21 06:54 with the same result. If the packages are made public, repeat this check before publishing a digest.

## Persistence of the 3740 buffered frames

There is no dedicated `.sql`. `outputs/b4_ids_de_logs_en_gnss_readings.csv` comes from `contar_message_id.py` over the export of the window (`raw/export.tsv.gz`, not published; SHA-256 in `README.md`). The SQL of that chain is the export query, `sql/db_export.sql` (same bytes as `fuente/auditoria_db_b_2026-11-20/raw/export.sql`). The related check of the 105 «sink write failed» ids (0 rows) is `v73_b_2026-11-20/pedido2/raw/sql/p2_dm.sql`, output `pedido2/p2_ids_105_en_gnss_readings.csv`; audit 1 version `sql/db_s4.sql`.
- `experiment-manifest.json` holds the seven full digests (six of the campaign, early-warning of the directed tests); its early-warning sources now point here.

## 2–3. E4: chunked SQL count of `gnss_readings`

**Live instance**, not a backup: pod `mysql-data-management-0`, MySQL 8.0.46, database `data_management`, `root@localhost` with `transaction_read_only = ON` (`v73_b_2026-11-20/dm_contexto.csv`).

| part | SQL | raw output | executed (UTC) |
|---|---|---|---|
| 1 h chunks 1–4 (chunk 5 stopped with `KILL QUERY`) | `v73_b_2026-11-20/raw/dm.sql` | `raw/dm_out.txt`, `raw/mem.log` | 2026-11-20 15:08:31–15:10:15 |
| 15 min chunks (33) | `v73_b_2026-11-20/raw/dm2/dm2.sql` (runner `raw/dm2/run_dm2.sh`) | `raw/dm2/dm2_out.txt`, `raw/dm2/mem.log` | 2026-11-20 15:16:46–15:26:32 |
| combined | — | `v73_b_2026-11-20/dm_tramos_completo.csv`: 37 contiguous chunks, 4 328 780 rows = 4 328 780 ids | — |

The column `fin_utc` is the **start** of each statement, not its end: MySQL evaluates `UTC_TIMESTAMP()` once, at statement start. Chunk 1 has `fin_utc` 15:16:46 while `raw/dm2/mem.log` shows it running until after 15:17:01.

## 4. Duplicate alerts

SQL `v73_b_2026-11-20/raw/ew.sql`, run on live `mysql-early-warning-0` at 2026-11-20 15:11:46; output `raw/ew_out.txt`; list `v73_b_2026-11-20/ew_alertas_duplicadas.csv`. `alerts` has no `reading_id`: a reading is (`sensor_id`, `alert_timestamp`); each alert has its own `message_id` (`uk_alert_message`).

| reading | alert ids |
|---|---|
| GXZM-DB050 @ 2019-07-17 01:57:18 | 535, 536 |
| GXZM-DB086 @ 2019-09-03 13:33:47 | 1840, 1841 |

## 5. Initial values of `ew_alerts_published_total`

Script `derivar.py`, output `outputs/b3_ew_alertas_por_serie.csv`, input `results/auditoria_resistencia/prometheus/B__ew_alerts.json`; cross-check `v73_b_2026-11-20/pedido2/p2_promql_resultados.csv` (instant queries at @t0 and @t1). The `level="orange"` series do not exist at @t0; the initial value is their first TSDB sample (1 at 12:55:03.935Z on 10.42.0.118, 1 at 12:54:52.616Z on 10.42.0.119), and `incremento_con_nacimiento` adds it, assuming the counter was created at 0.

## 6–7. Breaker rejections and alerts after closure

Script `v74_2026-11-21/calcular_v74.py` (self-check included), output `v74_2026-11-21/rechazos_y_alertas_tras_cierre.csv`, from the early-warning logs of `pedido2.md`. Closure = first OK call after removal (`cronologia_breaker_resumen.csv`); end of record = last log event of the run's driver (round 63). An alert counts from its `alert_emitted` line, written only after `recordAlert` succeeds (`consumer.go:419-436`).

| run | injection–removal | rejections cgprm / chqw5 | total | removal–closure | run total (= TSDB) |
|---|---|---|---|---|---|
| 1 | 244.0 s | 90 / 95 | **185** | 2 + 3 | 190 |
| 2 | 243.0 s | 85 / 84 | **169** | 3 + 2 | 174 |
| 3 | 243.0 s | 94 / 84 | **178** | 3 + 2 | 183 |

The ≈264 s Prometheus window ends after closure, so it includes the 5 rejections between removal and closure (174 and 183 in runs 2 and 3). Run 1 gives 133 because both `outcome="circuit_open"` series start during the test (first values 40 and 17) and the delta from the first non-NaN sample leaves those 57 out.

| run | closure → end of record (2026-09-30) | recorded | notified (`delivered`) | no push |
|---|---|---|---|---|
| 1 | 03:37:28.984–03:37:43.854 (14.9 s) | 23 (cgprm 8, chqw5 15) | 23 | 0 |
| 2 | 03:45:48.634–03:46:03.561 (14.9 s) | 23 (15 + 8) | 23 | 0 |
| 3 | 03:54:09.055–03:54:23.940 (14.9 s) | 23 (15 + 8) | 23 | 0 |

No `db_record_failed` in those windows.

**The 5 rejections between removal and closure are 5 alerts without push.** Each run, driver round 58 (sensors s0–s4) arrived 1.2–1.7 s after removal, while the circuit was still open (it stays open until the next half-open probe, which succeeded and closed it 13–14 s after removal). Each rejected `trace_id` has its own `alert_emitted` with `push_path=resolve_failed`, and there is no other alert in that interval (columns `alertas_retiro_cierre`, `sin_push_retiro_cierre`, `primera_alerta_retiro_cierre_utc`, `ultima_alerta_retiro_cierre_utc`; asserts in `calcular_v74.py`).

| run | alerts without push, removal → closure | first – last (2026-09-30) | all alerts without push in the run |
|---|---|---|---|
| 1 | 5 (cgprm 2, chqw5 3) | 03:37:17.569–03:37:17.644 | 199 + 5 = **204** |
| 2 | 5 (cgprm 3, chqw5 2) | 03:45:37.219–03:45:37.261 | 183 + 5 = **188** |
| 3 | 5 (cgprm 3, chqw5 2) | 03:53:57.656–03:53:57.747 | 192 + 5 = **197** |

204 / 188 / 197 are also the log counts in the sampling window of `pedido2.md` (= Δ `dispatch_degraded_count` of the CSV).

## A09. 191 / 171 / 181 (Table 6 of V6) against 199 / 183 / 192

Output `v74_2026-11-21/a09_degraded_alerts.csv`.

- **Instrument:** `degraded_alerts` in `data/B - SEPTIEMBRE 5 RUNS V2/chaos/netem-delay-ew-um-summary-*.env` = Δ `sum(ew_alert_dispatch_duration_seconds_count{push_path="resolve_failed"})` (Prometheus, `chaos/lib/sampler.sh:39`) between the first and last sample with epoch in [`fail_start`, `recovery_start`] (`sampler_delta`, `lib/sampler.sh:200-209`; called at `netem-delay-ew-um.sh:563`; go-tesis-infra@3f9d8b7).
- **Window actually sampled (client clock):** 03:33:12–03:37:03, 03:41:48–03:45:22, 03:50:09–03:53:43.
- **199 / 183 / 192:** `alert_emitted` with `push_path=resolve_failed` in the logs, injection to removal inclusive.
- **Difference −8 / −12 / −11:** the last sample is 13 s before removal, and the logs have 10 no-push alerts per run in that tail. The rest, +2 / −2 / −1 (Prometheus 191 / 171 / 181 against logs 189 / 173 / 182 up to the last sample), fits scrape staleness (up to 15 s) and the unmeasured client–server clock offset; it cannot be resolved event by event.
