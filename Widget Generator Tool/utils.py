"""
Utility functions for the Widget Generator Tool.

This module contains all helper functions for fetching data from Notion,
geocoding locations, and processing client information.
"""

import csv
import hashlib
import io
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests
from dotenv import load_dotenv

try:
    from notion_client import Client
except ImportError:
    Client = None
# Simple persistent cache for geocoding to avoid repeated external requests.
# Stored in public/geocode_cache.json
class _GeocodeCacheManager:
    """Thread-safe geocode cache manager."""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._cache = {}
        return cls._instance
    
    def load(self) -> None:
        path = _geocode_cache_path()
        if not os.path.exists(path):
            self._cache = {}
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                self._cache = json.load(fh)
        except Exception:
            self._cache = {}
    
    def save(self) -> None:
        path = _geocode_cache_path()
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self._cache, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def get(self, key: str):
        return self._cache.get(key)
    
    def set(self, key: str, value) -> None:
        self._cache[key] = value
    
    def get_all(self) -> dict:
        return self._cache


_geocode_cache_manager = _GeocodeCacheManager()
_GEOCODE_CACHE_LOCK = threading.Lock()


def _geocode_cache_path() -> str:
    public_dir = os.path.join(os.path.dirname(__file__), "public")
    if not os.path.exists(public_dir):
        try:
            os.makedirs(public_dir, exist_ok=True)
        except Exception:
            pass
    return os.path.join(public_dir, "geocode_cache.json")


def _load_geocode_cache() -> None:
    _geocode_cache_manager.load()


def _save_geocode_cache() -> None:
    _geocode_cache_manager.save()


def _geocode_cache_key(q: str) -> str:
    # Normalize query and return a short hash as key
    if not isinstance(q, str):
        q = str(q)
    norm = " ".join(q.strip().lower().split())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


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


# TODO: This function here is a bottleneck for the entire script.
# It loads entire database from Notion, and thus taking too much time.
# Then the entire data is filtered in the code, so we waste a lot of time and power
# to just get the neccessary data.
def fetch_notion_data(api_key, database_id):
    """Fetch Notion data that matches the server-side filter."""
    notion_filter = {"property": "Source", "select": {"equals": "БАЗА"}}

    if not Client:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        # Pass the filter in the JSON body
        response = requests.post(
            url, headers=headers, json={"filter": notion_filter}, timeout=30
        )
        response.raise_for_status()
        return response.json()

    client = Client(auth=api_key)
    all_results = []
    start_cursor = None

    response = client.databases.query(
        database_id=database_id, filter=notion_filter, start_cursor=start_cursor
    )

    while response.get("has_more"):  # type: ignore
        response = client.databases.query(
            database_id=database_id, filter=notion_filter, start_cursor=start_cursor
        )
        all_results.extend(response.get("results", []))  # type: ignore
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


