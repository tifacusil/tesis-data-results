# How the metrics were obtained — September 2026 campaign

This document describes how we obtained the raw data that `generar_resultados.py` uses to regenerate Figures 2 to 5 and Tables 7, 8 and 9.

## 1. Environments

| | System A | System B |
|---|---|---|
| Server | `concurso` (204.168.203.32) | `go-tesis` (178.105.104.95) |
| Deployment | systemd services | k3s, namespace `landslide` |
| Prometheus | `http://localhost:9090` | `http://localhost:31083` (NodePort) |
| Ladder | 17/09/2026 | 23/09/2026 |
| 12 h run | 18/09/2026, 05:17:31–17:20:32 UTC | 23/09/2026, from 12:30:00 UTC |

Each system has its own Prometheus. Queries run **on each system's own server**, and the two instances are never mixed.

## 2. Where each script input comes from

| Argument | Files | Source | Used for |
|---|---|---|---|
| `--escalera-a` / `--escalera-b` | `A - SPETIEMBRE 5 RUNS/vu-XXX-rN.json`, `B - SEPTIEMBRE 5 RUNS V2/vu-XXX-rN.json` | Artillery JSON reports (section 3), 5 runs per level (1, 10, 50 and 100 frames/s) | Latency, throughput and failures (Tables 7 and 8, Figure 2). They also define each run's window |
| `--prom-a` / `--prom-b` | `A-ladder-0917-timeseries.csv`, `B-ladder-0923-timeseries.csv` | Prometheus export (`data.zip`, section 4), one row per minute | Node CPU and memory at levels 10, 50 and 100 (Table 9, Figure 3). Per-service memory at 100 frames/s (Figure 4) |
| `--nivel1-dir` | `A_nivel1_{cpu,mem}.json`, `B_nivel1_{cpu,mem}.json` | `curl` queries to the Prometheus API (section 5) | Node CPU and memory at 1 frame/s (Table 9, Figure 3) |
| `--sat-b` | `B-12h-0923-saturation.csv` | Prometheus export (`data.zip`, section 4) | Broker queues and early-warning consumption over 12 h (Figure 5) |
| `--serie-b` | `B-12h-0923-timeseries.csv` | Prometheus export (`data.zip`, section 4) | Ingest rate over 12 h (Figure 5) |

`data.zip` also contains `A-12h-0918-{timeseries,saturation}.csv`, `resources-summary.json` and `RESUMEN.md`. The script does not use them, but the idle values in Table 10 come from them. Its maxima during each event do not; see *Table 10 verification* in section 3.

### Expected CSV columns

- `*-timeseries.csv`: `time` (ISO 8601, UTC), `fps`, `node_cpu_pct`, `node_mem_used_mib`, `cpu_pct_<service>`, `mem_mib_<service>`.
- `B-12h-0923-saturation.csv`: `time`, `fps`, `q_ew_evaluate`, `q_dm_persist`, `q_dead_letter`, `ew_consumed_fps`, `ew_dropped_5m`, `dr_dropped_5m`, `dm_dlq_5m`, `redis_buffer_pending`, `pod_restarts`, `rabbit_up`.

Services: `data-receiving`, `data-management`, `early-warning`, `data-analysis`, `project-management` and `user-management`.

### What is in this repo

`data/` holds the Artillery reports (`A - SPETIEMBRE 5 RUNS/`, `B - SEPTIEMBRE 5 RUNS V2/`) and `B-12h-0923-{saturation,timeseries}.csv`. It also holds the inputs of `chaos_evidence_b.py` (section 3). The ladder CSVs and the `nivel1/` files are not in this repo: get them from `data.zip` (section 4) and the queries in section 5.

## 3. Load tests (Artillery) and chaos

The scripts live in `load-tests/`. Ingestion is over TCP with binary DTU frames, not HTTP. That is why the scenarios use the custom engine `artillery-engine-dtu-tcp`, which hands frame building and sending to `dtu-emulator` (Python).

### Client machine requirements

```bash
npm install -g artillery
git clone <dtu-emulator>                  # by default, next to this repo: ../dtu-emulator
cp load-tests/.env.example load-tests/.env
```

`.env` variables:

| Variable | Purpose |
|---|---|
| `DTU_EMULATOR_PATH` | Path to `dtu-emulator`, if it is not in the default location |
| `DTU_EMULATOR_PYTHON` | Python interpreter to use |
| `GRAFANA_URL`, `GRAFANA_API_TOKEN` | Optional: mark each run in Grafana |

Engine variables:

| Variable | Default |
|---|---|
| `DTU_SENSOR_COUNT` | 100 sensors |
| `DTU_ENGINE_POOL_SIZE` | Peak `arrivalRate` of the scenario |
| `DTU_ENGINE_SEND_TIMEOUT_MS` | 120000 |

### Scenarios

