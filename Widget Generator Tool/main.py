"""
Widget Generator Tool - Flask Application

This Flask application generates embeddable map widgets from Notion databases.
"""

import hashlib
import json
import os
import re
import time
import asyncio
import requests
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template_string,
    request,
    url_for,
)

# Import templates and utilities
from templates import GENERATOR_HTML, INLINE_MAP_TEMPLATE
from utils import merge_clients
from notion_utils import fetch_clients_from_notion

# Initialize Flask app
STATIC_DIR = os.path.join(os.path.dirname(__file__), "public")
app = Flask(__name__, static_folder=STATIC_DIR)

# Increase max content length to handle large widget HTML payloads (100MB)
# Default is 16MB, but with 700+ geocoded clients, widgets can be larger
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle requests that exceed MAX_CONTENT_LENGTH."""
    return (
        jsonify(
            {
                "error": "Request too large",
                "message": f"Maximum request size is {app.config['MAX_CONTENT_LENGTH'] // (1024*1024)}MB",
                "suggestion": "Try reducing the number of clients or contact support",
            }
        ),
        413,
    )


@app.route("/")
def index():
    """Serve the main widget generator interface."""
    return render_template_string(GENERATOR_HTML)


@app.route("/api/generate-widget", methods=["POST"])
def generate_widget():
    """API endpoint to generate a widget from Notion data.

    Now stores the widget on the server and returns just the widget ID and preview URL.
    This avoids the client having to POST large HTML payloads back to the server.
    """
    data = request.get_json()
    # Support both camelCase and snake_case
    api_key = data.get("api_key") or data.get("apiKey")
    database_id = data.get("database_id") or data.get("databaseId")
    
    # Fallback to env vars if not provided in request
    if not api_key:
        api_key = os.environ.get("NOTION_API_KEY")
    if not database_id:
        database_id = os.environ.get("NOTION_DATABASE_ID")

    # CSV/stored clients removed — only Notion clients are used now.

    if not api_key or not database_id:
        return jsonify({"error": "Missing API key or database ID (check .env or request body)"}), 400

    notion_clients = []

    try:
        # Allow caller to opt-out of geocoding to speed up responses (default: False)
        geocode_flag = data.get("geocode")
        if geocode_flag is None:
            # support camelCase
            geocode_flag = (
                data.get("geocode")
                or data.get("doGeocode")
                or data.get("geocodeEnabled")
            )
        geocode_flag = bool(geocode_flag)

        if api_key and database_id:
            # fetch_clients_from_notion is async, run in event loop
            notion_clients = asyncio.run(
                fetch_clients_from_notion(api_key, database_id)
            )

        # Use Notion clients only; dedupe within the set if necessary.
        clients = merge_clients([], notion_clients, dedupe=True)

        pre_filter_count = len(clients)
        # Filter out clients without valid coordinates to prevent map rendering errors
        clients = [
            c for c in clients if c.get("lat") is not None and c.get("lng") is not None
        ]
        post_filter_count = len(clients)

        if pre_filter_count != post_filter_count:
            print(
                f"⚠️  Final Filter: Dropped {pre_filter_count - post_filter_count} clients due to missing coordinates"
            )
            print(
                f"   (These clients had addresses but geocoding failed or returned no results)"
            )

        # Prevent basic script injection by escaping tags
        clients_json = (
            json.dumps(clients).replace("<", "\\u003c").replace(">", "\\u003e")
        )

        # Prefer using the `public/widget.html` file as the authoritative template.
        # Read the file and replace the `const clients = [...]` declaration with actual data.
        template_path = os.path.join(os.path.dirname(__file__), "public", "widget.html")
        try:
            with open(template_path, "r", encoding="utf-8") as fh:
                tpl = fh.read()

            # Replace any existing clients declaration with our JSON array.
            # This looks for: const clients = [ ... ]; (multiline)
            tpl = re.sub(
                r"const\s+clients\s*=\s*\[.*?\];",
                lambda _m: f"const clients = {clients_json};",
                tpl,
                flags=re.S,
            )

            widget_html = tpl
        except FileNotFoundError:
            # Fall back to the inline template if the file isn't available
            widget_html = INLINE_MAP_TEMPLATE.format(clients_json=clients_json)

        # Store widget immediately on the server to avoid large payloads
        html_size_mb = len(widget_html.encode("utf-8")) / (1024 * 1024)
        print(
            f"[INFO] Generated widget HTML: {html_size_mb:.2f} MB for {len(clients)} clients"
        )

        wid = _store_widget(widget_html)
        preview_url = url_for("view_widget_id", wid=wid, _external=True)

        return jsonify(
            {
                "widget_id": wid,
                "preview_url": preview_url,
                "clients": len(clients),
                "size_mb": round(html_size_mb, 2),
            }
        )
    except (
        requests.RequestException,
        KeyError,
        ValueError,
        AttributeError,
        TypeError,
    ) as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/upload-csv", methods=["POST"])
def upload_csv():
    """CSV upload endpoint removed."""
    return jsonify({"error": "CSV upload is no longer supported"}), 410


@app.route("/api/clients", methods=["GET"])
def get_clients():
    """Stored CSV clients removed."""
    return jsonify({"error": "Stored CSV clients removed"}), 410


@app.route("/api/clear-clients", methods=["POST"])
def clear_clients():
    """Stored CSV clients removed."""
    return jsonify({"error": "Stored CSV clients removed"}), 410


@app.route("/generate", methods=["POST"])
def generate():
    """Alias for /api/generate-widget endpoint."""
    return generate_widget()


@app.route("/view-widget", methods=["GET", "POST"])
def view_widget():
    """Serve the generated widget. Accepts `html` via GET query or POST form.

    Using POST avoids extremely long URLs when the widget HTML is large.
    """
    # Deprecated: passing full HTML via GET query string is fragile (URI Too Long).
    # New flow: POST widget HTML to this endpoint; server stores it temporarily
    # and redirects to a short GET URL `/view-widget/<id>` which serves the HTML.
    if request.method == "POST":
        widget_html = request.form.get("html")
        if not widget_html:
            return "No widget data provided", 400

        # Log the size of the widget HTML for monitoring
        html_size_mb = len(widget_html.encode("utf-8")) / (1024 * 1024)
        print(f"[INFO] Received widget HTML: {html_size_mb:.2f} MB")

        wid = _store_widget(widget_html)
        return redirect(url_for("view_widget_id", wid=wid))

    # If someone attempts to GET /view-widget without an id, reject with helpful message.
    return "Send POST with form field 'html' (or request /view-widget/<id>)", 400


@app.route("/view-widget/<wid>", methods=["GET"])
def view_widget_id(wid: str):
    """Render stored widget by id. Returns 404 if expired or not found."""
    widget_html = _get_widget(wid)
    if not widget_html:
        return "Widget not found or expired", 404
    return render_template_string(widget_html)


@app.route("/api/widget/<wid>", methods=["GET"])
def get_widget_html(wid: str):
    """Get raw widget HTML by ID for embedding. Returns JSON with HTML content."""
    widget_html = _get_widget(wid)
    if not widget_html:
        return jsonify({"error": "Widget not found or expired"}), 404

    html_size_mb = len(widget_html.encode("utf-8")) / (1024 * 1024)
    return jsonify(
        {"widget_id": wid, "html": widget_html, "size_mb": round(html_size_mb, 2)}
    )


# Simple in-memory temporary store for large widget HTML payloads.
# Keys are short hex ids; values are tuples (html, expiry_timestamp).
_WIDGET_STORE = {}
_WIDGET_TTL = 60 * 60 * 24  # 24 hours (widgets now stored server-side)


def _store_widget(html: str) -> str:

    ts = str(time.time()).encode("utf-8")
    # Use a short hash to create compact ids
    wid = hashlib.sha1(ts + html.encode("utf-8")).hexdigest()[:12]
    expiry = time.time() + _WIDGET_TTL
    _WIDGET_STORE[wid] = (html, expiry)
    return wid


def _get_widget(wid: str):
    entry = _WIDGET_STORE.get(wid)
    if not entry:
        return None
    html, expiry = entry
    if time.time() > expiry:
        try:
            del _WIDGET_STORE[wid]
        except KeyError:
            print("An error occurred while deleting _WIDGET_STORE[wid].")
        return None
    return html


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5001)
