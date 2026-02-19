# Testing & Validation Guide

## Quick Start

### 1. Install Dependencies

```bash
cd "Widget Generator Tool"
pip install aiohttp requests python-dotenv
# or:
pip install -r requiremenents.txt
```

### 2. Verify Setup

```bash
# Check you have the cache manager
python3 -c "from geocode_cache_manager import _GeocodeCacheManager; print('✓ Cache manager imported')"

# Check aiohttp is installed
python3 -c "import aiohttp; print(f'✓ aiohttp {aiohttp.__version__} installed')"

# Check Google API key
python3 -c "from dotenv import load_dotenv; load_dotenv(); import os; print(f'✓ API key loaded' if os.getenv('GOOGLE_MAPS_API_KEY') else '✗ No API key')"
```

### 3. Run First Test

```bash
time python3 geocode_settlements.py

# Expected output:
# 🌍 Ukrainian Settlement Geocoder
# ===============================================================================
# Processing XXX clients...
# -------
#   Phase 1: Analyzing entries...
#   ✓ Found NNN unique locations to geocode
#   Phase 2: Fetching coordinates...
#   Phase 3: Applying results...
# ===============================================================================
# Summary:
#   Updated: NNN clients
#   Skipped: XXX clients (already have coordinates)
#   Failed:  X clients
```

---

## Performance Testing

### Test 1: First Run (Measure Baseline)

```bash
# Clear cache first
rm public/geocode_cache.json

# Run with timing
time python3 geocode_settlements.py

# Record the time
```

**Expected:**

- Uncached: 1-2 minutes for 700 entries
- API Calls: 300-500 (due to deduplication)

### Test 2: Second Run (Measure Cache Efficiency)

```bash
# Run immediately after Test 1 (cache still fresh)
time python3 geocode_settlements.py

# Should be nearly instant
```

**Expected:**

- Cached: <1 second
- API Calls: 0
- All entries skipped (no changes)

### Test 3: Partial Update (Measure Incremental)

```bash
# Add a new entry to index.js, or modify an address
# Then run:
time python3 geocode_settlements.py

# Should quickly update only new entries
```

**Expected:**

- Partial update: 5-30 seconds (depends on changes)
- API Calls: Only for new/modified addresses

### Test 4: Force Re-geocoding (Measure Worst Case)

```bash
# Force re-geocode everything
time python3 geocode_settlements.py --force

# This should still be much faster than original
```

**Expected:**

- Force: 1-2 minutes (same as first run)
- API Calls: 300-500 (avoids cache, hits concurrency limits)

---

## Verification Checklist

### ✅ Code Quality

```bash
# Check for syntax errors
python3 -m py_compile geocode_settlements.py
# Should complete without error

# Check imports
python3 -c "import geocode_settlements"
# Should import successfully
```

### ✅ Cache Functionality

```bash
# Check cache is saved
ls -lh public/geocode_cache.json
# File should exist and have reasonable size (>1KB)

# Check cache format
python3 -c "import json; data = json.load(open('public/geocode_cache.json')); print(f'Cache entries: {len(data)}')"
# Should show number of cached locations

# View sample entries
python3 << 'EOF'
import json
data = json.load(open('public/geocode_cache.json'))
for key, value in list(data.items())[:5]:
    print(f"{key}: {value}")
EOF
```

### ✅ Async Functionality

```bash
# Test async module loads
python3 -c "import asyncio; print('✓ asyncio available')"

# Test aiohttp session creation
python3 << 'EOF'
import asyncio
import aiohttp

async def test():
    async with aiohttp.ClientSession() as session:
        print("✓ aiohttp session created")

asyncio.run(test())
EOF
```

### ✅ Concurrent Processing

```bash
# Verify semaphore works
python3 << 'EOF'
import asyncio

async def test_semaphore():
    semaphore = asyncio.Semaphore(8)

    async def worker(i):
        async with semaphore:
            await asyncio.sleep(0.1)
            return i

    tasks = [worker(i) for i in range(20)]
    results = await asyncio.gather(*tasks)
    print(f"✓ Processed {len(results)} items with semaphore")

asyncio.run(test_semaphore())
EOF
```

