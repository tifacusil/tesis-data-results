#!/usr/bin/env bash
# logrun.sh - run one shell command and append it, with UTC timestamps and its exit code, to a log.
#
# Usage:  logrun.sh '<command>'
#         BITACORA=/path/log logrun.sh '<command>'     (default: tabla9/bitacora.log in this repo)
#
# The command runs in `bash -c`, so pipes and redirections work inside the quotes.
# Its stdout/stderr pass through unchanged. logrun.sh exits with the command's exit code.
# Stand-in for `script(1)`, which Git Bash on Windows does not ship.
# Writes only to the log file; the command itself decides what else is touched.
set -uo pipefail
[ $# -eq 1 ] || { echo "usage: logrun.sh '<command>'" >&2; exit 2; }
log=${BITACORA:-$(cd "$(dirname "$0")/.." && pwd)/tabla9/bitacora.log}
start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
bash -o pipefail -c "$1"
rc=$?
printf '%s  end=%s  exit=%d  cwd=%s\n    $ %s\n' "$start" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$rc" "$PWD" "$1" >> "$log"
exit $rc