| Scenario | Phases | Rate |
|---|---|---|
| `scenarios/vu-001.yml` … `vu-100.yml` | 180 s warm-up and 420 s measurement | `arrivalRate` = 1, 10, 50 or 100 frames/s |
| `scenarios/vu-sustained-12h.yml` | 180 s ramp (1 → `SUSTAINED_RATE`) and 43,200 s sustained | `SUSTAINED_RATE` |

All scenarios send GNSS frames: one `send` step per virtual user, spread across the sensors in the fleet.

### Per-system configuration (`load-tests/.env`)

Following `docs/runbook-fases.md`, everything runs in **Git Bash** from the root of `go-tesis-infra`. SSH, Redis and MySQL credentials live in `load-tests/.env`, which is never committed. The file has one block per system, and only the block for the system under test may be active. If the block does not match the target, the reset and the chaos act on the wrong system.

| Variable | System A (systemd) | System B (k3s) |
|---|---|---|
| `SSH_HOST` / `SSH_USER` | `204.168.203.32` / `concurso` | `178.105.104.95` / `gotesis` |
| `SSH_ORCHESTRATOR` | `native` | `k8s` |
| `REDIS_PASSWORD`, `MYSQL_EW_PASSWORD` | Required | Read from the pods |
| `MYSQL_EW_PORT` / `_USER` / `_DATABASE` | `3308` / `landslide` / `early_warning_db` | Defaults |
| `TARGET_HOST` (data-receiving, TCP) | `204.168.203.32:5100` | `178.105.104.95:5000` |
| Prometheus | `http://204.168.203.32:9090` | `http://178.105.104.95:31083` |
| `GATEWAY_URL` (chaos) | `http://204.168.203.32/health/data-management` | `http://178.105.104.95/api/v1/data/health` |

Before each run:

```bash
grep -E "^SSH_HOST|^SSH_ORCHESTRATOR|^SYSTEM" load-tests/.env    # confirm the active block
powershell.exe -Command "Get-Process python,node -EA SilentlyContinue | Stop-Process -Force"   # kill orphaned processes
```

### Ladder (Phase 1): `run-all.sh`

4 levels × 5 runs = 20 runs per system, about 3 h 30 min in total. Each run lasts 10 min (3 of warm-up and 7 of measurement), followed by a 30 s pause. Before each run, `reset-state.sh` runs `FLUSHDB` on Redis and `TRUNCATE TABLE alerts` on the early-warning MySQL. It then runs `artillery run --output results/<SYSTEM>/vu-<level>-r<N>.json` and samples client CPU into `vu-<level>-r<N>.client-cpu.csv`.

```bash
# A (block A active in .env), 17/09/2026
VU_LEVELS="001 010 050 100" REPEATS=5 \
  TARGET_HOST=204.168.203.32:5100 SYSTEM=A \
  ./load-tests/run-all.sh

# B (block B active in .env), 23/09/2026
VU_LEVELS="001 010 050 100" REPEATS=5 \
  TARGET_HOST=178.105.104.95:5000 SYSTEM=B \
  ./load-tests/run-all.sh
```

Only levels up to 100 are used: above that, the ceiling comes from the load generator, not the server. `SUSTAINED_RATE` is the last level that does not break the failure criterion in `plan-pruebas.md` §1.3: 100.

### 12 h endurance with chaos (Phase 2)

Two Git Bash terminals are used: terminal 1 generates the load and terminal 2 launches the chaos. The chaos starts once the 3 min ramp is over, and it times its injections from its own start. `run-endurance.sh` loads `.env` on its own, but for the chaos `.env` must be loaded by hand.

```bash
# Terminal 1: load
TARGET_HOST=<TARGET_HOST> SUSTAINED_RATE=100 SYSTEM=<A|B> \
  ./load-tests/run-endurance.sh

# Terminal 2: chaos
set -a; . load-tests/.env; set +a
GATEWAY_URL=<GATEWAY_URL> ./chaos/run-during-endurance.sh
```

If `reset-state.sh` fails, `run-endurance.sh` aborts the run unless `ALLOW_DIRTY_START=1` is set. The result is written to `results/<SYSTEM>/sustained-12h.json`, and an existing file is moved to `.bak`.

Injections run by `chaos/run-during-endurance.sh`:

| Since start | Script | A | B |
|---|---|---|---|
| t + 2 h | `kill-rabbitmq.sh` | Yes | Yes |
| t + 6 h | `pause-data-management.sh 90` | Yes | Yes |
| t + 10 h | `netem-delay-ew-da.sh 8000 180` | Skipped: A has no circuit breaker | Yes |

Each injection saves two snapshots to `chaos/results/`: `<scenario>-pre-<epoch>.snapshot` and `-post-<epoch>.snapshot`. They are instant queries to Prometheus made by `chaos/lib/capture.sh`. The snapshots for the runs we used, now in `chaos/results/old/`, are:

| Run | kill-rabbitmq (pre) | pause-data-management (pre) | netem-delay-ew-da (pre) |
|---|---|---|---|
| A, 18/09 | 1789715900 (07:18 UTC) | 1789730299 (11:18 UTC) | — |
| B, 23/09 | 1790173935 (14:32 UTC) | 1790188340 (18:32 UTC) | 1790202738 (22:32 UTC) |

