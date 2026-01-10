"""
Utility functions for the Widget Generator Tool.

This module contains all helper functions for fetching data from Notion,
geocoding locations, and processing client information.
"""

import os
import time
import requests
from dotenv import load_dotenv
import csv
import json
import io


try:
    from notion_client import Client
except ImportError:
    Client = None


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


def fetch_notion_data(api_key, database_id):
    """Fetch data from Notion database using the Notion API.

    Args:
        api_key: Notion API key
        database_id: Notion database ID

    Returns:
        dict: Notion API response containing database records
    """
    if not Client:
        # Fallback to direct HTTP request if notion_client is not available
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        response = requests.post(url, headers=headers, json={}, timeout=30)
        response.raise_for_status()
        return response.json()

    # Use notion_client library if available
    client = Client(auth=api_key)
    all_results = []
    start_cursor = None

    while True:
        params = {"database_id": database_id}
        if start_cursor:
            params["start_cursor"] = start_cursor

        response = client.databases.query(**params)
        all_results.extend(response.get("results", []))  # type: ignore

        if not response.get("has_more"):  # type: ignore
            break
        start_cursor = response.get("next_cursor")  # type: ignore

    return {"results": all_results}


def geocode_location(location_str: str):
    """
    Geocode a location string to lat/lng coordinates.
    Parses Ukrainian address format and uses OpenStreetMap Nominatim API.

    Args:
        location_str: Location string (e.g., "Київ", "Полтавська обл.,
        Лубенський р-н, с. Богодарівка")

    Returns:
        dict with 'lat' and 'lng' keys, or None if geocoding fails
    """
    if not location_str or not location_str.strip():
        return None

    # Parse Ukrainian address format
    parts = [p.strip() for p in location_str.split(",")]
    search_terms = []

    for part in parts:
        # Clean Ukrainian address abbreviations
        cleaned = part
        cleaned = cleaned.replace(" обл.", "")
        cleaned = cleaned.replace(" р-н", "")
        cleaned = cleaned.replace("с. ", "")
        cleaned = cleaned.replace("м. ", "")
        cleaned = cleaned.replace("смт. ", "")
        cleaned = cleaned.strip()
        if cleaned:
            search_terms.append(cleaned)

    # Try geocoding with progressively broader searches
    attempts = [
        ", ".join(search_terms),  # Full address
        (
            search_terms[0] if search_terms else ""
        ),  # First part only (usually city/village)
        location_str,  # Original string as fallback
    ]

    for query in attempts:
        if not query:
            continue

        try:
            # OpenStreetMap Nominatim API
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "ua",  # Limit to Ukraine
                "addressdetails": 1,
            }
            headers = {"User-Agent": "NotionMapWidget/1.0"}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data and len(data) > 0:
                result = data[0]
                return {"lat": float(result["lat"]), "lng": float(result["lon"])}

        except (requests.RequestException, ValueError) as e:
            print(f"  Geocoding error for '{query}': {e}")
            # Continue to next search term

    return None


