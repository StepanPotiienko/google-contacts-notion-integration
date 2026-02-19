#!/usr/bin/env python3
"""
Geocode Ukrainian settlements using Google Maps API.
Handles duplicate settlement names by checking oblast.
Converts address strings to lat/lng coordinates in the format needed for index.js

Usage:
  python3 geocode_settlements.py              # Geocode missing coordinates
  python3 geocode_settlements.py --verify     # Verify existing coordinates
  python3 geocode_settlements.py --force      # Force re-geocoding all
"""

import asyncio
import json
import os
import re
import sys
from typing import Optional, Tuple, Dict
from dotenv import load_dotenv
import aiohttp
import requests

from geocode_cache_manager import _GeocodeCacheManager

# Load environment variables
load_dotenv()
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

if not GOOGLE_MAPS_API_KEY:
    raise ValueError("GOOGLE_MAPS_API_KEY not found in .env file")

# Initialize persistent cache manager
cache_manager = _GeocodeCacheManager()
cache_manager.load()

# Pre-compile regex patterns for better performance
OBLAST_PATTERN = re.compile(r"\s*обл\.?\s*$", re.IGNORECASE)
CITY_PREFIX_PATTERN = re.compile(r"^м\.\s+", re.IGNORECASE)
DISTRICT_PATTERN = re.compile(r"\s*р-?н\.?\s*$", re.IGNORECASE)
SETTLEMENT_MARKER_PATTERN = re.compile(
    r"(?:с\.|село|смт\.|м\.|місто)\s+", re.IGNORECASE
)
SETTLEMENT_CLEANUP_PATTERN = re.compile(
    r"^(?:с\.|село|смт\.|м\.|місто)\s+", re.IGNORECASE
)