`chaos/lib/sampler.sh` samples Prometheus continuously while a scenario runs. `sampler_start <label> [target]` writes `chaos/results/<label>-samples-<ts>.csv` with the columns `epoch`, `iso_utc`, `breaker_state`, `calls_ok`, `calls_timeout`, `calls_circuit_open`, `calls_error`, `alerts_published`, `messages_consumed`, `messages_dropped`, `duplicates_skipped`, `queue_backlog` and `dispatch_*`. The PromQL expressions are in `_sampler_default_metrics` and can be overridden with `SAMPLER_METRICS`. Within `chaos/`, only `netem-delay-ew-um.sh` loads it, producing `netem-delay-ew-um-samples-*.csv`. It plays no part in the 12 h run.

> `chaos/results/old/` also holds B snapshots from 18–19/09: 1789771320, 1789785725 and 1789800125. They belong to a different 12 h run, not the one used in the article.

### Results

The `results/A` and `results/B` folders were archived in this repo as `data/A - SPETIEMBRE 5 RUNS` and `data/B - SEPTIEMBRE 5 RUNS V2`. These are the paths passed to `--escalera-a` and `--escalera-b`. `node load-tests/aggregate-results.js <SYSTEM>` gives a quick per-system summary, but the article's figures come from `generar_resultados.py`.

### Artillery report inventory (`recuperar_artillery.py`)

[`recuperar_artillery.py`](../recuperar_artillery.py) checks that the archived Artillery reports are complete before anything else uses them. It reads only `data/A - SPETIEMBRE 5 RUNS/*.json` and `data/B - SEPTIEMBRE 5 RUNS V2/*.json`; the two folders are fixed in the script (`SYSTEMS`). For each report it:

1. Counts the 10 s windows in `intermediate` and checks that `aggregate.summaries` exists.
2. Rates the report `USABLE` (at least 40 windows and an aggregate), `PARTIAL` (aggregate, fewer windows) or `UNUSABLE` (no aggregate).
3. Takes the start and end in UTC from `aggregate.firstMetricAt` / `lastMetricAt`, and the aggregate p95 of each metric.
4. Copies each `USABLE` report to `<out>/reports/<A|B>_<name>.json` and checks the copy against the original's SHA-256.
5. Writes `<out>/inventario-reportes.csv` (columns `System`, `Original`, `Copy`, `Status`, `Windows`, `StartUTC`, `EndUTC`, `MB`, `SHA256`, `Metrics`, `P95Aggregate`), sorted by `StartUTC`. This gives the order and time of every run.

It only reads the originals. A second run overwrites nothing: it re-checks every copy and exits with an error if one differs from its original. It uses only the Python standard library, version 3.11 or later.

From the root of this repo:

```bash
sha256sum -c SHA256SUMS.artillery     # the 42 reports are the ones used in the article
python3 recuperar_artillery.py        # writes artillery-inventory/; --out to change it
```

On Windows, run `py` instead of `python3`. `sha256sum` comes with Git for Windows (Git Bash).

Expected output: `42 JSON checked, 42 USABLE, 0 partial or unusable.`

| | A | B |
|---|---|---|
| Ladder reports (4 levels × 5 runs) | 20, 60–62 windows each | 20, 61–62 windows each |
| Ladder, first and last run (UTC) | 17/09 15:14:08 (`vu-001-r1`) – 18:47:45 (`vu-100-r5`) | 23/09 05:23:18 (`vu-001-r1`) – 08:59:23 (`vu-100-r5`) |
| `sustained-12h.json` | 4339 windows, 18/09 05:17:31–17:20:32 | 4339 windows, 23/09 12:31:20 – 24/09 00:34:21 |

A's 12 h times match section 1. B's first metric comes at 12:31:20, 80 s after the run was started at 12:30:00 (section 1).

### Table 10 verification

Table 10 (Item 7) is not produced by `generar_resultados.py`. For each chaos event on B it gives the maximum Redis buffer per replica, the maxima of the `early_warning.evaluate` and `data_management.persist` queues, the minimum reception rate, and the messages lost. All three rows were verified value by value on 22/10/2026, the day before B's Prometheus dropped the September data (section 8). The raw files are in [`tabla10/`](../tabla10/), with their `SHA256SUMS`.

They were extracted on `go-tesis` with the instant API over a range selector. That returns every raw scrape (15 s), unlike the 5 min steps of `B-12h-0923-saturation.csv`. Each row's window is 20 min either side of its injection (pre snapshots in the table above):

| Row | Event | Injection (UTC) | Window (UTC) | Files cover |
|---|---|---|---|---|
| 1 | `kill-rabbitmq` | 14:32 | 14:12–14:52 | 14:00–15:10 |
| 2 | `pause-data-management 90` | 18:32 | 18:12–18:52 | 18:00–19:10 |
| 3 | `netem-delay-ew-da 8000 180` | 22:32 | 22:12–22:52 | 22:00–23:20 |

