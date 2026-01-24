"""
Notion end-to-end benchmark: fetch clients from Notion and measure total time.
Reads `NOTION_API_KEY` and `NOTION_DATABASE_ID` from environment.
Run: python3 "Widget Generator Tool/notion_benchmark.py"
"""

import os
import time
from utils import fetch_clients_from_notion, _load_env_with_exports
from dotenv import load_dotenv

# Load .env files: repo root (general) and local (supports `export ` lines)
load_dotenv(os.path.join(os.getcwd(), ".env"))
_load_env_with_exports()

API_KEY = os.environ.get("NOTION_API_KEY")
DB_ID = os.environ.get("NOTION_DATABASE_ID")

if not API_KEY or not DB_ID:
    print(
        "Missing NOTION_API_KEY or NOTION_DATABASE_ID in environment; skipping Notion benchmark."
    )
    raise SystemExit(0)

print("Running Notion end-to-end benchmark...")
start = time.time()
clients = fetch_clients_from_notion(API_KEY, DB_ID)
end = time.time()
print(f"Fetched {len(clients)} clients in {end-start:.2f}s")

# Show a few sample clients
for c in clients[:5]:
    print(c.get("name"), c.get("lat"), c.get("lng"))

print("Notion benchmark complete.")