---

## Performance Benchmarking

### Create a Test Script

```python
# test_performance.py
import time
import os
from geocode_settlements import process_clients_from_js

def benchmark():
    print("Performance Benchmark")
    print("=" * 70)

    # Test 1: Measure geocoding (cache clear)
    print("\n1. COLD RUN (empty cache)")
    print("   Clearing cache...")
    if os.path.exists("public/geocode_cache.json"):
        os.remove("public/geocode_cache.json")

    print("   Running geocode...")
    start = time.time()
    clients = process_clients_from_js(force=True)
    elapsed = time.time() - start

    print(f"   Time: {elapsed:.1f}s")
    print(f"   Entries: {len(clients)}")
    print(f"   Speed: {len(clients)/elapsed:.1f} entries/sec")

    # Test 2: Measure cache hit
    print("\n2. HOT RUN (fully cached)")
    start = time.time()
    clients = process_clients_from_js()
    elapsed = time.time() - start

    print(f"   Time: {elapsed:.2f}s")
    print(f"   Entries: {len(clients)}")
    print(f"   Speed: {len(clients)/elapsed:.1f} entries/sec")

    # Test 3: Cache stats
    print("\n3. CACHE STATISTICS")
    import json
    if os.path.exists("public/geocode_cache.json"):
        with open("public/geocode_cache.json") as f:
            cache = json.load(f)
        print(f"   Cached locations: {len(cache)}")
        print(f"   Cache file size: {os.path.getsize('public/geocode_cache.json')} bytes")

if __name__ == "__main__":
    benchmark()
```

### Run Benchmark

```bash
time python3 test_performance.py

# Output should show:
# Performance Benchmark
# ===============================================================================
# 1. COLD RUN (empty cache)
#    Time: 125.3s  (or better with async)
#    Entries: 703
#    Speed: 5.6 entries/sec  (or better with concurrency)
#
# 2. HOT RUN (fully cached)
#    Time: 0.82s
#    Entries: 703
#    Speed: 857.3 entries/sec
#
# 3. CACHE STATISTICS
#    Cached locations: 420
#    Cache file size: 23456 bytes
```

---

## Comparison: Before vs. After

### Benchmark Results Template

Run the original version first (if you still have it):

```bash
# Original sequential version
time python3 geocode_settlements_original.py
# Record: _____ minutes

# New optimized version
rm public/geocode_cache.json
time python3 geocode_settlements.py
# Record: _____ minutes

# Calculate speedup
# Speedup = original_time / new_time = _____ x faster
```

### Example Results (Expected)

```
ORIGINAL (Sequential):
real    30m45.123s
user    0m12.456s
sys     0m2.345s

OPTIMIZED (Async):
real    1m23.456s
user    0m45.123s
sys     0m1.234s

SPEEDUP: 30m45 / 1m23 = 22.1x faster ✓
```

---

## Debugging

### Issue: "API Rate Limited (429)"

```bash
# Reduce semaphore size in geocode_settlements.py
# Change line ~330:
semaphore = asyncio.Semaphore(4)  # Was 8, now 4

python3 geocode_settlements.py
```

### Issue: "Cache File Corrupted"

```bash
# Delete and regenerate
rm public/geocode_cache.json
python3 geocode_settlements.py

# Verify cache
python3 -c "import json; print(json.load(open('public/geocode_cache.json')))"
```

### Issue: "Import Error: No module named 'aiohttp'"

```bash
pip install aiohttp

# Verify
python3 -c "import aiohttp; print(aiohttp.__version__)"
```

### Issue: "asyncio Error"

```bash
# Check Python version (need 3.6+)
python3 --version

# Test asyncio
python3 -c "import asyncio; asyncio.run(asyncio.sleep(0))"
```

### Issue: "Timeout Errors"

