"""
HTML templates for the Widget Generator Tool.

This module contains all HTML template strings used to generate
the client map widget and related pages.
"""

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

            <div class="form-group">
            </div>
            
            <button type="submit" id="generateBtn">
                Generate Widget
            </button>
        </form>

        <hr style="margin:30px 0; border:none; border-top:1px solid #e5e7eb;" />

        <!-- CSV upload and stored clients removed -->

        <div class="error" id="error"></div>

        <div class="result" id="result">
            <h2>✅ Widget Generated Successfully!</h2>
            <p style="margin-bottom: 15px; color: #666; font-size: 14px;">
                Copy the code below and paste it into your website:
            </p>
            <textarea id="widgetCode" readonly></textarea>
            <button class="copy-btn" onclick="copyWidget()">Copy to Clipboard</button>
            <button class="copy-btn" style="background: #3b82f6; margin-left: 10px;" onclick="openWidgetInTab()">Open in New Tab</button>
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
                
                // Store widget info for later use
                window.currentWidgetId = data.widget_id;
                window.currentPreviewUrl = data.preview_url;
                
                console.log('✓ Widget generated:', data);
                console.log('  Fetching HTML from /api/widget/' + data.widget_id);
                
                // Fetch the actual HTML for display/copying
                const widgetResponse = await fetch(`/api/widget/${data.widget_id}`);
                
                if (!widgetResponse.ok) {
                    const widgetError = await widgetResponse.json();
                    throw new Error(widgetError.error || `Failed to retrieve widget HTML (${widgetResponse.status})`);
                }
                
                const widgetData = await widgetResponse.json();
                
                if (!widgetData.html) {
                    throw new Error('Widget HTML is empty or undefined');
                }
                
                document.getElementById('widgetCode').value = widgetData.html;
                result.classList.add('show');
                
                // Update status message with widget info
                const existingStatus = result.querySelector('.status-info');
                if (existingStatus) existingStatus.remove();
                
                const statusMsg = document.createElement('div');
                statusMsg.className = 'status-info';
                statusMsg.style.cssText = 'margin-bottom: 15px; padding: 10px; background: #eff6ff; border-radius: 4px; font-size: 13px; color: #1e40af;';
                statusMsg.innerHTML = `
                    ✓ Generated widget for ${data.clients} clients (${data.size_mb} MB)<br>
                    Widget ID: <code style="background: white; padding: 2px 6px; border-radius: 3px;">${data.widget_id}</code><br>
                    HTML Size: ${widgetData.size_mb} MB
                `;
                result.insertBefore(statusMsg, result.firstChild);
                
            } catch (err) {
                console.error('Error:', err);
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
        
        // CSV/stored-client UI removed; no stored-count refresh needed.
        function openWidgetInTab() {
            // Use the stored preview URL to open widget directly (no POST needed!)
            if (window.currentPreviewUrl) {
                window.open(window.currentPreviewUrl, '_blank');
            } else {
                alert('Please generate a widget first');
            }
        }
    </script>
</body>
</html>
"""


INLINE_MAP_TEMPLATE = """<!DOCTYPE html>
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
        .maplibregl-popup {{
            z-index: 10000 !important;
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
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        var clients = {clients_json};

        function clientsToGeoJSON(list) {{
            return {{
                type: 'FeatureCollection',
                features: list
                    .filter(function(c) {{ return c.lat != null && c.lng != null; }})
                    .map(function(c, i) {{
                        return {{
                            type: 'Feature',
                            geometry: {{ type: 'Point', coordinates: [c.lng, c.lat] }},
                            properties: {{
                                name: c.name || '', color: c.color || '#ef4444',
                                phone: c.phone || '', email: c.email || '',
                                contact: c.contact || '', address: c.address || '',
                                notes: c.notes || '', label: c.label || '',
                                orgTitle: c.orgTitle || ''
                            }}
                        }};
                    }})
            }};
        }}

        function buildPopupHTML(clientsAtLocation) {{
            var html = '<div style="max-height:300px; overflow-y:auto;">';
            clientsAtLocation.forEach(function(c, index) {{
                html += '<div' + (index > 0 ? ' style="border-top:1px solid #efefef;padding-top:12px;margin-top:12px;"' : '') + '>';
                html += '<div class="popup-header">';
                var headerText = clientsAtLocation.length > 1 ? '(' + (index+1) + ') ' + escapeHtml(c.name) : escapeHtml(c.name);
                html += '<div class="popup-name">' + headerText + '</div>';
                if (c.label) {{
                    html += '<span class="popup-label" style="background-color:' + (c.color || '#ef4444') + '">' + escapeHtml(c.label) + '</span>';
                }}
                html += '</div><div class="popup-body">';
                if (c.address) {{ html += '<div class="popup-row">&#128205; <span class="popup-value">' + escapeHtml(c.address) + '</span></div>'; }}
                if (c.notes) {{ html += '<div class="popup-notes">' + escapeHtml(c.notes) + '</div>'; }}
                html += '</div></div>';
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
                        tiles: ['https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{{z}}/{{x}}/{{y}}.png'],
                        tileSize: 256,
                        attribution: '&copy; OpenStreetMap contributors, &copy; CartoDB'
                    }}
                }},
                layers: [{{ id: 'osm', type: 'raster', source: 'osm' }}]
            }},
            center: [30.5241361, 50.4500336],
            zoom: 5
        }});

        map.on('load', function() {{
            if (clients.length === 0) return;

            map.addSource('clients', {{
                type: 'geojson',
                data: fullGeoJSON,
                cluster: true,
                clusterMaxZoom: 24,
                clusterRadius: 50
            }});

            map.addLayer({{
                id: 'clusters', type: 'circle', source: 'clients',
                filter: ['has', 'point_count'],
                paint: {{
                    'circle-color': ['step', ['get', 'point_count'], '#f87171', 10, '#ef4444', 30, '#dc2626', 100, '#b91c1c'],
                    'circle-radius': ['step', ['get', 'point_count'], 18, 10, 24, 30, 30, 100, 36],
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff'
                }}
            }});

            map.addLayer({{
                id: 'cluster-count', type: 'symbol', source: 'clients',
                filter: ['has', 'point_count'],
                layout: {{
                    'text-field': ['get', 'point_count_abbreviated'],
                    'text-font': ['Open Sans Bold'],
                    'text-size': 13,
                    'text-allow-overlap': true
                }},
                paint: {{ 'text-color': '#ffffff' }}
            }});

            map.addLayer({{
                id: 'unclustered-point', type: 'circle', source: 'clients',
                filter: ['!', ['has', 'point_count']],
                paint: {{
                    'circle-color': '#ef4444',
                    'circle-radius': 8,
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff'
                }}
            }});

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
                        source.getClusterLeaves(clusterId, Math.min(pointCount, 50), 0, function(err2, leaves) {{
                            if (err2 || !leaves) return;
                            var popupClients = leaves.map(function(leaf) {{ return leaf.properties; }});
                            new maplibregl.Popup({{ maxWidth: '360px' }})
                                .setLngLat(clusterCoords)
                                .setHTML(buildPopupHTML(popupClients))
                                .addTo(map);
                        }});
                    }} else {{
                        map.easeTo({{ center: clusterCoords, zoom: expansionZoom }});
                    }}
                }});
            }});

            map.on('click', 'unclustered-point', function(e) {{
                var feature = e.features[0];
                var coords = feature.geometry.coordinates.slice();
                var colocated = clients.filter(function(c) {{
                    return c.lat != null && c.lng != null &&
                        c.lat.toFixed(6) === coords[1].toFixed(6) &&
                        c.lng.toFixed(6) === coords[0].toFixed(6);
                }});
                var popupClients = colocated.length > 0 ? colocated : [feature.properties];
                new maplibregl.Popup({{ maxWidth: '320px' }})
                    .setLngLat(coords)
                    .setHTML(buildPopupHTML(popupClients))
                    .addTo(map);
            }});

            map.on('mouseenter', 'clusters', function() {{ map.getCanvas().style.cursor = 'pointer'; }});
            map.on('mouseleave', 'clusters', function() {{ map.getCanvas().style.cursor = ''; }});
            map.on('mouseenter', 'unclustered-point', function() {{ map.getCanvas().style.cursor = 'pointer'; }});
            map.on('mouseleave', 'unclustered-point', function() {{ map.getCanvas().style.cursor = ''; }});

            var bounds = new maplibregl.LngLatBounds();
            clients.forEach(function(c) {{
                if (c.lat != null && c.lng != null) bounds.extend([c.lng, c.lat]);
            }});
            if (!bounds.isEmpty()) map.fitBounds(bounds, {{ padding: 50, maxZoom: 12 }});
        }});
    </script>
</body>
</html>"""


NOTION_EMBED_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
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
    <div class="card">
        <div class="title">Client Map in Notion</div>
        <div class="desc">Open the map view in Notion. This avoids iframe restrictions and ensures it loads reliably.</div>
        <a class="btn" href="{embed_url}" target="_blank" rel="noopener noreferrer">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M14 3H21V10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M10 14L21 3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M21 14V21H3V3H10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Open Notion Map
        </a>
    </div>
</body>
</html>"""


NOTION_MAP_WIDGET_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
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
    <div id="notion-map-container">
        {map_content}
    </div>
</body>
</html>"""