```bash
P=http://localhost:31083
mkdir -p tabla10 && cd tabla10
# row, end (T), range, start of reception
for spec in "1 2026-09-23T15:10:00Z 70m 2026-09-23T14:00:00Z" \
            "2 2026-09-23T19:10:00Z 70m 2026-09-23T18:00:00Z" \
            "3 2026-09-23T23:20:00Z 80m 2026-09-23T22:00:00Z"; do
  set -- $spec; r=$1; T=$2; R=$3; S=$4
  for m in data_receiving_redis_buffer_pending rabbitmq_queue_messages rabbitmq_queue_messages_ready \
           data_receiving_messages_dropped_total ew_messages_dropped_total dm_messages_dlq_total; do
    curl -sG "$P/api/v1/query" --data-urlencode "query=${m}[$R]" --data-urlencode "time=$T" > "B-fila$r-$m.json"; done
  curl -sG "$P/api/v1/query_range" --data-urlencode 'query=sum(rate(data_receiving_frames_total[1m]))' \
    --data-urlencode start=$S --data-urlencode end=$T --data-urlencode step=15s > "B-fila$r-recepcion.json"
done
sha256sum *.json > SHA256SUMS
```

The extremes inside each window, for example for row 3 (22:12–22:52):

```bash
W='select(.[0]>=1790201520 and .[0]<=1790203920)'
jq "[.data.result[]|[.values[]|$W|.[1]|tonumber]|max]|max" B-fila3-data_receiving_redis_buffer_pending.json
jq "[.data.result[]|select(.metric.queue|test(\"early_warning.evaluate|data_management.persist\"))|{q:.metric.queue,max:([.values[]|$W|.[1]|tonumber]|max)}]" B-fila3-rabbitmq_queue_messages.json
jq "[.data.result[0].values[]|$W|.[1]|tonumber]|min" B-fila3-recepcion.json
```

| Row | Redis buffer, max per replica | `early_warning.evaluate`, max | `data_management.persist`, max | Reception, min (frames/s) | Lost |
|---|---|---|---|---|---|
| 1 | 3752 (`10.42.0.90`, 14:34:05) | 759 (14:33:36) | 1046 (14:33:36) | 69.387 (14:34:00) | 0 |
| 2 | 49 (`10.42.0.91`, 18:32:41) | 13 (18:21:51) | 56 (18:32:51) | 96.089 (18:32:30) | 0 |
| 3 | 95 (`10.42.0.92`, 22:37:00) | 44 (22:38:21) | 8 (22:36:36) | 88.366 (22:37:00) | 0 |

- **Redis buffer:** the other replicas peak at 3743 and 3750 (row 1), 13 and 14 (row 2), and 86 and 86 (row 3).
- **Queues:** ready plus unacknowledged, as in `data.zip` (section 4). `rabbitmq_queue_messages_ready` gives lower peaks (946 and 719 in row 1, 0 and 0 in row 2, 4 and 0 in row 3), so it does not reproduce the table. It is kept in the folder to show this.
- **Row 2, `early_warning.evaluate`:** the window peak of 13 comes 10 min before the pause. From the injection onwards the peak is 11 (18:41:21).
- **Lost:** `data_receiving_messages_dropped_total`, `ew_messages_dropped_total` and `dm_messages_dlq_total` are 0 on every instance over each file's whole span.

### Chaos event evidence (`chaos_evidence_b.py`)

[`chaos_evidence_b.py`](../chaos_evidence_b.py) checks the claims the manuscript makes about *how* B behaved during its three chaos events, beyond the Table 10 values above. It has two subcommands:

| Subcommand | Needs | What it does |
|---|---|---|
| `export` | Network access to B's Prometheus, within its 30-day retention | Downloads the series for each event window (10 min margin on each side, 15 s step) and for the whole 12 h run (5 min step), writes one CSV per query and a `manifiesto.json` with the query, window, step and SHA-256 of each file. Aborts if a query comes back empty instead of writing an empty CSV. |
| `verify` | Only the frozen files below; no server access | Checks every CSV against the SHA-256 in the manifest, recomputes each claim and prints `[OK]` or `[FAIL]` with the numbers behind it. Exits with code 1 if any check fails. |

`export` was run once, on 23/10/2026 at 02:46 UTC, the day B's Prometheus started dropping the September data. **It cannot be run again**: from then on, `verify` over the frozen export is the reproducible step. The script uses only the Python standard library, version 3.11 or later.

The frozen export keeps the Spanish names it was written with (`manifiesto.json`, its keys `archivos`/`archivo`/`consulta`, and the file names below). Renaming them would change the files whose SHA-256 is recorded here, so the script reads them as they are.

The event windows are fixed in the script (`EVENTS`). Each key is also the file-name prefix of its CSVs:

| Key | Event | Window (UTC) | Source of the limits |
|---|---|---|---|
| `caida_broker` | Broker kill | 14:32:24–14:33:02 | Creation of `rabbitmq-0` (`.status.startTime`) and last data-receiving log line before its restart |
| `pausa_dm` | data-management pause | 18:32:20–18:34:04 | Pre and post snapshots `1790188340` / `1790188444` |
| `netem_da` | Delay towards data-analysis | 22:32:18–22:36:07 | Pre and post snapshots `1790202738` / `1790202967` |

Per window, the suffixes are `buffer_por_pod` (Redis buffer per pod), `cpu_nodo_pct` (node CPU, %), `iowait_frac`, `reinicios` (container restarts) and `ready`. The two whole-run files are `corrida12h__buffer_sum` and `corrida12h__buffer_max`.

#### Inputs

| Argument | Path in `data/` | Source | SHA-256 |
|---|---|---|---|
| `--evidence` | `evidencia-b-0923/` | Output of `export` (17 CSVs) | `manifiesto.json`: `247f6ddeb3252ab995b5f42e1d75d62ba7c069b28c7ba93b22cf53051362b032`; each CSV is checked against it |
| `--artillery` | `B - SEPTIEMBRE 5 RUNS V2/sustained-12h.json` | Artillery report of B's 12 h run | `57fc9df4aec189820abdda08fdfa98b8060aa1a7a92543bb3439d9b17e985f50` |
| `--logs` | `data-receiving-logs-2026-09-23/*.log` | `kubectl logs --previous` of the three data-receiving pods, captured on 06/10/2026. They cover 04:49–14:33 UTC of 23/09, the container instance that ended with the broker kill. Kubernetes discards them at the pods' next restart, so this copy is the only one. | `69b4v`: `b6113fc834fe99f833d45cd628b513fafc03e244c0003c6ccfbe8c3607432b46`<br>`7rpf9`: `d9a2a871c447a7faab3d1c90d90aa5dd2124f1a3d078c85ac308f17642bc9110`<br>`8fgq2`: `f7d36846313e45b669b8a317637f67263fbdde7464c62e1a3f0e809d8b1bba21` |
| `--series`, `--saturation` | `B-12h-0923-timeseries.csv`, `B-12h-0923-saturation.csv` | `data.zip` (section 4) | As in section 4 |
| `--snapshots` | `B - SEPTIEMBRE 5 RUNS V2/chaos/` | Chaos snapshots (table above) | — |

The logs were captured with:

```bash
for p in 69b4v 7rpf9 8fgq2; do
  sudo k3s kubectl logs -n landslide data-receiving-d9f59874f-$p --previous > data-receiving-$p-previous.log
done
```

#### Running it

From the root of this repo:

```bash
python3 chaos_evidence_b.py verify \
  --evidence data/evidencia-b-0923 \
  --artillery "data/B - SEPTIEMBRE 5 RUNS V2/sustained-12h.json" \
  --logs data/data-receiving-logs-2026-09-23 \
  --series data/B-12h-0923-timeseries.csv \
  --saturation data/B-12h-0923-saturation.csv \
  --snapshots "data/B - SEPTIEMBRE 5 RUNS V2/chaos"
```

The export, for the record (it now returns no data):

```bash
python3 chaos_evidence_b.py export --prom http://localhost:31083 --out evidencia-b-0923
```

#### What it checks

The expected output is 9 `[OK]` lines and `All checks passed.`

| # | Claim | Evidence | Verified value |
|---|---|---|---|
| 1 | The generator's failures add up to the aggregate total | Artillery `intermediate` periods | 315 = 210 (period from 14:33:00) + 105 (from 14:33:10) |
| 2 | No generator failure while the broker was down: data-receiving acknowledged from the Redis buffer | Artillery periods starting before 14:33:00 | 0 failures |
| 3 | All failed publishes fall inside the broker outage | `rabbitmq publish failed; buffered in redis for retry` in the logs | 3740, 14:32:24–14:33:01 |
| 4 | Every replica reports the same buffer peak, so the gauge is global, not per instance | `caida_broker__buffer_por_pod.csv` | 3743–3752 |
| 5 | The real buffer peak matches the failed publishes (±2 %) | Checks 3 and 4 | 3752 vs. 3740 |
| 6 | `sum()` over the replicas triples the buffer (the `redis_buffer_pending` column of `B-12h-0923-saturation.csv`) | `corrida12h__buffer_{sum,max}.csv` | 14:35: `sum` 11 223, `max` 3741, ratio 3.00 |
| 7 | The liveness probe restarted data-management during the 90 s pause | `pausa_dm__reinicios.csv`, `pausa_dm__ready.csv` | One restart (18:33:50); `ready` 0 from 18:33:05 to 18:34:05 |
| 8 | `consumed_dm` falls between the pause snapshots, because the restarted pod's counter reset | Pause snapshots | 5 034 103 → 2 891 907 |
| 9 | Data-analysis CPU spikes when the netem delay is removed (> 5 × its baseline) | `B-12h-0923-timeseries.csv` | Baseline 0.80, max 10.67 in the following 5 min |