```bash
# Increase timeout in geocode_settlements.py
# Change line ~340:
timeout = aiohttp.ClientTimeout(total=120)  # Was 60, now 120

python3 geocode_settlements.py
```

---

## Output Validation

### Check Output File

```bash
# After running, you should have:
ls -la public/index.js*

# Expected:
# index.js       (Original, unchanged)
# index.js.new   (New output, should be reviewed)

# Compare sizes
wc -l public/index.js public/index.js.new
# Should be approximately the same number of lines
```

### Validate JSON

```bash
# Check if new file is valid JavaScript
python3 << 'EOF'
import re
import json

with open("public/index.js.new") as f:
    content = f.read()

# Extract clients array
match = re.search(r'const clients = \[(.*?)\];', content, re.DOTALL)
if match:
    json_str = "[" + match.group(1) + "]"
    try:
        clients = json.loads(json_str)
        print(f"✓ Valid JSON: {len(clients)} clients")

        # Check coordinates
        with_coords = sum(1 for c in clients if c.get("lat") and c.get("lng"))
        print(f"✓ Clients with coordinates: {with_coords}/{len(clients)}")

        # Sample coordinates
        sample = clients[0]
        print(f"✓ Sample: {sample.get('name')} at ({sample.get('lat')}, {sample.get('lng')})")
    except json.JSONDecodeError as e:
        print(f"✗ JSON Error: {e}")
else:
    print("✗ Could not find clients array")
EOF
```

### Commit Changes

```bash
# Review changes
diff public/index.js public/index.js.new | head -50

# If satisfied:
mv public/index.js.new public/index.js
git add public/index.js geocode_cache.json
git commit -m "Update: Geocoded coordinates for 703 clients"
```

---

## Monitoring Ongoing Operations

### Watch Cache Growth

```bash
# Monitor cache file size
watch -n 1 'ls -lh public/geocode_cache.json'

# Or periodic check
while true; do
    size=$(stat -f "%z" public/geocode_cache.json 2>/dev/null || echo 0)
    count=$(python3 -c "import json; print(len(json.load(open('public/geocode_cache.json'))))" 2>/dev/null || echo 0)
    echo "$(date): Cache size=$size bytes, Entries=$count"
    sleep 5
done
```

### Monitor API Calls

```bash
# The script prints when it makes API calls
# Count them in output:
python3 geocode_settlements.py 2>&1 | grep -c "Fetching coordinates"
```

---

## Success Criteria

✅ All of these should be true after optimization:

- [ ] Script runs without errors
- [ ] Cache file is created: `public/geocode_cache.json`
- [ ] First run completes in <2 minutes (uncached)
- [ ] Second run completes in <1 second (cached)
- [ ] Output file valid: `public/index.js.new`
- [ ] Coordinates are correctly formatted: `[lat, lng]`
- [ ] All clients have coordinates (0 failures)
- [ ] Performance is 15-30x faster than original

If all ✅, optimization is successful!

---

## Performance Expectations

### Minimal Dataset (10-50 entries)

- First run: 2-5 seconds
- Cached: <0.1 seconds

### Medium Dataset (100-300 entries)

- First run: 10-30 seconds
- Cached: <0.5 seconds

### Large Dataset (700+ entries)

- First run: 1-2 minutes
- Cached: <1 second
- Partial update (50 new): 5-10 seconds

### Huge Dataset (1000+ entries)

- First run: 2-5 minutes
- Cached: <1 second
- May need to adjust semaphore down to 4

---

## Reporting

If you want to track performance over time:

```python
# performance_log.py
import json
import os
import time
from datetime import datetime
from geocode_settlements import process_clients_from_js

def log_performance():
    start = time.time()
    clients = process_clients_from_js()
    elapsed = time.time() - start

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "duration_seconds": elapsed,
        "clients_processed": len(clients),
        "throughput": len(clients) / elapsed,
    }

    # Append to log
    log_file = "performance.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    print(f"Logged: {elapsed:.1f}s for {len(clients)} clients")

if __name__ == "__main__":
    log_performance()
```

Run it regularly to track improvements!
