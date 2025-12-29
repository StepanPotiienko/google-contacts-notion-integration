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
    Returns a list of clients with name, lat, lng, and additional properties.
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

            # Filter: Only include entries where Source = "БАЗА"
            source_prop = props.get("Source") or props.get("source")
            source_value = None
            if source_prop:
                if source_prop.get("type") == "select" and source_prop.get("select"):
                    source_value = source_prop["select"].get("name", "")
                elif source_prop.get("type") == "rich_text" and source_prop.get("rich_text"):
                    source_value = source_prop["rich_text"][0]["plain_text"] if source_prop["rich_text"] else ""
            
            # Skip entries that don't have Source = "БАЗА"
            if source_value != "БАЗА":
                continue

            # Extract name
            name_prop = props.get("Name") or props.get("name")
            name = "Unnamed"
            if name_prop and name_prop.get("title"):
                name = (
                    name_prop["title"][0]["plain_text"]
                    if name_prop["title"]
                    else "Unnamed"
                )

            # === Extract additional properties for popup ===
            
            # Phone number (Ukrainian field first as БАЗА entries use it)
            phone = ""
            phone_prop = props.get("ТЕЛЕФОН") or props.get("Phone")
            if phone_prop and phone_prop.get("rich_text") and phone_prop["rich_text"]:
                phone = phone_prop["rich_text"][0]["plain_text"]
            
            # Email
            email = ""
            email_prop = props.get("ЕЛ.АДРЕСА") or props.get("Email") or props.get("E-mail 1 - Value")
            if email_prop:
                if email_prop.get("type") == "email":
                    email = email_prop.get("email") or ""
                elif email_prop.get("type") == "rich_text" and email_prop.get("rich_text"):
                    email = email_prop["rich_text"][0]["plain_text"] if email_prop["rich_text"] else ""
            
            # Contact person
            contact = ""
            contact_prop = props.get("КОНТАКТ")
            if contact_prop and contact_prop.get("rich_text") and contact_prop["rich_text"]:
                contact = contact_prop["rich_text"][0]["plain_text"]
            
            # Notes/Comments (Ukrainian field first as БАЗА entries use it)
            notes = ""
            notes_prop = props.get("ПРИМІТКА") or props.get("Notes")
            if notes_prop and notes_prop.get("rich_text") and notes_prop["rich_text"]:
                notes = notes_prop["rich_text"][0]["plain_text"]
                # Truncate long notes
                if len(notes) > 100:
                    notes = notes[:100] + "..."
            
            # Organization title
            org_title = ""
            org_title_prop = props.get("Organization Title")
            if org_title_prop and org_title_prop.get("select"):
                org_title = org_title_prop["select"].get("name", "")

            # Extract label color
            label_color = "#ef4444"  # default red
            label_name = ""
            labels_prop = props.get("Labels") or props.get("Label")
            if labels_prop:
                if labels_prop.get("type") == "multi_select" and labels_prop.get(
                    "multi_select"
                ):
                    # Get first label's color
                    first_label = labels_prop["multi_select"][0]
                    notion_color = first_label.get("color", "red")
                    label_name = first_label.get("name", "")
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
                    label_name = labels_prop["select"].get("name", "")
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
            address_display = ""  # For showing in popup
            latlng = None

            # 1. Try the Адреса property (Ukrainian address field)
            address_ua = props.get("Адреса")
            if address_ua and address_ua.get("rich_text"):
                place = (
                    address_ua["rich_text"][0]["plain_text"]
                    if address_ua["rich_text"]
                    else ""
                )
                address_display = place

            # 2. Try the Place property (Notion location type)
            if not latlng and not place:
                place_prop = props.get("Place") or props.get("place")
                if place_prop and place_prop.get("type") == "place":
                    location_value = place_prop.get("place")
                    if location_value:
                        if "latitude" in location_value and "longitude" in location_value:
                            latlng = (
                                location_value["latitude"],
                                location_value["longitude"],
                            )
                            address_display = location_value.get("name", "")
                        elif "name" in location_value:
                            place = location_value["name"]
                            address_display = place

            # 3. Try formatted address
            if not latlng and not place:
                addr_formatted = props.get("Address 1 - Formatted")
                if addr_formatted and addr_formatted.get("rich_text"):
                    place = (
                        addr_formatted["rich_text"][0]["plain_text"]
                        if addr_formatted["rich_text"]
                        else ""
                    )
                    address_display = place

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
                    address_display = place

            # Build client data object with all properties
            client_data = {
                "name": name,
                "color": label_color,
                "phone": phone,
                "email": email,
                "contact": contact,
                "address": address_display,
                "notes": notes,
                "label": label_name,
                "orgTitle": org_title,
            }

            # If we already have coordinates, use them
            if latlng:
                entries_with_place += 1
                entries_geocoded += 1
                client_data["lat"] = latlng[0]
                client_data["lng"] = latlng[1]
                clients.append(client_data)
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
                            client_data["lat"] = lat
                            client_data["lng"] = lng
                            clients.append(client_data)
                            continue
                    except (ValueError, IndexError):
                        pass
                time.sleep(0.25)  # Rate limiting for geocoding (250ms)
                coords = geocode_location(place)
                if coords:
                    entries_geocoded += 1
                    client_data["lat"] = coords["lat"]
                    client_data["lng"] = coords["lng"]
                    clients.append(client_data)
                else:
                    print(f"  ⚠️  Failed to geocode: {name} - {place}")

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
INLINE_MAP_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Client Map</title>
    <link href="https://unpkg.com/maplibre-gl@3.6.1/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/maplibre-gl@3.6.1/dist/maplibre-gl.js"></script>
    <style>
        html, body {{ height: 100%; margin: 0; }}
        #map {{ position: fixed; inset: 0; }}
        .marker {{ 
            width: 14px; 
            height: 14px; 
            border-radius: 50%; 
            border: 3px solid white; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            cursor: pointer;
            transition: transform 0.2s;
        }}
        .marker:hover {{
            transform: scale(1.2);
        }}
        .maplibregl-popup {{
            max-width: 320px !important;
        }}
        .maplibregl-popup-content {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            font-size: 13px; 
            color: #111827; 
            padding: 0;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        .maplibregl-popup-close-button {{
            font-size: 18px;
            padding: 8px 12px;
            color: #6b7280;
            right: 4px;
            top: 4px;
        }}
        .maplibregl-popup-close-button:hover {{
            background: transparent;
            color: #111827;
        }}
        .popup-header {{
            padding: 16px 16px 12px;
            border-bottom: 1px solid #e5e7eb;
            background: #f9fafb;
        }}
        .popup-name {{
            font-size: 15px;
            font-weight: 600;
            color: #111827;
            margin: 0 0 4px 0;
            padding-right: 20px;
        }}
        .popup-label {{
            display: inline-block;
            font-size: 11px;
            font-weight: 500;
            padding: 2px 8px;
            border-radius: 12px;
            color: white;
        }}
        .popup-body {{
            padding: 12px 16px;
        }}
        .popup-row {{
            display: flex;
            align-items: flex-start;
            margin-bottom: 8px;
            gap: 8px;
        }}
        .popup-row:last-child {{
            margin-bottom: 0;
        }}
        .popup-icon {{
            width: 16px;
            height: 16px;
            flex-shrink: 0;
            margin-top: 2px;
            color: #9ca3af;
        }}
        .popup-value {{
            color: #374151;
            word-break: break-word;
        }}
        .popup-value a {{
            color: #2563eb;
            text-decoration: none;
        }}
        .popup-value a:hover {{
            text-decoration: underline;
        }}
        .popup-notes {{
            font-size: 12px;
            color: #6b7280;
            font-style: italic;
            background: #f3f4f6;
            padding: 8px 12px;
            border-radius: 6px;
            margin-top: 8px;
        }}
        .popup-coords {{
            font-size: 11px;
            color: #9ca3af;
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid #e5e7eb;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        const clients = {clients_json};
        
        // SVG icons for popup
        const icons = {{
            phone: '<svg class="popup-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/></svg>',
            email: '<svg class="popup-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
            address: '<svg class="popup-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>',
            contact: '<svg class="popup-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
            org: '<svg class="popup-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9,22 9,12 15,12 15,22"/></svg>'
        }};
        
        function buildPopupHTML(c) {{
            let html = '<div class="popup-header">';
            html += '<div class="popup-name">' + escapeHtml(c.name) + '</div>';
            if (c.label) {{
                html += '<span class="popup-label" style="background-color:' + c.color + '">' + escapeHtml(c.label) + '</span>';
            }}
            html += '</div>';
            
            html += '<div class="popup-body">';
            
            if (c.contact) {{
                html += '<div class="popup-row">' + icons.contact + '<span class="popup-value">' + escapeHtml(c.contact) + '</span></div>';
            }}
            
            if (c.phone) {{
                const phoneClean = c.phone.replace(/[^+\\d]/g, '');
                html += '<div class="popup-row">' + icons.phone + '<span class="popup-value"><a href="tel:' + phoneClean + '">' + escapeHtml(c.phone) + '</a></span></div>';
            }}
            
            if (c.email) {{
                html += '<div class="popup-row">' + icons.email + '<span class="popup-value"><a href="mailto:' + escapeHtml(c.email) + '">' + escapeHtml(c.email) + '</a></span></div>';
            }}
            
            if (c.address) {{
                html += '<div class="popup-row">' + icons.address + '<span class="popup-value">' + escapeHtml(c.address) + '</span></div>';
            }}
            
            if (c.orgTitle) {{
                html += '<div class="popup-row">' + icons.org + '<span class="popup-value">' + escapeHtml(c.orgTitle) + '</span></div>';
            }}
            
            if (c.notes) {{
                html += '<div class="popup-notes">' + escapeHtml(c.notes) + '</div>';
            }}
            
            html += '<div class="popup-coords">📍 ' + c.lat.toFixed(5) + ', ' + c.lng.toFixed(5) + '</div>';
            html += '</div>';
            
            return html;
        }}
        
        function escapeHtml(text) {{
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        const map = new maplibregl.Map({{
            container: 'map',
            style: {{
                version: 8,
                sources: {{
                    osm: {{
                        type: 'raster',
                        tiles: ['https://tile.openstreetmap.org/{{{{z}}}}/{{{{x}}}}/{{{{y}}}}.png'],
                        tileSize: 256,
                        attribution: '© OpenStreetMap contributors'
                    }}
                }},
                layers: [{{ id: 'osm', type: 'raster', source: 'osm' }}]
            }},
            center: [30.5241361, 50.4500336],
            zoom: 5
        }});

        map.on('load', () => {{
            if (clients.length === 0) return;
            const bounds = new maplibregl.LngLatBounds();
            clients.forEach(c => bounds.extend([c.lng, c.lat]));
            map.fitBounds(bounds, {{ padding: 50, maxZoom: 12 }});

            clients.forEach(c => {{
                const el = document.createElement('div');
                el.className = 'marker';
                el.style.backgroundColor = c.color || '#ef4444';
                
                const popup = new maplibregl.Popup({{ offset: 15, maxWidth: '320px' }})
                    .setHTML(buildPopupHTML(c));
                
                new maplibregl.Marker({{ element: el }})
                    .setLngLat([c.lng, c.lat])
                    .setPopup(popup)
                    .addTo(map);
            }});
        }});
    </script>
</body>
</html>'''


def simplify_ukrainian_address(address):
    """Simplify Ukrainian address format for better geocoding.
    Converts abbreviations and removes unnecessary parts.
    """
    import re
    
    # Common Ukrainian abbreviations and their expansions/simplifications
    # Order matters - more specific patterns first
    replacements = [
        # Building/apartment/office - remove these as they confuse geocoder
        (r',?\s*буд\.?\s*№?\s*[\d\-А-Яа-яA-Za-z/]+', ''),  # Building number
        (r',?\s*кв\.?\s*№?\s*\d+', ''),  # Apartment number
        (r',?\s*оф\.?\s*№?\s*\d+', ''),  # Office number
        (r',?\s*б\.\s*\d+', ''),  # Building abbreviation with number
        # Oblast abbreviations
        (r'\s+обл\.?,?\s*', ' область, '),
        # Rayon (district) abbreviations  
        (r'\s+р-н\.?,?\s*', ' район, '),
        (r'\s+район\.?,?\s*', ' район, '),
        # Settlement type abbreviations - keep them for better matching
        (r'\bс\.\s*', 'село '),
        (r'\bсмт\.?\s+', 'смт '),  # Urban-type settlement
        (r'\bм\.\s+', ''),  # City - just remove the abbreviation
        # Street abbreviations
        (r'\bвул\.\s*', 'вулиця '),
        (r'\bпров\.\s*', 'провулок '),
        (r'\bпросп\.\s*', 'проспект '),
        # Clean up
        (r'\s+', ' '),  # Multiple spaces to single
        (r',\s*,', ','),  # Double commas
        (r'^\s*,\s*', ''),  # Leading comma
        (r'\s*,\s*$', ''),  # Trailing comma
    ]
    
    result = address
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    # Add Ukraine to improve geocoding accuracy
    if 'україна' not in result.lower() and 'ukraine' not in result.lower():
        result = result.strip() + ', Україна'
    
    return result.strip()


def geocode_with_google(location):
    """
    Geocode a location using Google Geocoding API.
    Requires GOOGLE_MAPS_API_KEY in environment.
    
    Returns dict with 'lat' and 'lng' or None if not found.
    """
    google_api_key = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not google_api_key:
        return None
    
    import urllib.parse
    
    try:
        # Simplify address for better results
        simplified = simplify_ukrainian_address(location)
        encoded = urllib.parse.quote(simplified)
        
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded}&key={google_api_key}&region=ua&language=uk"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get("status") == "OK" and data.get("results"):
            result = data["results"][0]
            location_data = result.get("geometry", {}).get("location", {})
            
            if "lat" in location_data and "lng" in location_data:
                return {
                    "lat": location_data["lat"],
                    "lng": location_data["lng"]
                }
        
        return None
    except Exception as e:
        print(f"  ⚠️  Google geocoding error: {e}")
        return None


def geocode_location(location):
    """
    Convert location string to coordinates using multiple geocoding services.
    
    Geocoding priority:
    1. Manual mapping (ukraine_settlements.py) - fastest, most reliable for known places
    2. Google Geocoding API (if GOOGLE_MAPS_API_KEY is set) - best Ukrainian coverage
    3. OpenStreetMap Nominatim - free fallback
    """
    import urllib.parse
    import time as time_module
    
    # === 1. Try manual mapping first (fastest, no API calls) ===
    try:
        from ukraine_settlements import lookup_settlement
        manual_coords = lookup_settlement(location)
        if manual_coords:
            print(f"  ✓ Found in manual mapping: {location[:40]}...")
            return manual_coords
    except ImportError:
        pass  # Manual mapping not available
    
    # === 2. Try Google Geocoding API (best Ukrainian coverage) ===
    google_coords = geocode_with_google(location)
    if google_coords:
        print(f"  ✓ Found via Google: {location[:40]}...")
        return google_coords
    
    # === 3. Fall back to OpenStreetMap Nominatim ===
    try:
        simplified = simplify_ukrainian_address(location)
        
        # Try with simplified address
        encoded = urllib.parse.quote(simplified)
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded}&limit=1&countrycodes=ua"
        headers = {"User-Agent": "AgroprideOS-ClientMapWidget/1.0 (agropride.os@gmail.com)"}
        response = requests.get(url, headers=headers, timeout=15)
        data = response.json()

        if data and len(data) > 0:
            print(f"  ✓ Found via OSM: {location[:40]}...")
            return {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
        
        # If simplified address failed, try extracting just the settlement and oblast
        import re
        # Try to extract the main settlement name
        parts = location.split(',')
        if len(parts) >= 2:
            # Try just the settlement + oblast
            oblast_part = None
            settlement_part = None
            
            for part in parts:
                part = part.strip()
                if 'обл' in part.lower():
                    oblast_part = part.replace('обл.', 'область').replace('обл', 'область')
                elif any(x in part.lower() for x in ['село', 'с.', 'смт', 'м.', 'місто']):
                    settlement_part = part
            
            if settlement_part:
                # Clean settlement name
                settlement_clean = re.sub(r'^(с\.|село|смт\.?|м\.|місто)\s*', '', settlement_part, flags=re.IGNORECASE).strip()
                if oblast_part:
                    fallback_query = f"{settlement_clean}, {oblast_part}, Україна"
                else:
                    fallback_query = f"{settlement_clean}, Україна"
                
                time_module.sleep(0.5)  # Rate limiting
                encoded = urllib.parse.quote(fallback_query)
                url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded}&limit=1&countrycodes=ua"
                response = requests.get(url, headers=headers, timeout=15)
                data = response.json()
                
                if data and len(data) > 0:
                    print(f"  ✓ Found via OSM (fallback): {location[:40]}...")
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
    app.run(debug=True, host="0.0.0.0", port=5001)
