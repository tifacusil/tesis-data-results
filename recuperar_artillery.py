#!/usr/bin/env python3
"""
recuperar_artillery.py: inventories the Artillery JSON reports of the September 2026
campaign and copies the usable ones with an A_/B_ prefix.

It reads only the two archived result folders, fixed below in SYSTEMS:
  data/A - SPETIEMBRE 5 RUNS        (System A, 17-18/09/2026)
  data/B - SEPTIEMBRE 5 RUNS V2     (System B, 22-23/09/2026)

For each *.json it counts the 10 s windows (`intermediate`), checks the `aggregate`
block, extracts the aggregate p95 of every metric and the first/last metric time in
UTC, and rates the file USABLE, PARTIAL or UNUSABLE. USABLE files are copied to
<out>/reports/<system>_<name>.json and each copy is checked against the original's
SHA-256. It writes <out>/inventario-reportes.csv sorted by start time.

The originals are only read, never modified or deleted. A second run overwrites nothing:
it re-checks every existing copy and stops if one differs from its original.

Uses only the Python standard library (3.11 or later).

Usage, from the root of this repo:
  python3 recuperar_artillery.py
  python3 recuperar_artillery.py --out other/folder
"""
import argparse, csv, hashlib, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SYSTEMS = {
    "A": ROOT / "data" / "A - SPETIEMBRE 5 RUNS",
    "B": ROOT / "data" / "B - SEPTIEMBRE 5 RUNS V2",
}
MIN_WINDOWS = 40  # a 10 min ladder run gives about 60 windows of 10 s
COLUMNS = ["System", "Original", "Copy", "Status", "Windows", "StartUTC", "EndUTC",
           "MB", "SHA256", "Metrics", "P95Aggregate"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def utc(ms):
    if not ms:
        return ""
    return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def relative(path):
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def diagnose(path):
    row = {"Windows": 0, "StartUTC": "", "EndUTC": "", "Metrics": "", "P95Aggregate": ""}
    try:
        j = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return row | {"Status": f"ERROR reading JSON: {e}"}

    aggregate = j.get("aggregate") if isinstance(j, dict) else None
    aggregate = aggregate if isinstance(aggregate, dict) else {}
    windows = j.get("intermediate") if isinstance(j, dict) else None
    summaries = aggregate.get("summaries")

    row["Windows"] = len(windows) if isinstance(windows, list) else 0
    row["StartUTC"] = utc(aggregate.get("firstMetricAt"))
    row["EndUTC"] = utc(aggregate.get("lastMetricAt"))
    if isinstance(summaries, dict):
        row["Metrics"] = " | ".join(summaries)
        row["P95Aggregate"] = " | ".join(
            f"{name}={v['p95']}" for name, v in summaries.items()
            if isinstance(v, dict) and v.get("p95") is not None)

    if summaries and row["Windows"] >= MIN_WINDOWS:
        row["Status"] = "USABLE: windows + aggregate"
    elif summaries:
        row["Status"] = "PARTIAL: aggregate, too few windows"
    else:
        row["Status"] = "UNUSABLE: no summaries"
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--out", type=Path, default=Path("artillery-inventory"),
                   help="folder for the inventory and the copies (default: artillery-inventory)")
    a = p.parse_args()

    copies = a.out / "reports"
    copies.mkdir(parents=True, exist_ok=True)

    rows = []
    for system, folder in SYSTEMS.items():
        if not folder.is_dir():
            sys.exit(f"Folder not found: {folder}")
        for f in sorted(folder.glob("*.json")):
            row = {"System": system, "Original": relative(f), "Copy": "",
                   "MB": round(f.stat().st_size / 2**20, 2), "SHA256": sha256(f)}
            row |= diagnose(f)
            if row["Status"].startswith("USABLE"):
                target = copies / f"{system}_{f.name}"
                if not target.exists():
                    shutil.copy2(f, target)
                if sha256(target) != row["SHA256"]:
                    sys.exit(f"Copy differs from its original: {target}\n"
                             "Nothing was overwritten; check it by hand.")
                row["Copy"] = relative(target)
            rows.append(row)
            print(f"{system}  {f.name:<22} {row['Windows']:>5}  {row['Status']}")

    rows.sort(key=lambda r: (r["StartUTC"], r["System"], r["Original"]))
    inventory = a.out / "inventario-reportes.csv"
    with open(inventory, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    usable = sum(r["Status"].startswith("USABLE") for r in rows)
    print(f"\n{len(rows)} JSON checked, {usable} USABLE, {len(rows) - usable} partial or unusable.")
    print(f"Copies checked by SHA-256 in: {copies.resolve()}")
    print(f"Inventory: {inventory.resolve()}")


if __name__ == "__main__":
    main()
