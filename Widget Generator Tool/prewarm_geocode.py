"""
Pre-warm geocode cache by fetching place strings from Notion and geocoding them.
Run: python3 "Widget Generator Tool/prewarm_geocode.py"
Uses NOTION_API_KEY and NOTION_DATABASE_ID from environment or .env.
"""

import os
import time
from pathlib import Path

from utils import fetch_notion_data, _load_env_with_exports, batch_geocode
from dotenv import load_dotenv

# Load .env files: repo root and local tool .env (supports `export ` lines)
load_dotenv(os.path.join(os.getcwd(), ".env"))
_load_env_with_exports()

API_KEY = os.environ.get("NOTION_API_KEY")
DB_ID = os.environ.get("NOTION_DATABASE_ID")

if not API_KEY or not DB_ID:
    print(
        "Missing NOTION_API_KEY or NOTION_DATABASE_ID in environment; aborting prewarm."
    )
    raise SystemExit(1)

print("Fetching Notion database to collect addresses...")
ndata = fetch_notion_data(API_KEY, DB_ID)
results = ndata.get("results", [])
print(f"Found {len(results)} entries")

places = []
for page in results:
    props = page.get("properties", {})
    # Try similar fields to `fetch_clients_from_notion`
    place = ""
    address_ua = props.get("АДРЕСА") or props.get("Адреса")
    if address_ua and address_ua.get("rich_text"):
        place = address_ua["rich_text"][0].get("plain_text", "")
    if not place:
        place_prop = props.get("Place") or props.get("place")
        if place_prop and place_prop.get("type") == "place":
            location_value = place_prop.get("place")
            if location_value:
                if "name" in location_value:
                    place = location_value.get("name", "")
    if not place:
        af = props.get("Address 1 - Formatted")
        if af and af.get("rich_text"):
            place = af["rich_text"][0].get("plain_text", "")
    if not place:
        address_parts = []
        for key in [
            "Address 1 - Street",
            "Address 1 - City",
            "Address 1 - Region",
            "Address 1 - Country",
        ]:
            comp = props.get(key)
            if comp and comp.get("rich_text"):
                txt = comp["rich_text"][0].get("plain_text", "")
                if txt:
                    address_parts.append(txt)
        if address_parts:
            place = ", ".join(address_parts)
    if place:
        places.append(place)

# Deduplicate while preserving order
seen = set()
uniq = []
for p in places:
    k = " ".join(p.strip().lower().split())
    if k in seen:
        continue
    seen.add(k)
    uniq.append(p)

print(f"Collected {len(uniq)} unique place strings to geocode")
if not uniq:
    print("No places to geocode; exiting.")
    raise SystemExit(0)

# Run batch geocode (this will populate cache and save it)
start = time.time()
# Conservative defaults; change rate/burst if you want faster but be mindful of rate limits
res = batch_geocode(uniq, max_workers=8, rate=4.0, burst=4)
end = time.time()
print(
    f"Geocoded {len([r for r in res.values() if r])}/{len(uniq)} places in {end-start:.2f}s"
)
print("Pre-warm complete. Cache saved to public/geocode_cache.json if writable.")
