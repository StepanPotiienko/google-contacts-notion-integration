import time
import json

import requests  # type: ignore
from flask import Flask, jsonify, render_template_string, request, send_file  # type: ignore
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
import os
from dotenv import load_dotenv  # type: ignore
import csv

STATIC_DIR = os.path.join(os.path.dirname(__file__), "public")
app = Flask(__name__, static_folder=STATIC_DIR)

def _load_env_with_exports():
    """Load .env and also support lines that start with 'export '.
    This helps when .env uses shell-style `export KEY="value"` lines.
    """
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_path)
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    kv = line[len("export ") :]
                    if "=" in kv:
                        key, val = kv.split("=", 1)
                        key = key.strip()
                        # remove optional surrounding quotes
                        val = val.strip().strip('"').strip("'")
                        os.environ.setdefault(key, val)


_load_env_with_exports()

# Widget generator interface
# TODO: Move to another file and fetch it from there
GENERATOR_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Client Map Widget Generator</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { 
            max-width: 800px; 
            margin: 0 auto; 
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            padding: 40px;
        }
        h1 { 
            color: #333; 
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .form-group { 
            margin-bottom: 20px; 
        }
        label { 
            display: block; 
            margin-bottom: 8px; 
            font-weight: 600;
            color: #333;
            font-size: 14px;
        }
        input { 
            width: 100%; 
            padding: 12px; 
            border: 1px solid #ddd; 
            border-radius: 4px;
            font-size: 14px;
            font-family: 'Courier New', monospace;
        }
        input:focus {
            outline: none;
            border-color: #2563eb;
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
        }
        button { 
            background: #2563eb; 
            color: white; 
            padding: 12px 24px; 
            border: none; 
            border-radius: 4px; 
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            width: 100%;
        }
        button:hover { 
            background: #1d4ed8; 
        }
        button:disabled {
            background: #9ca3af;
            cursor: not-allowed;
        }
        .result { 
            margin-top: 30px; 
            padding: 20px;
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 4px;
            display: none;
        }
        .result.show { 
            display: block; 
        }
        .result h2 {
            color: #059669;
            font-size: 18px;
            margin-bottom: 15px;
        }
        textarea { 
            width: 100%; 
            height: 200px; 
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            resize: vertical;
        }
        .copy-btn {
            margin-top: 10px;
            background: #059669;
            width: auto;
            display: inline-block;
        }
        .copy-btn:hover {
            background: #047857;
        }
        .error {
            background: #fee2e2;
            border: 1px solid #fecaca;
            color: #991b1b;
            padding: 12px;
            border-radius: 4px;
            margin-top: 15px;
            display: none;
        }
        .error.show {
            display: block;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #2563eb;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            animation: spin 1s linear infinite;
            display: inline-block;
            margin-right: 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .info-box {
            background: #dbeafe;
            border: 1px solid #bfdbfe;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
            font-size: 13px;
            color: #1e40af;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🗺️ Client Map Widget Generator</h1>
        <p class="subtitle">Generate an embeddable map widget from your Notion database</p>
        
        <div class="info-box">
            <strong>How it works:</strong> Enter your Notion credentials below. This tool will fetch your client data 
            and generate a standalone HTML widget that you can paste directly into your website.
        </div>

        <form id="generatorForm">
            <div class="form-group">
                <label for="apiKey">Notion API Key (starts with ntn_)</label>
                <input type="password" id="apiKey" placeholder="ntn_xxxxxxxxxxxxx" required>
            </div>
            
            <div class="form-group">
                <label for="databaseId">Database ID</label>
                <input type="text" id="databaseId" value="23ef1b322cf9808b9355f50913158855" required>
            </div>
            
            <button type="submit" id="generateBtn">
                Generate Widget
            </button>
        </form>

        <div class="error" id="error"></div>

        <div class="result" id="result">
            <h2>✅ Widget Generated Successfully!</h2>
            <p style="margin-bottom: 15px; color: #666; font-size: 14px;">
                Copy the code below and paste it into your website:
            </p>
            <textarea id="widgetCode" readonly></textarea>
            <button class="copy-btn" onclick="copyWidget()">Copy to Clipboard</button>
        </div>
    </div>

    <script>
        document.getElementById('generatorForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const btn = document.getElementById('generateBtn');
            const error = document.getElementById('error');
            const result = document.getElementById('result');
            
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span>Generating...';
            error.classList.remove('show');
            result.classList.remove('show');
            
            const apiKey = document.getElementById('apiKey').value;
            const databaseId = document.getElementById('databaseId').value;
            
            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ apiKey, databaseId })
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Failed to generate widget');
                }
                
                document.getElementById('widgetCode').value = data.widget;
                result.classList.add('show');
                
            } catch (err) {
                error.textContent = err.message;
                error.classList.add('show');
            } finally {
                btn.disabled = false;
                btn.innerHTML = 'Generate Widget';
            }
        });
        
        function copyWidget() {
            const textarea = document.getElementById('widgetCode');
            textarea.select();
            document.execCommand('copy');
            
            const btn = event.target;
            const originalText = btn.textContent;
            btn.textContent = '✓ Copied!';
            setTimeout(() => {
                btn.textContent = originalText;
            }, 2000);
        }
    </script>
