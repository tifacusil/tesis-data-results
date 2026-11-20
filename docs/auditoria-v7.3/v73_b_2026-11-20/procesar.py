"""Parse the raw mysql -t -vvv outputs in raw/ into CSV files (run: py -I procesar.py)."""
import csv, hashlib, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")

def blocks(path):
    """Yield (query, rows, footer) for each statement in a mysql -vvv output."""
    text = open(path, encoding="utf-8").read()
    parts = re.split(r"^-{14}\n", text, flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        query, body = parts[i].strip(), parts[i + 1]
        lines = [l for l in body.splitlines() if l.startswith("|")]
        rows = [[c.strip() for c in l.strip("|").split("|")] for l in lines]
        footer = next((l for l in body.splitlines() if re.search(r"rows? in set|Query OK|^ERROR", l)), "")
        yield query, rows, body, footer

def write(name, header, rows):
    with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(header); w.writerows(rows)
    print(name, len(rows))

dm = list(blocks(os.path.join(RAW, "dm_out.txt")))
ctx = next(r for q, r, b, f in dm if q.startswith("SELECT CURRENT_USER()"))
ddl = next(b for q, r, b, f in dm if q.startswith("SHOW CREATE TABLE"))
open(os.path.join(HERE, "show_create_gnss_readings.txt"), "w", encoding="utf-8").write(ddl.strip() + "\n")
total = next(r for q, r, b, f in dm if "COUNT(*) AS filas FROM" in q and "desde" not in q)
tramos = [(r[1], f) for q, r, b, f in dm if "AS desde" in q and len(r) > 1]
write("dm_contexto.csv", ctx[0], ctx[1:])
write("dm_count_ventana.csv", ["filas", "segundos"], [[total[1][0], re.search(r"\(([\d.]+) sec", next(f for q, r, b, f in dm if "COUNT(*) AS filas FROM" in q and "desde" not in q)).group(1)]])
write("dm_tramos_1h.csv", ["desde_utc", "hasta_utc", "filas", "ids_distintos", "fin_utc", "segundos"],
      [row + [re.search(r"\(([\d.]+) sec", f).group(1)] for row, f in tramos])
interrumpidas = [q for q, r, b, f in dm if "AS desde" in q and len(r) <= 1]
errors = re.findall(r"^ERROR.*$", open(os.path.join(RAW, "dm_out.txt"), encoding="utf-8").read(), flags=re.M)

ew = list(blocks(os.path.join(RAW, "ew_out.txt")))
ectx = next(r for q, r, b, f in ew if q.startswith("SELECT CURRENT_USER()"))
open(os.path.join(HERE, "show_create_alerts.txt"), "w", encoding="utf-8").write(
    next(b for q, r, b, f in ew if q.startswith("SHOW CREATE TABLE")).strip() + "\n")
cnt = next(r for q, r, b, f in ew if "lecturas_distintas" in q)
dup = next(r for q, r, b, f in ew if "GROUP_CONCAT" in q)
write("ew_contexto.csv", ectx[0], ectx[1:])
write("ew_count_ventana.csv", cnt[0], cnt[1:])
rows = []
for cells in dup[1:]:  # GROUP_CONCAT uses '|', so rejoin every cell after the third
    sensor, ts, n, filas = cells[0], cells[1], cells[2], "|".join(cells[3:]).strip()
    for item in filas.split(" ; "):
        rows.append([sensor, ts, n] + item.split("|"))
write("ew_alertas_duplicadas.csv", ["sensor_id", "alert_timestamp", "n", "id", "alert_level", "created_at", "message_id"], rows)

mem = [l.split() for l in open(os.path.join(RAW, "mem.log"), encoding="utf-8") if l.split() and l.split()[0].endswith("Z") and "mem=" in l]
write("dm_memoria_pod.csv", ["hora_utc", "memoria"], [[a, b.split("=")[1]] for a, b in mem])

dm2 = [(r[1], f) for q, r, b, f in blocks(os.path.join(RAW, "dm2", "dm2_out.txt")) if "AS desde" in q and len(r) > 1]
todos = [row + [re.search(r"\(([\d.]+) sec", f).group(1), "1h", "raw/dm_out.txt"] for row, f in tramos]
todos += [row + [re.search(r"\(([\d.]+) sec", f).group(1), "15min", "raw/dm2/dm2_out.txt"] for row, f in dm2]
write("dm_tramos_completo.csv", ["desde_utc", "hasta_utc", "filas", "ids_distintos", "fin_utc", "segundos", "tramo", "fuente"], todos)
contiguo = all(a[1] == b[0] for a, b in zip(todos, todos[1:])) and todos[0][0] == "2026-09-23 12:31:20" and todos[-1][1] == "2026-09-24 00:39:21"
mem2 = [l.split() for l in open(os.path.join(RAW, "dm2", "mem.log"), encoding="utf-8") if " anon=" in l]
write("dm2_memoria_pod.csv", ["hora_utc", "fase", "tramo", "anon_mib", "current_mib"],
      [[x[0], "pre" if x[1] == "pre" else "durante", x[-3].split("=")[1] if x[1] == "pre" else x[1].split("=")[1],
        x[-2].split("=")[1].rstrip("Mi"), x[-1].split("=")[1].rstrip("Mi")] for x in mem2])
s = sum(int(r[2]) for r, _ in tramos)
json.dump({"dm": {"filas_ventana": int(total[1][0]), "tramos_completos": len(tramos), "tramos_interrumpidos": len(interrumpidas),
                  "filas_en_tramos_completos": s, "ids_en_tramos_completos": sum(int(r[3]) for r, _ in tramos),
                  "errores": errors, "abortos_memoria": [l.strip() for l in open(os.path.join(RAW, "mem.log"), encoding="utf-8") if l.startswith("ABORT")],
                  "completo": {"tramos": len(todos), "contiguo_t0_t1": contiguo, "filas": sum(int(r[2]) for r in todos),
                               "ids_sumados": sum(int(r[3]) for r in todos), "tramos_con_ids_distinto_de_filas": sum(r[2] != r[3] for r in todos),
                               "anon_max_mib_segunda_corrida": max(int(x[-2].split("=")[1].rstrip("Mi")) for x in mem2)}},
           "ew": {"alertas": int(cnt[1][0]), "lecturas_distintas": int(cnt[1][1]), "filas_duplicadas": len(rows)}},
          open(os.path.join(HERE, "resumen.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(open(os.path.join(HERE, "resumen.json"), encoding="utf-8").read())

files = sorted(os.path.relpath(os.path.join(d, f), HERE).replace("\\", "/") for d, _, fs in os.walk(HERE) for f in fs if f != "SHA256SUMS")
with open(os.path.join(HERE, "SHA256SUMS"), "w", newline="\n") as f:
    for p in files:
        f.write(f"{hashlib.sha256(open(os.path.join(HERE, p), 'rb').read()).hexdigest()}  {p}\n")
