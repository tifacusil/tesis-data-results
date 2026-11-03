# Table 9 from the Prometheus backups: replication guide

[`tabla9/`](../tabla9/) rebuilds the evidence behind **Table 9** of the thesis: node CPU % and node memory used, in MiB, for System A and System B at 1, 10, 50 and 100 frames/s. It starts from the raw Prometheus data in the 14/10/2026 TSDB backups ([methodology §9](metrics-methodology.md#9-restoring-the-prometheus-backups)) and the Artillery reports in `data/`. It also records the tool versions.

**Result:** the rebuilt [`tabla9/tabla9.csv`](../tabla9/tabla9.csv) is byte-identical to the published [`data/output/tabla9.csv`](../data/output/tabla9.csv). The four 1 frame/s exports are byte-identical to [`data/nivel1/`](../data/nivel1/). A clean run of the scripts in an empty folder reproduces all 11 files in `tabla9/SHA256SUMS` (step 10).

History: the package was first built on 2026-11-03, between 01:03 and 01:06 UTC, in a stand-alone folder (`~/evidencia-v6`). It was moved into this repo at 01:14 UTC and regenerated in place. All commands from both phases are in [`tabla9/bitacora.log`](../tabla9/bitacora.log), unedited, so its first entries show the old paths.

Scope: Table 9 and the versions only. Tables 7, 8 and 10 and Figures 2–5 have their own checks (README, *Quick check* and *Full regeneration*).

## Contents

| Path | What it is |
|---|---|
| `tabla9/prometheus/{A,B}_nivel1_{cpu,mem}.json` | Raw `query_range` responses, 1 frame/s level (step 2) |
| `tabla9/prometheus/{A,B}_ladder_{cpu,mem}.json` | Raw `query_range` responses, levels 10/50/100 (step 3) |
| `tabla9/tabla9.csv` | Table 9 |
| `tabla9/tabla9_por_corrida.csv` | One row per run (40): UTC window, samples used, and the run's median CPU and memory |
| `tabla9/versions.txt` | Tool, library and Prometheus versions, plus the SHA-256 of the two Python scripts (step 8) |
| `tabla9/SHA256SUMS` | SHA-256 of the 11 files above, for `cd tabla9 && sha256sum -c SHA256SUMS` |
| `tabla9/bitacora.log` | UTC start and end time, exit code, working folder and exact command of every step. Not hashed |

| Script | Purpose | Writes |
|---|---|---|
| [`build_tabla9.py`](../build_tabla9.py) `--out <dir> [--prom-dir tabla9/prometheus]` | Table 9 from the JSON files and the Artillery windows. Imports `generar_resultados.py` | 2 CSVs |
| [`scripts/logrun.sh`](../scripts/logrun.sh) `'<cmd>'` | Runs one command and appends it, with its timestamps and exit code, to `tabla9/bitacora.log` (or `$BITACORA`) | the log only |
| [`scripts/restore_backups.sh`](../scripts/restore_backups.sh) `<backup_dir> <work_dir> [port_A] [port_B]` | Checks the SHA-256 of the archives, unpacks them, and starts `prom-a` and `prom-b`: methodology §9 as a script | `<work_dir>`, 2 containers |
| [`scripts/export_prometheus.sh`](../scripts/export_prometheus.sh) `<url> <promql> <start> <end> <step> <out>` | One range query, saved as raw JSON | `<out>` |
| [`scripts/collect_versions.sh`](../scripts/collect_versions.sh) `<python> <prom_url>...` | Versions, printed to stdout | stdout |
| [`scripts/run_all.sh`](../scripts/run_all.sh) `<out> <python> [prom_A] [prom_B]` | Runs steps 2–4 and 8 in one go, then writes `SHA256SUMS` | `<out>` |

Each script prints its usage when run with no arguments. They use `set -euo pipefail`, or Python assertions in `build_tabla9.py`, and stop with a non-zero exit code at the first failure. None of them modifies its inputs. They only write to the output path you give them. The one exception is `restore_backups.sh`, which writes into its work folder because Prometheus compacts the blocks it opens. It never touches the `.tar.gz` archives.

`.gitattributes` keeps `tabla9/**` byte for byte (`-text`) and the `*.sh` files with LF endings, because bash fails on CR line endings.

## Requirements

| Item | Version used | Needed for |
|---|---|---|
| Bash | 5.3.15 (Git Bash, MINGW64, Windows 11) | all scripts |
| curl | 8.21.0 | `export_prometheus.sh`, readiness checks |
| GNU coreutils `sha256sum` | 8.32 | checksums |
| Docker | 29.8.0 client and server (Docker Desktop) | restored Prometheus |
| Prometheus image | `prom/prometheus:v3.5.4@sha256:a75c5a35bc21d7afe69551eefa3cb1e1fb1775fe759408007a66b54ec3de1f29`, the same version as the servers | restored Prometheus |
| Python | 3.13.15, with this repo's `requirements.txt` (numpy 2.5.3, scipy 1.18.1, matplotlib 3.11.2) | `build_tabla9.py` |
| Backups | `A-prometheus-tsdb-20261014.tar.gz` (`157e6cf3…8d66`) and `B-prometheus-tsdb-20261014.tar.gz` (`7425191c…1877`), not in this repo (methodology §9) | the September 2026 data |
| Disk | 2.2 GB free for the unpacked TSDBs | |

Not needed: `jq` (the scripts use `grep` and Python to check JSON), `promtool` (Prometheus itself returns HTTP 400 on bad PromQL, see step 9), `kubectl`, and `script` (replaced by `logrun.sh`).

**Access and ports:** `localhost` only. Restored A is on **9092** and restored B is on **9091**, the same ports as methodology §9. No access to the servers is needed. B's live Prometheus keeps 30 days and no longer holds September.

**Time zone:** every `start`, `end` and window is in **UTC**. The Unix epochs are UTC by definition, and the ISO times carry a `Z` suffix. The PC runs at −05:00.

**Offline check (no Docker, no backups):** the committed JSON files are enough to rebuild Table 9. The [`reproduce`](../.github/workflows/reproduce.yml) workflow does this on every push:

```bash
(cd tabla9 && sha256sum -c SHA256SUMS)
python3 build_tabla9.py --out /tmp/t9 && cmp /tmp/t9/tabla9.csv data/output/tabla9.csv && cmp /tmp/t9/tabla9_por_corrida.csv tabla9/tabla9_por_corrida.csv
```

## Steps

From the root of this repo. Set these variables once, and change the paths for another machine:

```bash
BACKUPS=/c/Users/adria/Escritorio/TESIS/respaldo-prometheus   # folder with the two .tar.gz and SHA256SUMS.txt
WORK=/c/Users/adria/prom-restore-v6                            # disposable, 2.2 GB
PY=/c/Users/adria/Escritorio/TESIS/resultados/venv/Scripts/python.exe   # any python with requirements.txt
L=scripts/logrun.sh
```

### 1. Check and restore the backups

```bash
$L "cd $BACKUPS && sha256sum A-prometheus-tsdb-20261014.tar.gz B-prometheus-tsdb-20261014.tar.gz"
$L "scripts/restore_backups.sh $BACKUPS $WORK 9092 9091"
```

Purpose: start one Prometheus per system on the frozen data. It uses no scrape jobs and a retention of `100y`. With the default 15 days, Prometheus would delete the September blocks on start-up. Expected output:

```
A-prometheus-tsdb-20261014.tar.gz: OK
B-prometheus-tsdb-20261014.tar.gz: OK
Prometheus Server is Ready.
Prometheus Server is Ready.
```

Here this took 16 s (log: 01:03:47 → 01:04:03 UTC). On a slower disk, the WAL replay can take minutes. The script waits up to 10 minutes per instance. `docker ps` should then show `prom-a … 0.0.0.0:9092->9090/tcp` and `prom-b … 0.0.0.0:9091->9090/tcp`.

### 2. Export the 1 frame/s level

```bash
CPU='100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))'
MEM1='(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1048576'
$L "scripts/export_prometheus.sh http://localhost:9092 '$CPU'  1789658040 1789661220 60s tabla9/prometheus/A_nivel1_cpu.json"
$L "scripts/export_prometheus.sh http://localhost:9092 '$MEM1' 1789658040 1789661220 60s tabla9/prometheus/A_nivel1_mem.json"
$L "scripts/export_prometheus.sh http://localhost:9091 '$CPU'  1790140980 1790144200 60s tabla9/prometheus/B_nivel1_cpu.json"
$L "scripts/export_prometheus.sh http://localhost:9091 '$MEM1' 1790140980 1790144200 60s tabla9/prometheus/B_nivel1_mem.json"
$L "sha256sum tabla9/prometheus/*_nivel1_*.json data/nivel1/*.json"
```

| File | Query | start | end | step |
|---|---|---|---|---|
| `A_nivel1_cpu.json` | `100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))` | 1789658040 (2026-09-17T15:14:00Z) | 1789661220 (2026-09-17T16:07:00Z) | 60s |
| `A_nivel1_mem.json` | `(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1048576` | same | same | 60s |
| `B_nivel1_cpu.json` | CPU query | 1790140980 (2026-09-23T05:23:00Z) | 1790144200 (2026-09-23T06:16:40Z) | 60s |
| `B_nivel1_mem.json` | memory query | same | same | 60s |

These are the windows of [methodology §5](metrics-methodology.md#5-extracting-the-1-frames-level): they cover the five runs of the level. Expected output: the same four hashes for both copies, which are also the ones listed in §5 (folder prefixes left out):

```
45cd4a36145a120353da3373b0dd4712734a0ab58c9281b73cdf4b20f57dd6bc  A_nivel1_cpu.json
4a629a272a6b68af1b2e3769cb6aec823c94b7059a8598c67efc5185436eefb1  A_nivel1_mem.json
b11b20b5bb187360e824c9b8dbad56277c06db301b17154f84bed305875db046  B_nivel1_cpu.json
d06842f3c080aaa2479debaa8739952f16792457d6f368abe600e3df7594862c  B_nivel1_mem.json
```

### 3. Export levels 10, 50 and 100

```bash
MEML='(sum(node_memory_MemTotal_bytes) - sum(node_memory_MemAvailable_bytes)) / 1048576'
$L "scripts/export_prometheus.sh http://localhost:9092 '$CPU'  2026-09-17T16:00:00Z 2026-09-17T19:00:00Z 60s tabla9/prometheus/A_ladder_cpu.json"
$L "scripts/export_prometheus.sh http://localhost:9092 '$MEML' 2026-09-17T16:00:00Z 2026-09-17T19:00:00Z 60s tabla9/prometheus/A_ladder_mem.json"
$L "scripts/export_prometheus.sh http://localhost:9091 '$CPU'  2026-09-23T06:10:00Z 2026-09-23T09:10:00Z 60s tabla9/prometheus/B_ladder_cpu.json"
$L "scripts/export_prometheus.sh http://localhost:9091 '$MEML' 2026-09-23T06:10:00Z 2026-09-23T09:10:00Z 60s tabla9/prometheus/B_ladder_mem.json"
```

| File | Query | start (UTC) | end (UTC) | step | samples |
|---|---|---|---|---|---|
| `A_ladder_cpu.json` | CPU query | 2026-09-17T16:00:00Z (1789660800) | 2026-09-17T19:00:00Z (1789671600) | 60s | 181 |
| `A_ladder_mem.json` | `(sum(node_memory_MemTotal_bytes) - sum(node_memory_MemAvailable_bytes)) / 1048576` | same | same | 60s | 181 |
| `B_ladder_cpu.json` | CPU query | 2026-09-23T06:10:00Z (1790143800) | 2026-09-23T09:10:00Z (1790154600) | 60s | 181 |
| `B_ladder_mem.json` | memory query (`sum` form) | same | same | 60s | 181 |

These are the windows and queries of `data/A-ladder-0917-timeseries.csv` and `data/B-ladder-0923-timeseries.csv`, which the published Table 9 used ([methodology §4](metrics-methodology.md#4-the-datazip-export)). Cross-check (log, 01:06:06 UTC): rounded to the CSV's decimals (2 for CPU, 1 for memory), all 181 values of each of the four series equal the `node_cpu_pct` and `node_mem_used_mib` columns of those CSVs:

```
A node_cpu_pct 181 rows, mismatches: 0
A node_mem_used_mib 181 rows, mismatches: 0
B node_cpu_pct 181 rows, mismatches: 0
B node_mem_used_mib 181 rows, mismatches: 0
```

### 4. Build Table 9

```bash
$L "$PY -I build_tabla9.py --out tabla9"
$L "diff tabla9/tabla9.csv data/output/tabla9.csv && echo IDENTICAL"
```

Expected output: `IDENTICAL`, and:

```
tramas_s,cpu_A,cpu_B,mem_ocupada_A_MiB,mem_ocupada_B_MiB,corridas_A,corridas_B
1,5.7,24.8,3328.5,2826.9,5,5
10,13.3,35.3,3334.1,2832.9,5,5
50,39.7,61.3,3338.3,2864.4,5,5
100,68.0,80.7,3388.5,2886.4,5,5
```

### 5. How each run's time window was obtained

There is no separate list of run times. The windows come from the Artillery reports themselves (`data/A - SPETIEMBRE 5 RUNS/vu-XXX-rN.json`, `data/B - SEPTIEMBRE 5 RUNS V2/...`), through the same function the article used. `build_tabla9.py` imports `generar_resultados.cargar_escalera` rather than copying it:

1. Each report has `intermediate[]`, one entry per 10 s period. `period` is the period's start, in Unix **milliseconds** (UTC).
2. Periods with no `dtu_tcp.round_trip_ms` measurements are dropped.
3. The first 18 remaining periods (3 min) are the **warm-up** and are excluded. The next 42 periods (7 min) are the **effective window**: `[period_18, period_59 + 10 s)`.
4. Prometheus samples with `window_start <= t < window_end` belong to the run. With a 60 s step that is always 7 samples.

The 40 windows are in `tabla9/tabla9_por_corrida.csv`. Span per level, from the first window start to the last window end:

| System, level | first start (UTC) | last end (UTC) | samples per run |
|---|---|---|---|
| A, 1 | 2026-09-17 15:17:00 | 16:06:50 | 7 7 7 7 7 |
| A, 10 | 16:10:40 | 17:00:20 | 7 7 7 7 7 |
| A, 50 | 17:04:10 | 17:54:00 | 7 7 7 7 7 |
| A, 100 | 17:57:50 | 18:47:40 | 7 7 7 7 7 |
| B, 1 | 2026-09-23 05:26:10 | 06:16:30 | 7 7 7 7 7 |
| B, 10 | 06:20:20 | 07:10:50 | 7 7 7 7 7 |
| B, 50 | 07:14:40 | 08:05:00 | 7 7 7 7 7 |
| B, 100 | 08:09:00 | 08:59:20 | 7 7 7 7 7 |

Every window lies inside its export range (step 2 for level 1, step 3 for the rest). `build_tabla9.py` asserts that each window gets at least one sample.

### 6. Aggregation

Run value: the median of its 7 samples. Level value: the median of the 5 run values, rounded to 0.1. This is the rule of `generar_resultados.py` ([methodology §6](metrics-methodology.md#6-windows-and-aggregation)).

### 7. Run steps 2–4 and 8 in one go

```bash
$L "scripts/run_all.sh tabla9 $PY http://localhost:9092 http://localhost:9091"
```

### 8. Versions and checksums

```bash
$L "scripts/collect_versions.sh $PY http://localhost:9092 http://localhost:9091 > tabla9/versions.txt"
$L "cd tabla9 && sha256sum prometheus/*.json tabla9.csv tabla9_por_corrida.csv versions.txt > SHA256SUMS"
```

`versions.txt` holds what the Requirements table lists, the SHA-256 of `generar_resultados.py` and `build_tabla9.py`, and `GET /api/v1/status/buildinfo` of both restored instances: `version 3.5.4`, revision `9e1e3b5104fff654a84131b9854be18862569bb7`, go1.25.11. It records file hashes and not the git commit, because a commit would change the file with every commit of this repo.

### 9. Failure checks

These confirm that the scripts stop instead of writing bad files. Each is in the log with its non-zero exit code.

| Case | Command | Result |
|---|---|---|
| Query with no series | `export_prometheus.sh http://localhost:9091 'up{job="nope"}' 2026-09-23T06:10:00Z 2026-09-23T06:20:00Z 60s …/neg1.json` | `empty result for: …`, exit 1, no file left |
| No server | `export_prometheus.sh http://localhost:9999 up 0 60 60s …/neg2.json` | `curl: (7) Failed to connect`, exit 7, no file left |
| Bad PromQL | `export_prometheus.sh http://localhost:9091 'sum(' 0 60 60s …/neg3.json` | `curl: (22) … error: 400`, exit 22 |

### 10. Replicability check

Run everything from scratch in an empty temporary folder, then compare with the committed `tabla9/`:

```bash
T=<empty temp dir>/replica-repo
$L "scripts/run_all.sh $T $PY > /dev/null && cmp $T/SHA256SUMS tabla9/SHA256SUMS && (cd $T && sha256sum -c $PWD/tabla9/SHA256SUMS) && diff -r --exclude=bitacora.log $T tabla9 && echo REPLICA-EQUAL"
$L "diff tabla9/tabla9.csv data/output/tabla9.csv && cmp tabla9/prometheus/A_nivel1_cpu.json data/nivel1/A_nivel1_cpu.json && … && echo MATCHES-PUBLISHED"
```

Results:

| When (UTC) | Where | Result |
|---|---|---|
| 01:05:39–01:05:53 | stand-alone folder vs. a temp folder | 11/11 `OK`, trees and `SHA256SUMS` equal |
| 01:14:55–01:14:59 | regenerated in place in this repo | the 10 data files are unchanged (`DATA-UNCHANGED`). Only `versions.txt` changed, on purpose: the git commit line became script hashes |
| 01:14:59–01:15:02 | this repo vs. a temp folder | 11/11 `OK`, `REPLICA-EQUAL` |
| 01:15:02–01:15:03 | this repo vs. published | `MATCHES-PUBLISHED` (Table 9 and the four `data/nivel1/` files) |

What changes between runs and what does not:

- **The JSON exports** do not change. The Prometheus response holds no request time, and the series are frozen in the backup.
- **The CSVs** do not change. Python prints floats the same way on every platform.
- **`versions.txt`** is identical on the same machine with the same restored ports. It **will** differ on another machine (OS line, curl/docker versions) or with other ports (the URL in the buildinfo lines). A `versions.txt: FAILED` line from `sha256sum -c` is a difference in environment, not in data.
- **`bitacora.log`** always differs (times), and is not hashed.

### 11. Clean-up

```bash
docker rm -f prom-a prom-b
rm -rf $WORK      # the unpacked TSDB copy; the archives stay untouched
```

## Decisions and why

- **Restored backups, not live servers.** B's live Prometheus no longer holds September. Using the 14/10 backups for both systems keeps A and B on the same footing, and the package can be reproduced without server access.
- **Re-export raw JSON instead of reading the `data.zip` CSVs.** The CSVs are rounded, and they were assembled by hand (methodology §4, *Provenance*). The raw JSON has full precision and a documented query, range and step. Step 3 shows that both sources agree, and step 4 shows that they give the same Table 9.
- **Two memory query forms.** The 1 frame/s files use the §5 form, so they stay byte-identical to `data/nivel1/`. The ladder files use the `sum(...)` form of `data.zip`. Each system has one node_exporter, so both give the same number.
- **Export windows.** The level 1 windows are the §5 epochs. The ladder windows are the exact `data.zip` ranges. A wider single window would have worked too, but it would not map one to one onto an archived source.
- **Warm-up excluded, never re-derived.** The run windows come from `generar_resultados.cargar_escalera`, imported. Re-implementing it risked a silently different cut. In particular, empty periods are dropped **before** the 18 warm-up periods are counted.
- **Half-open windows** `[start, end)` with a 60 s step give exactly 7 samples per run. This is the article's rule, unchanged.
- **Duplicate 1 frame/s files.** `tabla9/prometheus/*_nivel1_*.json` duplicate `data/nivel1/`, so `tabla9/` holds every input `build_tabla9.py` reads from Prometheus. CI checks that both copies are identical.
- **Layout.** Following this repo's conventions, the Python script is at the root next to `generar_resultados.py`, the evidence is in `tabla9/` with its own `SHA256SUMS` like `tabla10/`, and this guide is in `docs/`. The shell scripts are in `scripts/`, the first in the repo.

## Problems found

| Problem | Resolution |
|---|---|
| The original request assumed an earlier session that had produced this folder. That session did not exist | Everything was built from scratch, so every command here is one that was actually run |
| Docker daemon not running (`failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`) | Started Docker Desktop. Not logged: it ran before `logrun.sh` existed |
| `python`/`python3` are Microsoft Store stubs ("Python was not found") | Used the existing venv `TESIS/resultados/venv` (Python 3.13.15, same pins as `requirements.txt`) |
| `script(1)` is not available in Git Bash | Wrote `logrun.sh` |
| `jq` and `promtool` are absent | Not needed |
| Windows Python does not accept `/c/...` paths (logged `FileNotFoundError`, exit 1, at 01:05:55 UTC) | Re-ran with `C:/...` paths. Arguments passed from Bash to scripts are converted by Git Bash and are not affected |
| Docker volume paths under Git Bash | `restore_backups.sh` sets `MSYS_NO_PATHCONV=1` and converts paths with `cygpath -w` |
| The first two failure checks (01:05:52 and 01:05:53 UTC) are logged with `exit=0` | That command ended in `; test ! -e <file>`, so the log recorded the exit code of `test`, not of the export. They were re-run at 01:06:03 and 01:06:04 (exit 1 and exit 7), and those are the runs step 9 quotes |
| Importing `generar_resultados` left a `__pycache__/` in the repo | Removed. `build_tabla9.py` sets `sys.dont_write_bytecode`, and `.gitignore` lists `__pycache__/` |
| `core.autocrlf=true` on this PC would check out `.sh` files with CRLF | `.gitattributes`: `*.sh text eol=lf` |
| Read-only exploration (reading docs, `ls`, `grep`) ran before the log existed | It changed nothing. The log starts at the first command that touched evidence (the archive hashes, 01:03:22 UTC) |
| The original request said "docker instead of kubectl" for System A, but the [setup guide](setup-guide.md) says A runs systemd services and its 2 Docker containers are stopped | The table below follows the setup guide. Check on `concurso` with `systemctl list-units --type=service` and `docker ps -a` before relying on either |

Open: none for Table 9. `prometheus-B-20261020.tar.gz` (methodology §8) was not tried.

## Running it on System A (`concurso`) or System B (`go-tesis`) directly

The scripts take URLs, so nothing in them is tied to the restored backups.

| | Restored here | Live System A | Live System B |
|---|---|---|---|
| Prometheus URL | `http://localhost:9092` (A), `:9091` (B) | `http://localhost:9090` on `concurso` | `http://localhost:31083` (NodePort) on `go-tesis` |
| Restore step | `restore_backups.sh` | skip | skip |
| Holds Sept 2026? | yes | yes, retention is 1 year (until about Sept 2027) | **no**, retention is 30 days: use the backups |
| Versions | `collect_versions.sh` as is | systemd, per the setup guide. `curl …/api/v1/status/buildinfo` still gives the Prometheus version. Remove the two `docker` lines of `collect_versions.sh` (they look up the `prom/prometheus:v3.5.4` image), and use `prometheus --version` / `systemctl status prometheus` instead | k3s: replace the two `docker` lines with `sudo kubectl -n landslide get pods -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.containers[*].image}{"\n"}{end}'` |

Example on `concurso`, A only: run the `A` rows of the `run_all.sh` table one by one:

```bash
scripts/export_prometheus.sh http://localhost:9090 "$CPU" 1789658040 1789661220 60s A_nivel1_cpu.json   # etc.
```

`build_tabla9.py` needs this repo and the Python stack. Copy the JSON files back with `scp` and build Table 9 on the PC, which avoids installing the Python stack on the servers.

**Other dates (a new campaign):** change the eight `start`/`end` values in the heredoc of `scripts/run_all.sh`, and the Artillery folders in `ESCALERA` inside `build_tabla9.py`. The run windows then follow automatically from the new reports. Choose each export range so it covers every run window of its level. `build_tabla9.py` stops with an `AssertionError` naming `(system, level, run)` if a window gets no samples.