It also prints, with no pass/fail threshold, the 105 publishes that were never acknowledged (the Redis write was cancelled at shutdown, 14:33:01–14:33:02; 315 / 105 = 3.00), and node CPU for each event: the mean and max over the 10 min before, during the window, and over the 5 min after.

| Event | Before | During | After | iowait, max |
|---|---|---|---|---|
| `caida_broker` | 85.2 % (max 87.5) | 86.5 % (max 87.2) | 85.9 % (max 98.6) | 0.050 |
| `pausa_dm` | 85.6 % (max 89.8) | 90.7 % (max 96.1) | 85.0 % (max 86.7) | 0.053 |
| `netem_da` | 84.7 % (max 87.4) | 87.9 % (max 94.4) | 95.4 % (max 99.4) | 0.058 |

Two points the checks settle for the manuscript:

- **The `redis_buffer_pending` column of `B-12h-0923-saturation.csv` is three times the real backlog.** Each data-receiving replica runs `SCAN sensor_buffer:*` over the shared Redis and publishes the global count, so `sum()` over three replicas counts it three times. Use `max()`, or the per-replica values in Table 10, as above.
- **The 90 s pause on B was in fact a restart.** The liveness probe (`httpGet /health`, `periodSeconds: 15`, `failureThreshold: 3`) killed the frozen container after about 45 s. A has no probe, so on A it remained a pause.

## 4. The `data.zip` export

`data.zip` holds no Artillery output. It holds Prometheus series exported over the windows of both phases: the `*-ladder-*` files cover Phase 1 and the `*-12h-*` files cover Phase 2, chaos included (section 3). According to its `RESUMEN.md`, the CSVs were exported from each system's Prometheus: `localhost:9090` on A and NodePort `31083` on B. The windows were detected with:

```
sum(rate(data_receiving_frames_total[1m]))
```

| File | Window (UTC) | Resolution | Rows |
|---|---|---|---|
| `A-ladder-0917-timeseries.csv` | 17/09 16:00 → 19:00 | 1 min | 181 |
| `A-12h-0918-timeseries.csv` | 18/09 05:25 → 17:20 | 1 min | 716 |
| `A-12h-0918-saturation.csv` | 18/09 05:25 → 17:20 | 5 min | 144 |
| `B-ladder-0923-timeseries.csv` | 23/09 06:10 → 09:10 | 1 min | 181 |
| `B-12h-0923-timeseries.csv` | 23/09 12:35 → 24/09 00:30 | 1 min | 716 |
| `B-12h-0923-saturation.csv` | 23/09 12:35 → 24/09 00:30 | 5 min | 144 |

Queries that generate each column, verified against the archived data (see *Query verification*). `<label>` is `service` on A and `app` on B:

| Column | PromQL query | CSV |
|---|---|---|
| `fps` | `sum(rate(data_receiving_frames_total[1m]))` | All |
| `node_cpu_pct` | `100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))` | `*-timeseries` |
| `node_mem_used_mib` | `(sum(node_memory_MemTotal_bytes) - sum(node_memory_MemAvailable_bytes)) / 1048576` | `*-timeseries` |
| `mem_mib_<svc>` | `sum(process_resident_memory_bytes{<label>="<svc>"}) / 1048576`. On A, for data-management, project-management and user-management: `sum(jvm_memory_used_bytes{service="<svc>"}) / 1048576` | `*-timeseries` |
| `cpu_pct_<svc>` | `100 * sum(rate(process_cpu_seconds_total{<label>="<svc>"}[1m]))` | `*-timeseries` |
| `q_ew_evaluate` | `sum(rabbitmq_queue_messages{queue="early_warning.evaluate"})` | `B-12h-saturation` |
| `q_dm_persist` | `sum(rabbitmq_queue_messages{queue="data_management.persist"})` | `B-12h-saturation` |
| `q_dead_letter` | `sum(rabbitmq_queue_messages_ready{queue="sensors.dead_letter"})` | `B-12h-saturation` |
| `ew_consumed_fps` | `sum(rate(ew_messages_consumed_total[5m]))` | `B-12h-saturation` |
| `ew_publish_in_fps` | `sum(rate(rabbitmq_queue_messages_published_total{queue="early_warning.evaluate"}[5m]))` | `B-12h-saturation` |
| `ew_dropped_5m` | `sum(increase(ew_messages_dropped_total[5m]))` | `B-12h-saturation` |
| `dr_dropped_5m` | `sum(increase(data_receiving_messages_dropped_total[5m]))` | `*-12h-saturation` |
| `dm_dlq_5m` | `sum(increase(dm_messages_dlq_total[5m]))` | `B-12h-saturation` |
| `redis_buffer_pending` | `sum(data_receiving_redis_buffer_pending)`. Three times the real backlog: every replica reports the global count (section 3, *Chaos event evidence*) | `B-12h-saturation` |
| `pod_restarts` | `sum(kube_pod_container_status_restarts_total{namespace="landslide"})` | `B-12h-saturation` |
| `rabbit_up` | `max(rabbitmq_up)` | `B-12h-saturation` |
| `dr_published_fps` | `sum(rate(data_receiving_messages_published_total[5m]))` | `A-12h-saturation` |
| `ew_processed_fps` | `sum(rate(ew_messages_processed_total[5m]))` | `A-12h-saturation` |