def parse_csv_to_clients(
    file_bytes: bytes, geocode: bool = True, max_geocode: int | None = None
) -> list[dict]:
    """
    Parse a CSV file (bytes) into a list of client dicts suitable for the widget.

    The parser is tolerant to different encodings and delimiters, and supports
    common column names in Ukrainian and English. If latitude/longitude are
    missing but an address is present and `geocode` is True, the function will
    attempt to geocode addresses using `geocode_location`.
    """
    # Try common encodings
    encodings = ("utf-8-sig", "utf-8", "cp1251", "latin-1")
    text = None
    for enc in encodings:
        try:
            text = file_bytes.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        # As a last resort, replace errors
        text = file_bytes.decode("utf-8", errors="replace")

    sample = text[:4096]
    # Detect delimiter: prefer semicolon if present in sample, else comma
    delimiter = ";" if ";" in sample and sample.count(";") >= sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    name_keys = {"name", "покупець", "пІб", "пиб", "client", "клієнт", "ПОКУПЕЦЬ"}
    addr_keys = {"address", "адреса", "адреса_1", "place", "адреса1", "АДРЕСА"}
    lat_keys = {"lat", "latitude", "широта"}
    lng_keys = {"lng", "lon", "longitude", "довгота"}
    phone_keys = {"phone", "телефон", "тел"}
    email_keys = {"email", "ел.адреса", "e-mail", "e-mail 1 - value"}
    notes_keys = {"notes", "примітка", "примітки"}
    label_keys = {"label", "labels", "мітка"}
    org_keys = {"org", "organization", "orgtitle", "organization title"}

    clients: list[dict] = []
    geocoded = 0

    for row in reader:
        # Normalize row keys to lowercase without surrounding spaces
        norm_row = {}
        for k, v in row.items():
            # normalize key
            key = k or ""
            if not isinstance(key, str):
                key = str(key)
            key = key.strip()

            # normalize value; handle lists and non-strings safely
            if isinstance(v, list):
                val = ",".join(str(x) for x in v)
            else:
                val = v or ""
                if not isinstance(val, str):
                    val = str(val)
            val = val.strip()

            norm_row[key] = val

        lower_map = {k.lower(): v for k, v in norm_row.items()}

        def find_first(keys: set):
            for k in keys:
                if k in lower_map and lower_map[k]:
                    return lower_map[k]
            return ""

        name = find_first(name_keys) or "Unnamed"
        address = find_first(addr_keys)
        phone = find_first(phone_keys)
        email = find_first(email_keys)
        notes = find_first(notes_keys)
        label = find_first(label_keys)
        org = find_first(org_keys)

        lat_raw = find_first(lat_keys)
        lng_raw = find_first(lng_keys)

        lat = None
        lng = None
        if lat_raw and lng_raw:
            try:
                lat = float(lat_raw.replace(",", "."))
                lng = float(lng_raw.replace(",", "."))
            except Exception:
                lat = None
                lng = None

        client = {
            "name": name,
            "color": "#ef4444",
            "phone": phone,
            "email": email,
            "contact": "",
            "address": address,
            "notes": notes,
            "label": label,
            "orgTitle": org,
        }

        if lat is not None and lng is not None:
            client["lat"] = lat
            client["lng"] = lng
            clients.append(client)
            continue

        # If we have an address and geocoding is allowed, try geocoding
        if address and geocode:
            time.sleep(0.25)
            coords = geocode_location(address)
            if coords:
                client["lat"] = coords["lat"]
                client["lng"] = coords["lng"]
                clients.append(client)
                geocoded += 1
                # optional early stop if many geocodes performed
                if max_geocode and geocoded >= max_geocode:
                    break
                continue
            else:
                # Could not geocode; skip
                continue

        # Nothing usable -> skip row
    return clients


def _clients_store_path() -> str:
    """Return path to persistent clients store JSON inside public folder."""
    public_dir = os.path.join(os.path.dirname(__file__), "public")
    if not os.path.exists(public_dir):
        try:
            os.makedirs(public_dir, exist_ok=True)
        except Exception:
            pass
    return os.path.join(public_dir, "clients_store.json")


def load_clients_store() -> list[dict]:
    path = _clients_store_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []


