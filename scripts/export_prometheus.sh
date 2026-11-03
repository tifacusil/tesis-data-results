#!/usr/bin/env bash
# export_prometheus.sh - save one Prometheus range query (/api/v1/query_range) as raw JSON.
#
# Usage:  export_prometheus.sh <prom_url> <promql> <start> <end> <step> <out.json>
#   prom_url  e.g. http://localhost:9092 (restored A), http://localhost:9091 (restored B),
#             http://localhost:9090 (live A on concurso), http://localhost:31083 (live B NodePort)
#   start/end Unix epoch seconds (UTC) or RFC 3339 (2026-09-17T15:14:00Z); both ends inclusive
#   step      e.g. 60s
#
# Read-only: one HTTP GET. The response body is written unchanged, so files are comparable
# byte for byte with earlier `curl -G ... > file` extractions (same parameter order).
# Fails (exit 1, no output file left) on HTTP error, status != success, or an empty result.
set -euo pipefail
[ $# -eq 6 ] || { sed -n '2,12p' "$0"; exit 2; }
url=$1 query=$2 start=$3 end=$4 step=$5 out=$6
tmp="$out.part"
trap 'rm -f "$tmp"' EXIT
curl -fsS -G "$url/api/v1/query_range" \
  --data-urlencode "query=$query" --data-urlencode "start=$start" \
  --data-urlencode "end=$end" --data-urlencode "step=$step" > "$tmp"
grep -q '"status":"success"' "$tmp" || { echo "query failed: $(head -c 300 "$tmp")" >&2; exit 1; }
grep -q '"result":\[\]' "$tmp" && { echo "empty result for: $query [$start, $end]" >&2; exit 1; }
mv "$tmp" "$out"
