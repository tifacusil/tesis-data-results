"""Turn the raw outputs of pedido 2 into CSV (run: py -I procesar_pedido2.py). Inputs: raw/sql/*.out.txt, *.meta,
raw/promql/api_log.json. Rewrites SHA256SUMS for this folder at the end."""
import csv, hashlib, json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")

def blocks(path):
    parts = re.split(r"^-{14}\n", open(path, encoding="utf-8").read(), flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        body = parts[i + 1]
        rows = [[c.strip() for c in l.strip("|").split("|")] for l in body.splitlines() if l.startswith("|")]
        foot = next((l for l in body.splitlines() if re.search(r"in set|Empty set|Query OK|^ERROR", l)), "")
        yield parts[i].strip(), rows, foot

def write(name, header, rows):
    with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(header); w.writerows(rows)

meta = {}
for m in ("p2_explain", "p2_dm"):
    for line in open(os.path.join(RAW, "sql", m + ".meta"), encoding="utf-8"):
        for k, v in re.findall(r"(\w+)=(\S+)", line):
            meta.setdefault(m, {})[k] = v
write("p2_ejecucion.csv", ["script", "inicio_utc", "fin_utc", "rc", "restartCount_antes", "restartCount_despues",
                           "anon_mib_antes", "anon_mib_despues"],
      [[m, v["start_utc"], v["end_utc"], v["rc"], v["restartCount_antes"], v["restartCount_despues"], v["mem_antes"], v["mem_despues"]]
       for m, v in meta.items()])

b = list(blocks(os.path.join(RAW, "sql", "p2_dm.out.txt")))
ctx = next(r for q, r, f in b if q.startswith("SELECT CURRENT_USER()"))
write("p2_contexto.csv", ctx[0], ctx[1:])
exp = [(q, r) for q, r, f in b if q.startswith("EXPLAIN")]
write("p2_explain.csv", ["consulta"] + exp[0][1][0], [["ids_105" if "IN (" in q else "filas_por_minuto"] + r[1] for q, r in exp])
ids = next((q, r, f) for q, r, f in b if q.startswith("SELECT message_id") and "IN (" in q)
write("p2_ids_105_en_gnss_readings.csv", ["message_id", "timestamp", "received_at"], ids[1][1:])
mins = next(r for q, r, f in b if "AS minuto" in q and not q.startswith("EXPLAIN"))
write("p2_filas_por_minuto_1430_1440.csv", ["minuto_utc", "filas", "nominal", "diferencia"],
      [[m, int(n), 6000, int(n) - 6000] for m, n in mins[1:]])
win = int(next(r for q, r, f in b if "filas_1433_1436" in q)[1][0])
write("p2_deficit_1433_1436.csv", ["ventana_utc", "filas", "nominal_24000", "deficit", "fallos_artillery"],
      [["2026-09-23 14:33:00 a 14:36:59", win, 24000, 24000 - win, 315]])

log = json.load(open(os.path.join(RAW, "promql", "api_log.json"), encoding="utf-8"))
rows = []
for e in log:
    if e["tipo"] in ("increase", "resets", "crudo_t0", "crudo_t1", "pod_ip", "etiquetas"):
        res = e["respuesta"]["data"]["result"]
        if not res:
            rows.append([e["tipo"], e["query"], e["time"], e["ejecutado_utc"], "", "", "", "sin series"])
        for r in res:
            m = r["metric"]
            rows.append([e["tipo"], e["query"], e["time"], e["ejecutado_utc"], m.get("instance", ""),
                         m.get("pod", ""), m.get("level", m.get("outcome", m.get("pod_ip", ""))), r["value"][1]])
write("p2_promql_resultados.csv", ["tipo", "query", "time", "ejecutado_utc", "instance", "pod", "level_outcome_o_pod_ip", "valor"], rows)

files = sorted(os.path.relpath(os.path.join(d, f), HERE).replace("\\", "/") for d, _, fs in os.walk(HERE) for f in fs if f != "SHA256SUMS")
with open(os.path.join(HERE, "SHA256SUMS"), "w", newline="\n") as f:
    for p in files:
        f.write(f"{hashlib.sha256(open(os.path.join(HERE, p), 'rb').read()).hexdigest()}  {p}\n")
print("ok", len(files), "archivos")