Each CSV comes from `/api/v1/query_range`, with `start` and `end` equal to its first and last row. The step is 60 s for the `*-timeseries` files and 300 s for the `*-saturation` files.

How to read these columns:

- **Queues:** `q_ew_evaluate` and `q_dm_persist` count all messages, ready plus unacknowledged. The ready-only variant does not reproduce the data. `q_dead_letter` is 0 for the whole run, so the two variants cannot be told apart there.
- **`redis_buffer_pending`:** this is the **sum over replicas**, since the per-replica maximum does not reproduce the data. Table 10, by contrast, uses the per-replica maximum, which comes from a different export (section 3, *Table 10 verification*). They are different definitions and must not be mixed.
- **`pod_restarts`:** this is the cumulative counter, which is why it starts at 3314. It is not a per-window increment.
- **Ties:** for `mem_mib_` of project-management and user-management (B), of early-warning (A), and for `node_mem_used_mib`, `sum`, `max` and `avg` give the same result. There is only one series: one replica, the only instance scraped on A (`:8092`), or a single node_exporter.

Limitations stated in `RESUMEN.md` itself:

- A's Prometheus does not scrape RabbitMQ. It also scrapes only the early-warning instance on `:8092`, not the one on `:8088`.
- On A, `jvm_memory_used` is not RSS: the real RSS of the Java processes is higher.
- A's `cpu_pct_data-analysis`, between 300 and 380 %, is not plausible and is ignored.
- Neither Prometheus measures MySQL, Redis or RabbitMQ per process.

> **Note:** the ladders in `data.zip` start at 16:00 (A) and 06:10 (B). They therefore do not cover the 1 frame/s level, which was extracted separately (section 5).

### Provenance and integrity

A team member gathered the files and zipped them by hand, without a script. According to the zip's internal timestamps, the files were generated on 25/09/2026 between 14:50 and 15:53, after all runs had finished. To check that a copy is identical to the one used in the article, compare these SHA-256 hashes:

| File | SHA-256 |
|---|---|
| `data.zip` | `f3a6c99304e81d976a81977034b3db319108c59d08e1ced3e2263d278b903fbd` |
| `A-12h-0918-saturation.csv` | `396ebf2cd299ac14e304d8843a17c439c174cc00aaad8b0fca9ae3e0914a6dad` |
| `A-12h-0918-timeseries.csv` | `afcfb7f9f984cb3867ec71080797ed7b5b9846f7c0f78cf5de689954a5eaea2d` |
| `A-ladder-0917-timeseries.csv` | `4be71809c2b8dcb301b3f7de770664138fb79afa60c7d431ba63f047844fe71b` |
| `B-12h-0923-saturation.csv` | `e5b2f31e5e9de79e7e88c1e5911b52ebb3a99ea9f111027d7205f47b268dd549` |
| `B-12h-0923-timeseries.csv` | `d501c274a6c99beaf1037f2ee94eb8a7dab4a9540b01d910cdb3de77597e816b` |
| `B-ladder-0923-timeseries.csv` | `b603ea6198a0abb1560f472f42c05f451477dcce6c53f278874b4101b78ad8ec` |
| `resources-summary.json` | `e3bbf7a7dc74aeb1255e39f6c9365986d96b9311a4a72cc37c6d667d34185512` |
| `RESUMEN.md` | `a03f0a2665e19fe5eef5179dba94a25cb1de1f3d494a569d46ba03b02eb87d48` |

```bash
sha256sum *.csv resources-summary.json RESUMEN.md
```

### Query verification

On 20/10/2026, `reconstruir_data_zip.py` confirmed that the queries in the table above generate the same data as the archived CSVs. The script takes each column, tries several candidate queries at the same timestamps as the CSV, and accepts one only if it matches at least 99 % of the rows, within the rounding used when the file was written. All **70 columns** match on **100 % of the rows**: 42 for B and 28 for A. To repeat it, from the folder holding the CSVs:

```bash
python reconstruir_data_zip.py --prom http://178.105.104.95:31083 --sistema B \
  --csv B-ladder-0923-timeseries.csv B-12h-0923-timeseries.csv B-12h-0923-saturation.csv --salida reconstruccion-B
python reconstruir_data_zip.py --prom http://204.168.203.32:9090 --sistema A \
  --csv A-ladder-0917-timeseries.csv A-12h-0918-timeseries.csv A-12h-0918-saturation.csv --salida reconstruccion-A
```

