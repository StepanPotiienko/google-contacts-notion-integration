#!/usr/bin/env python3
"""Generate widget with Google Maps (similar to Notion's map view)"""

import os
import json
from dotenv import load_dotenv
from main import fetch_clients_from_notion

load_dotenv()

# Google Maps template (looks more like Notion)
GOOGLE_MAP_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Client Map</title>
    <style>
        html, body { height: 100%; margin: 0; padding: 0; }
        #map { width: 100%; height: 100vh; }
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        const clients = {clients_json};
        
        function initMap() {
            const map = new google.maps.Map(document.getElementById('map'), {
                zoom: 6,
                center: { lat: 50.4501, lng: 30.5234 }
            });

            if (clients.length > 0) {
                const bounds = new google.maps.LatLngBounds();
                
                clients.forEach(client => {
                    const marker = new google.maps.Marker({
                        position: { lat: client.lat, lng: client.lng },
                        map: map,
                        title: client.name
                    });
                    
                    const infoWindow = new google.maps.InfoWindow({
                        content: `<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 8px;"><strong>${client.name}</strong></div>`
                    });
                    
                    marker.addListener('click', () => {
                        infoWindow.open(map, marker);
                    });
                    
                    bounds.extend(marker.position);
                });
                
                map.fitBounds(bounds);
            }
        }
    </script>
    <script async defer
        src="https://maps.googleapis.com/maps/api/js?key=YOUR_GOOGLE_MAPS_API_KEY&callback=initMap">
    </script>
</body>
</html>"""

# Alternative: Link to Notion map
NOTION_LINK_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Client Map</title>
    <style>
        html, body {
            height: 100%;
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
        }
        .container {
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.1);
            max-width: 500px;
        }
        h1 { margin: 0 0 16px 0; font-size: 24px; color: #111; }
        p { color: #666; margin: 0 0 24px 0; line-height: 1.5; }
        .btn {
            display: inline-block;
            padding: 12px 24px;
            background: #2563eb;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            transition: background 0.2s;
        }
        .btn:hover { background: #1d4ed8; }
        .note {
            margin-top: 20px;
            padding: 16px;
            background: #fef3c7;
            border-radius: 8px;
            font-size: 14px;
            color: #92400e;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📍 View Client Map</h1>
        <p>Click below to open the interactive map in Notion with all {client_count} client locations.</p>
        <a href="{notion_url}" target="_blank" class="btn">Open Notion Map</a>
        <div class="note">
            <strong>Note:</strong> Notion maps cannot be embedded in iframes due to security restrictions. 
            The map will open in a new tab.
        </div>
    </div>
</body>
</html>"""


def main():
    notion_url = os.getenv("NOTION_MAP_EMBED_URL")

    if not notion_url:
        print("❌ NOTION_MAP_EMBED_URL not set in .env")
        return

    # Option 1: Just create a link to Notion map
    print("📍 Generating widget that links to Notion map...")

    widget_html = NOTION_LINK_TEMPLATE.replace("{notion_url}", notion_url).replace(
        "{client_count}", "all"
    )

    output_path = os.path.join(os.path.dirname(__file__), "public", "widget.html")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(widget_html)

    print(f"✅ Widget generated!")
    print(f"   Output: {output_path}")
    print(f"\n🌐 This widget links directly to your Notion map")
    print(f"   Notion URL: {notion_url}")
    print(f"\n   open '{output_path}'")


if __name__ == "__main__":
    main()