def save_clients_store(clients: list[dict]) -> None:
    path = _clients_store_path()
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(clients, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


def merge_clients(
    existing: list[dict], new: list[dict], dedupe: bool = True
) -> list[dict]:
    """Merge two client lists and optionally deduplicate by name+lat+lng.

    Deduplication key uses lowercased name and rounded coords to 5 decimals.
    """
    if not dedupe:
        return existing + new

    def normalize_name(n: str) -> str:
        if not n:
            return ""
        if not isinstance(n, str):
            n = str(n)
        return " ".join(n.lower().split())

    def normalize_phone(p: str) -> str:
        if not p:
            return ""
        if not isinstance(p, str):
            p = str(p)
        # Keep leading + if present, otherwise digits only
        import re

        cleaned = re.sub(r"[^+\d]", "", p)
        # normalize leading + and digits
        if cleaned.startswith("+"):
            return cleaned
        return re.sub(r"[^\d]", "", cleaned)

    def normalize_email(e: str) -> str:
        if not e:
            return ""
        if not isinstance(e, str):
            e = str(e)
        return e.strip().lower()

    def coord_key(c: dict) -> tuple | None:
        lat = c.get("lat")
        lng = c.get("lng")
        try:
            if lat is None or lng is None:
                return None
            lat_k = round(float(lat), 5)
            lng_k = round(float(lng), 5)
            return (lat_k, lng_k)
        except Exception:
            return None

    seen_keys: set = set()
    merged: list[dict] = []

    def keys_for_client(c: dict) -> list[str]:
        keys: list[str] = []
        name = normalize_name(c.get("name") or "")
        coords = coord_key(c)
        if name and coords is not None:
            keys.append(f"name_coord:{name}:{coords[0]}:{coords[1]}")
        elif name:
            keys.append(f"name:{name}")

        phone = normalize_phone(c.get("phone") or "")
        if phone:
            keys.append(f"phone:{phone}")

        email = normalize_email(c.get("email") or "")
        if email:
            keys.append(f"email:{email}")

        # fallback key using rounded coords only
        if coords is not None:
            keys.append(f"coord:{coords[0]}:{coords[1]}")

        return keys

    for c in existing + new:
        client_keys = keys_for_client(c)
        # if any key already seen, consider it a duplicate
        if any(k in seen_keys for k in client_keys if k):
            continue
        # otherwise add all non-empty keys to seen and include client
        for k in client_keys:
            if k:
                seen_keys.add(k)
        merged.append(c)

    return merged


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
                elif source_prop.get("type") == "rich_text" and source_prop.get(
                    "rich_text"
                ):
                    source_value = (
                        source_prop["rich_text"][0]["plain_text"]
                        if source_prop["rich_text"]
                        else ""
                    )

            # Skip entries that don't have Source = "БАЗА"

            if source_value != "БАЗА":
                continue

            # If we reach here, entry passed the filter
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
            email_prop = (
                props.get("ЕЛ.АДРЕСА")
                or props.get("Email")
                or props.get("E-mail 1 - Value")
            )
            if email_prop:
                if email_prop.get("type") == "email":
                    email = email_prop.get("email") or ""
                elif email_prop.get("type") == "rich_text" and email_prop.get(
                    "rich_text"
                ):
                    email = (
                        email_prop["rich_text"][0]["plain_text"]
                        if email_prop["rich_text"]
                        else ""
                    )

            # Contact person
            contact = ""
            contact_prop = props.get("КОНТАКТ")
            if (
                contact_prop
                and contact_prop.get("rich_text")
                and contact_prop["rich_text"]
            ):
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

            # 1. Try the АДРЕСА property (Ukrainian address field - uppercase version has data)
            address_ua = props.get("АДРЕСА") or props.get("Адреса")
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
                        if (
                            "latitude" in location_value
                            and "longitude" in location_value
                        ):
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

            # 4. Build from components
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

        print("\n" + "=" * 60)
        print("📊 Processing Summary:")
        print(f"  Total entries in database: {total_entries}")
        print(f"  Entries matching filter (Source=БАЗА): {entries_processed}")
        print(f"  Entries with location data: {entries_with_place}")
        print(f"  Successfully geocoded: {entries_geocoded}")
        print(f"  Final client count: {len(clients)}")
        print("=" * 60 + "\n")

        return clients

    except (requests.RequestException, KeyError, ValueError, AttributeError) as e:
        print(f"\n❌ Error fetching clients: {str(e)}\n")
        raise