def parse_address(address: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse Ukrainian address to extract oblast, district, and settlement name.

    Format: "Область обл., Район р-н, с. Settlement"
    Returns: (oblast, district, settlement_name)

    Examples:
      "Полтавська обл., Лубенський р-н, с. Богодарівка"
        -> ("Полтавська", "Лубенський", "Богодарівка")
      "Київська обл., Обухівський р-н, м. Миронівка"
        -> ("Київська", "Обухівський", "Миронівка")
      "м. Київ, вул. Жилянська, буд. 59, оф. 107"
        -> ("Київ", None, "Київ")  # City case
    """
    # Remove extra spaces
    address = address.strip()

    # Split by comma
    parts = [p.strip() for p in address.split(",")]

    oblast = None
    district = None
    settlement = None

    # First part usually contains oblast or city
    if len(parts) > 0:
        oblast_part = parts[0]
        # Extract oblast name (remove "обл." suffix) - use pre-compiled pattern
        oblast = OBLAST_PATTERN.sub("", oblast_part).strip()

        # Handle city prefix (м.) - use pre-compiled pattern
        oblast = CITY_PREFIX_PATTERN.sub("", oblast).strip()
        oblast = oblast.strip() if oblast else None

    # Second part usually contains district
    if len(parts) > 1:
        district_part = parts[1]
        # Extract district name (remove "р-н" or "р-н." suffix) - use pre-compiled pattern
        district = DISTRICT_PATTERN.sub("", district_part).strip()

        # If this part contains settlement marker, extract settlement from here
        if SETTLEMENT_MARKER_PATTERN.search(district_part):
            settlement = SETTLEMENT_CLEANUP_PATTERN.sub("", district_part).strip()
            # Try to keep just the settlement name (before any additional info)
            settlement = settlement.split()[0] if settlement else None
        else:
            district = district.strip() if district else None

    # Third part usually contains settlement
    if not settlement and len(parts) > 2:
        settlement_part = parts[2]
        # Remove prefixes like "с.", "село", "смт.", "м.", "місто"
        settlement = SETTLEMENT_CLEANUP_PATTERN.sub("", settlement_part).strip()
        settlement = settlement.strip() if settlement else None

    # If still no settlement, use oblast as settlement (for cities)
    if not settlement and oblast:
        settlement = oblast

    return oblast, district, settlement


def geocode_settlement(oblast: str, settlement: str) -> Optional[Tuple[float, float]]:
    """
    Geocode a settlement in a specific oblast using Google Maps API.
    Returns (lat, lng) or None if not found.

    Prioritizes oblast-specific results to handle duplicate settlement names.
    """

    # Create cache key
    cache_key = f"{oblast}|{settlement}".lower()

    # Check persistent cache first
    cached = cache_manager.get(cache_key)
    if cached is not None:
        if cached:
            print(f"    [cached] ({cached[0]:.5f}, {cached[1]:.5f})")
        return cached

    # Build query with oblast for disambiguation
    query = f"{settlement}, {oblast}, Україна"

    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": query,
            "key": GOOGLE_MAPS_API_KEY,
            "language": "uk",  # Ukrainian language
        }

        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()

        data = response.json()

        if data.get("status") == "OK" and data.get("results"):
            # Get the first result
            location = data["results"][0]["geometry"]["location"]
            lat = location["lat"]
            lng = location["lng"]

            # Cache the result persistently
            cache_manager.set(cache_key, (lat, lng))

            return (lat, lng)
        else:
            # Cache the failure persistently
            cache_manager.set(cache_key, None)
            return None

    except requests.exceptions.RequestException as e:
        print(f"    [API Error] {e}")
        return None


async def geocode_settlement_async(
    session: aiohttp.ClientSession,
    oblast: str,
    settlement: str,
    semaphore: asyncio.Semaphore,
) -> Tuple[str, Optional[Tuple[float, float]]]:
    """
    Async geocoding with semaphore for rate limiting.
    Returns (cache_key, (lat, lng)) or (cache_key, None)
    """
    cache_key = f"{oblast}|{settlement}".lower()

    # Check persistent cache first
    cached = cache_manager.get(cache_key)
    if cached is not None:
        return cache_key, cached

    query = f"{settlement}, {oblast}, Україна"

    async with semaphore:
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": query,
                "key": GOOGLE_MAPS_API_KEY,
                "language": "uk",
            }

            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                data = await response.json()

                if data.get("status") == "OK" and data.get("results"):
                    location = data["results"][0]["geometry"]["location"]
                    result = (location["lat"], location["lng"])
                    cache_manager.set(cache_key, result)
                    return cache_key, result
                else:
                    cache_manager.set(cache_key, None)
                    return cache_key, None

        except Exception as e:
            print(f"    [Async API Error] {cache_key}: {e}")
            return cache_key, None


def process_clients_from_js(force: bool = False) -> list:
    """
    Read the clients array from index.js and geocode missing coordinates.
    Uses async concurrent requests for faster geocoding.

    Args:
        force: If True, re-geocode all clients regardless of existing coordinates
    """
    index_js_path = os.path.join(os.path.dirname(__file__), "public", "index.js")

    with open(index_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract the clients array
    match = re.search(r"const clients = \[(.*?)\];", content, re.DOTALL)
    if not match:
        raise ValueError("Could not find clients array in index.js")

    json_str = "[" + match.group(1) + "]"

    # Parse JSON
    clients = json.loads(json_str)

    print(f"\nProcessing {len(clients)} clients...")
    print("-" * 70)

    # Phase 1: Identify what needs geocoding
    geocoding_tasks = {}  # Maps cache_key to (oblast, settlement, client_indices)
    missing_coords = []
    skipped_count = 0

    for idx, client in enumerate(clients):
        has_coords = bool(client.get("lat") and client.get("lng"))

        if has_coords and not force:
            skipped_count += 1
            continue

        address = client.get("address", "")
        if not address:
            print(f"{idx:2d}. ⚠ Missing address: {client.get('name')}")
            continue

        oblast, district, settlement = parse_address(address)

        if not oblast or not settlement:
            print(f"{idx:2d}. ✗ Could not parse address: {client['name'][:40]}")
            missing_coords.append(client)
            continue

        cache_key = f"{oblast}|{settlement}".lower()

        # Reuse the same geocoding result for duplicate locations
        if cache_key not in geocoding_tasks:
            geocoding_tasks[cache_key] = (oblast, settlement, [])

        geocoding_tasks[cache_key][2].append(idx)

    print(f"  Unique locations to geocode: {len(geocoding_tasks)}")
    print(f"  Skipped (cached): {skipped_count}")

    # Phase 2: Geocode using async concurrency
    if geocoding_tasks:
        print("\n  Fetching coordinates...")
        results = asyncio.run(_geocode_batch(geocoding_tasks))

        # Phase 3: Apply results to clients
        updated_count = 0
        failed_count = 0

        for cache_key, (oblast, settlement, client_indices) in geocoding_tasks.items():
            coords = results.get(cache_key)

            if coords:
                # Apply to all clients with this location
                for client_idx in client_indices:
                    clients[client_idx]["lat"] = round(coords[0], 10)
                    clients[client_idx]["lng"] = round(coords[1], 10)
                    updated_count += 1
            else:
                # Track failures
                for client_idx in client_indices:
                    missing_coords.append(clients[client_idx])
                failed_count += len(client_indices)

        # Save cache to disk
        cache_manager.save()

        print("\n" + "=" * 70)
        print(f"Summary:")
        print(f"  Updated: {updated_count} clients")
        print(f"  Skipped: {skipped_count} clients (already have coordinates)")
        print(f"  Failed:  {failed_count} clients")

        if missing_coords:
            print(f"\n⚠️  Clients that failed (need manual review):")
            for client in missing_coords[:10]:  # Show first 10
                print(f"  • {client['name']}")
                print(f"    {client.get('address', 'NO ADDRESS')}")
            if len(missing_coords) > 10:
                print(f"  ... and {len(missing_coords) - 10} more")
    else:
        print(f"Summary:")
        print(f"  Updated: 0 clients")
        print(f"  Skipped: {skipped_count} clients (already have coordinates)")

    return clients


async def _geocode_batch(
    geocoding_tasks: Dict[str, Tuple[str, str, list]],
) -> Dict[str, Optional[Tuple[float, float]]]:
    """
    Geocode a batch of unique locations concurrently.
    Limits concurrent requests using a semaphore to avoid rate limiting.
    """
    # Semaphore: Allow 8 concurrent requests (Google Maps API typically allows ~100/sec)
    semaphore = asyncio.Semaphore(8)

    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [
            geocode_settlement_async(session, oblast, settlement, semaphore)
            for cache_key, (oblast, settlement, _) in geocoding_tasks.items()
        ]

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # Build results dict, handling any exceptions
    results = {}
    for item in results_list:
        if isinstance(item, Exception):
            print(f"    [Batch Error] {item}")
            continue
        cache_key, coords = item
        results[cache_key] = coords

    return results


def generate_js_output(clients: list) -> str:
    """
    Generate the JavaScript code for the clients array in the original format.
    Each client on its own line as a JSON object.
    """

    lines = ["const clients = ["]

    for i, client in enumerate(clients):
        # Create JSON representation with proper spacing (space after colons)
        json_str = json.dumps(client, ensure_ascii=False, separators=(", ", ": "))

        # Format as JavaScript object with proper spacing
        if i < len(clients) - 1:
            lines.append(f"  {json_str},")
        else:
            lines.append(f"  {json_str}")

    lines.append("];")
    lines.append("")
    lines.append("")

    # Add the rest of the file (icons and functions)
    lines.append("const icons = {")
    lines.append(
        '  address: \'<svg class="popup-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>\','
    )
    lines.append(
        '  contact: \'<svg class="popup-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>\''
    )
    lines.append("};")
    lines.append("")
    lines.append("function buildPopupHTML(c) {")
    lines.append("  let html = '<div class=\"popup-header\">';")
    lines.append(
        "  html += '<div class=\"popup-name\">' + escapeHtml(c.name) + '</div>';"
    )
    lines.append("  html += '</div>';")
    lines.append("")
    lines.append("  html += '<div class=\"popup-body\">';")
    lines.append("")
    lines.append("  if (c.address) {")
    lines.append(
        "    html += '<div class=\"popup-row\">' + icons.address + '<span class=\"popup-value\">' + escapeHtml(c.address) + '</span></div>';"
    )
    lines.append("  }")
    lines.append("")
    lines.append(
        "  html += '<div class=\"popup-coords\">📍 ' + c.lat.toFixed(5) + ', ' + c.lng.toFixed(5) + '</div>';"
    )
    lines.append("  html += '</div>';")
    lines.append("")
    lines.append("  return html;")
    lines.append("}")
    lines.append("")
    lines.append("function escapeHtml(text) {")
    lines.append("  if (!text) return '';")
    lines.append("  const div = document.createElement('div');")
    lines.append("  div.textContent = text;")
    lines.append("  return div.innerHTML;")
    lines.append("}")
    lines.append("")
    lines.append("const map = new maplibregl.Map({")
    lines.append("  container: 'map',")
    lines.append("  style: {")
    lines.append("    version: 8,")
    lines.append("    sources: {")
    lines.append("      osm: {")
    lines.append("        type: 'raster',")
    lines.append("        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],")
    lines.append("        tileSize: 256,")
    lines.append("        attribution: '© OpenStreetMap contributors'")
    lines.append("      }")
    lines.append("    },")
    lines.append("    layers: [{ id: 'osm', type: 'raster', source: 'osm' }]")
    lines.append("  },")
    lines.append("  center: [30.5241361, 50.4500336],")
    lines.append("  zoom: 5")
    lines.append("});")
    lines.append("")
    lines.append("map.on('load', () => {")
    lines.append("  if (clients.length === 0) return;")
    lines.append("  const bounds = new maplibregl.LngLatBounds();")
    lines.append("  clients.forEach(c => bounds.extend([c.lng, c.lat]));")
    lines.append("  map.fitBounds(bounds, { padding: 50, maxZoom: 12 });")
    lines.append("")
    lines.append("  clients.forEach(c => {")
    lines.append("    const el = document.createElement('div');")
    lines.append("    el.className = 'marker';")
    lines.append("    el.style.backgroundColor = c.color || '#ef4444';")
    lines.append("")
    lines.append(
        "    const popup = new maplibregl.Popup({ offset: 15, maxWidth: '320px' })"
    )
    lines.append("      .setHTML(buildPopupHTML(c));")
    lines.append("")
    lines.append("    new maplibregl.Marker({ element: el })")
    lines.append("      .setLngLat([c.lng, c.lat])")
    lines.append("      .setPopup(popup)")
    lines.append("      .addTo(map);")
    lines.append("  });")
    lines.append("});")

    return "\n".join(lines)


def main():
    """Main entry point"""

    force_recode = "--force" in sys.argv
    verify_mode = "--verify" in sys.argv

    print("🌍 Ukrainian Settlement Geocoder")
    print("=" * 70)
    print(f"Using Google Maps API Key: {GOOGLE_MAPS_API_KEY[:20]}...")
    print()

    if force_recode:
        print("MODE: Force re-geocoding all clients")
    elif verify_mode:
        print("MODE: Verify existing coordinates")
    else:
        print("MODE: Geocode missing coordinates only")
    print("=" * 70)

    try:
        # Process clients and geocode missing coordinates
        clients = process_clients_from_js(force=force_recode)

        # Generate output
        print("\n" + "=" * 70)
        print("✓ Generating JavaScript output...")

        js_output = generate_js_output(clients)

        # Save to output file
        output_path = os.path.join(os.path.dirname(__file__), "public", "index.js.new")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(js_output)

        print(f"✓ Output saved to: {output_path}")
        print()
        print("📋 Next steps:")
        print(f"   1. Review the changes in: {output_path}")
        print(f"   2. If satisfied, run: mv {output_path} public/index.js")
        print(f"   3. Commit the changes to git")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
