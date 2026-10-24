#!/usr/bin/env python3
"""
chaos_evidence_b.py: freezes and verifies the evidence for the three chaos injections
of System B's 12 h run (2026-09-23, times in UTC).

Two steps, kept separate on purpose:

  export   Downloads each window's series from Prometheus and writes them as CSV, with a
           manifest (query, window, step, sha256). Needs access to System B's Prometheus
           and only works within its retention (30 days).
  verify   Recomputes each claim in the manuscript from the frozen files (Prometheus CSVs,
           Artillery JSON, data-receiving logs). Needs no server access: this is the step
           a reviewer repeats.

Uses only the Python standard library (3.11 or later).

Usage:
  python3 chaos_evidence_b.py export --prom http://<host>:31083 --out evidencia-b-0923
  python3 chaos_evidence_b.py verify --evidence data/evidencia-b-0923 \
      --artillery "data/B - SEPTIEMBRE 5 RUNS V2/sustained-12h.json" \
      --logs data/data-receiving-logs-2026-09-23 \
      --series data/B-12h-0923-timeseries.csv --saturation data/B-12h-0923-saturation.csv \
      --snapshots "data/B - SEPTIEMBRE 5 RUNS V2/chaos"

verify exits with code 1 if any check fails.

The frozen export (23/10/2026) uses Spanish file names and manifest keys (manifiesto.json,
"archivos", "archivo", caida_broker__*.csv, ...). They are kept as exported so the
SHA-256 values stay valid, and this script reads them under those names.
"""
import argparse, csv, glob, hashlib, json, os, statistics as st, sys, urllib.parse, urllib.request
from datetime import datetime, timezone


def ts(iso_str):
    return int(datetime.fromisoformat(iso_str).timestamp())


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Fault windows. Source of each limit:
#   caida_broker (broker kill): creation of rabbitmq-0 (kubectl, .status.startTime) and the
#                last data-receiving log line before its restart.
#   pausa_dm (data-management pause) / netem_da (delay towards data-analysis): timestamps
#                of the orchestrator's pre/post snapshots
#                (pause-data-management-{pre,post}-*.snapshot, netem-delay-ew-da-*).
# The keys are the file-name prefixes of the frozen export.
EVENTS = {
    "caida_broker": (ts("2026-09-23T14:32:24+00:00"), ts("2026-09-23T14:33:02+00:00")),
    "pausa_dm":     (1790188340, 1790188444),
    "netem_da":     (1790202738, 1790202967),
}
MARGIN = 600            # 10 min before and after each window
STEP = 15               # s, same as the scrape interval
# Grid aligned with the first row of B-12h-0923-saturation.csv (12:35, 5 min step),
# so the samples match those behind Table 10.
RUN_12H = (ts("2026-09-23T12:35:00+00:00"), ts("2026-09-24T00:35:00+00:00"))

# (file suffix, PromQL). Exported for every window in EVENTS.
WINDOW_QUERIES = [
    ("buffer_por_pod", "data_receiving_redis_buffer_pending"),
    ("cpu_nodo_pct", '100*(1-avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))'),
    ("iowait_frac", 'avg(rate(node_cpu_seconds_total{mode="iowait"}[1m]))'),
    ("reinicios", 'kube_pod_container_status_restarts_total{namespace="landslide"}'),
    ("ready", 'kube_pod_container_status_ready{namespace="landslide"}'),
]
# Queries over the whole run (5 min step, as in Table 10).
RUN_QUERIES = [
    ("buffer_sum", "sum(data_receiving_redis_buffer_pending)"),
    ("buffer_max", "max(data_receiving_redis_buffer_pending)"),
]
MANIFEST = "manifiesto.json"


# ---------------------------------------------------------------- export
def query_range(prom, q, start, end, step):
    url = prom.rstrip("/") + "/api/v1/query_range?" + urllib.parse.urlencode(
        {"query": q, "start": start, "end": end, "step": step})
    with urllib.request.urlopen(url, timeout=60) as r:
        body = json.load(r)
    if body.get("status") != "success":
        raise RuntimeError(f"Prometheus rejected {q!r}: {body}")
    return body["data"]["result"]


def label(metric):
    keep = {k: v for k, v in metric.items() if k not in ("__name__", "job")}
    return ",".join(f"{k}={v}" for k, v in sorted(keep.items())) or "total"


def write_csv(path, series):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_utc", "unix", "serie", "valor"])
        for s in series:
            for t, v in s["values"]:
                w.writerow([iso(int(t)), int(t), label(s["metric"]), v])


