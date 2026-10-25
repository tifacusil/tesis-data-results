# tesis-data-results

Data, scripts and documentation behind the results of the thesis that
compares **System A** (the baseline replicating Bai et al. 2020: Java,
C# and Python on systemd) with **System B** (the Go rewrite on k3s) for
landslide monitoring.

The systems' code lives in their own repos (A without a prefix, B with the
`go-` prefix); the manifests and test tooling in
[`tifacusil/go-tesis-infra`](https://github.com/tifacusil/go-tesis-infra).

## Documentation

| document | what it covers |
|---|---|
| [`docs/setup-guide.md`](docs/setup-guide.md) | Deploying System A and System B from scratch, as surveyed on the live servers: versions, ports, systemd units, MySQL/Redis/RabbitMQ/Consul setup, nginx + consul-template, k3s, image digests and A ↔ B version parity. |
| [`docs/metrics-methodology.md`](docs/metrics-methodology.md) | How the metrics were obtained in the September 2026 campaign: environments, load tests and chaos, the `data.zip` export and its queries, the 1 frame/s level, windows and aggregation, how to run `generar_resultados.py`, how to check B's chaos events with `chaos_evidence_b.py`, the `go-tesis-infra` commits that ran the campaign, and how to restore the Prometheus backups. |

## Contents

| path | what it is |
|---|---|
| [`generar_resultados.py`](generar_resultados.py) | Regenerates Figures 2–5, Tables 7–9 and the other files in `data/output/` from the inputs in `data/`. Needs [`requirements.txt`](requirements.txt). Usage: [methodology §7](docs/metrics-methodology.md#7-running-the-script). |
| [`test_generar_resultados.py`](test_generar_resultados.py) | Runs `generar_resultados.py` and checks Tables 7, 8 and 9 against the published values, and that two runs give identical files. Prints `OK`. |
| [`chaos_evidence_b.py`](chaos_evidence_b.py) | Checks, offline and from frozen files, what B did during its three chaos events on 23/09/2026: Redis-buffer ACKs during the broker outage, the tripled buffer metric, the liveness restart during the pause and node CPU. Exits with code 1 if a check fails. See [methodology, *Chaos event evidence*](docs/metrics-methodology.md#chaos-event-evidence-chaos_evidence_bpy). |
| [`recuperar_artillery.py`](recuperar_artillery.py) | Inventories the 42 Artillery reports in `data/A - SPETIEMBRE 5 RUNS` and `data/B - SEPTIEMBRE 5 RUNS V2`: windows, aggregate, p95, start/end in UTC, SHA-256. It copies the usable ones with an `A_`/`B_` prefix. See [methodology, *Artillery report inventory*](docs/metrics-methodology.md#artillery-report-inventory-recuperar_artillerypy). |
| [`client_cpu.py`](client_cpu.py) | Client-machine CPU (whole PC, Artillery, DTU emulators) per ladder run and level, in the effective window. Writes `data/output/client-cpu-*.csv`. See [methodology, *Client CPU*](docs/metrics-methodology.md#client-cpu-client_cpupy). |
| [`SHA256SUMS.artillery`](SHA256SUMS.artillery) | SHA-256 of those 42 reports, for `sha256sum -c`. |
| [`reconstruir_data_zip.py`](reconstruir_data_zip.py) | Finds and verifies the PromQL queries that produced each `data.zip` CSV column. See [methodology §4](docs/metrics-methodology.md#4-the-datazip-export). |
| [`reconstruccion-A/`](reconstruccion-A/), [`reconstruccion-B/`](reconstruccion-B/) | Output of `reconstruir_data_zip.py`: the reconstructed CSVs and, per CSV, a `.consultas.md` with the query chosen for each column and its match. The reconstructed CSVs come from new queries and are not byte-identical to the `data.zip` originals: they are not script inputs. |
| [`tabla10/`](tabla10/) | Raw Prometheus samples from B, with `SHA256SUMS`, that verify the three rows of Table 10 (broker kill, pause, delay towards data-analysis). See [methodology, *Table 10 verification*](docs/metrics-methodology.md#table-10-verification). |
| [`config/system-a/nginx/`](config/system-a/nginx/) | System A's nginx and consul-template configuration, copied from the server. Used by [setup guide §3.7](docs/setup-guide.md#37-nginx--consul-template-http-gateway-80-and-tcp-5100). |
| [`data/`](data/) | Raw inputs: the Artillery reports of both systems with their chaos snapshots (`A - SPETIEMBRE 5 RUNS/`, `B - SEPTIEMBRE 5 RUNS V2/`), `data.zip` (`data/data.zip`), the two ladder CSVs and B's two 12 h CSVs extracted from it, the 1 frame/s extractions (`nivel1/`), the frozen chaos-event export (`evidencia-b-0923/`) and the data-receiving logs. The methodology says where each one comes from and gives their SHA-256. `data/output/` holds the figures and tables written by `generar_resultados.py`. |

Not in this repo: the Prometheus TSDB backups of A and B (14/10/2026, 858 MB; B also
20/10/2026), because of their size. The methodology gives their SHA-256, and
[§9](docs/metrics-methodology.md#9-restoring-the-prometheus-backups) explains how to restore them
and repeat every Prometheus extraction from them.

## Quick check

From the root of this repo, with Python 3.11 or later (standard library only; on Windows, `py` instead of `python3`):

```bash
sha256sum -c SHA256SUMS.artillery
(cd tabla10 && sha256sum -c SHA256SUMS)
python3 recuperar_artillery.py
python3 chaos_evidence_b.py verify \
  --evidence data/evidencia-b-0923 \
  --artillery "data/B - SEPTIEMBRE 5 RUNS V2/sustained-12h.json" \
  --logs data/data-receiving-logs-2026-09-23 \
  --series data/B-12h-0923-timeseries.csv \
  --saturation data/B-12h-0923-saturation.csv \
  --snapshots "data/B - SEPTIEMBRE 5 RUNS V2/chaos"
python3 client_cpu.py --sistema A "data/A - SPETIEMBRE 5 RUNS" \
  --sistema B "data/B - SEPTIEMBRE 5 RUNS V2" --out data/output
git diff --exit-code data/output
```

Expected: 42 `OK` lines, then 21 more for `tabla10/`, `42 JSON checked, 42 USABLE, 0 partial or unusable.`, then 9 `[OK]` lines and `All checks passed.`, then the client CPU table and no diff in `data/output`.

## Full regeneration

Figures 2–5 and Tables 7–9 need NumPy, SciPy and Matplotlib. With Python 3.13.15 and the pinned versions in `requirements.txt`, a run reproduces `data/output/`. On Windows it is byte for byte. On Linux, the CSVs are byte for byte and the PNGs are pixel for pixel, because the PNG compression differs (methodology §7):

```bash
python3 -m venv venv && . venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 test_generar_resultados.py
python3 generar_resultados.py   --escalera-a "data/A - SPETIEMBRE 5 RUNS" --escalera-b "data/B - SEPTIEMBRE 5 RUNS V2"   --prom-a data/A-ladder-0917-timeseries.csv --prom-b data/B-ladder-0923-timeseries.csv   --nivel1-dir data/nivel1   --sat-b data/B-12h-0923-saturation.csv --serie-b data/B-12h-0923-timeseries.csv   --salida data/output
git diff --exit-code data/output
```

Expected: `OK` from the test, then no diff in `data/output` (on Linux, only the PNG files show as changed). The [`reproduce`](.github/workflows/reproduce.yml) workflow runs this and the quick check on every push and pull request. See [methodology §6–7](docs/metrics-methodology.md#6-windows-and-aggregation).
