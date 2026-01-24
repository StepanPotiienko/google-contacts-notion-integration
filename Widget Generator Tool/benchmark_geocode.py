"""
Simple benchmark for CSV parsing and batch geocoding.
Run from repo root with: python3 "Widget Generator Tool/benchmark_geocode.py"
"""

import time
import glob
import os
from pathlib import Path

from utils import parse_csv_to_clients, batch_geocode

CSV_DIR = os.path.join(os.path.dirname(__file__), "..", "notion")
CSV_DIR = os.path.normpath(CSV_DIR)

files = sorted(glob.glob(os.path.join(CSV_DIR, "clients_*.csv")))
if not files:
    print("No CSV files found in notion/ to benchmark.")
    raise SystemExit(1)

print(f"Found {len(files)} CSV files to test:")
for f in files:
    print(" -", os.path.basename(f))

all_addresses = []

# Parse each CSV without geocoding (fast)
for f in files:
    b = Path(f).read_bytes()
    t0 = time.time()
    clients = parse_csv_to_clients(b, geocode=False)
    t1 = time.time()
    print(
        f"Parsed {os.path.basename(f)} -> {len(clients)} clients in {t1-t0:.3f}s (no geocode)"
    )
    for c in clients:
        addr = c.get("address")
        if addr:
            all_addresses.append(addr)

# Deduplicate addresses
seen = set()
uniq_addresses = []
for a in all_addresses:
    key = " ".join(str(a).strip().lower().split())
    if key in seen:
        continue
    seen.add(key)
    uniq_addresses.append(a)

print(f"Collected {len(uniq_addresses)} unique addresses from CSVs")

# Run batch geocode on a limited sample to measure rate
sample = uniq_addresses[:40]
if not sample:
    print("No addresses to geocode; finishing.")
    raise SystemExit(0)

print(
    f"Geocoding sample of {len(sample)} addresses (this will call external Nominatim API)"
)

t0 = time.time()
res = batch_geocode(sample, max_workers=4, rate=4.0, burst=4)

t1 = time.time()

successful = sum(1 for v in res.values() if v)
print(f"Batch geocode: {successful}/{len(sample)} succeeded in {t1-t0:.2f}s")

# Show a few results
for a in sample[:5]:
    print(a, "->", res.get(a))

print("Benchmark complete.")
