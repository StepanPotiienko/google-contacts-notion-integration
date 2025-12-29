#!/usr/bin/env python3
"""Regenerate the widget HTML file with interactive map"""

import os
import json
from dotenv import load_dotenv
from main import fetch_clients_from_notion

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
    
    # Create the HTML with enhanced popup showing all client data
    widget_html = f'''<!DOCTYPE html>
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
            contact: '<svg class="popup-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
        }};
        
        function buildPopupHTML(c) {{
            let html = '<div class="popup-header">';
            html += '<div class="popup-name">' + escapeHtml(c.name) + '</div>';
            html += '</div>';
            
            html += '<div class="popup-body">';
            
            if (c.address) {{
                html += '<div class="popup-row">' + icons.address + '<span class="popup-value">' + escapeHtml(c.address) + '</span></div>';
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
                        tiles: ['https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png'],
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
