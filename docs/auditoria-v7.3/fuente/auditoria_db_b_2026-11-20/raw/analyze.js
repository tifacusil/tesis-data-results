// Local reproduction of audit steps 1-3 over the streamed export.
// Usage: node analyze.js export.tsv sink_ids.txt outdir
// Semantics mirror the SQL in s1.sql / s2.sql / s3.sql:
//   step 2: per sensor, order by timestamp, LAG(timestamp), LAG(received_at);
//           gap when TIMESTAMPDIFF(SECOND, prev_ts, ts) > 3600; faltantes = d/3600 - 1.
const fs = require('fs');
const readline = require('readline');
const [, , tsvPath, idsPath, outDir] = process.argv;

const toSec = s => Date.parse(s.replace(' ', 'T') + 'Z') / 1000;
const fmt = sec => new Date(sec * 1000).toISOString().slice(0, 19).replace('T', ' ');
const OUT_A = toSec('2026-09-23 14:32:00'), OUT_B = toSec('2026-09-23 14:37:00');

async function main() {
  const ids = new Set(fs.readFileSync(idsPath, 'utf8').trim().split(/\r?\n/));
  const bySensor = new Map(); // sensor -> [[ts, recv], ...]
  const sinkHits = [];
  let rows = 0, header = null, minRecv = Infinity, maxRecv = -Infinity, nullMsg = 0;
  const rl = readline.createInterface({ input: fs.createReadStream(tsvPath) });
  for await (const line of rl) {
    if (!header) { header = line; continue; }
    const [msg, sensor, ts, recv] = line.split('\t');
    if (msg === 'NULL') nullMsg++;
    const t = toSec(ts), r = toSec(recv);
    if (Number.isNaN(t) || Number.isNaN(r)) throw new Error('bad row: ' + line);
    rows++;
    if (r < minRecv) minRecv = r;
    if (r > maxRecv) maxRecv = r;
    let a = bySensor.get(sensor);
    if (!a) bySensor.set(sensor, a = []);
    a.push([t, r]);
    if (ids.has(msg)) sinkHits.push(line);
  }

  const sensors = [...bySensor.keys()].sort();
  const s1 = [], gaps = [], dups = [];
  let pairs = 0, eq3600 = 0, lt3600 = 0, gt3600 = 0, nonMultiple = 0, dMin = Infinity, dMax = -Infinity;
  for (const s of sensors) {
    const a = bySensor.get(s).sort((x, y) => x[0] - y[0] || x[1] - y[1]);
    s1.push([s, a.length, fmt(a[0][0]), fmt(a[a.length - 1][0])]);
    let run = 1;
    for (let i = 1; i < a.length; i++) {
      const d = a[i][0] - a[i - 1][0];
      pairs++; dMin = Math.min(dMin, d); dMax = Math.max(dMax, d);
      if (d === 3600) eq3600++; else if (d < 3600) lt3600++; else gt3600++;
      if (d === 0) run++; else { if (run > 1) dups.push([s, fmt(a[i - 1][0]), run]); run = 1; }
      if (d > 3600) {
        if (d % 3600 !== 0) nonMultiple++;
        const prevRecv = a[i - 1][1], recv = a[i][1];
        const inOutage = (prevRecv >= OUT_A && prevRecv <= OUT_B) || (recv >= OUT_A && recv <= OUT_B);
        gaps.push({ s, prev_ts: fmt(a[i - 1][0]), ts: fmt(a[i][0]), prev_recv: fmt(prevRecv), recv: fmt(recv),
                    recvSec: recv, faltantes: d / 3600 - 1, inOutage });
      }
    }
    if (run > 1) dups.push([s, fmt(a[a.length - 1][0]), run]);
  }
  gaps.sort((x, y) => x.recvSec - y.recvSec || (x.s < y.s ? -1 : 1));

  const sum = f => gaps.filter(f).reduce((n, g) => n + g.faltantes, 0);
  const summary = {
    export_header: header, rows, null_message_id: nullMsg,
    min_received_at: fmt(minRecv), max_received_at: fmt(maxRecv), sensors: sensors.length,
    step2: {
      gap_rows: gaps.length,
      a_total_faltantes: sum(() => true),
      b_faltantes_1432_1437: sum(g => g.inOutage), b_gap_rows: gaps.filter(g => g.inOutage).length,
      c_faltantes_fuera: sum(g => !g.inOutage), c_gap_rows: gaps.filter(g => !g.inOutage).length,
      d_pares_consecutivos: pairs, d_espaciado_3600: eq3600, d_espaciado_menor_3600: lt3600,
      d_espaciado_mayor_3600: gt3600, d_huecos_no_multiplo_3600: nonMultiple, d_min: dMin, d_max: dMax,
    },
    step3_duplicate_groups: dups.length,
    sink_ids_in_window: sinkHits.length,
  };

  fs.writeFileSync(`${outDir}/step1_local.tsv`, 'sensor_id\tn\tmin_timestamp\tmax_timestamp\n' + s1.map(r => r.join('\t')).join('\n') + '\n');
  fs.writeFileSync(`${outDir}/huecos_paso2.csv`,
    'sensor_id,prev_ts,timestamp,prev_recv,received_at,faltantes,en_intervalo_1432_1437\n' +
    gaps.map(g => [g.s, g.prev_ts, g.ts, g.prev_recv, g.recv, g.faltantes, g.inOutage ? 1 : 0].join(',')).join('\n') + '\n');
  fs.writeFileSync(`${outDir}/duplicados_paso3.tsv`, 'sensor_id\ttimestamp\tc\n' + dups.map(r => r.join('\t')).join('\n') + '\n');
  fs.writeFileSync(`${outDir}/sink_ids_en_ventana.tsv`, header + '\n' + sinkHits.join('\n') + '\n');
  fs.writeFileSync(`${outDir}/summary.json`, JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary, null, 2));
}

main().catch(e => { console.error(e); process.exit(1); });
