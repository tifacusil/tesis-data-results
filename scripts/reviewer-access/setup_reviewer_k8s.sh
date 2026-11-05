#!/usr/bin/env bash
# setup_reviewer_k8s.sh - System B (go-tesis) part of the reviewer access: Kubernetes and MySQL.
#
# Usage:  bash setup_reviewer_k8s.sh [expiry]
#   expiry  last day of access, YYYY-MM-DD (default 2027-03-31); the token expires on its own then
#
# Run on go-tesis as the cluster admin user (no sudo), with reviewer-readonly.yaml next to it,
# before `sudo bash setup_reviewer.sh`. Idempotent: re-running issues a fresh token.
# What it does:
#  1. applies reviewer-readonly.yaml (ServiceAccount revisor + read-only RBAC) in namespace landslide;
#  2. issues a token for it valid until <expiry> and writes ~/revisor-kubeconfig.yaml (mode 600);
#  3. creates the SELECT-only MySQL user revisor in the four mysql-*-0 pods, with the password
#     in ~/revisor-mysql-password.txt (generated if missing), using each pod's own root password.
set -euo pipefail
[ "${1:-}" != "-h" ] || { sed -n '2,14p' "$0"; exit 2; }
EXPIRY=${1:-2027-03-31}
NS=landslide
DIR=$(cd "$(dirname "$0")" && pwd)
PW_FILE=$HOME/revisor-mysql-password.txt
export KUBECONFIG=${KUBECONFIG:-$HOME/.kube/config}

kubectl -n "$NS" apply -f "$DIR/reviewer-readonly.yaml"

HOURS=$(( ($(date -u -d "$EXPIRY 23:59" +%s) - $(date -u +%s)) / 3600 ))
TOKEN=$(kubectl -n "$NS" create token revisor --duration="${HOURS}h")
CA=$(kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')
umask 077
cat > "$HOME/revisor-kubeconfig.yaml" <<EOF
apiVersion: v1
kind: Config
clusters:
  - name: go-tesis
    cluster:
      server: https://127.0.0.1:6443
      certificate-authority-data: $CA
users:
  - name: revisor
    user:
      token: $TOKEN
contexts:
  - name: revisor@go-tesis
    context:
      cluster: go-tesis
      user: revisor
      namespace: $NS
current-context: revisor@go-tesis
EOF
echo "kubeconfig: ~/revisor-kubeconfig.yaml (token valid ${HOURS}h)"

[ -s "$PW_FILE" ] || head -c 32 /dev/urandom | base64 | tr -d '/+=\n' | head -c 24 > "$PW_FILE"
for s in data-management early-warning project-management user-management; do
  # The password goes in through stdin and root's through the pod's own env: neither hits argv here.
  kubectl -n "$NS" exec -i "mysql-$s-0" -- sh -c '
    read -r PW; export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"
    mysql -uroot -N -e "
      CREATE USER IF NOT EXISTS revisor@\"%\" IDENTIFIED BY \"$PW\" WITH MAX_USER_CONNECTIONS 5;
      ALTER USER revisor@\"%\" IDENTIFIED BY \"$PW\";
      GRANT SELECT, SHOW VIEW ON \`$MYSQL_DATABASE\`.* TO revisor@\"%\";" &&
    echo "  mysql-'"$s"': revisor has SELECT on $MYSQL_DATABASE"' < "$PW_FILE"
done
echo "Next: sudo bash $DIR/setup_reviewer.sh <public_key.pub> $EXPIRY"
