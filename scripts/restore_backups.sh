#!/usr/bin/env bash
# restore_backups.sh - start one Prometheus per system, with no scrape jobs, on the 14/10/2026 TSDB backups.
#
# Usage:  restore_backups.sh <backup_dir> <work_dir> [port_A] [port_B]
#   backup_dir  folder with A-/B-prometheus-tsdb-20261014.tar.gz and SHA256SUMS.txt
#   work_dir    empty folder (or one created by a previous run) where the archives are unpacked
#   port_A      host port for System A's restored Prometheus (default 9092)
#   port_B      host port for System B's restored Prometheus (default 9091)
#
# What it touches: never the archives. It verifies their SHA-256, unpacks them into <work_dir>,
# and starts containers prom-a / prom-b with no scrape jobs (nothing new is written to the TSDB).
# Prometheus still compacts the blocks it opens, so <work_dir> is disposable: re-run from the archives.
# Stop afterwards with:  docker rm -f prom-a prom-b
# Exits non-zero on any failure (checksum, unpack, docker, readiness timeout).
set -euo pipefail
[ $# -ge 2 ] || { sed -n '2,15p' "$0"; exit 2; }
backup=$(cd "$1" && pwd); mkdir -p "$2"; work=$(cd "$2" && pwd)
pa=${3:-9092}; pb=${4:-9091}
image='prom/prometheus:v3.5.4@sha256:a75c5a35bc21d7afe69551eefa3cb1e1fb1775fe759408007a66b54ec3de1f29'
winpath() { if command -v cygpath >/dev/null; then cygpath -w "$1"; else echo "$1"; fi; }

(cd "$backup" && grep -- '-prometheus-tsdb-20261014.tar.gz' SHA256SUMS.txt | sha256sum -c -)

# Unpack only once per work_dir; a second run reuses it (delete work_dir for a pristine restore).
[ -d "$work/tsdb-A/prom-respaldo-20261014" ] || { mkdir -p "$work/tsdb-A"; tar xzf "$backup/A-prometheus-tsdb-20261014.tar.gz" -C "$work/tsdb-A"; }
[ -d "$work/tsdb-B/prometheus" ]             || { mkdir -p "$work/tsdb-B"; tar xzf "$backup/B-prometheus-tsdb-20261014.tar.gz" -C "$work/tsdb-B"; }
printf 'global:\n  scrape_interval: 15s\n' > "$work/empty.yml"

for spec in "a $pa tsdb-A/prom-respaldo-20261014" "b $pb tsdb-B/prometheus"; do
  set -- $spec
  docker rm -f "prom-$1" >/dev/null 2>&1 || true
  # retention 100y is required: the default 15 d would delete the September blocks on start-up
  MSYS_NO_PATHCONV=1 docker run -d --name "prom-$1" -p "$2:9090" \
    -v "$(winpath "$work/$3"):/prometheus" -v "$(winpath "$work/empty.yml"):/etc/prometheus/prometheus.yml:ro" \
    "$image" --config.file=/etc/prometheus/prometheus.yml \
    --storage.tsdb.path=/prometheus --storage.tsdb.retention.time=100y >/dev/null
done

for p in "$pa" "$pb"; do
  for _ in $(seq 1 120); do curl -fsS "http://localhost:$p/-/ready" >/dev/null 2>&1 && break; sleep 5; done
  curl -fsS "http://localhost:$p/-/ready" || { echo "Prometheus on :$p not ready after 10 min" >&2; exit 1; }
done
