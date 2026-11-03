#!/usr/bin/env bash
# collect_versions.sh - print the versions of every tool and data source used to build tabla9/.
#
# Usage:  scripts/collect_versions.sh <python> <prom_url> [<prom_url> ...] > versions.txt
#   python    interpreter with this repo's requirements.txt installed (numpy, scipy, matplotlib)
#   prom_url  each Prometheus queried, e.g. http://localhost:9092 http://localhost:9091
#
# Read-only: version flags, sha256sum of the two Python scripts, `docker image inspect`,
# and GET /api/v1/status/buildinfo. No timestamps and no git commit are printed (a commit
# would change with every commit of this repo), so two runs on the same machine give the same bytes.
# curl, docker and the python packages are required (exit 1 if missing); jq, promtool and
# kubectl are optional and reported as "absent".
set -euo pipefail
[ $# -ge 2 ] || { sed -n '2,13p' "$0"; exit 2; }
repo=$(cd "$(dirname "$0")/.." && pwd)
py=$1; shift

echo "os: $(uname -srm)"
echo "bash: ${BASH_VERSION}"
echo "curl: $(curl --version | head -1)"
echo "coreutils sha256sum: $(sha256sum --version | head -1)"
echo "docker client/server: $(docker version --format '{{.Client.Version}} / {{.Server.Version}}')"
echo "prometheus image: $(docker image inspect --format '{{index .RepoDigests 0}}' prom/prometheus:v3.5.4)"
"$py" -I -c 'import sys, numpy, scipy, matplotlib; print("python:", sys.version.split()[0]); print("numpy:", numpy.__version__); print("scipy:", scipy.__version__); print("matplotlib:", matplotlib.__version__)'
for t in jq promtool kubectl; do
  if command -v "$t" >/dev/null; then
    case $t in kubectl) v=$(kubectl version --client 2>/dev/null | head -1);; *) v=$("$t" --version 2>&1 | head -1);; esac
    echo "$t: $v (not used by the scripts)"
  else echo "$t: absent (not needed)"; fi
done
(cd "$repo" && sha256sum generar_resultados.py build_tabla9.py | sed 's/^/script sha256: /')
for u in "$@"; do
  b=$(curl -fsS "$u/api/v1/status/buildinfo")
  echo "prometheus $u buildinfo: $b"
done