Each `reconstruccion-*/<csv>.consultas.md` records the chosen query, the match and any tied queries. This shows that the queries reproduce the data, not that the team member typed exactly these strings. For reproducibility, that is what matters.

## 5. Extracting the 1 frame/s level

This uses the Prometheus range API with a 60 s step. The window covers all five runs of the level.

| System | `start` (epoch) | `end` (epoch) | UTC |
|---|---|---|---|
| A | 1789658040 | 1789661220 | 17/09, 15:14–16:07 |
| B | 1790140980 | 1790144200 | 23/09, 05:23–06:17 |

PromQL queries:

```
# Node CPU (%)
100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))

# Node memory used (MiB)
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1048576
```

### System A (on `concurso`)

```bash
curl -G http://localhost:9090/api/v1/query_range \
  --data-urlencode 'query=100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))' \
  --data-urlencode 'start=1789658040' --data-urlencode 'end=1789661220' \
  --data-urlencode 'step=60s' > A_nivel1_cpu.json

curl -G http://localhost:9090/api/v1/query_range \
  --data-urlencode 'query=(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1048576' \
  --data-urlencode 'start=1789658040' --data-urlencode 'end=1789661220' \
  --data-urlencode 'step=60s' > A_nivel1_mem.json
```

### System B (on `go-tesis`)

```bash
curl -G http://localhost:31083/api/v1/query_range \
  --data-urlencode 'query=100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))' \
  --data-urlencode 'start=1790140980' --data-urlencode 'end=1790144200' \
  --data-urlencode 'step=60s' > B_nivel1_cpu.json

curl -G http://localhost:31083/api/v1/query_range \
  --data-urlencode 'query=(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1048576' \
  --data-urlencode 'start=1790140980' --data-urlencode 'end=1790144200' \
  --data-urlencode 'step=60s' > B_nivel1_mem.json
```

> **Note:** the first extraction for B used A's window by mistake, so it measured B idle on 17/09. It was repeated with the correct window shown above. To check a file, the first timestamp in `data.result[0].values` must equal its system's `start`.

Copying the files to the local machine:

```bash
scp concurso@204.168.203.32:~/A_nivel1_*.json nivel1/
scp gotesis@178.105.104.95:~/B_nivel1_*.json nivel1/
```

## 6. Windows and aggregation

The script derives the windows from the Artillery JSON files, with no extra input:

1. Each run is split into 10 s periods. The first 18 (3 min of warm-up) are discarded and the next 42 form the **effective window**.
2. Latency: each run's value is the median of its 42 periods.
3. Resources: each run's value is the median of the Prometheus samples whose `time` falls inside that run's effective window.
4. Each level's value is the median of its five runs.
5. A vs. B test: exact permutation Mann-Whitney (5 vs. 5) with Bonferroni over 4 levels (α = 0.0125), Cliff's delta, and a 95 % CI by hierarchical bootstrap (B = 10,000, seed 7).

## 7. Running the script

```bash
python3 generar_resultados.py \
  --escalera-a "data/A - SPETIEMBRE 5 RUNS" \
  --escalera-b "data/B - SEPTIEMBRE 5 RUNS V2" \
  --prom-a A-ladder-0917-timeseries.csv \
  --prom-b B-ladder-0923-timeseries.csv \
  --nivel1-dir nivel1 \
  --sat-b data/B-12h-0923-saturation.csv \
  --serie-b data/B-12h-0923-timeseries.csv \
  --salida salida
```

`--prom-a`, `--prom-b` and `--nivel1-dir` point to files that are not in this repo (section 2).

In Windows `cmd`, replace `\` with `^`. In PowerShell, use the backtick.

Output files: `tabla7_tabla8.csv`, `tabla9.csv`, `valores_por_corrida.csv` and `figura{2,3,4,5}_*.png`.

## 8. Documentation status

- [x] **Artillery reports.** All 42 inventoried and hashed in `SHA256SUMS.artillery` by `recuperar_artillery.py` (section 3).
- [x] **Queries behind `data.zip`.** Identified and verified against the archived data (section 4).
- [x] **Table 10.** All three rows verified value by value. The raw samples are in `tabla10/` (section 3).
- [x] **Chaos event evidence.** Exported from B's Prometheus on 23/10/2026 and checked offline by `chaos_evidence_b.py` (section 3).
- [x] **Raw TSDB backup of B.** `prometheus-B-20261020.tar.gz` was created on 20/10/2026 on `go-tesis` with:
  ```bash
  sudo kubectl -n landslide exec prometheus-6489f5b487-8wx8n -- tar czf - -C /prometheus . > prometheus-B-20261020.tar.gz
  ```
  It is stored in the team's shared Google Drive folder. SHA-256: `898a017a30e597dcb368e1e326c1b6ed113e433254844c82081c26131848dbdb`. It was kept because B's Prometheus keeps 30 days and has no persistent volume: from 23/10, the raw September data survives only in this backup. A keeps 1 year.
