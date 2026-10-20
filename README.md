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

`data.zip` also contains `A-12h-0918-{timeseries,saturation}.csv`, `resources-summary.json` and `RESUMEN.md`. The script does not use them, but the idle values and the maxima in Table 10 come from them.

### Expected CSV columns

- `*-timeseries.csv`: `time` (ISO 8601, UTC), `fps`, `node_cpu_pct`, `node_mem_used_mib`, `cpu_pct_<service>`, `mem_mib_<service>`.
- `B-12h-0923-saturation.csv`: `time`, `fps`, `q_ew_evaluate`, `q_dm_persist`, `q_dead_letter`, `ew_consumed_fps`, `ew_dropped_5m`, `dr_dropped_5m`, `dm_dlq_5m`, `redis_buffer_pending`, `pod_restarts`, `rabbit_up`.

Services: `data-receiving`, `data-management`, `early-warning`, `data-analysis`, `project-management` and `user-management`.

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

The `results/A` and `results/B` folders were archived as `A - SPETIEMBRE 5 RUNS` and `B - SEPTIEMBRE 5 RUNS V2`. These are the paths passed to `--escalera-a` and `--escalera-b`. `node load-tests/aggregate-results.js <SYSTEM>` gives a quick per-system summary, but the article's figures come from `generar_resultados.py`.

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

Metrics documented in `RESUMEN.md`:

| Column | Definition |
|---|---|
| `node_cpu_pct` | `100 * (1 - idle)` from node_exporter |
| `node_mem_used_mib` | `MemTotal - MemAvailable`, in MiB |
| `mem_mib_<service>` | B: RSS summed over replicas. A: RSS for the Python/.NET services and `jvm_memory_used` for the Java services |
| `q_ew_evaluate`, `q_dead_letter` | RabbitMQ queues `early_warning.evaluate` and `sensors.dead_letter` (B only) |
| `dr_dropped_5m`, `ew_dropped_5m`, `dm_dlq_5m` | `data_receiving_messages_dropped_total`, `ew_messages_dropped_total` and `dm_messages_dlq_total` |

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
  --escalera-a "A - SPETIEMBRE 5 RUNS" \
  --escalera-b "B - SEPTIEMBRE 5 RUNS V2" \
  --prom-a A-ladder-0917-timeseries.csv \
  --prom-b B-ladder-0923-timeseries.csv \
  --nivel1-dir nivel1 \
  --sat-b B-12h-0923-saturation.csv \
  --serie-b B-12h-0923-timeseries.csv \
  --salida salida
```

In Windows `cmd`, replace `\` with `^`. In PowerShell, use the backtick.

Output files: `tabla7_tabla8.csv`, `tabla9.csv`, `valores_por_corrida.csv` and `figura{2,3,4,5}_*.png`.

