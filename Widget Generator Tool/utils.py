"""
Utility functions for the Widget Generator Tool.

This module contains all helper functions for fetching data from Notion,
geocoding locations, and processing client information.
"""

import csv
import re
import hashlib
import io
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests
from tqdm import tqdm

from geocode_cache_manager import _GeocodeCacheManager

try:
    from notion_client import Client
except ImportError:
    Client = None


_geocode_cache_manager = _GeocodeCacheManager()
_GEOCODE_CACHE_LOCK = threading.Lock()


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


# TODO: This function here is a bottleneck for the entire script.
# It loads entire database from Notion, and thus taking too much time.
# Then the entire data is filtered in the code, so we waste a lot of time and power
# to just get the neccessary data.
async def fetch_notion_data(api_key, database_id):
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
    all_results: list = []
    start_cursor = None

    response = await client.databases.query(
        database_id=database_id, filter=notion_filter, start_cursor=start_cursor
    )
    all_results.extend(response.get("results", []))
    start_cursor = response.get("next_cursor")

    while response.get("has_more"):
        response = await client.databases.query(
            database_id=database_id, filter=notion_filter, start_cursor=start_cursor
        )
        all_results.extend(response.get("results", []))
        start_cursor = response.get("next_cursor")

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
    except (OSError, PermissionError, ValueError, TypeError, IOError):
        print("Could not load geocode cache from disk.")

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
        except (OSError, PermissionError, ValueError, TypeError, IOError):
            return addr, None

    # Execute queries in thread pool
    # success_count tracks number of successful geocodes we have persisted
    success_count = 0
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(to_query)))) as ex:
        futures = {ex.submit(worker, a): a for a in to_query}
        total = len(to_query)

        # Use tqdm if available
        try:
            use_tqdm = True
            progress_bar = tqdm(total=total, desc="Geocoding", ncols=80)
        except (ImportError, NameError):
            use_tqdm = False
            progress_bar = None

        completed = 0
        try:
            for fut in as_completed(futures):
                a = futures[fut]
                try:
                    result = fut.result()
                    if result is not None:
                        addr, coords = result
                    else:
                        addr, coords = a, None
                except (TimeoutError, ConnectionError, ValueError, KeyError):
                    addr, coords = a, None

                    if coords:
                        results[addr] = coords

                    try:
                        key = _geocode_cache_key(addr)
                        with _GEOCODE_CACHE_LOCK:
                            _geocode_cache_manager.set(key, coords)
                            success_count += 1

                            # Periodically flush to disk to avoid losing progress
                            if autosave_every and success_count % autosave_every == 0:
                                _save_geocode_cache()

                    except (ValueError, TypeError, OSError, PermissionError, IOError):
                        print("Could not update geocode cache on disk.")

                else:
                    results[addr] = None
                completed += 1

                if use_tqdm and progress_bar is not None:
                    progress_bar.update(1)
                else:
                    print(f"\nGeocoding: {completed}/{total}", end="\r", flush=True)

        finally:
            if use_tqdm and progress_bar is not None:
                progress_bar.close()
            else:
                # Add a break line
                print()

    # Ensure any remaining new entries are persisted
    try:
        with _GEOCODE_CACHE_LOCK:
            _save_geocode_cache()
    except (ValueError, TypeError, OSError, PermissionError, IOError):
        print("Could not save geocode cache on disk.")

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
        except (UnicodeDecodeError, TypeError, SyntaxError):
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

        def find_first(keys: set, row: dict) -> Optional[str]:
            """Find first non-empty value for any of the given keys in the row."""
            lower_map = {k.lower(): v for k, v in row.items()}

            for k in keys:
                if k in lower_map and lower_map[k]:
                    return lower_map[k]
            return None

        name = find_first(name_keys, norm_row) or "Unnamed"
        address = find_first(addr_keys, norm_row)
        phone = find_first(phone_keys, norm_row)
        email = find_first(email_keys, norm_row)
        notes = find_first(notes_keys, norm_row)
        label = find_first(label_keys, norm_row)
        org = find_first(org_keys, norm_row)

        lat_raw = find_first(lat_keys, norm_row)
        lng_raw = find_first(lng_keys, norm_row)

        lat = None
        lng = None

        if lat_raw and lng_raw:
            try:
                lat = float(lat_raw.replace(",", "."))
                lng = float(lng_raw.replace(",", "."))
            except (TypeError, ValueError, AttributeError):
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

    # Perform batch geocoding for collected addresses (respect max_geocode)
    max_req = max_geocode if max_geocode is not None else None
    if addresses:
        t_bg = time.time()
        coords_map = batch_geocode(
            addresses, max_workers=4, rate=4.0, burst=4, max_requests=max_req
        )
        t_bg_end = time.time()
        print(
            f"CSV batch geocoding time: {t_bg_end - t_bg:.2f}s for {len(addresses)} places"
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
        except OSError:
            print("Could not create public directory.")
    return os.path.join(public_dir, "clients_store.json")


def load_clients_store() -> list[dict]:
    """Load clients store from JSON file."""
    path = _clients_store_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, PermissionError, IOError, ValueError, TypeError):
        print("Could not load clients store from disk. Using an empty list.")
        return []


def save_clients_store(clients: list[dict]) -> None:
    """Save clients store to JSON file."""
    path = _clients_store_path()
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(clients, fh, ensure_ascii=False, indent=2)
    except (OSError, PermissionError, IOError, ValueError, TypeError):
        print("Could not save clients store to disk.")
        return


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
        except (TypeError, ValueError):
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