def batch_geocode(
    addresses: list[str],
    max_workers: int = 4,
    rate: float = 4.0,
    burst: int = 4,
    max_requests: Optional[int] = None,  # type: ignore
    autosave_every: int = 20,
) -> dict:
    """
    Batch geocode a list of address strings using `geocode_location` with a
    small shared rate limiter. Returns a mapping address -> coords or None.
    """
    if not addresses:
        return {}

    # Ensure cache loaded
    try:
        _load_geocode_cache()
    except Exception:
        pass
    # Deduplicate while preserving order and normalize keys
    seen = set()
    uniq = []
    norm_map = {}
    for a in addresses:
        if not isinstance(a, str):
            a = str(a)
        norm = " ".join(a.strip().lower().split())
        if norm in seen:
            continue
        seen.add(norm)
        uniq.append(a)
        norm_map[a] = norm

    if max_requests is not None:
        uniq = uniq[:max_requests]

    results: dict = {}
    to_query: list[str] = []
    # Fill results from cache where available
    for a in uniq:
        key = _geocode_cache_key(a)
        cached = _geocode_cache_manager.get(key)
        if cached:
            results[a] = cached
        else:
            to_query.append(a)
            to_query.append(a)

    if not to_query:
        return results

    # Thread-local requests.Session reuse
    thread_local = threading.local()

    def get_session():
        if not hasattr(thread_local, "session"):
            s = requests.Session()
            s.headers.update({"User-Agent": "NotionMapWidget/1.0"})
            thread_local.session = s
        return thread_local.session

    # Token-bucket rate limiter
    bucket = {"tokens": float(burst), "last": time.time()}
    bucket_lock = threading.Lock()

    def acquire_token():
        while True:
            with bucket_lock:
                now = time.time()
                elapsed = now - bucket["last"]
                # refill tokens
                refill = elapsed * rate
                if refill > 0:
                    bucket["tokens"] = min(float(burst), bucket["tokens"] + refill)
                    bucket["last"] = now
                if bucket["tokens"] >= 1.0:
                    bucket["tokens"] -= 1.0
                    return
            # sleep briefly before next check (non-busy wait)
            time.sleep(max(0.01, 1.0 / (rate * 4)))

    url = "https://nominatim.openstreetmap.org/search"
    def worker(addr: str):
        # double-check cache (in case another thread saved it)
        key = _geocode_cache_key(addr)
        cached = _geocode_cache_manager.get(key)
        if cached:
            return addr, cached

        acquire_token()
        session = get_session()
        try:
            params = {
                "q": addr,
                "format": "json",
                "limit": 1,
                "countrycodes": "ua",
                "addressdetails": 1,
            }
            resp = session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data and len(data) > 0:
                r = data[0]
                coords = {"lat": float(r["lat"]), "lng": float(r["lon"])}
                return addr, coords
        except Exception:
            return addr, None
        return addr, None
        return addr, None

    # Execute queries in thread pool
    # success_count tracks number of successful geocodes we have persisted
    success_count = 0
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(to_query)))) as ex:
        futures = {ex.submit(worker, a): a for a in to_query}
        total = len(to_query)

        # Use tqdm if available
        try:
            from tqdm import tqdm  # type: ignore

            use_tqdm = True
            bar = tqdm(total=total, desc="Geocoding", ncols=80)
        except Exception:
            use_tqdm = False
            bar = None

        completed = 0
        try:
            for fut in as_completed(futures):
                a = futures[fut]
                try:
                    addr, coords = fut.result()
                except Exception:
                if coords:
                    results[addr] = coords
                    # Persist each successful result into the shared cache incrementally
                    try:
                        key = _geocode_cache_key(addr)
                        with _GEOCODE_CACHE_LOCK:
                            _geocode_cache_manager.set(key, coords)
                            success_count += 1
                            # Periodically flush to disk to avoid losing progress
                            if autosave_every and success_count % autosave_every == 0:
                                _save_geocode_cache()
                    except Exception:
                        pass
                        pass
                else:
                    results[addr] = None
                completed += 1
                if use_tqdm and bar is not None:
                    bar.update(1)
                else:
                    print(f"\nGeocoding: {completed}/{total}", end="\r", flush=True)
        finally:
            if use_tqdm and bar is not None:
                bar.close()
            else:
                print()

    # Ensure any remaining new entries are persisted
    try:
        with _GEOCODE_CACHE_LOCK:
            _save_geocode_cache()
    except Exception:
        pass

    # Include cached addresses results (already in results) and return
    return results


