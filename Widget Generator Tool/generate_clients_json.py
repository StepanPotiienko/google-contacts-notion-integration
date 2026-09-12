#!/usr/bin/env python3
"""Generate clients.json for the widget map from a live Notion query.

Reuses the existing fetch + geocode + cache logic in notion_utils so the
output format matches exactly what the map widget expects.

Designed to run inside a GitHub Actions workflow (run-sync.yml) where
NOTION_API_KEY and NOTION_DATABASE_ID are provided as secrets.
The generated file is written to CLIENTS_JSON_PATH (default ./clients.json)
so the workflow can upload/commit it. The Notion token never leaves the
workflow runner / secrets.

Usage:
    CLIENTS_JSON_PATH=clients.json \
    NOTION_API_KEY=... NOTION_DATABASE_ID=... \
    python3 generate_clients_json.py
"""

import json
import os
import sys

# Make notion_utils importable from anywhere this script runs.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from notion_utils import stream_clients_from_notion  # noqa: E402


def main() -> int:
    api_key = os.environ.get("NOTION_API_KEY")
    db_id = os.environ.get("NOTION_DATABASE_ID")

    if not api_key or not db_id:
        print("ERROR: NOTION_API_KEY and NOTION_DATABASE_ID must be set", file=sys.stderr)
        return 1

    clients = []
    for batch in stream_clients_from_notion(api_key, db_id):
        for c in batch:
            # Normalize coords to floats (they sometimes arrive as tuples/ints)
            c["lat"] = float(c["lat"])
            c["lng"] = float(c["lng"])
            # Anonymize: strip personal data — the map shows only name +
            # coordinates. PII (phone/email/address/contact/notes) must NOT
            # exist in the public clients.json (it was a PII leak before).
            clients.append({
                "name": c.get("name", ""),
                "label": c.get("label", ""),
                "color": c.get("color", "#ef4444"),
                "lat": c["lat"],
                "lng": c["lng"],
            })
        # drop any that somehow lack coords
        clients = [c for c in clients if isinstance(c.get("lat"), (int, float))]

    out_path = os.environ.get("CLIENTS_JSON_PATH") or "clients.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True) if os.path.dirname(out_path) else None
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(clients, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(clients)} clients to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
