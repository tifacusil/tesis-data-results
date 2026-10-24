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
| [`docs/metrics-methodology.md`](docs/metrics-methodology.md) | How the metrics were obtained in the September 2026 campaign: environments, load tests and chaos, the `data.zip` export and its queries, the 1 frame/s level, windows and aggregation, how to run `generar_resultados.py`, and how to check B's chaos events with `chaos_evidence_b.py`. |

## Contents

| path | what it is |
|---|---|
| [`generar_resultados.py`](generar_resultados.py) | Regenerates Figures 2–5 and Tables 7–9 from the raw inputs. Usage: [methodology §7](docs/metrics-methodology.md#7-running-the-script). |
| [`chaos_evidence_b.py`](chaos_evidence_b.py) | Checks, offline and from frozen files, what B did during its three chaos events on 23/09/2026: Redis-buffer ACKs during the broker outage, the tripled buffer metric, the liveness restart during the pause and node CPU. Exits with code 1 if a check fails. See [methodology, *Chaos event evidence*](docs/metrics-methodology.md#chaos-event-evidence-chaos_evidence_bpy). |
| [`recuperar_artillery.py`](recuperar_artillery.py) | Inventories the 42 Artillery reports in `data/A - SPETIEMBRE 5 RUNS` and `data/B - SEPTIEMBRE 5 RUNS V2`: windows, aggregate, p95, start/end in UTC, SHA-256. It copies the usable ones with an `A_`/`B_` prefix. See [methodology, *Artillery report inventory*](docs/metrics-methodology.md#artillery-report-inventory-recuperar_artillerypy). |
| [`SHA256SUMS.artillery`](SHA256SUMS.artillery) | SHA-256 of those 42 reports, for `sha256sum -c`. |
| [`reconstruir_data_zip.py`](reconstruir_data_zip.py) | Finds and verifies the PromQL queries that produced each `data.zip` CSV column. See [methodology §4](docs/metrics-methodology.md#4-the-datazip-export). |
| [`reconstruccion-A/`](reconstruccion-A/), [`reconstruccion-B/`](reconstruccion-B/) | Output of `reconstruir_data_zip.py`: the reconstructed CSVs and, per CSV, a `.consultas.md` with the query chosen for each column and its match. |
| [`tabla10/`](tabla10/) | Raw Prometheus samples from B, with `SHA256SUMS`, that verify the three rows of Table 10 (broker kill, pause, delay towards data-analysis). See [methodology, *Table 10 verification*](docs/metrics-methodology.md#table-10-verification). |
| [`config/system-a/nginx/`](config/system-a/nginx/) | System A's nginx and consul-template configuration, copied from the server. Used by [setup guide §3.7](docs/setup-guide.md#37-nginx--consul-template-http-gateway-80-and-tcp-5100). |
| [`data/`](data/) | Raw inputs: the Artillery reports of both systems with their chaos snapshots (`A - SPETIEMBRE 5 RUNS/`, `B - SEPTIEMBRE 5 RUNS V2/`), B's two 12 h CSVs from `data.zip`, the frozen chaos-event export (`evidencia-b-0923/`) and the data-receiving logs. The methodology says where each one comes from and gives their SHA-256. `data/output/` holds the figures and tables written by `generar_resultados.py`. |

Not in this repo: the rest of `data.zip` (the ladder CSVs and A's 12 h CSVs),
the 1 frame/s extractions (`nivel1/`) and the Prometheus TSDB backup, which is
in the team's shared Google Drive folder. The methodology gives the SHA-256 of
`data.zip`, its CSVs and the TSDB backup, and the queries that rebuild `nivel1/`.

## Quick check

From the root of this repo, with Python 3.11 or later (standard library only; on Windows, `py` instead of `python3`):

```bash
sha256sum -c SHA256SUMS.artillery
python3 recuperar_artillery.py
python3 chaos_evidence_b.py verify \
  --evidence data/evidencia-b-0923 \
  --artillery "data/B - SEPTIEMBRE 5 RUNS V2/sustained-12h.json" \
  --logs data/data-receiving-logs-2026-09-23 \
  --series data/B-12h-0923-timeseries.csv \
  --saturation data/B-12h-0923-saturation.csv \
  --snapshots "data/B - SEPTIEMBRE 5 RUNS V2/chaos"
```

Expected: 42 `OK` lines, `42 JSON checked, 42 USABLE, 0 partial or unusable.`, then 9 `[OK]` lines and `All checks passed.`
