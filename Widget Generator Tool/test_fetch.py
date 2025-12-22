#!/usr/bin/env python3
"""Test script to verify Notion map fetching with BeautifulSoup"""

import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup


load_dotenv()


def fetch_notion_map_view(embed_url):
    """Fetch Notion map view page and extract the embeddable content using BeautifulSoup"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        print(f"🔍 Fetching Notion map from: {embed_url}")
        response = requests.get(embed_url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "lxml")

        # Create iframe embed
        iframe_html = f'<iframe src="{embed_url}" style="width:100%;height:100vh;border:none;" allowfullscreen></iframe>'

        # Try to extract the map data from the page
        scripts = soup.find_all("script")

        print(f"✅ Fetched page successfully!")
        print(f"   - Page title: {soup.title.string if soup.title else 'No title'}")
        print(f"   - Found {len(scripts)} scripts")
        print(f"   - Response status: {response.status_code}")
        print(f"   - Content length: {len(response.content)} bytes")

        return iframe_html

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching Notion map: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


if __name__ == "__main__":
    embed_url = os.getenv("NOTION_MAP_EMBED_URL")

    if not embed_url:
        print("❌ NOTION_MAP_EMBED_URL not found in .env file")
        exit(1)

    print("=" * 60)
    print("Testing Notion Map Fetch with BeautifulSoup")
    print("=" * 60)

    result = fetch_notion_map_view(embed_url)

    if result:
        print("\n" + "=" * 60)
        print("✅ Success! Generated iframe embed:")
        print("=" * 60)
        print(result[:200] + "..." if len(result) > 200 else result)
    else:
        print("\n❌ Failed to fetch Notion map")
