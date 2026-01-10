"""
Widget Generator Tool - Flask Application

This Flask application generates embeddable map widgets from Notion databases.
"""

import json
import os
import re

import requests

# For some reason IntelliSense marks this as an error, but Flask application works fine.
# pylint: disable=import-error
from flask import Flask, jsonify, render_template_string, request, redirect, url_for  # type: ignore

# Import templates and utilities
from templates import GENERATOR_HTML, INLINE_MAP_TEMPLATE
from utils import (
    _load_env_with_exports,
    fetch_clients_from_notion,
    parse_csv_to_clients,
    load_clients_store,
    save_clients_store,
    merge_clients,
)

# Initialize Flask app
STATIC_DIR = os.path.join(os.path.dirname(__file__), "public")
app = Flask(__name__, static_folder=STATIC_DIR)

# Load environment variables
_load_env_with_exports()


@app.route("/")
def index():
    """Serve the main widget generator interface."""
    return render_template_string(GENERATOR_HTML)


@app.route("/api/generate-widget", methods=["POST"])
def generate_widget():
    """API endpoint to generate a widget from Notion data."""
    data = request.get_json()
    # Support both camelCase and snake_case
    api_key = data.get("api_key") or data.get("apiKey")
    database_id = data.get("database_id") or data.get("databaseId")
    include_stored = data.get("include_stored")
    if include_stored is None:
        include_stored = data.get("includeStored")
    if include_stored is None:
        include_stored = True

    if not api_key or not database_id:
        return jsonify({"error": "Missing API key or database ID"}), 400

    try:
        notion_clients = []
        if api_key and database_id:
            notion_clients = fetch_clients_from_notion(api_key, database_id)

        stored_clients = load_clients_store() if include_stored else []

        # Merge stored (CSV) and Notion clients, deduplicating by name+coords
        clients = merge_clients(stored_clients, notion_clients, dedupe=True)
        clients_json = json.dumps(clients)

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

        return jsonify({"widget": widget_html, "clients": len(clients)})
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
    """Accept a CSV file upload, parse it into clients, and return widget HTML."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded (field name 'file')"}), 400

    uploaded = request.files["file"]
    try:
        content = uploaded.read()
        new_clients = parse_csv_to_clients(content)

        # Load existing stored clients, merge and deduplicate, then save
        existing = load_clients_store()
        merged = merge_clients(existing, new_clients, dedupe=True)
        save_clients_store(merged)

        clients_json = json.dumps(merged)
        widget_html = INLINE_MAP_TEMPLATE.format(clients_json=clients_json)
        return jsonify({"widget": widget_html, "clients": len(merged)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/clients", methods=["GET"])
def get_clients():
    """Return the currently stored clients."""
    try:
        clients = load_clients_store()
        return jsonify({"clients": clients, "count": len(clients)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/clear-clients", methods=["POST"])
def clear_clients():
    """Clear the stored clients list."""
    try:
        save_clients_store([])
        return jsonify({"cleared": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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


# Simple in-memory temporary store for large widget HTML payloads.
# Keys are short hex ids; values are tuples (html, expiry_timestamp).
_WIDGET_STORE = {}
_WIDGET_TTL = 60 * 10  # 10 minutes


def _store_widget(html: str) -> str:
    import time, hashlib

    ts = str(time.time()).encode("utf-8")
    # Use a short hash to create compact ids
    wid = hashlib.sha1(ts + html.encode("utf-8")).hexdigest()[:12]
    expiry = time.time() + _WIDGET_TTL
    _WIDGET_STORE[wid] = (html, expiry)
    return wid


def _get_widget(wid: str):
    import time

    entry = _WIDGET_STORE.get(wid)
    if not entry:
        return None
    html, expiry = entry
    if time.time() > expiry:
        try:
            del _WIDGET_STORE[wid]
        except KeyError:
            pass
        return None
    return html


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
