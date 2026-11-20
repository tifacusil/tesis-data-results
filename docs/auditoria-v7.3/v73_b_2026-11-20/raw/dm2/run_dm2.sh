#!/bin/bash
# Remaining 15-min chunks, one mysql call each, read-only session; guard on cgroup anon memory.
K="kubectl --kubeconfig $HOME/.kube/config -n landslide"; P=mysql-data-management-0
D=$HOME/v73-dm2-$(date -u +%Y%m%dT%H%M%SZ); mkdir -p "$D"; echo "dir=$D start_utc=$(date -u +%FT%TZ)"
anon() { $K exec $P -- sh -c 'awk "/^anon /{print int(\$2/1048576)}" /sys/fs/cgroup/memory.stat; awk "{print int(\$1/1048576)}" /sys/fs/cgroup/memory.current' 2>/dev/null | paste -sd' '; }
a=$(date -u -d '2026-09-23 16:31:20' +%s); end=$(date -u -d '2026-09-24 00:39:21' +%s); i=0
while [ $a -lt $end ]; do
  b=$((a+900)); [ $b -gt $end ] && b=$end; i=$((i+1))
  A=$(date -u -d @$a '+%F %T'); B=$(date -u -d @$b '+%F %T')
  for w in $(seq 30); do read an cur <<<"$(anon)"; [ "${an:-999}" -lt 200 ] && break; sleep 2; done
  echo "$(date -u +%TZ) pre tramo=$i anon=${an}Mi current=${cur}Mi" >> "$D/mem.log"
  [ "${an:-999}" -ge 200 ] && { echo "STOP anon alto antes de tramo $i" | tee -a "$D/mem.log"; break; }
  q="SET SESSION transaction_read_only = ON; SET SESSION internal_tmp_mem_storage_engine = MEMORY; SET SESSION tmp_table_size = 4194304; SET SESSION max_heap_table_size = 4194304; USE data_management; SELECT '$A' AS desde, '$B' AS hasta, COUNT(*) AS filas, COUNT(DISTINCT message_id) AS ids, UTC_TIMESTAMP() AS fin_utc FROM gnss_readings IGNORE INDEX (idx_gnss_sensor_ts, idx_gnss_project_ts, uk_gnss_message) WHERE received_at >= '$A' AND received_at < '$B';"
  echo "$q" >> "$D/dm2.sql"
  $K exec $P -- sh -c "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -t -vvv -e \"$q\"" >> "$D/dm2_out.txt" 2>&1 &
  pid=$!; killed=0
  while kill -0 $pid 2>/dev/null; do
    read an cur <<<"$(anon)"; echo "$(date -u +%TZ) tramo=$i anon=${an}Mi current=${cur}Mi" >> "$D/mem.log"
    if [ "${an:-0}" -ge 230 ]; then echo "ABORT tramo=$i anon=${an}Mi" | tee -a "$D/mem.log"; killed=1
      $K exec $P -- sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "SELECT CONCAT(\"KILL QUERY \",id,\";\") FROM information_schema.processlist WHERE info LIKE \"%COUNT(DISTINCT message_id)%\" AND id<>CONNECTION_ID()" | mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' >> "$D/mem.log" 2>&1
    fi; sleep 2
  done; wait $pid; echo "tramo=$i rc=$? $A $B" >> "$D/mem.log"
  [ $killed = 1 ] && break
  a=$b
done
echo "end_utc=$(date -u +%FT%TZ) tramos=$i"; $K get pod $P --no-headers
grep -c 'tramo=.* rc=0' "$D/mem.log"; awk '/ anon=/{split($3,x,"=");v=x[2]+0; if(v>m)m=v} END{print "max_anon="m"Mi"}' "$D/mem.log"
