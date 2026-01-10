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
                <label for="includeStored"><input type="checkbox" id="includeStored" checked> Include stored CSV clients</label>
            </div>
            
            <button type="submit" id="generateBtn">
                Generate Widget
            </button>
        </form>

        <hr style="margin:30px 0; border:none; border-top:1px solid #e5e7eb;" />

        <form id="uploadForm" enctype="multipart/form-data">
            <div class="form-group">
                <label for="csvFile">Upload CSV file (clients)</label>
                <input type="file" id="csvFile" accept=".csv,text/csv" />
            </div>
            <button type="submit" id="uploadBtn">Upload CSV and Add to Map</button>
        </form>

        <div style="margin-top:12px; font-size:13px; color:#374151;">Currently stored clients: <span id="storedCount">—</span></div>

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
            const includeStored = document.getElementById('includeStored').checked;
            
            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ apiKey, databaseId, includeStored })
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
        
        async function refreshStoredCount() {
            try {
                const r = await fetch('/api/clients');
                const d = await r.json();
                if (r.ok) {
                    document.getElementById('storedCount').textContent = d.count;
                }
            } catch (err) {
                // ignore
            }
        }

        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('uploadBtn');
            const error = document.getElementById('error');
            const result = document.getElementById('result');

            const fileInput = document.getElementById('csvFile');
            if (!fileInput.files || fileInput.files.length === 0) {
                error.textContent = 'Please choose a CSV file to upload.';
                error.classList.add('show');
                return;
            }

            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span>Uploading...';
            error.classList.remove('show');
            result.classList.remove('show');

            try {
                const form = new FormData();
                form.append('file', fileInput.files[0]);

                const response = await fetch('/api/upload-csv', {
                    method: 'POST',
                    body: form,
                });

                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || 'Failed to upload CSV');
                }

                document.getElementById('widgetCode').value = data.widget;
                result.classList.add('show');
                refreshStoredCount();
            } catch (err) {
                error.textContent = err.message;
                error.classList.add('show');
            } finally {
                btn.disabled = false;
                btn.innerHTML = 'Upload CSV and Add to Map';
            }
        });

        // Initial load
        refreshStoredCount();
        function openWidgetInTab() {
            const widgetCode = document.getElementById('widgetCode').value;
            // Create a temporary form to POST the widget HTML to /view-widget in a new tab/window.
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/view-widget';
            form.target = '_blank';
            form.style.display = 'none';

            const input = document.createElement('textarea');
            input.name = 'html';
            input.value = widgetCode;
            form.appendChild(input);

            document.body.appendChild(form);
            form.submit();
            // Clean up the form element after a short delay to ensure submission
            setTimeout(() => document.body.removeChild(form), 1000);
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
                        tiles: ['https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{{z}}/{{x}}/{{y}}.png'],
                        tileSize: 256,
                        attribution: '© OpenStreetMap contributors, © CartoDB'
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