def export(a):
    os.makedirs(a.out, exist_ok=True)
    jobs = [(f"{ev}__{n}", q, i - MARGIN, f + MARGIN, STEP)
            for ev, (i, f) in EVENTS.items() for n, q in WINDOW_QUERIES]
    jobs += [(f"corrida12h__{n}", q, *RUN_12H, 300) for n, q in RUN_QUERIES]
    manifest = {"prometheus": a.prom, "exportado": iso(int(datetime.now(timezone.utc).timestamp())),
                "archivos": []}
    for name, q, start, end, step in jobs:
        series = query_range(a.prom, q, start, end, step)
        if not series:
            # Empty = retention already dropped the window; do not write a misleading CSV.
            sys.exit(f"ERROR: {name} has no data ({q}). Retention expired?")
        path = os.path.join(a.out, name + ".csv")
        write_csv(path, series)
        with open(path, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        manifest["archivos"].append({"archivo": name + ".csv", "consulta": q, "inicio": iso(start),
                                     "fin": iso(end), "paso_s": step, "series": len(series), "sha256": sha})
        print(f"  {name}.csv  ({len(series)} series)")
    with open(os.path.join(a.out, MANIFEST), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Done: {len(jobs)} files in {a.out}")


# ---------------------------------------------------------------- verify
def load(evidence, name):
    """{series: [(unix, value), ...]} from an exported CSV, after checking its sha256."""
    path = os.path.join(evidence, name + ".csv")
    with open(os.path.join(evidence, MANIFEST), encoding="utf-8") as f:
        expected = {x["archivo"]: x["sha256"] for x in json.load(f)["archivos"]}
    with open(path, "rb") as f:
        if hashlib.sha256(f.read()).hexdigest() != expected[name + ".csv"]:
            sys.exit(f"ERROR: {path} does not match the sha256 in the manifest")
    out = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["serie"], []).append((int(r["unix"]), float(r["valor"])))
    return out


def changes(points):
    return [(t, v) for (t, v), (_, v0) in zip(points[1:], points) if v != v0]


def between(points, a, b):
    return [v for t, v in points if a <= t <= b]


def log_lines(folder):
    """(pod, unix_float, msg, error) from the data-receiving JSON logs."""
    for path in sorted(glob.glob(os.path.join(folder, "*.log"))):
        pod = os.path.basename(path).split("-previous")[0]
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    j = json.loads(line)
                except ValueError:
                    continue
                yield pod, datetime.fromisoformat(j["time"]).timestamp(), j.get("msg", ""), j.get("error", "")


class Report:
    def __init__(self):
        self.failures = 0

    def check(self, text, ok, detail):
        self.failures += not ok
        print(f"  [{'OK' if ok else 'FAIL'}] {text}\n         {detail}")


def verify(a):
    rep = Report()
    kill_start, kill_end = EVENTS["caida_broker"]

    print("\n1. Generator failures vs. the broker outage")
    with open(a.artillery, encoding="utf-8") as f:
        art = json.load(f)
    total = art["aggregate"]["counters"].get("vusers.failed", 0)
    periods = [(p["firstCounterAt"] / 1000, p["counters"].get("vusers.failed", 0))
               for p in art["intermediate"] if p["counters"].get("vusers.failed")]
    for t, n in periods:
        print(f"         period from {iso(int(t))}: {n} failures")
    rep.check("the generator's failures add up to the aggregate total",
              sum(n for _, n in periods) == total, f"{sum(n for _, n in periods)} vs {total}")
    early = sum(n for t, n in periods if t < kill_start + 36)   # periods starting before 14:33:00
    rep.check("no generator failure while the broker was down (14:32:24 to 14:33:00)",
              early == 0, f"failures in periods starting before {iso(kill_start + 36)}: {early}")

    lines = list(log_lines(a.logs))
    failed_pub = [t for _, t, m, _ in lines if m.startswith("rabbitmq publish failed")]
    no_ack = [t for _, t, m, e in lines if m == "sink write failed" and "context canceled" in e]
    rep.check("all failed publishes fall inside the broker outage",
              bool(failed_pub) and kill_start <= min(failed_pub) and max(failed_pub) <= kill_end,
              f"{len(failed_pub)} failures, {iso(int(min(failed_pub)))} to {iso(int(max(failed_pub)))}")
    print(f"         not acknowledged (buffer write cancelled at shutdown): {len(no_ack)}, "
          f"{iso(int(min(no_ack)))} to {iso(int(max(no_ack)))}; generator total / not acknowledged = {total / len(no_ack):.2f}")

    print("\n2. Redis buffer: a global gauge published by every pod")
    peaks = {s: max(v for _, v in p) for s, p in load(a.evidence, "caida_broker__buffer_por_pod").items()}
    for s, v in peaks.items():
        print(f"         {s}: peak {v:.0f}")
    rep.check("the pods report the same peak (±1 %): the metric is global, not per instance",
              max(peaks.values()) <= 1.01 * min(peaks.values()), f"min {min(peaks.values()):.0f}, max {max(peaks.values()):.0f}")
    real_peak = max(peaks.values())
    rep.check("the real buffer peak matches the failed publishes (±2 %)",
              abs(real_peak - len(failed_pub)) <= 0.02 * len(failed_pub), f"peak {real_peak:.0f} vs {len(failed_pub)} failures")
    # Compared at the peak of max(): while draining, the pods update the gauge in different
    # RetryWorker passes and the sum/max ratio drops temporarily.
    total_sum = dict(load(a.evidence, "corrida12h__buffer_sum")["total"])
    t_peak, v_max = max(load(a.evidence, "corrida12h__buffer_max")["total"], key=lambda x: x[1])
    rep.check(f"sum(...) over the {len(peaks)} pods multiplies the value by {len(peaks)} (Table 10 figure)",
              abs(total_sum[t_peak] / v_max - len(peaks)) < 0.05,
              f"{iso(t_peak)}: sum={total_sum[t_peak]:.0f}, max={v_max:.0f}, ratio={total_sum[t_peak] / v_max:.2f}")
    with open(a.saturation, encoding="utf-8") as f:
        sat = max(float(r["redis_buffer_pending"] or 0) for r in csv.DictReader(f))
    print(f"         peak in {os.path.basename(a.saturation)}: {sat:.0f} = {sat / real_peak:.2f} × real peak")

    print("\n3. data-management pause (SIGSTOP, 90 s)")
    p_start, p_end = EVENTS["pausa_dm"]
    restarts = {s: changes(p) for s, p in load(a.evidence, "pausa_dm__reinicios").items() if "container=data-management," in s}
    ready = {s: changes(p) for s, p in load(a.evidence, "pausa_dm__ready").items() if "container=data-management," in s}
    for s in restarts:
        print(f"         {s}: restarts {[(iso(t), v) for t, v in restarts[s]]}; ready {[(iso(t), v) for t, v in ready.get(s, [])]}")
    in_window = [t for c in restarts.values() for t, _ in c if p_start <= t <= p_end + STEP]
    rep.check("the liveness probe restarted data-management during the pause",
              len(in_window) == 1, f"restarts within {iso(p_start)}..{iso(p_end)}: {len(in_window)}")
    snaps = {}
    for path in glob.glob(os.path.join(a.snapshots, "pause-data-management-*.snapshot")):
        with open(path, encoding="utf-8") as f:
            kv = dict(l.strip().split("=", 1) for l in f if "=" in l)
        snaps["pre" if "-pre-" in path else "post"] = int(kv["consumed_dm"])
    rep.check("consumed_dm falls between snapshots (the restarted pod's counter went back to 0)",
              snaps["post"] < snaps["pre"], f"pre {snaps['pre']} -> post {snaps['post']}")

    print("\n4. System B node CPU: 10 min before vs. the window (and 5 min after)")
    for ev in ("caida_broker", "pausa_dm", "netem_da"):
        i, f = EVENTS[ev]
        cpu = load(a.evidence, f"{ev}__cpu_nodo_pct")["total"]
        io = load(a.evidence, f"{ev}__iowait_frac")["total"]
        before, during, after = between(cpu, i - MARGIN, i - 1), between(cpu, i, f), between(cpu, f + 1, f + 300)
        print(f"         {ev}: before {st.mean(before):.1f} % (max {max(before):.1f}) | window {st.mean(during):.1f} % "
              f"(max {max(during):.1f}) | after {st.mean(after):.1f} % (max {max(after):.1f}) | "
              f"iowait max {max(v for _, v in io):.3f}")
    with open(a.series, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    i, f = EVENTS["netem_da"]
    da = [(ts(r["time"].replace("Z", "+00:00")), float(r["cpu_pct_data-analysis"])) for r in rows]
    base_da, after_da = st.median(between(da, i - MARGIN, i - 1)), max(between(da, f, f + 300))
    rep.check("data-analysis CPU spikes when the netem delay is removed (>5× its baseline)",
              after_da > 5 * base_da, f"baseline {base_da:.2f}, max in the following 5 min {after_da:.2f}")

    print(f"\n{'All checks passed.' if not rep.failures else f'{rep.failures} check(s) failed.'}")
    return 1 if rep.failures else 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # Windows console
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="download the window series from Prometheus")
    e.add_argument("--prom", required=True, help="base URL of System B's Prometheus")
    e.add_argument("--out", default="evidencia-b-0923")
    v = sub.add_parser("verify", help="recompute every claim from the frozen files")
    v.add_argument("--evidence", required=True, help="folder written by export")
    v.add_argument("--artillery", required=True, help="Artillery JSON of the 12 h run")
    v.add_argument("--logs", required=True, help="folder with the data-receiving *.log files")
    v.add_argument("--series", required=True, help="B-12h-0923-timeseries.csv")
    v.add_argument("--saturation", required=True, help="B-12h-0923-saturation.csv")
    v.add_argument("--snapshots", required=True, help="folder with the chaos *.snapshot files")
    a = p.parse_args()
    sys.exit(export(a) if a.cmd == "export" else verify(a))


if __name__ == "__main__":
    main()
