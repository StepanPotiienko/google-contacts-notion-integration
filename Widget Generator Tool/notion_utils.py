"""Utilities for fetching and processing Notion data."""

import asyncio
import time
import json  # added import

import requests
from utils import (
    _GEOCODE_CACHE_LOCK,
    _geocode_cache_key,
    _geocode_cache_manager,
    _load_geocode_cache,
    _save_geocode_cache,
    batch_geocode,
    fetch_notion_data,
)


async def fetch_clients_from_notion(api_key, database_id):
    """Fetch client location data from Notion database.
    Returns a list of clients with name, lat, lng, and additional properties.
    """

    clients = []
    entries_processed = 0
    entries_with_place = 0
    entries_geocoded = 0
    dropped_source_mismatch = 0
    dropped_no_address = 0
    failed_geocodes = []

    try:
        print("Fetching data from Notion...")
        notion_data = await fetch_notion_data(api_key, database_id)
        total_entries = len(notion_data.get("results", []))
        print(f"Found {total_entries} total entries in database")

        # Collect pages needing geocoding to batch later
        pending_pages: list[tuple[dict, str, str, str, str]] = (
            []
        )  # (client_data, place, name, page_id, page_edited)

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

            if source_value != "БАЗА":
                dropped_source_mismatch += 1
                continue

            # If we reach here, entry has passed the filter
            # and we can safely extract name
            name_prop = props.get("Name") or props.get("name")
            name = "Unnamed"
            if name_prop and name_prop.get("title"):
                name = (
                    name_prop["title"][0]["plain_text"]
                    if name_prop["title"]
                    else "Unnamed"
                )

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
                    label_color = color_map.get(notion_color, "#ef4444")

                elif labels_prop.get("type") == "select" and labels_prop.get("select"):
                    notion_color = labels_prop["select"].get("color", "red")
                    label_name = labels_prop["select"].get("name", "")
                    label_color = color_map.get(notion_color, "#ef4444")

            # Extract place - try multiple sources
            place = ""
            address_display = ""  # For showing in popup
            latlng = None

            # 1. Try iterating through known address fields until we find one with text
            address_candidates = ["АДРЕСА", "Адреса", "Address 1 - Formatted"]
            for candidate_key in address_candidates:
                candidate_prop = props.get(candidate_key)
                if candidate_prop and candidate_prop.get("rich_text"):
                    potential_place = (
                        candidate_prop["rich_text"][0]["plain_text"]
                        if candidate_prop["rich_text"]
                        else ""
                    )
                    if potential_place and potential_place.strip():
                        place = potential_place
                        address_display = place
                        break  # Found a valid address, stop looking

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

            # 3. Try Address 1 - Formatted
            if not latlng and not place:
                addr_formatted = props.get("Address 1 - Formatted")
                if addr_formatted and addr_formatted.get("rich_text"):
                    # Only use if rich_text is not empty
                    potential_place = (
                        addr_formatted["rich_text"][0]["plain_text"]
                        if addr_formatted["rich_text"]
                        else ""
                    )
                    if potential_place and potential_place.strip():
                        place = potential_place
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
                        # Only use if rich_text is not empty
                        txt = (
                            comp["rich_text"][0]["plain_text"]
                            if comp["rich_text"]
                            else ""
                        )
                        if txt and txt.strip():
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

                # Defer geocoding for batch processing, include page id
                # and edit time for change-detection
                page_id = page.get("id")
                page_edited = page.get("last_edited_time") or ""
                pending_pages.append((client_data, place, name, page_id, page_edited))
            else:
                dropped_no_address += 1
                # Log the first few dropped addresses to debug
                if dropped_no_address <= 5:
                    print(
                        f"DEBUG: Dropped client '{name}' - No address found in properties. Available keys: {list(props.keys())}"
                    )
                    # Inspect 'Адреса' or 'АДРЕСА' specifically
                    addr_debug = props.get("АДРЕСА") or props.get("Адреса")
                    if addr_debug:
                        print(
                            f"DEBUG: Found 'Адреса' property content: {json.dumps(addr_debug, default=str)}"
                        )
                    else:
                        print("DEBUG: 'Адреса' property is missing or None")

        # Batch geocode collected places with page-level change-detection using last_edited_time
        if pending_pages:
            # Ensure cache loaded
            try:
                _load_geocode_cache()
            except (ValueError, TypeError, OSError, PermissionError, IOError):
                print("Could not load geocode cache.")

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

                    coords_found = False

                    page_cached = None
                    if page_key:
                        page_cached = _geocode_cache_manager.get(page_key)

                    # If page-specific cache exists and timestamps match
                    if page_cached:
                        # page_cached stored as {'coords': {...}, 'last_edited_time': ...}
                        if isinstance(page_cached, dict) and page_cached.get("coords"):
                            if page_cached.get("last_edited_time") == edited:
                                coords = page_cached.get("coords")

                                if coords:
                                    p["client"]["lat"] = coords["lat"]
                                    p["client"]["lng"] = coords["lng"]
                                    coords_found = True

                        # If page cache is a raw coords dict, assume valid
                        if (
                            not coords_found
                            and isinstance(page_cached, dict)
                            and page_cached.get("lat")
                        ):
                            coords = page_cached
                            p["client"]["lat"] = coords.get("lat")
                            p["client"]["lng"] = coords.get("lng")
                            coords_found = True

                    # Fall back to address-keyed cache if page cache didn't work
                    if not coords_found:
                        addr_key = _geocode_cache_key(place)
                        addr_cached = _geocode_cache_manager.get(addr_key)
                        coords = None
                        if addr_cached:
                            # address cache may be {'coords': {...}} or raw coords
                            if isinstance(addr_cached, dict) and addr_cached.get(
                                "coords"
                            ):
                                coords = addr_cached.get("coords")
                            elif isinstance(addr_cached, dict) and addr_cached.get(
                                "lat"
                            ):
                                coords = {
                                    "lat": addr_cached.get("lat"),
                                    "lng": addr_cached.get("lng"),
                                }

                        if coords:
                            # assign to client and create page-specific cache entry for faster next runs
                            p["client"]["lat"] = coords["lat"]
                            p["client"]["lng"] = coords["lng"]
                            coords_found = True
                            try:
                                pid = p.get("page_id")
                                edited = p.get("edited") or ""
                                if pid:
                                    page_key = f"page::{pid}"
                                    with _GEOCODE_CACHE_LOCK:
                                        _geocode_cache_manager.set(
                                            page_key,
                                            {
                                                "coords": coords,
                                                "last_edited_time": edited,
                                                "address": place,
                                            },
                                        )
                            except (
                                ValueError,
                                TypeError,
                                OSError,
                                PermissionError,
                                IOError,
                            ):
                                print(
                                    "An error occurred while saving geocode cache for page."
                                )

                    # If we found coords from cache, mark as geocoded and don't re-query
                    if coords_found:
                        entries_geocoded += 1
                    else:
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
                f"⏱ Batch geocoding time: {t_geocode_end - t_geocode_start:.2f}s \
                    for {len(uniq_places)} places"
            )

            # Assign returned coords to all pages referencing each place and
            # persist page-level cache
            for norm, entry in place_map.items():
                place = entry["place"]
                pages = entry["pages"]
                coords = coords_map.get(place)
                for p in pages:
                    client_obj = p["client"]
                    pid = p.get("page_id")
                    edited = p.get("edited") or ""

                    # If client already has lat/lng from cache, it's already geocoded
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
                                    _geocode_cache_manager.set(
                                        page_key,
                                        {
                                            "coords": coords,
                                            "last_edited_time": edited,
                                            "address": place,
                                        },
                                    )
                        except (
                            ValueError,
                            TypeError,
                            OSError,
                            PermissionError,
                            IOError,
                        ):
                            print(
                                "An error occurred while saving geocode cache for page."
                            )
                    else:
                        # Geocoding failed — do NOT add to results (no valid coordinates)
                        if "failed_geocodes" in locals():
                            failed_geocodes.append(
                                f"{client_obj.get('name', 'Unknown')} ({place})"
                            )
                        print(
                            f"  ⚠️  Failed to geocode: {client_obj.get('name', 'Unknown')} - {place}"
                        )
                        continue

                    clients.append(client_obj)

            # flush cache after processing
            try:
                with _GEOCODE_CACHE_LOCK:
                    _save_geocode_cache()
            except (
                FileNotFoundError,
                IOError,
                PermissionError,
                OSError,
                ValueError,
                TypeError,
            ):
                pass

        return clients

    except (requests.RequestException, KeyError, ValueError, AttributeError) as e:
        print(f"\nError fetching clients: {str(e)}\n")
        raise

    finally:
        print(f"\n--- Notion Fetch Summary ---")
        print(
            f"Total entries fetched: {total_entries if 'total_entries' in locals() else 'Unknown'}"
        )
        print(f"Dropped (Source != 'БАЗА'): {dropped_source_mismatch}")
        print(f"Dropped (No Address/Coords): {dropped_no_address}")
        print(
            f"Passed to geocoding/processing: {len(clients) + len(pending_pages) if 'pending_pages' in locals() else 0}"
        )
        if "failed_geocodes" in locals() and failed_geocodes:
            print(f"\n--- FAILED GEOCODES ({len(failed_geocodes)}) ---")
            for fail in failed_geocodes:
                print(f" - {fail}")
        print(f"----------------------------\n")


