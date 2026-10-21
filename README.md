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
| [`docs/setup-guide.md`](docs/setup-guide.md) | Deploying System A and System B from scratch, as surveyed on the live servers: versions, ports, systemd units, nginx + consul-template, k3s, image digests, and what could not be verified. |
| [`docs/metrics-methodology.md`](docs/metrics-methodology.md) | How the metrics were obtained in the September 2026 campaign: environments, load tests and chaos, the `data.zip` export and its queries, the 1 frame/s level, windows and aggregation, and how to run `generar_resultados.py`. |

Suggested reading order: set up the systems (setup guide), run the tests
(infra runbooks, linked from the setup guide), then extract and process the
metrics (methodology).

## Contents

| path | what it is |
|---|---|
| [`generar_resultados.py`](generar_resultados.py) | Regenerates Figures 2–5 and Tables 7–9 from the raw inputs. Usage: [methodology §7](docs/metrics-methodology.md#7-running-the-script). |
| [`reconstruir_data_zip.py`](reconstruir_data_zip.py) | Finds and verifies the PromQL queries that produced each `data.zip` CSV column. See [methodology §4](docs/metrics-methodology.md#4-the-datazip-export). |
| [`reconstruccion-A/`](reconstruccion-A/), [`reconstruccion-B/`](reconstruccion-B/) | Output of `reconstruir_data_zip.py`: the reconstructed CSVs and, per CSV, a `.consultas.md` with the query chosen for each column and its match. |
| [`config/system-a/nginx/`](config/system-a/nginx/) | System A's nginx and consul-template configuration, copied from the server. Used by [setup guide §3.7](docs/setup-guide.md#37-nginx--consul-template-http-gateway-80-and-tcp-5100). |

The raw inputs (`data.zip`, the Artillery reports, the Prometheus TSDB
backup) are not in this repo; the methodology says where each one comes from
and gives the SHA-256 of `data.zip`, its CSVs and the TSDB backup.