def parse_csv_to_clients(
    file_bytes: bytes, geocode: bool = True, max_geocode: Optional[int] = None
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

    # Collect rows requiring geocoding and unique addresses
    pending: list[tuple[dict, str]] = []
    addr_seen: set = set()
    addresses: list[str] = []

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
            pending.append((client, address))
            if address not in addr_seen:
                addr_seen.add(address)
                addresses.append(address)
            continue

        # Nothing usable -> skip row
    # Perform batch geocoding for collected addresses (respect max_geocode)
    max_req = max_geocode if max_geocode is not None else None
    if addresses:
        t_bg = time.time()
        coords_map = batch_geocode(
            addresses, max_workers=4, rate=4.0, burst=4, max_requests=max_req
        )
        t_bg_end = time.time()
        print(
            f"⏱ CSV batch geocoding time: {t_bg_end - t_bg:.2f}s for {len(addresses)} places"
        )
        for client_obj, addr in pending:
            coords = coords_map.get(addr)
            if coords:
                client_obj["lat"] = coords["lat"]
                client_obj["lng"] = coords["lng"]
                clients.append(client_obj)
                geocoded += 1

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

    def coord_key(c: dict) -> tuple | None:  # type: ignore
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

    clients = []
    entries_processed = 0
    entries_with_place = 0
    entries_geocoded = 0

    try:
        print("Fetching data from Notion...")
        notion_data = fetch_notion_data(api_key, database_id)
        total_entries = len(notion_data.get("results", []))
        print(f"Found {total_entries} total entries in database")

        # Collect pages needing geocoding to batch later
        pending_pages: list[tuple[dict, str, str]] = []  # (client_data, place, name)

        for page in notion_data.get("results", []):
            entries_processed += 1
            # Print lightweight progress every 50 pages to avoid flooding
            if entries_processed % 50 == 0:
                print(
                    f"Processing Notion pages: {entries_processed}/{total_entries}",
                    end="\r",
                    flush=True,
                )
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

                # Defer geocoding for batch processing, include page id and edit time for change-detection
                page_id = page.get("id")
                page_edited = page.get("last_edited_time") or ""
                pending_pages.append((client_data, place, name, page_id, page_edited))  # type: ignore

        # Batch geocode collected places with page-level change-detection using last_edited_time
        if pending_pages:
            # Ensure cache loaded
            try:
                _load_geocode_cache()
            except Exception:
                pass

            # Group pending pages by normalized place
            place_map: dict = {}
            for client_data, plc, name, page_id, page_edited in pending_pages:
                norm = " ".join(plc.strip().lower().split())
                if norm not in place_map:
                    place_map[norm] = {"place": plc, "pages": []}
                place_map[norm]["pages"].append(
                    {
                        "client": client_data,
                        "page_id": page_id,
                        "edited": page_edited,
                        "name": name,
                    }
                )

            # Decide which places actually need geocoding (if any page referencing them changed)
            uniq_places: list[str] = []
            needs_geocode_for_place: dict = {}

            for norm, entry in place_map.items():
                place = entry["place"]
                pages = entry["pages"]
                need_geo = False
                for p in pages:
                    pid = p.get("page_id")
                    edited = p.get("edited") or ""
                    page_key = f"page::{pid}" if pid else None

                    page_cached = None
                    if page_key:
                        page_cached = _geocode_cache_manager.get(page_key)

                    # If page-specific cache exists and timestamps match, use it
                    if page_cached:
                        # page_cached may be stored as {'coords': {...}, 'last_edited_time': ...}
                        if isinstance(page_cached, dict) and page_cached.get("coords"):
                            if page_cached.get("last_edited_time") == edited:
                                coords = page_cached.get("coords")
                                p["client"]["lat"] = coords["lat"]
                                p["client"]["lng"] = coords["lng"]
                                continue
                        # If page cache is a raw coords dict, assume valid
                        if isinstance(page_cached, dict) and page_cached.get("lat"):
                            coords = page_cached
                            p["client"]["lat"] = coords.get("lat")
                            p["client"]["lng"] = coords.get("lng")
                            continue

                    # Fall back to address-keyed cache
                    addr_key = _geocode_cache_key(place)
                    addr_cached = _geocode_cache_manager.get(addr_key)
                    addr_cached = _GEOCODE_CACHE.get(addr_key)
                    if addr_cached:
                        # address cache may be {'coords': {...}} or raw coords
                        if isinstance(addr_cached, dict) and addr_cached.get("coords"):
                            coords = addr_cached.get("coords")
                        elif isinstance(addr_cached, dict) and addr_cached.get("lat"):
                            coords = {
                                "lat": addr_cached.get("lat"),
                                "lng": addr_cached.get("lng"),
                            }
                        else:
                            coords = None

                        if coords:
                            # assign to client and create page-specific cache entry for faster next runs
                            p["client"]["lat"] = coords["lat"]
                            try:
                                pid = p.get("page_id")
                                edited = p.get("edited") or ""
                                if pid:
                                    page_key = f"page::{pid}"
                                    with _GEOCODE_CACHE_LOCK:
                                        _geocode_cache_manager.set(page_key, {
                                            "coords": coords,
                                            "last_edited_time": edited,
                                            "address": place,
                                        })
                            except Exception:
                                pass
                                pass
                            continue

                    # If we reached here, this page needs geocoding
                    need_geo = True

                if need_geo:
                    uniq_places.append(place)
                    needs_geocode_for_place[place] = entry["pages"]

            t_geocode_start = time.time()
            coords_map = (
                {}
                if not uniq_places
                else batch_geocode(uniq_places, max_workers=4, rate=4.0, burst=4)
            )
            t_geocode_end = time.time()

            print(
                f"⏱ Batch geocoding time: {t_geocode_end - t_geocode_start:.2f}s for {len(uniq_places)} places"
            )

            # Assign returned coords to all pages referencing each place and persist page-level cache
            for norm, entry in place_map.items():
                place = entry["place"]
                pages = entry["pages"]
                coords = coords_map.get(place)
                for p in pages:
                    client_obj = p["client"]
                    pid = p.get("page_id")
                    edited = p.get("edited") or ""

                    # If client already has lat/lng from cache above, keep it
                    if client_obj.get("lat") and client_obj.get("lng"):
                        clients.append(client_obj)
                        continue

                    # Otherwise, try to use coords from batch result
                    if coords:
                        entries_geocoded += 1
                        client_obj["lat"] = coords["lat"]
                        client_obj["lng"] = coords["lng"]
                        # persist page-specific cache
                        try:
                            if pid:
                                page_key = f"page::{pid}"
                                with _GEOCODE_CACHE_LOCK:
                                    _geocode_cache_manager.set(page_key, {
                                        "coords": coords,
                                        "last_edited_time": edited,
                                        "address": place,
                                    })
                        except Exception:
                            pass
                            pass
                    else:
                        print(f"  ⚠️  Failed to geocode: {p.get('name')} - {place}")

            # flush cache after processing
            try:
                with _GEOCODE_CACHE_LOCK:
                    _save_geocode_cache()
            except Exception:
                pass

        return clients

    except (requests.RequestException, KeyError, ValueError, AttributeError) as e:
        print(f"\n❌ Error fetching clients: {str(e)}\n")
        raise
