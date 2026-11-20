// Read-only audit of ew_evaluations_total against the restored B backup (local Prometheus).
// Usage: node audit_ew.js <outdir>
const fs = require('fs');
const OUT = process.argv[2];
const P = 'http://localhost:9091';
const T_END = '2026-09-24T00:34:21Z';                    // evaluation time for step 1
const W_START = Date.parse('2026-09-23T12:31:20Z') / 1000; // window (43381 s)
const W_END = Date.parse(T_END) / 1000;
const X_START = '2026-09-23T12:25:00Z', X_END = '2026-09-24T00:40:00Z'; // export range

const log = [];
async function api(path, params) {
  const url = `${P}${path}?` + new URLSearchParams(params);
  const ran = new Date().toISOString();
  const body = await (await fetch(url)).text();
  log.push({ ran_utc: ran, path, params, response: body });
  const j = JSON.parse(body);
  if (j.status !== 'success') throw new Error(body);
  return j.data;
}
const key = m => `${m.outcome}|${m.instance}`;

(async () => {
  const build = await api('/api/v1/status/buildinfo', {});

  // Step 1
  const s1 = {};
  for (const q of ['sum by (outcome) (increase(ew_evaluations_total[43381s]))',
                   'sum by (outcome, pod) (increase(ew_evaluations_total[43381s]))',
                   'sum by (outcome, instance) (increase(ew_evaluations_total[43381s]))'])
    s1[q] = (await api('/api/v1/query', { query: q, time: T_END })).result;

  // Step 2a: query_range, step = scrape interval (15s), as specified
  const qr = (await api('/api/v1/query_range',
    { query: 'ew_evaluations_total', start: X_START, end: X_END, step: '15s' })).result;
  // Step 2b: raw samples (range selector, no lookback alignment). 44101s so 12:25:00 is included.
  const raw = (await api('/api/v1/query', { query: 'ew_evaluations_total[44101s]', time: X_END })).result;

  const csv = ['source,outcome,instance,timestamp_unix,timestamp_utc,value'];
  for (const [src, set, f] of [['raw', raw, 'values'], ['query_range_15s', qr, 'values']])
    for (const s of set) for (const [t, v] of s[f])
      csv.push([src, s.metric.outcome, s.metric.instance, t, new Date(t * 1000).toISOString(), v].join(','));
  fs.writeFileSync(`${OUT}/ew_evaluations_samples.csv`, csv.join('\n') + '\n');

  // Manual reset-aware delta: sum of positive steps; on a drop, add the new value (counter restarted from 0).
  const manual = vals => {
    let inc = 0, resets = 0;
    for (let i = 1; i < vals.length; i++) {
      const a = +vals[i - 1][1], b = +vals[i][1];
      if (b < a) { resets++; inc += b; } else inc += b - a;
    }
    return { inc, resets, n: vals.length,
             first: vals[0] && [new Date(vals[0][0] * 1000).toISOString(), vals[0][1]],
             last: vals.at(-1) && [new Date(vals.at(-1)[0] * 1000).toISOString(), vals.at(-1)[1]] };
  };
  const inc1 = Object.fromEntries(s1['sum by (outcome, instance) (increase(ew_evaluations_total[43381s]))']
    .map(r => [key(r.metric), +r.value[1]]));
  const intervals = [];
  const rows = raw.map(s => {
    const v = s.values;
    for (let i = 1; i < v.length; i++) intervals.push(+(v[i][0] - v[i - 1][0]).toFixed(3));
    const inWin = v.filter(([t]) => t > W_START && t <= W_END);
    return { outcome: s.metric.outcome, instance: s.metric.instance,
             increase_window: inc1[key(s.metric)] ?? null,
             manual_window: manual(inWin), manual_export_range: manual(v) };
  }).sort((a, b) => (a.outcome + a.instance).localeCompare(b.outcome + b.instance));
  const hist = {};
  for (const d of intervals) hist[d] = (hist[d] || 0) + 1;

  const result = { build, step1: s1, step2: rows, scrape_interval_histogram_s: hist,
                   raw_series: raw.length, query_range_series: qr.length };
  fs.writeFileSync(`${OUT}/ew_result.json`, JSON.stringify(result, null, 2));
  fs.writeFileSync(`${OUT}/ew_api_log.json`, JSON.stringify(log, null, 2));
  console.log(JSON.stringify({ step1: s1, step2: rows.map(r => ({ o: r.outcome, i: r.instance,
    inc: r.increase_window, man: r.manual_window.inc, res: r.manual_window.resets,
    manX: r.manual_export_range.inc, resX: r.manual_export_range.resets, n: r.manual_window.n })),
    hist }, null, 1));
})().catch(e => { console.error(e); process.exit(1); });
