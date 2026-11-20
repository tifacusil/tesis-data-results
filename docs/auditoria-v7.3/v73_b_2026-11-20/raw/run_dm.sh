#!/bin/bash
# Runs dm.sql (stdin) in mysql-data-management-0, read-only session, polling pod memory.
K="kubectl --kubeconfig $HOME/.kube/config -n landslide"
D=$HOME/v73-$(date -u +%Y%m%dT%H%M%SZ); mkdir -p "$D"; cat > "$D/dm.sql"
echo "dir=$D start_utc=$(date -u +%FT%TZ)"
$K exec -i mysql-data-management-0 -- sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -t -vvv' < "$D/dm.sql" > "$D/dm_out.txt" 2>&1 &
pid=$!
while kill -0 $pid 2>/dev/null; do
  m=$($K top pod mysql-data-management-0 --no-headers 2>/dev/null | awk '{print $3}')
  echo "$(date -u +%TZ) mem=$m" >> "$D/mem.log"
  if [ -n "$m" ] && [ "${m%Mi}" -ge 290 ] 2>/dev/null; then
    echo "ABORT mem=$m" >> "$D/mem.log"
    $K exec mysql-data-management-0 -- sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "SELECT CONCAT(\"KILL QUERY \",id,\";\") FROM information_schema.processlist WHERE info LIKE \"%COUNT(DISTINCT message_id)%\" AND id<>CONNECTION_ID()" | mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' >> "$D/mem.log" 2>&1
  fi
  sleep 10
done
wait $pid; echo "rc=$? end_utc=$(date -u +%FT%TZ)"
$K get pod mysql-data-management-0 --no-headers
cat "$D/mem.log" | awk '{print $2}' | sort -t= -k2 -V | tail -1