</body>
</html>
"""

# Using Notion embed template for the widget


# Widget template that embeds scraped Notion map content
NOTION_MAP_WIDGET_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>Client Map</title>
    <style>
        :root {{ color-scheme: light dark; }}
        html, body {{ 
            height: 100%; 
            margin: 0; 
            padding: 0;
            overflow: hidden;
        }}
        #notion-map-container {{ 
            width: 100%; 
            height: 100vh; 
            position: relative;
        }}
        .loading {{
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: #666;
        }}
        iframe {{
            border: none;
            width: 100%;
            height: 100%;
        }}
    </style>
</head>
<body>
    <div id=\"notion-map-container\">
        {map_content}
    </div>
</body>
</html>"""


def fetch_clients_from_notion(api_key, database_id):
    """Fetch client location data from Notion database.
    Returns a list of clients with name, lat, lng.
    """
    print("\n" + "=" * 60)
    print("🔍 Fetching data from Notion...")
    clients = []
    entries_processed = 0
    entries_with_place = 0
    entries_geocoded = 0

    try:
        notion_data = fetch_notion_data(api_key, database_id)
        total_entries = len(notion_data.get("results", []))
        print(f"✅ Found {total_entries} total entries in database")

        for page in notion_data.get("results", []):
            entries_processed += 1
            props = page.get("properties", {})

            # Extract name
            name_prop = props.get("Name") or props.get("name")
            name = "Unnamed"
            if name_prop and name_prop.get("title"):
                name = (
                    name_prop["title"][0]["plain_text"]
                    if name_prop["title"]
                    else "Unnamed"
                )

            # Extract label color
            label_color = "#ef4444"  # default red
            labels_prop = props.get("Labels") or props.get("Label")
            if labels_prop:
                if labels_prop.get("type") == "multi_select" and labels_prop.get(
                    "multi_select"
                ):
                    # Get first label's color
                    first_label = labels_prop["multi_select"][0]
                    notion_color = first_label.get("color", "red")
                    # Map Notion colors to hex
                    color_map = {
                        "gray": "#6b7280",
                        "brown": "#92400e",
                        "orange": "#ea580c",
                        "yellow": "#eab308",
                        "green": "#16a34a",
                        "blue": "#2563eb",
                        "purple": "#9333ea",
                        "pink": "#db2777",
                        "red": "#ef4444",
                        "default": "#6b7280",
                    }
                    label_color = color_map.get(notion_color, "#ef4444")
                elif labels_prop.get("type") == "select" and labels_prop.get("select"):
                    notion_color = labels_prop["select"].get("color", "red")
                    color_map = {
                        "gray": "#6b7280",
                        "brown": "#92400e",
                        "orange": "#ea580c",
                        "yellow": "#eab308",
                        "green": "#16a34a",
                        "blue": "#2563eb",
                        "purple": "#9333ea",
                        "pink": "#db2777",
                        "red": "#ef4444",
                        "default": "#6b7280",
                    }
                    label_color = color_map.get(notion_color, "#ef4444")

            # Extract place - try multiple sources
            place = ""
            latlng = None

            # 1. Try the Place property (Notion location type)
            place_prop = props.get("Place") or props.get("place")
            if place_prop and place_prop.get("type") == "place":
                location_value = place_prop.get("place")
                if location_value:
                    if "latitude" in location_value and "longitude" in location_value:
                        latlng = (
                            location_value["latitude"],
                            location_value["longitude"],
                        )
                    elif "name" in location_value:
                        place = location_value["name"]

            # 2. Try formatted address
            if not latlng and not place:
                addr_formatted = props.get("Address 1 - Formatted")
                if addr_formatted and addr_formatted.get("rich_text"):
                    place = (
                        addr_formatted["rich_text"][0]["plain_text"]
                        if addr_formatted["rich_text"]
                        else ""
                    )

            # 3. Build from components
            if not latlng and not place:
                address_parts = []
                for key in [
                    "Address 1 - Street",
                    "Address 1 - City",
                    "Address 1 - Region",
                    "Address 1 - Country",
                ]:
                    comp = props.get(key)
                    if comp and comp.get("rich_text"):
                        txt = (
                            comp["rich_text"][0]["plain_text"]
                            if comp["rich_text"]
                            else ""
                        )
                        if txt:
                            address_parts.append(txt)
                if address_parts:
                    place = ", ".join(address_parts)

            # If we already have coordinates, use them
            if latlng:
                entries_with_place += 1
                entries_geocoded += 1
                clients.append(
                    {
                        "name": name,
                        "lat": latlng[0],
                        "lng": latlng[1],
                        "color": label_color,
                    }
                )
            # Otherwise, geocode the place string
            elif place:
                entries_with_place += 1
                # Check if it's already in lat,lng format
                if "," in place and place.count(",") == 1:
                    try:
                        parts = place.split(",")
                        lat = float(parts[0].strip())
                        lng = float(parts[1].strip())
                        if -90 <= lat <= 90 and -180 <= lng <= 180:
                            entries_geocoded += 1
                            clients.append(
                                {
                                    "name": name,
                                    "lat": lat,
                                    "lng": lng,
                                    "color": label_color,
                                }
                            )
                            continue
                    except (ValueError, IndexError):
                        pass
                time.sleep(1)  # Rate limiting for geocoding
                coords = geocode_location(place)
                if coords:
                    entries_geocoded += 1
                    clients.append(
                        {
                            "name": name,
                            "lat": coords["lat"],
                            "lng": coords["lng"],
                            "color": label_color,
                        }
                    )

        print("=" * 60)
        print("📊 SUMMARY:")
        print(f"   Total entries: {entries_processed}")
        print(f"   With Place filled: {entries_with_place}")
        print(f"   Successfully geocoded: {entries_geocoded}")
        print("=" * 60 + "\n")

        return clients

    except Exception as e:
        print(f"❌ Error fetching from Notion: {e}")
        return []


