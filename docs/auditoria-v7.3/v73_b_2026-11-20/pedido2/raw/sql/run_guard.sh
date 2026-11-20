#!/bin/bash
# usage: run_guard.sh <label> < file.sql ; read-only mysql -t -vvv in mysql-data-management-0 with restartCount
# before/after and a guard on cgroup anon memory (KILL QUERY at >= 230 MiB).
K="kubectl --kubeconfig $HOME/.kube/config -n landslide"; P=mysql-data-management-0; L=$1
D=$HOME/v73-p2; mkdir -p "$D"; cat > "$D/$L.sql"
rc() { $K get pod $P -o jsonpath='{.status.containerStatuses[0].restartCount}'; }
mem() { $K exec $P -- sh -c 'awk "/^anon /{print int(\$2/1048576)}" /sys/fs/cgroup/memory.stat; awk "{print int(\$1/1048576)}" /sys/fs/cgroup/memory.current' 2>/dev/null | paste -sd' '; }
echo "label=$L start_utc=$(date -u +%FT%TZ) restartCount_antes=$(rc) mem_antes=$(mem)" | tee "$D/$L.meta"
$K exec -i $P -- sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -t -vvv' < "$D/$L.sql" > "$D/$L.out.txt" 2>&1 &
pid=$!
while kill -0 $pid 2>/dev/null; do
  read an cur <<<"$(mem)"; echo "$(date -u +%TZ) anon=${an}Mi current=${cur}Mi" >> "$D/$L.mem.log"
  if [ "${an:-0}" -ge 230 ]; then echo "ABORT anon=${an}Mi" | tee -a "$D/$L.mem.log"
    $K exec $P -- sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "SELECT CONCAT(\"KILL QUERY \",id,\";\") FROM information_schema.processlist WHERE user=\"root\" AND command=\"Query\" AND id<>CONNECTION_ID()" | mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'; fi
  sleep 2
done; wait $pid; r=$?
echo "rc=$r end_utc=$(date -u +%FT%TZ) restartCount_despues=$(rc) mem_despues=$(mem)" | tee -a "$D/$L.meta"