# ─────────────────────────────────────────────────────────────────────────────
# Streaming helpers — used by the SSE endpoint for live Notion loading
# ─────────────────────────────────────────────────────────────────────────────

def _extract_client_from_page(page):
    """Extract client data from a single Notion page.

    Returns (client_data, place, page_id, page_edited) when valid,
    or None when the page should be skipped (wrong Source / no address).
    client_data already has lat/lng set when latlng was embedded in the page;
    in that case place is None and geocoding is not needed.
    """
    props = page.get("properties", {})

    # Filter: Source must equal "БАЗА"
    source_prop = props.get("Source") or props.get("source")
    source_value = None
    if source_prop:
        if source_prop.get("type") == "select" and source_prop.get("select"):
            source_value = source_prop["select"].get("name", "")
        elif source_prop.get("type") == "rich_text" and source_prop.get("rich_text"):
            source_value = source_prop["rich_text"][0]["plain_text"] if source_prop["rich_text"] else ""
    if source_value != "БАЗА":
        return None

    # Name
    name_prop = props.get("Name") or props.get("name")
    name = "Unnamed"
    if name_prop and name_prop.get("title"):
        name = name_prop["title"][0]["plain_text"] if name_prop["title"] else "Unnamed"

    # Phone
    phone = ""
    phone_prop = props.get("ТЕЛЕФОН") or props.get("Phone")
    if phone_prop and phone_prop.get("rich_text") and phone_prop["rich_text"]:
        phone = phone_prop["rich_text"][0]["plain_text"]

    # Email
    email = ""
    email_prop = props.get("ЕЛ.АДРЕСА") or props.get("Email") or props.get("E-mail 1 - Value")
    if email_prop:
        if email_prop.get("type") == "email":
            email = email_prop.get("email") or ""
        elif email_prop.get("type") == "rich_text" and email_prop.get("rich_text"):
            email = email_prop["rich_text"][0]["plain_text"] if email_prop["rich_text"] else ""

    # Contact
    contact = ""
    contact_prop = props.get("КОНТАКТ")
    if contact_prop and contact_prop.get("rich_text") and contact_prop["rich_text"]:
        contact = contact_prop["rich_text"][0]["plain_text"]

    # Notes
    notes = ""
    notes_prop = props.get("ПРИМІТКА") or props.get("Notes")
    if notes_prop and notes_prop.get("rich_text") and notes_prop["rich_text"]:
        notes = notes_prop["rich_text"][0]["plain_text"]
        if len(notes) > 100:
            notes = notes[:100] + "..."

    # Organization title
    org_title = ""
    org_title_prop = props.get("Organization Title")
    if org_title_prop and org_title_prop.get("select"):
        org_title = org_title_prop["select"].get("name", "")

    # Color / label
    color_map = {
        "gray": "#6b7280", "brown": "#92400e", "orange": "#ea580c",
        "yellow": "#eab308", "green": "#16a34a", "blue": "#2563eb",
        "purple": "#9333ea", "pink": "#db2777", "red": "#ef4444",
        "default": "#6b7280",
    }
    label_color = "#ef4444"
    label_name = ""
    labels_prop = props.get("Labels") or props.get("Label")
    if labels_prop:
        if labels_prop.get("type") == "multi_select" and labels_prop.get("multi_select"):
            first = labels_prop["multi_select"][0]
            label_color = color_map.get(first.get("color", "red"), "#ef4444")
            label_name = first.get("name", "")
        elif labels_prop.get("type") == "select" and labels_prop.get("select"):
            label_color = color_map.get(labels_prop["select"].get("color", "red"), "#ef4444")
            label_name = labels_prop["select"].get("name", "")

    # Address / coordinates
    place = ""
    address_display = ""
    latlng = None

    for candidate_key in ["АДРЕСА", "Адреса", "Address 1 - Formatted"]:
        candidate_prop = props.get(candidate_key)
        if candidate_prop and candidate_prop.get("rich_text"):
            txt = candidate_prop["rich_text"][0]["plain_text"] if candidate_prop["rich_text"] else ""
            if txt and txt.strip():
                place = txt
                address_display = place
                break

    if not latlng and not place:
        place_prop = props.get("Place") or props.get("place")
        if place_prop and place_prop.get("type") == "place":
            loc = place_prop.get("place")
            if loc:
                if "latitude" in loc and "longitude" in loc:
                    latlng = (loc["latitude"], loc["longitude"])
                    address_display = loc.get("name", "")
                elif "name" in loc:
                    place = loc["name"]
                    address_display = place

    if not latlng and not place:
        addr_formatted = props.get("Address 1 - Formatted")
        if addr_formatted and addr_formatted.get("rich_text"):
            txt = addr_formatted["rich_text"][0]["plain_text"] if addr_formatted["rich_text"] else ""
            if txt and txt.strip():
                place = txt
                address_display = place

    if not latlng and not place:
        parts = []
        for key in ["Address 1 - Street", "Address 1 - City", "Address 1 - Region", "Address 1 - Country"]:
            comp = props.get(key)
            if comp and comp.get("rich_text"):
                txt = comp["rich_text"][0]["plain_text"] if comp["rich_text"] else ""
                if txt and txt.strip():
                    parts.append(txt)
        if parts:
            place = ", ".join(parts)
            address_display = place

    client_data = {
        "name": name, "color": label_color, "phone": phone,
        "email": email, "contact": contact, "address": address_display,
        "notes": notes, "label": label_name, "orgTitle": org_title,
    }

    if latlng:
        client_data["lat"] = latlng[0]
        client_data["lng"] = latlng[1]
        return (client_data, None, None, None)

    if place:
        # Already a lat,lng string?
        if "," in place and place.count(",") == 1:
            try:
                parts = place.split(",")
                lat = float(parts[0].strip())
                lng = float(parts[1].strip())
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    client_data["lat"] = lat
                    client_data["lng"] = lng
                    return (client_data, None, None, None)
            except (ValueError, IndexError):
                pass
        page_id = page.get("id")
        page_edited = page.get("last_edited_time") or ""
        return (client_data, place, page_id, page_edited)

    return None  # No usable address


