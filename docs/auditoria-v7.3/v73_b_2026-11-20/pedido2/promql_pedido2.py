"""PromQL for pedido 2 against the restored B TSDB (B-prometheus-tsdb-20261014.tar.gz) on localhost:9091.
Saves every request and its literal response with the UTC execution time to raw/promql/api_log.json."""
import json, os, urllib.parse, urllib.request
from datetime import datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
API = "http://localhost:9091/api/v1/query"
T0, T1, RNG = "2026-09-23T12:31:20Z", "2026-09-24T00:39:21Z", "43681s"   # 12 h 08 min 01 s
Q = []
for m in ("ew_alerts_published_total", "ew_alert_delivery_latency_seconds_count", 'ew_evaluations_total{result="alert"}',
          'ew_evaluations_total{outcome="alert"}'):
    for by in ("", " by (instance)"):
        Q.append(("increase", f"sum{by} (increase({m}[{RNG}]))", T1))
    Q.append(("resets", f"sum by (instance) (resets({m}[{RNG}]))", T1))
    Q.append(("crudo_t0", m, T0))
    Q.append(("crudo_t1", m, T1))
    Q.append(("muestras", f"{m}[{RNG}]", T1))
Q.append(("increase", f"sum by (instance, level) (increase(ew_alerts_published_total[{RNG}]))", T1))
Q.append(("increase", f"sum by (outcome) (increase(ew_evaluations_total[{RNG}]))", T1))
Q.append(("etiquetas", "count by (outcome, instance) (ew_evaluations_total)", T1))
Q.append(("pod_ip", 'kube_pod_info{namespace="landslide", pod=~"early-warning.*"}', "2026-09-23T18:00:00Z"))
Q.append(("pod_ip", 'kube_pod_info{namespace="landslide", pod=~"early-warning.*"}', "2026-09-30T03:45:00Z"))
for run, a, b in (("1", "2026-09-30T03:33:12Z", "2026-09-30T03:39:00Z"), ("2", "2026-09-30T03:41:32Z", "2026-09-30T03:47:30Z"),
                  ("3", "2026-09-30T03:49:53Z", "2026-09-30T03:56:00Z")):
    s = int((datetime.fromisoformat(b.replace("Z", "+00:00")) - datetime.fromisoformat(a.replace("Z", "+00:00"))).total_seconds())
    Q.append((f"breaker_corrida_{run}", f'ew_outbound_calls_total{{target="user-management"}}[{s + 60}s]', b))
    Q.append((f"breaker_corrida_{run}", f'ew_circuit_breaker_state{{target="user-management"}}[{s + 60}s]', b))
log = []
for kind, q, t in Q:
    url = API + "?" + urllib.parse.urlencode({"query": q, "time": t})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    body = urllib.request.urlopen(url, timeout=60).read().decode()
    log.append({"tipo": kind, "query": q, "time": t, "ejecutado_utc": now, "respuesta": json.loads(body)})
json.dump(log, open(os.path.join(HERE, "raw", "promql", "api_log.json"), "w", encoding="utf-8"), ensure_ascii=False)
for e in log:
    if e["tipo"] in ("increase", "resets", "crudo_t0", "crudo_t1", "pod_ip", "etiquetas"):
        res = e["respuesta"]["data"]["result"]
        print(e["tipo"], e["query"][:90], e["time"], [({k: v for k, v in r["metric"].items() if k in ("instance", "level", "outcome", "pod", "pod_ip")}, r["value"][1]) for r in res])
