#!/usr/bin/env bash
# setup_reviewer.sh - create the read-only Linux user "revisor" for the thesis reviewers.
#
# Usage:  sudo bash setup_reviewer.sh <public_key.pub> [expiry]
#         sudo bash setup_reviewer.sh --revoke
#   public_key.pub  SSH public key the reviewers log in with (the private key is handed over apart)
#   expiry          last day of access, YYYY-MM-DD (default 2027-03-31)
#
# Runs on both servers and detects which one it is on (k3s present = System B, go-tesis).
# On System B run setup_reviewer_k8s.sh first: it leaves ~/revisor-kubeconfig.yaml and
# ~/revisor-mysql-password.txt in the invoking user's home. On System A put the MySQL password
# for the reviewer in ~/revisor-mysql-password.txt (any random string) before running this.
#
# What it leaves in place (idempotent, safe to re-run):
#  - user revisor: SSH key only (no password), not in sudo/docker, expires on <expiry>;
#  - ~/.my.cnf with the read-only MySQL credentials, so reviewers never type the password;
#  - a per-user firewall (own nftables table, matched by UID): revisor can only open connections
#    to read-only endpoints. Every other service (Redis, RabbitMQ, Consul, the apps) is rejected.
#      B (k3s):     Kubernetes API (token bound to the "view" role), kubectl proxy, MySQL pods.
#      A (systemd): Prometheus :9090 and MySQL 3306-3310 (SELECT-only user).
#  - A: revisor in systemd-journal (journalctl), the SELECT-only MySQL user on every instance
#    (root via auth_socket, so no password is needed) and Prometheus without
#    --web.enable-lifecycle, so it cannot be stopped or reloaded over HTTP.
set -euo pipefail
[ $# -ge 1 ] || { sed -n '2,24p' "$0"; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
OWNER_HOME=$(getent passwd "${SUDO_USER:?run with sudo from your own user}" | cut -d: -f6)
MYSQL_PW_FILE="$OWNER_HOME/revisor-mysql-password.txt"
if command -v k3s >/dev/null; then MODE=k3s; else MODE=systemd; fi

if [ "$1" = "--revoke" ]; then
  systemctl disable --now revisor-firewall.service 2>/dev/null || true
  nft delete table inet revisor 2>/dev/null || true
  rm -f /etc/systemd/system/revisor-firewall.service /usr/local/sbin/revisor-firewall /usr/local/bin/revisor-mysql
  systemctl daemon-reload
  id revisor >/dev/null 2>&1 && userdel -r revisor
  echo "Linux user revoked. Still to do: DROP USER revisor in MySQL and, on B,"
  echo "kubectl -n landslide delete -f reviewer-readonly.yaml"
  exit 0
fi

PUBKEY=$(cat "$1"); EXPIRY=${2:-2027-03-31}

# --- User ----------------------------------------------------------------------
id revisor >/dev/null 2>&1 || useradd -m -s /bin/bash -e "$EXPIRY" -c "Thesis reviewer (read-only)" revisor
usermod -e "$EXPIRY" -p '*' revisor          # '*' = no password, without locking key login
gpasswd -d revisor sudo   >/dev/null 2>&1 || true
gpasswd -d revisor docker >/dev/null 2>&1 || true
RH=/home/revisor
install -d -m 700 -o revisor -g revisor "$RH/.ssh"
echo "$PUBKEY" > "$RH/.ssh/authorized_keys"
chown revisor:revisor "$RH/.ssh/authorized_keys"; chmod 600 "$RH/.ssh/authorized_keys"

if [ -f "$MYSQL_PW_FILE" ]; then
  printf '[client]\nuser=revisor\npassword=%s\nhost=127.0.0.1\n' "$(tr -d '\n' < "$MYSQL_PW_FILE")" > "$RH/.my.cnf"
  chown revisor:revisor "$RH/.my.cnf"; chmod 600 "$RH/.my.cnf"
fi

# --- Per server ----------------------------------------------------------------
if [ "$MODE" = k3s ]; then
  install -d -m 700 -o revisor -g revisor "$RH/.kube"
  install -m 600 -o revisor -g revisor "$OWNER_HOME/revisor-kubeconfig.yaml" "$RH/.kube/config"
  # k3s's kubectl wrapper ignores ~/.kube/config unless KUBECONFIG is set.
  for f in .bashrc .profile; do
    grep -q 'KUBECONFIG=' "$RH/$f" 2>/dev/null || sed -i '1i export KUBECONFIG=$HOME/.kube/config' "$RH/$f"
  done
  command -v mysql >/dev/null || { apt-get update -qq && apt-get install -y -qq mysql-client-core-8.0; }
  cat > /usr/local/bin/revisor-mysql <<'EOF'
#!/bin/sh
# Read-only MySQL session on one service's database; the pod IP changes when it restarts.
[ -n "$1" ] || { echo "usage: revisor-mysql <data-management|early-warning|project-management|user-management> [mysql args]"; exit 1; }
S=$1; shift
IP=$(kubectl -n landslide get pod "mysql-$S-0" -o jsonpath='{.status.podIP}') || exit 1
exec mysql -h "$IP" "$@"
EOF
  chmod 755 /usr/local/bin/revisor-mysql
  ALLOW='
    oifname "lo" ip daddr 127.0.0.1 tcp dport { 6443, 8001 } accept
    ip daddr 10.42.0.0/16 tcp dport 3306 accept'
else
  usermod -aG systemd-journal revisor
  UNIT=/etc/systemd/system/prometheus.service
  if grep -q -- '--web.enable-lifecycle' "$UNIT"; then
    cp -a "$UNIT" "$OWNER_HOME/prometheus.service.bak-$(date +%Y%m%d)"
    # Drop the flag's line; if it closed ExecStart, also the "\" of the line before.
    python3 - "$UNIT" <<'EOF'
import re, sys
p = sys.argv[1]; out = []
for l in open(p).read().split("\n"):
    if "--web.enable-lifecycle" in l:
        if not l.rstrip().endswith("\\") and out:
            out[-1] = re.sub(r"\s*\\$", "", out[-1])
        continue
    out.append(l)
open(p, "w").write("\n".join(out))
EOF
    systemd-analyze verify "$UNIT" 2>&1 | grep -i prometheus.service && { cp -a "$OWNER_HOME/prometheus.service.bak-$(date +%Y%m%d)" "$UNIT"; echo "invalid unit, restored" >&2; exit 1; }
    systemctl daemon-reload && systemctl restart prometheus.service
    echo "Prometheus restarted without --web.enable-lifecycle (backup in $OWNER_HOME)."
  fi
  ALLOW='
    oifname "lo" ip daddr 127.0.0.1 tcp dport { 9090, 3306-3310 } accept'

  # SELECT-only MySQL user on every instance, from 127.0.0.1 only.
  if [ -f "$MYSQL_PW_FILE" ] && command -v mysql >/dev/null; then
    RPW=$(tr -d '\n' < "$MYSQL_PW_FILE")
    for PS in 3306:mysqld 3307:mysqld-data-mgmt 3308:mysqld-early-warning 3309:mysqld-project-mgmt 3310:mysqld-user-management; do
      P=${PS%%:*}; SOCK=/var/run/mysqld/${PS#*:}.sock
      M() { mysql -uroot --socket="$SOCK" -N "$@"; }
      SCHEMAS=$(M -e "SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('mysql','sys','performance_schema','information_schema')") || { echo "  :$P failed, skipping"; continue; }
      SQL="CREATE USER IF NOT EXISTS 'revisor'@'127.0.0.1' IDENTIFIED BY '$RPW' WITH MAX_USER_CONNECTIONS 5; ALTER USER 'revisor'@'127.0.0.1' IDENTIFIED BY '$RPW';"
      for D in $SCHEMAS; do SQL="$SQL GRANT SELECT, SHOW VIEW ON \`$D\`.* TO 'revisor'@'127.0.0.1';"; done
      M -e "$SQL" && echo "  :$P revisor has SELECT on: $(echo $SCHEMAS)"
    done
  fi
fi

# --- Per-user firewall (persisted through a systemd unit) ----------------------
UID_R=$(id -u revisor)
cat > /usr/local/sbin/revisor-firewall <<EOF
#!/bin/sh
# Network-level read-only for user revisor (see setup_reviewer.sh).
# Own nftables table: k3s/kube-router and docker never touch it, and a reject here is final
# even if another table accepts the packet. Priority -10 runs after dstnat (-100), so ClusterIP
# DNAT has already happened and the rules see the real pod IP and port.
set -e
# Remove the earlier iptables version (kube-router accepted pod traffic before it on B).
iptables -w -D OUTPUT -m owner --uid-owner $UID_R -j REVISOR-OUT 2>/dev/null || true
iptables -w -F REVISOR-OUT 2>/dev/null || true
iptables -w -X REVISOR-OUT 2>/dev/null || true
ip6tables -w -D OUTPUT -m owner --uid-owner $UID_R -j REJECT 2>/dev/null || true
nft -f - <<'NFT'
table inet revisor
delete table inet revisor
table inet revisor {
  chain output {
    type filter hook output priority -10; policy accept;
    meta skuid != $UID_R accept
    ct state established,related accept
$ALLOW
    reject
  }
}
NFT
EOF
chmod 700 /usr/local/sbin/revisor-firewall
cat > /etc/systemd/system/revisor-firewall.service <<'EOF'
[Unit]
Description=Read-only firewall for user revisor
After=network-online.target k3s.service docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/revisor-firewall

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable revisor-firewall.service >/dev/null
systemctl restart revisor-firewall.service

echo
echo "Done: user revisor (expires $EXPIRY) on $(hostname), mode $MODE."
nft list table inet revisor
