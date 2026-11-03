#!/usr/bin/env bash
# run_all.sh - rebuild the whole tabla9/ evidence set into one folder.
#
# Usage:  scripts/run_all.sh <out_dir> <python> [prom_A_url] [prom_B_url]
#   out_dir     tabla9 to refresh the committed copy, or an empty temp folder to check it
#   prom_A_url  default http://localhost:9092 (restored A backup; live A on concurso: http://localhost:9090)
#   prom_B_url  default http://localhost:9091 (restored B backup; live B on go-tesis: http://localhost:31083)
#
# Steps: 8 range queries (export_prometheus.sh) -> <out>/prometheus/*.json, Table 9 (build_tabla9.py)
# -> <out>/tabla9*.csv, tool versions -> <out>/versions.txt, then <out>/SHA256SUMS over all of them.
# Prometheus must already be serving the September 2026 data (scripts/restore_backups.sh).
# Read-only towards Prometheus and the repo; writes only inside <out_dir>. Stops on the first error.
set -euo pipefail
[ $# -ge 2 ] || { sed -n '2,13p' "$0"; exit 2; }
out=$1 py=$2 pa=${3:-http://localhost:9092} pb=${4:-http://localhost:9091}
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$out/prometheus"

CPU='100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))'
MEM1='(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1048576'                  # methodology §5 form
MEML='(sum(node_memory_MemTotal_bytes) - sum(node_memory_MemAvailable_bytes)) / 1048576'        # data.zip form (§4)
#      system url  name    query  start                 end                   (UTC, step 60s)
while read -r s u name q start end; do
  "$here/export_prometheus.sh" "$u" "${!q}" "$start" "$end" 60s "$out/prometheus/${s}_${name}.json"
done <<EOF
A $pa nivel1_cpu CPU  1789658040           1789661220
A $pa nivel1_mem MEM1 1789658040           1789661220
B $pb nivel1_cpu CPU  1790140980           1790144200
B $pb nivel1_mem MEM1 1790140980           1790144200
A $pa ladder_cpu CPU  2026-09-17T16:00:00Z 2026-09-17T19:00:00Z
A $pa ladder_mem MEML 2026-09-17T16:00:00Z 2026-09-17T19:00:00Z
B $pb ladder_cpu CPU  2026-09-23T06:10:00Z 2026-09-23T09:10:00Z
B $pb ladder_mem MEML 2026-09-23T06:10:00Z 2026-09-23T09:10:00Z
EOF

"$py" -I "$here/../build_tabla9.py" --prom-dir "$out/prometheus" --out "$out"
"$here/collect_versions.sh" "$py" "$pa" "$pb" > "$out/versions.txt"
(cd "$out" && sha256sum prometheus/*.json tabla9.csv tabla9_por_corrida.csv versions.txt > SHA256SUMS)
cat "$out/SHA256SUMS"
