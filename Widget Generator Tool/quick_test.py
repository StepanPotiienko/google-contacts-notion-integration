#!/usr/bin/env python3
"""Quick test - Generate widget from CSV data"""

import os
import json

# Simple map template
INLINE_MAP_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Client Map</title>
    <link href="https://unpkg.com/maplibre-gl@3.6.1/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/maplibre-gl@3.6.1/dist/maplibre-gl.js"></script>
    <style>
        html, body { height: 100%; margin: 0; }
        #map { position: fixed; inset: 0; }
        .marker { width: 12px; height: 12px; background: #ef4444; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 0 1px rgba(0,0,0,0.2); }
        .maplibregl-popup-content { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; color: #111827; padding: 12px; border-radius: 8px; }
    </style>
</head>
<body>
    <div id="map"></div>
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
                        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    }
                },
                layers: [{ id: 'osm', type: 'raster', source: 'osm' }]
            },
            center: [30.5241361, 50.4500336],
            zoom: 6
        });

        map.on('load', () => {
            if (clients.length === 0) {
                console.log('No clients to display');
                return;
            }
            
            // Fit map to show all markers
            const bounds = new maplibregl.LngLatBounds();
            clients.forEach(c => bounds.extend([c.lng, c.lat]));
            map.fitBounds(bounds, { padding: 50, maxZoom: 12 });

            // Add markers
            clients.forEach(c => {
                const el = document.createElement('div');
                el.className = 'marker';
                const popup = new maplibregl.Popup({ offset: 15 })
                    .setHTML(`<strong>${c.name}</strong>`);
                new maplibregl.Marker(el)
                    .setLngLat([c.lng, c.lat])
                    .setPopup(popup)
                    .addTo(map);
            });
            
            console.log(`Displayed ${clients.length} clients on map`);
        });
    </script>
</body>
</html>"""


def main():
    # For testing, create sample data
    clients = [
        {"name": "Kyiv Office", "lat": 50.4501, "lng": 30.5234},
        {"name": "Lviv Branch", "lat": 49.8397, "lng": 24.0297},
        {"name": "Odesa Center", "lat": 46.4825, "lng": 30.7233},
    ]

    print(f"📍 Generating test widget with {len(clients)} sample locations...")

    # Generate widget - use replace to avoid conflicts with CSS/JS braces
    clients_json = json.dumps(clients, ensure_ascii=False)
    widget_html = INLINE_MAP_TEMPLATE.replace("{clients_json}", clients_json)

    # Write to file
    output_path = os.path.join(os.path.dirname(__file__), "public", "widget.html")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(widget_html)

    print("✅ Widget generated!")
    print(f"   File: {output_path}")
    print("\n🌐 Open it now:")
    print(f"   open '{output_path}'")


if __name__ == "__main__":
    main()
