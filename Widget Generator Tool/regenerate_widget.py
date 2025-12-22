#!/usr/bin/env python3
"""Regenerate the widget HTML file with interactive map"""

import os
import json
from dotenv import load_dotenv
from main import fetch_clients_from_notion, INLINE_MAP_TEMPLATE

# Load environment variables
load_dotenv()


def main():
    api_key = os.getenv("NOTION_API_KEY")
    database_id = os.getenv("NOTION_DATABASE_ID")

    if not api_key or not database_id:
        print("❌ Error: NOTION_API_KEY and NOTION_DATABASE_ID must be set in .env")
        return

    # Fetch client location data from Notion
    clients = fetch_clients_from_notion(api_key, database_id)

    if not clients:
        print("⚠️  Warning: No clients with location data found")

    # Generate interactive map widget
    clients_json = json.dumps(clients, ensure_ascii=False)
    # Use replace instead of format to avoid conflict with {{ }} in JavaScript
    widget_html = INLINE_MAP_TEMPLATE.replace("{clients_json}", clients_json)

    # Write to file
    output_path = os.path.join(os.path.dirname(__file__), "public", "widget.html")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(widget_html)

    print(f"\n✅ Widget generated successfully!")
    print(f"   Output: {output_path}")
    print(f"   Clients on map: {len(clients)}")
    print(f"\n📍 Open the widget:")
    print(f"   file://{output_path}")


if __name__ == "__main__":
    main()