def _resolve_batch(items):
    """Geocode a mini-batch of (client_data, place, page_id, page_edited) tuples.

    Uses the existing geocode cache (page-level + address-level) and only calls
    the geocoding API for addresses that are not cached.  Returns a list of
    client dicts that have valid lat/lng.
    """
    try:
        _load_geocode_cache()
    except Exception:
        pass

    results = []
    to_geocode = []  # (client_data, place, page_id, page_edited)

    for client_data, place, page_id, page_edited in items:
        # Already has coordinates
        if client_data.get("lat") is not None:
            results.append(client_data)
            continue
        if not place:
            continue

        coords = None

        # Page-level cache (fastest — exact page match with edit timestamp)
        if page_id:
            page_key = f"page::{page_id}"
            pc = _geocode_cache_manager.get(page_key)
            if pc and isinstance(pc, dict):
                if pc.get("coords") and pc.get("last_edited_time") == page_edited:
                    coords = pc["coords"]
                elif pc.get("lat"):
                    coords = {"lat": pc["lat"], "lng": pc["lng"]}

        # Address-level cache fallback
        if not coords:
            addr_key = _geocode_cache_key(place)
            ac = _geocode_cache_manager.get(addr_key)
            if ac and isinstance(ac, dict):
                if ac.get("coords"):
                    coords = ac["coords"]
                elif ac.get("lat"):
                    coords = {"lat": ac["lat"], "lng": ac["lng"]}

        if coords:
            client_data["lat"] = coords["lat"]
            client_data["lng"] = coords["lng"]
            results.append(client_data)
        else:
            to_geocode.append((client_data, place, page_id, page_edited))

    # Hit the geocoding API for anything not yet cached
    if to_geocode:
        unique_places = list({p for _, p, _, _ in to_geocode if p})
        if unique_places:
            coords_map = batch_geocode(unique_places, max_workers=4, rate=4.0, burst=4)
            for client_data, place, page_id, page_edited in to_geocode:
                coords = coords_map.get(place) if place else None
                if coords:
                    client_data["lat"] = coords["lat"]
                    client_data["lng"] = coords["lng"]
                    results.append(client_data)
                    if page_id:
                        try:
                            with _GEOCODE_CACHE_LOCK:
                                _geocode_cache_manager.set(
                                    f"page::{page_id}",
                                    {"coords": coords, "last_edited_time": page_edited, "address": place},
                                )
                        except Exception:
                            pass
        try:
            with _GEOCODE_CACHE_LOCK:
                _save_geocode_cache()
        except Exception:
            pass

    return results


def stream_clients_from_notion(api_key, database_id, batch_size=25):
    """Generator: yields lists of geocoded client dicts progressively.

    Fetches all Notion pages once, then resolves them in mini-batches so the
    SSE endpoint can flush each batch to the browser as soon as it is ready.
    Clients whose addresses are already in the geocode cache are returned
    almost instantly; uncached ones are geocoded just-in-time.
    """
    notion_data = asyncio.run(fetch_notion_data(api_key, database_id))
    pages = notion_data.get("results", [])

    pending = []  # list of (client_data, place, page_id, page_edited)
    for page in pages:
        result = _extract_client_from_page(page)
        if result is None:
            continue
        pending.append(result)

        if len(pending) >= batch_size:
            resolved = _resolve_batch(pending)
            pending = []
            if resolved:
                yield resolved

    # Flush remaining pages
    if pending:
        resolved = _resolve_batch(pending)
        if resolved:
            yield resolved