# Optional: Use Notion Map link-only widget (avoids iframe restrictions)
NOTION_EMBED_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>Client Map (Notion Link)</title>
    <style>
        :root {{ color-scheme: light dark; }}
        html, body {{ height: 100%; margin: 0; }}
        body {{ display: grid; place-items: center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .card {{ max-width: 640px; margin: 24px; padding: 24px; border-radius: 12px; border: 1px solid #e5e7eb; background: #ffffff; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }}
        .title {{ font-size: 18px; font-weight: 600; color: #111827; margin-bottom: 8px; }}
        .desc {{ font-size: 14px; color: #6b7280; margin-bottom: 16px; }}
        .btn {{ display: inline-flex; align-items: center; gap: 8px; background: #2563eb; color: white; text-decoration: none; padding: 12px 16px; border-radius: 8px; font-weight: 600; }}
        .btn:hover {{ background: #1d4ed8; }}
        .btn svg {{ width: 18px; height: 18px; }}
        @media (prefers-color-scheme: dark) {{
            .card {{ border-color: #374151; background: #111827; }}
            .title {{ color: #e5e7eb; }}
            .desc {{ color: #9ca3af; }}
        }}
    </style>
</head>
<body>
    <div class=\"card\">
        <div class=\"title\">Client Map in Notion</div>
        <div class=\"desc\">Open the map view in Notion. This avoids iframe restrictions and ensures it loads reliably.</div>
        <a class=\"btn\" href=\"{embed_url}\" target=\"_blank\" rel=\"noopener noreferrer\">
            <svg viewBox=\"0 0 24 24\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"><path d=\"M14 3H21V10\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/><path d=\"M10 14L21 3\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/><path d=\"M21 14V21H3V3H10\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/></svg>
            Open Notion Map
        </a>
    </div>
</body>
</html>"""

# Inline map template using MapLibre GL JS (no Leaflet, no Notion iframe)
INLINE_MAP_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>Client Map</title>
    <link href=\"https://unpkg.com/maplibre-gl@3.6.1/dist/maplibre-gl.css\" rel=\"stylesheet\" />
    <script src=\"https://unpkg.com/maplibre-gl@3.6.1/dist/maplibre-gl.js\"></script>
    <style>
        html, body { height: 100%; margin: 0; }
        #map { position: fixed; inset: 0; }
        .marker { 
            width: 14px; 
            height: 14px; 
            border-radius: 50%; 
            border: 3px solid white; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            cursor: pointer;
            transition: transform 0.2s;
        }
        .marker:hover {
            transform: scale(1.2);
        }
        .maplibregl-popup-content { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            font-size: 14px; 
            color: #111827; 
            padding: 12px 16px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .maplibregl-popup-content strong {
            display: block;
            margin-bottom: 4px;
        }
    </style>
</head>
<body>
    <div id=\"map\"></div>
    <script>
        const clients = {clients_json};

        const map = new maplibregl.Map({
            container: 'map',
            style: {
                version: 8,
                sources: {
                    osm: {
                        type: 'raster',
                        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
                        tileSize: 256,
                        attribution: '© OpenStreetMap contributors'
                    }
                },
                layers: [{ id: 'osm', type: 'raster', source: 'osm' }]
            },
            center: [30.5241361, 50.4500336],
            zoom: 5
        });

        map.on('load', () => {
            if (clients.length === 0) return;
            const bounds = new maplibregl.LngLatBounds();
            clients.forEach(c => bounds.extend([c.lng, c.lat]));
            map.fitBounds(bounds, { padding: 50, maxZoom: 12 });

            clients.forEach(c => {
                const el = document.createElement('div');
                el.className = 'marker';
                el.style.backgroundColor = c.color || '#ef4444';
                
                const popup = new maplibregl.Popup({ offset: 15 })
                    .setHTML(`<div class="popup"><strong>${c.name}</strong></div>`);
                
                new maplibregl.Marker({ element: el })
                    .setLngLat([c.lng, c.lat])
                    .setPopup(popup)
                    .addTo(map);
            });
        });
    </script>
</body>
</html>"""


def geocode_location(location):
    """Convert location string to coordinates using OpenStreetMap Nominatim"""
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={location}&limit=1"
        headers = {"User-Agent": "ClientMapWidget/1.0"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        if data and len(data) > 0:
            return {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
        return None
    except Exception as e:
        print(f"  ❌ Geocoding error for '{location}': {e}")
        return None


def fetch_notion_data(api_key, database_id):
    """Fetch ALL data from Notion database (handles pagination)"""
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    all_results = []
    has_more = True
    start_cursor = None

    try:
        while has_more:
            payload = {}
            if start_cursor:
                payload["start_cursor"] = start_cursor

            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            all_results.extend(data.get("results", []))
            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

            print(
                f"  Fetched {len(data.get('results', []))} entries... (Total so far: {len(all_results)})"
            )

        return {"results": all_results}
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch from Notion: {str(e)}")


def get_clients_from_csv():
    """Read clients from the simplest CSV in data/ and geocode Place."""
    print("🧾 Using CSV mode (data/ folder)...")
    csv_dir = os.path.join(os.path.dirname(__file__), "data")
    if not os.path.isdir(csv_dir):
        raise Exception("data/ directory not found")

    csv_paths = [
        os.path.join(csv_dir, f)
        for f in os.listdir(csv_dir)
        if f.lower().endswith(".csv")
    ]
    if not csv_paths:
        raise Exception("No CSV files found in data/")

    # Prefer non-"_all" CSV for simpler schema
    csv_file = None
    for p in csv_paths:
        if "_all" not in os.path.basename(p):
            csv_file = p
            break
    if not csv_file:
        csv_file = csv_paths[0]

    print(f"   Reading: {os.path.basename(csv_file)}")
    clients = []
    entries_processed = 0
    entries_with_place = 0
    entries_geocoded = 0
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries_processed += 1
            name = (row.get("Name") or "Unnamed").strip()
            place = (row.get("Place") or "").strip()
            if place:
                entries_with_place += 1
                time.sleep(0.2)
                coords = geocode_location(place)
                if coords:
                    entries_geocoded += 1
                    clients.append(
                        {"name": name, "lat": coords["lat"], "lng": coords["lng"]}
                    )
    print("Data loaded from CSV.")
    print("📊 CSV SUMMARY:")
    print(f"   Total entries: {entries_processed}")
    print(f"   With Place filled: {entries_with_place}")
    print(f"   Successfully geocoded: {entries_geocoded}")
    return clients


def write_widget_html(clients, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    mode = os.getenv("WIDGET_MODE", "link").lower()
    if mode == "inline":
        clients_json = json.dumps(clients, ensure_ascii=False)
        widget_html = INLINE_MAP_TEMPLATE.format(clients_json=clients_json)
    else:
        embed_url = os.getenv("NOTION_MAP_EMBED_URL")
        if not embed_url:
            raise ValueError(
                "NOTION_MAP_EMBED_URL is not set. Set it in .env or switch to WIDGET_MODE=inline."
            )
        widget_html = NOTION_EMBED_TEMPLATE.format(embed_url=embed_url)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(widget_html)
    return widget_html


@app.route("/")
def index():
    return render_template_string(GENERATOR_HTML)


@app.route("/generate", methods=["POST"])
def generate_widget():
    data = request.json
    api_key = data.get("apiKey")
    database_id = data.get("databaseId")
    use_csv = data.get("useCsv")

    if not api_key or not database_id:
        return jsonify({"error": "API key and Database ID are required"}), 400

    try:
        # Fetch data from Notion
        print("\n" + "=" * 60)
        print("🔍 Fetching data from Notion...")
        clients = []
        entries_processed = 0
        entries_with_place = 0
        entries_geocoded = 0

        # Optional CSV mode for faster debugging or offline generation
        if use_csv:
            clients = get_clients_from_csv()
            print("Skipping Notion API.")
        else:
            # Fetch data from Notion and process
            notion_data = fetch_notion_data(api_key, database_id)

            total_entries = len(notion_data.get("results", []))
            print(f"✅ Found {total_entries} total entries in database")
            print("=" * 60 + "\n")

            # DEBUG: Print available properties from first entry
            if notion_data.get("results"):
                first_entry = notion_data["results"][0]
                print("\n" + "=" * 80)
                print("🔍 DEBUG: Available properties in first entry:")
                print("=" * 80)
                for prop_name, prop_value in first_entry.get("properties", {}).items():
                    prop_type = prop_value.get("type", "unknown")
                    print(f"   Property: '{prop_name}'")
                    print(f"   Type: {prop_type}")
                    print(f"   Value: {prop_value}")
                    print("-" * 80)
                print("=" * 80)
                print()

            for page in notion_data.get("results", []):
                entries_processed += 1
                props = page.get("properties", {})

                # Extract name
                name_prop = props.get("Name") or props.get("name")
                name = "Unnamed"
                if name_prop and name_prop.get("title"):
                    name = (
                        name_prop["title"][0]["plain_text"]
                        if name_prop["title"]
                        else "Unnamed"
                    )

                # Extract place - try multiple sources
                place = ""

                # 1. Try the Place property (Notion location type)
                place_prop = props.get("Place") or props.get("place")
                if place_prop and place_prop.get("type") == "place":
                    location_value = place_prop.get("place")
                    if location_value:
                        if (
                            "latitude" in location_value
                            and "longitude" in location_value
                        ):
                            lat = location_value["latitude"]
                            lng = location_value["longitude"]
                            clients.append({"name": name, "lat": lat, "lng": lng})
                            entries_with_place += 1
                            entries_geocoded += 1
                            continue
                        elif "name" in location_value:
                            place = location_value["name"]

                # 2. Try formatted address
                if not place:
                    addr_formatted = props.get("Address 1 - Formatted")
                    if addr_formatted and addr_formatted.get("rich_text"):
                        formatted_text = (
                            addr_formatted["rich_text"][0]["plain_text"]
                            if addr_formatted["rich_text"]
                            else ""
                        )
                        if formatted_text:
                            place = formatted_text

                # 3. Build from components
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
                            txt = (
                                comp["rich_text"][0]["plain_text"]
                                if comp["rich_text"]
                                else ""
                            )
                            if txt:
                                address_parts.append(txt)
                    if address_parts:
                        place = ", ".join(address_parts)

                # Geocode if we have a place string
                if place:
                    entries_with_place += 1
                    # If appears as 'lat,lng', try parsing
                    if "," in place and place.count(",") == 1:
                        try:
                            parts = place.split(",")
                            lat = float(parts[0].strip())
                            lng = float(parts[1].strip())
                            if -90 <= lat <= 90 and -180 <= lng <= 180:
                                clients.append({"name": name, "lat": lat, "lng": lng})
                                entries_geocoded += 1
                                continue
                        except (ValueError, IndexError):
                            pass
                    time.sleep(1)
                    coords = geocode_location(place)
                    if coords:
                        entries_geocoded += 1
                        clients.append(
                            {"name": name, "lat": coords["lat"], "lng": coords["lng"]}
                        )
                    else:
                        print("  ❌ Failed to geocode")

        # Instead of fetching from Notion API in the /generate route,
        # use the already processed clients data to create the map
        # Generate interactive map widget with client locations
        clients_json = json.dumps(clients, ensure_ascii=False)
        widget_html = INLINE_MAP_TEMPLATE.format(clients_json=clients_json)

        return jsonify({"widget": widget_html, "clientCount": len(clients)})

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}\n")
        return jsonify({"error": str(e)}), 500


@app.route("/refresh", methods=["POST", "GET"])
def refresh():
    """Regenerate widget and write to public/widget.html.
    Fetches client location data from Notion and renders an interactive map.
    """
    output_path = os.path.join(STATIC_DIR, "widget.html")
    try:
        api_key = os.getenv("NOTION_API_KEY")
        database_id = os.getenv("NOTION_DATABASE_ID")

        if not api_key or not database_id:
            return (
                jsonify(
                    {
                        "error": "NOTION_API_KEY and NOTION_DATABASE_ID must be set in .env"
                    }
                ),
                400,
            )

        # Fetch client location data from Notion
        clients = fetch_clients_from_notion(api_key, database_id)

        # Generate interactive map widget
        clients_json = json.dumps(clients, ensure_ascii=False)
        widget_html = INLINE_MAP_TEMPLATE.format(clients_json=clients_json)

        # Write to file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(widget_html)

        return jsonify(
            {
                "message": "Refreshed",
                "output": output_path,
                "source": "notion-api",
                "clientCount": len(clients),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def start_scheduler():
    scheduler = BackgroundScheduler()

    def nightly_job():
        print("⏰ Nightly job started")
        # Honor USE_CSV env for nightly as well
        try:
            refresh()
            print("⏰ Nightly job finished")
        except Exception as e:
            print(f"[Scheduler] ERROR: {e}")

    scheduler.add_job(nightly_job, "cron", hour=0, minute=0)
    scheduler.start()


# Direct route to serve the generated widget regardless of static config
@app.route("/widget", methods=["GET"])
def serve_widget():
    output_path = os.path.join(STATIC_DIR, "widget.html")
    if not os.path.exists(output_path):
        return jsonify({"error": "widget.html not found. Run /refresh first."}), 404
    return send_file(output_path, mimetype="text/html")


if __name__ == "__main__":
    start_scheduler()
    app.run(debug=True, host="0.0.0.0", port=5000)
