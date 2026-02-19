#!/usr/bin/env python3
"""Regenerate the widget HTML file with interactive map"""

import os
import json
from dotenv import load_dotenv
import asyncio
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
    # fetch_clients_from_notion is async, so we need to run it in an event loop
    clients = asyncio.run(fetch_clients_from_notion(api_key, database_id))

    # Filter out clients without valid coordinates
    clients = [c for c in clients if c.get("lat") is not None and c.get("lng") is not None]

    if not clients:
        print("⚠️  Warning: No clients with location data found")

    # Generate interactive map widget
    clients_json = json.dumps(clients, ensure_ascii=False)

    # Create the HTML with GeoJSON clustering
    widget_html = f"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Client Map</title>
    <link href="https://unpkg.com/maplibre-gl@3.6.1/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/maplibre-gl@3.6.1/dist/maplibre-gl.js"></script>
    <style>
        @font-face {{
            font-family: 'Rubik One Local';
            src: url('Rubik.ttf') format('truetype');
            font-style: normal;
            font-display: swap;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Rubik One Local', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-weight: 400;
        }}

        #map {{
            position: fixed;
            inset: 0;
        }}

        .maplibregl-popup {{
            z-index: 10000 !important;
            max-width: 320px !important;
        }}

        #controls {{
            position: absolute;
            top: 14px;
            left: 14px;
            z-index: 10001;
            background: rgba(255, 255, 255, 0.98);
            padding: 10px 12px;
            border-radius: 12px;
            border: 1px solid rgba(15, 23, 42, 0.04);
            box-shadow: 0 10px 30px rgba(2, 6, 23, 0.12);
            display: flex;
            gap: 12px;
            align-items: center;
        }}

        .search-wrapper {{
            position: relative;
            display: flex;
            align-items: center;
            min-width: 260px;
        }}

        .search-icon {{
            position: absolute;
            left: 10px;
            width: 16px;
            height: 16px;
            color: #6b7280;
            pointer-events: none;
        }}

        #search {{
            width: 100%;
            padding: 8px 36px 8px 34px;
            border-radius: 10px;
            border: 1px solid #e6eef8;
            outline: none;
            font-size: 14px;
            box-shadow: inset 0 1px 4px rgba(16, 24, 40, 0.03);
            transition: box-shadow 0.15s, border-color 0.15s;
            background: transparent;
        }}

        #search:focus {{
            box-shadow: 0 6px 18px rgba(37, 99, 235, 0.12);
            border-color: rgba(37, 99, 235, 0.6);
        }}

        #clear-btn {{
            position: absolute;
            right: 8px;
            background: transparent;
            border: none;
            font-size: 16px;
            color: #9ca3af;
            cursor: pointer;
            padding: 4px;
            display: none;
        }}

        #clear-btn:hover {{
            color: #374151;
        }}

        .suggestions {{
            position: absolute;
            top: calc(100% + 8px);
            left: 0;
            right: 0;
            background: white;
            border: 1px solid #e6eef8;
            box-shadow: 0 6px 20px rgba(2, 6, 23, 0.12);
            border-radius: 10px;
            max-height: 220px;
            overflow: auto;
            z-index: 10002;
            display: none;
        }}

        .suggestion-item {{
            padding: 10px 12px;
            font-size: 14px;
            color: #111827;
            cursor: pointer;
        }}

        .suggestion-item:hover {{
            background: #f8fafc;
        }}

        .maplibregl-popup-content {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 13px;
            color: #111827;
            padding: 0;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
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
    <div id="controls">
        <div class="search-wrapper">
            <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="7" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input id="search" type="search" placeholder="Пошук..." autocomplete="off" />
            <button id="clear-btn" aria-label="Clear search">×</button>
            <div id="suggestions" class="suggestions" role="listbox"></div>
        </div>
    </div>
    <div id="map"></div>
    <script>
        const clients = {clients_json};

        function clientsToGeoJSON(list) {{
            return {{
                type: 'FeatureCollection',
                features: list
                    .filter(function(c) {{ return c.lat != null && c.lng != null; }})
                    .map(function(c, i) {{
                        return {{
                            type: 'Feature',
                            geometry: {{
                                type: 'Point',
                                coordinates: [c.lng, c.lat]
                            }},
                            properties: {{
                                _index: i,
                                name: c.name || '',
                                color: c.color || '#ef4444',
                                phone: c.phone || '',
                                email: c.email || '',
                                contact: c.contact || '',
                                address: c.address || '',
                                notes: c.notes || '',
                                label: c.label || '',
                                orgTitle: c.orgTitle || ''
                            }}
                        }};
                    }})
            }};
        }}

        function buildPopupHTML(clientsAtLocation) {{
            var html = '<div style="max-height:300px; overflow-y:auto;">';

            clientsAtLocation.forEach(function(c, index) {{
                html += '<div' + (index > 0 ? ' style="border-top: 1px solid #efefef; padding-top: 12px; margin-top: 12px;"' : '') + '>';

                html += '<div class="popup-header">';
                var headerText = clientsAtLocation.length > 1 ? '(' + (index + 1) + ') ' + escapeHtml(c.name) : escapeHtml(c.name);
                html += '<div class="popup-name" style="font-weight:600; font-size:14px; margin-bottom:4px;">' + headerText + '</div>';

                if (c.label) {{
                    html += '<div class="popup-label" style="background-color:' + (c.color || '#ef4444') + '; font-size:10px; padding:2px 6px; border-radius:4px; color:white; display:inline-block; margin-bottom:8px;">' + escapeHtml(c.label) + '</div>';
                }}
                html += '</div>';

                html += '<div class="popup-body" style="font-size:13px; color:#374151;">';

                if (c.address) {{
                    html += '<div class="popup-row" style="display:flex; align-items:start; gap:6px; margin-bottom:4px;">' +
                        '<span style="font-weight:500;">&#128205;</span> ' +
                        '<span class="popup-value">' + escapeHtml(c.address) + '</span></div>';
                }}

                if (c.notes) {{
                    html += '<div class="popup-notes" style="background:#f3f4f6; padding:6px; border-radius:4px; margin-top:6px; font-style:italic; font-size:12px;">' + escapeHtml(c.notes) + '</div>';
                }}

                html += '</div>';
                html += '</div>';
            }});

            html += '</div>';
            return html;
        }}

        function escapeHtml(text) {{
            if (!text) return '';
            var div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        var fullGeoJSON = clientsToGeoJSON(clients);

        var map = new maplibregl.Map({{
            container: 'map',
            style: {{
                version: 8,
                glyphs: 'https://fonts.openmaptiles.org/{{fontstack}}/{{range}}.pbf',
                sources: {{
                    osm: {{
                        type: 'raster',
                        tiles: ['https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png'],
                        tileSize: 256,
                        attribution: '&copy; OpenStreetMap contributors'
                    }}
                }},
                layers: [{{ id: 'osm', type: 'raster', source: 'osm' }}]
            }},
            center: [30.5241361, 50.4500336],
            zoom: 5
        }});

        map.on('load', function() {{
            if (clients.length === 0) return;

            // Add clustered GeoJSON source
            map.addSource('clients', {{
                type: 'geojson',
                data: fullGeoJSON,
                cluster: true,
                clusterMaxZoom: 24,
                clusterRadius: 50
            }});

            // Cluster circles — sized and colored by point count
            map.addLayer({{
                id: 'clusters',
                type: 'circle',
                source: 'clients',
                filter: ['has', 'point_count'],
                paint: {{
                    'circle-color': [
                        'step',
                        ['get', 'point_count'],
                        '#f87171',
                        10, '#ef4444',
                        30, '#dc2626',
                        100, '#b91c1c'
                    ],
                    'circle-radius': [
                        'step',
                        ['get', 'point_count'],
                        18,
                        10, 24,
                        30, 30,
                        100, 36
                    ],
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff'
                }}
            }});

            // Cluster count labels
            map.addLayer({{
                id: 'cluster-count',
                type: 'symbol',
                source: 'clients',
                filter: ['has', 'point_count'],
                layout: {{
                    'text-field': ['get', 'point_count_abbreviated'],
                    'text-font': ['Open Sans Bold'],
                    'text-size': 13,
                    'text-allow-overlap': true
                }},
                paint: {{
                    'text-color': '#ffffff'
                }}
            }});

            // Individual (unclustered) points
            map.addLayer({{
                id: 'unclustered-point',
                type: 'circle',
                source: 'clients',
                filter: ['!', ['has', 'point_count']],
                paint: {{
                    'circle-color': '#ef4444',
                    'circle-radius': 8,
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff'
                }}
            }});

            // Click on cluster: zoom in or show popup at max zoom
            map.on('click', 'clusters', function(e) {{
                var features = map.queryRenderedFeatures(e.point, {{ layers: ['clusters'] }});
                if (!features.length) return;

                var clusterId = features[0].properties.cluster_id;
                var pointCount = features[0].properties.point_count;
                var clusterCoords = features[0].geometry.coordinates;
                var source = map.getSource('clients');

                source.getClusterExpansionZoom(clusterId, function(err, expansionZoom) {{
                    if (err) return;

                    if (expansionZoom > 20 || expansionZoom <= map.getZoom()) {{
                        // At max zoom — show all leaves in a popup
                        source.getClusterLeaves(clusterId, Math.min(pointCount, 50), 0, function(err2, leaves) {{
                            if (err2 || !leaves) return;

                            var popupClients = leaves.map(function(leaf) {{
                                return {{
                                    name: leaf.properties.name,
                                    color: leaf.properties.color,
                                    phone: leaf.properties.phone,
                                    email: leaf.properties.email,
                                    contact: leaf.properties.contact,
                                    address: leaf.properties.address,
                                    notes: leaf.properties.notes,
                                    label: leaf.properties.label,
                                    orgTitle: leaf.properties.orgTitle
                                }};
                            }});

                            new maplibregl.Popup({{ maxWidth: '360px' }})
                                .setLngLat(clusterCoords)
                                .setHTML(buildPopupHTML(popupClients))
                                .addTo(map);
                        }});
                    }} else {{
                        map.easeTo({{
                            center: clusterCoords,
                            zoom: expansionZoom
                        }});
                    }}
                }});
            }});

            // Click on individual point: show popup
            map.on('click', 'unclustered-point', function(e) {{
                var feature = e.features[0];
                var coords = feature.geometry.coordinates.slice();
                var props = feature.properties;

                // Find all clients at the exact same coordinate (co-located)
                var colocated = clients.filter(function(c) {{
                    return c.lat != null && c.lng != null &&
                        c.lat.toFixed(6) === coords[1].toFixed(6) &&
                        c.lng.toFixed(6) === coords[0].toFixed(6);
                }});

                var popupClients = colocated.length > 0 ? colocated : [{{
                    name: props.name,
                    color: props.color,
                    phone: props.phone,
                    email: props.email,
                    contact: props.contact,
                    address: props.address,
                    notes: props.notes,
                    label: props.label,
                    orgTitle: props.orgTitle
                }}];

                // Handle antimeridian wrapping
                while (Math.abs(e.lngLat.lng - coords[0]) > 180) {{
                    coords[0] += e.lngLat.lng > coords[0] ? 360 : -360;
                }}

                new maplibregl.Popup({{ maxWidth: '320px' }})
                    .setLngLat(coords)
                    .setHTML(buildPopupHTML(popupClients))
                    .addTo(map);
            }});

            // Cursor styling
            map.on('mouseenter', 'clusters', function() {{
                map.getCanvas().style.cursor = 'pointer';
            }});
            map.on('mouseleave', 'clusters', function() {{
                map.getCanvas().style.cursor = '';
            }});
            map.on('mouseenter', 'unclustered-point', function() {{
                map.getCanvas().style.cursor = 'pointer';
            }});
            map.on('mouseleave', 'unclustered-point', function() {{
                map.getCanvas().style.cursor = '';
            }});

            // Fit bounds to show all markers
            var bounds = new maplibregl.LngLatBounds();
            clients.forEach(function(c) {{
                if (c.lat != null && c.lng != null) {{
                    bounds.extend([c.lng, c.lat]);
                }}
            }});
            if (!bounds.isEmpty()) {{
                map.fitBounds(bounds, {{ padding: 50, maxZoom: 12 }});
            }}

            // Search functionality
            var searchInput = document.getElementById('search');
            var searchInputWrapper = document.querySelector('.search-wrapper');
            var suggestionsBox = document.getElementById('suggestions');
            var clearBtn = document.getElementById('clear-btn');
            var debounceTimer = null;

            function filterMapByQuery(q) {{
                var ql = (q || '').trim().toLowerCase();

                if (!ql) {{
                    map.getSource('clients').setData(fullGeoJSON);
                    return;
                }}

                var matching = clients.filter(function(c) {{
                    var text = [c.name, c.address, c.contact, c.phone, c.email]
                        .filter(Boolean)
                        .join(' ')
                        .toLowerCase();
                    return text.indexOf(ql) !== -1;
                }});

                map.getSource('clients').setData(clientsToGeoJSON(matching));
            }}

            function showSuggestions(q) {{
                var ql = (q || '').trim().toLowerCase();
                suggestionsBox.innerHTML = '';

                if (!ql) {{
                    suggestionsBox.style.display = 'none';
                    return;
                }}

                var matches = clients.filter(function(c) {{
                    var text = [c.name, c.address, c.contact, c.phone]
                        .filter(Boolean)
                        .join(' ')
                        .toLowerCase();
                    return text.indexOf(ql) !== -1;
                }}).slice(0, 10);

                if (matches.length === 0) {{
                    suggestionsBox.style.display = 'none';
                    return;
                }}

                matches.forEach(function(client) {{
                    var div = document.createElement('div');
                    div.className = 'suggestion-item';
                    div.textContent = client.name + (client.address ? ' (' + client.address + ')' : '');

                    div.addEventListener('click', function() {{
                        // Reset filter to show all
                        map.getSource('clients').setData(fullGeoJSON);

                        // Fly to client
                        map.flyTo({{
                            center: [client.lng, client.lat],
                            zoom: Math.max(map.getZoom(), 14),
                            essential: true
                        }});

                        // Show popup after map finishes moving
                        map.once('moveend', function() {{
                            var colocated = clients.filter(function(c) {{
                                return c.lat != null && c.lng != null &&
                                    c.lat.toFixed(6) === client.lat.toFixed(6) &&
                                    c.lng.toFixed(6) === client.lng.toFixed(6);
                            }});

                            new maplibregl.Popup({{ maxWidth: '320px' }})
                                .setLngLat([client.lng, client.lat])
                                .setHTML(buildPopupHTML(colocated.length > 0 ? colocated : [client]))
                                .addTo(map);
                        }});

                        searchInput.value = client.name;
                        suggestionsBox.style.display = 'none';
                        clearBtn.style.display = 'block';
                    }});

                    suggestionsBox.appendChild(div);
                }});

                suggestionsBox.style.display = 'block';
            }}

            searchInput.addEventListener('input', function(e) {{
                var val = e.target.value;
                clearBtn.style.display = val ? 'block' : 'none';
                showSuggestions(val);

                // Debounce map filtering
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(function() {{
                    filterMapByQuery(val);
                }}, 200);
            }});

            clearBtn.addEventListener('click', function() {{
                searchInput.value = '';
                filterMapByQuery('');
                suggestionsBox.style.display = 'none';
                clearBtn.style.display = 'none';
            }});

            document.addEventListener('click', function(e) {{
                if (!searchInputWrapper.contains(e.target)) {{
                    suggestionsBox.style.display = 'none';
                }}
            }});

        }});

    </script>
</body>

</html>"""

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
