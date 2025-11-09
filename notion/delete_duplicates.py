"""Delete duplicates in Notion database"""

import hashlib
import itertools
import json
import os
import time
from collections import defaultdict

from dotenv import load_dotenv
from notion_client import Client
from notion_client.errors import (
    RequestTimeoutError,
    APIResponseError,
    HTTPResponseError,
)

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_API_KEY")
DATABASE_ID = os.getenv("CRM_DATABASE_ID")
PROGRESS_FILE = "fetch_progress.json"


def print_first_n_entries_of_a_dict(n: int, iterable) -> list:
    """Print first n entries of a dict for debugging purposes"""
    return list(itertools.islice(iterable, n))


def return_database_chunk(notion, database_id: str) -> dict:
    """Fetch a chunk of the Notion database and return it with retry logic"""

    max_retries = 5
    base_delay = 2

    # Try to load progress from previous run
    all_results = []
    start_cursor = None

    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                progress = json.load(f)
                all_results = progress.get("results", [])
                start_cursor = progress.get("next_cursor")
                print(
                    f"Resuming from previous run with {len(all_results)} pages already fetched..."
                )
        except IOError as e:
            print(f"Could not load progress file: {e}")
            all_results = []
            start_cursor = None

    has_more = True
    retry_count = 0

    while has_more:
        try:
            # Query with current cursor
            if start_cursor:
                data = notion.databases.query(database_id, start_cursor=start_cursor)
            else:
                data = notion.databases.query(database_id)

            # Add results to our collection
            all_results.extend(data["results"])

            has_more = data["has_more"]
            start_cursor = data["next_cursor"]

            print(f"Fetched {len(all_results)} pages so far...")

            # Save progress after each successful fetch
            try:
                with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "results": all_results,
                            "next_cursor": start_cursor,
                            "has_more": has_more,
                        },
                        f,
                    )
            except IOError as e:
                print(f"Warning: Could not save progress: {e}")

            # Reset retry count on success
            retry_count = 0

            # Rate limiting - be gentle with the API
            time.sleep(0.5)

        except RequestTimeoutError as e:
            retry_count += 1
            if retry_count > max_retries:
                print(
                    f"\nMax retries ({max_retries}) reached. Progress saved to {PROGRESS_FILE}"
                )
                print(
                    f"You can run the script again to resume from {len(all_results)} pages."
                )
                raise

            delay = base_delay * (2 ** (retry_count - 1))  # Exponential backoff
            print(
                f"\nTimeout error! Retry {retry_count}/{max_retries} after {delay}s..."
            )
            print(f"Progress: {len(all_results)} pages fetched so far")
            time.sleep(delay)
            continue

        except APIResponseError as e:
            retry_count += 1
            if retry_count > max_retries:
                print(
                    f"\nMax retries ({max_retries}) reached. Progress saved to {PROGRESS_FILE}"
                )
                print(
                    f"You can run the script again to resume from {len(all_results)} pages."
                )
                raise

            delay = base_delay * (2 ** (retry_count - 1))
            print(
                f"\nAPI error: {e}. Retry {retry_count}/{max_retries} after {delay}s..."
            )
            time.sleep(delay)
            continue

        except HTTPResponseError as e:
            retry_count += 1
            if retry_count > max_retries:
                print(
                    f"\nMax retries ({max_retries}) reached. Progress saved to {PROGRESS_FILE}"
                )
                print(
                    f"You can run the script again to resume from {len(all_results)} pages."
                )
                raise

            delay = base_delay * (2 ** (retry_count - 1))
            print(
                f"\nHTTP error (status {e.status}): {e}. Retry {retry_count}/{max_retries} after {delay}s..."
            )
            time.sleep(delay)
            continue

    # Clean up progress file on successful completion
    if os.path.exists(PROGRESS_FILE):
        try:
            os.remove(PROGRESS_FILE)
            print("Fetch completed successfully. Progress file cleaned up.")
        except OSError:
            pass

    return {
        "object": "list",
        "results": all_results,
        "next_cursor": None,
        "has_more": False,
    }


def get_page_content_hash(page):
    """
    Create a hash of the page's content by serializing all properties.
    This helps identify duplicates by comparing the entire content.
    """

    # TODO: #properties = page.get("title").get("text").get("content")
    # TODO: AttributeError: 'NoneType' object has no attribute  'get'

    # By now we assume 'properties' is a dictionary of all page properties exists
    properties = page["properties"]

    content_parts = []

    for prop_name, prop_value in sorted(properties.items()):
        prop_type = prop_value.get("type")
        value = extract_property_value(prop_value, prop_type)

        if value is not None:
            if isinstance(value, (list, tuple)):
                content_parts.append(
                    f"{prop_name}:{','.join(sorted(str(v) for v in value))}"
                )
            else:
                content_parts.append(f"{prop_name}:{str(value)}")

    content_string = "|".join(sorted(content_parts))
    return hashlib.md5(content_string.encode()).hexdigest()


def extract_property_value(prop, prop_type):
    """Extract the value from a property based on its type"""
    if not prop or prop_type not in prop:
        return None

    if prop_type == "title":
        return (
            "".join([t["plain_text"] for t in prop["title"]]) if prop["title"] else ""
        )
    elif prop_type == "rich_text":
        return (
            "".join([t["plain_text"] for t in prop["rich_text"]])
            if prop["rich_text"]
            else ""
        )
    elif prop_type == "select":
        return prop["select"]["name"] if prop["select"] else None
    elif prop_type == "multi_select":
        return (
            [item["name"] for item in prop["multi_select"]]
            if prop["multi_select"]
            else []
        )
    elif prop_type == "number":
        return prop["number"]
    elif prop_type == "url":
        return prop["url"]
    elif prop_type == "email":
        return prop["email"]
    elif prop_type == "phone_number":
        return prop["phone_number"]
    elif prop_type == "date":
        if prop["date"]:
            return (
                f"{prop['date']['start']}-{prop['date']['end']}"
                if prop["date"]["end"]
                else prop["date"]["start"]
            )
        return None
    elif prop_type == "checkbox":
        return prop["checkbox"]
    elif prop_type == "formula":
        return extract_property_value(prop["formula"], prop["formula"]["type"])
    elif prop_type == "relation":
        return [rel["id"] for rel in prop["relation"]] if prop["relation"] else []
    elif prop_type == "rollup":
        return "rollup_exists"
    elif prop_type == "people":
        return [person["id"] for person in prop["people"]] if prop["people"] else []
    elif prop_type == "files":
        return [file["name"] for file in prop["files"]] if prop["files"] else []
    elif prop_type == "status":
        return prop["status"]["name"] if prop["status"] else None
    else:
        return f"unsupported_{prop_type}"


def get_phone_number(page):
    """Extract phone number from page properties"""
    properties = page.get("properties", {})

    # Try common phone property names
    phone_props = ["Phone", "phone", "Phone Number", "PhoneNumber", "Телефон"]

    for prop_name in phone_props:
        if prop_name in properties:
            prop = properties[prop_name]
            prop_type = prop.get("type")

            if prop_type == "phone_number":
                return prop.get("phone_number", "")
            elif prop_type == "rich_text":
                texts = prop.get("rich_text", [])
                if texts:
                    return texts[0].get("plain_text", "")

    return ""


def normalize_phone(phone):
    """Normalize phone number by removing spaces, dashes, parentheses, etc."""
    if not phone:
        return ""
    # Remove all non-digit characters except +
    normalized = "".join(c for c in phone if c.isdigit() or c == "+")
    return normalized


def find_duplicate_pages(pages):
    """Find duplicate pages by comparing phone numbers and content hashes"""
    phone_groups = defaultdict(list)
    hash_groups = defaultdict(list)

    for page in pages:
        page_title = get_page_title(page)
        phone = get_phone_number(page)
        normalized_phone = normalize_phone(phone)

        page_info = {
            "id": page["id"],
            "title": page_title,
            "phone": phone,
            "created_time": page["created_time"],
            "last_edited_time": page["last_edited_time"],
        }

        # Group by phone number (if exists and not empty)
        if normalized_phone:
            phone_groups[normalized_phone].append(page_info)

        # Also group by content hash as fallback
        try:
            content_hash = get_page_content_hash(page)
            hash_groups[content_hash].append(page_info)
        except (KeyError, AttributeError) as e:
            print(f"Warning: Could not hash page {page_title}: {e}")
            continue

    # Find duplicates by phone number (primary method)
    phone_duplicates = {
        phone: pages for phone, pages in phone_groups.items() if len(pages) > 1
    }

    # Find duplicates by content hash (secondary method)
    hash_duplicates = {
        hash_val: pages for hash_val, pages in hash_groups.items() if len(pages) > 1
    }

    # Merge both duplicate detection methods
    all_duplicates = {}

    # Add phone-based duplicates
    for phone, pages in phone_duplicates.items():
        all_duplicates[f"phone:{phone}"] = pages

    # Add hash-based duplicates (only if not already in phone duplicates)
    for hash_val, pages in hash_duplicates.items():
        page_ids = {p["id"] for p in pages}
        # Check if these pages are already marked as duplicates by phone
        already_found = False
        for dup_pages in phone_duplicates.values():
            if any(p["id"] in page_ids for p in dup_pages):
                already_found = True
                break

        if not already_found:
            all_duplicates[f"hash:{hash_val}"] = pages

    return all_duplicates


def get_page_title(page):
    """Extract page title from properties"""
    properties = page.get("properties", {})

    # Check if 'Name' property exists and has content
    if "Name" in properties:
        name_prop = properties["Name"]
        if name_prop.get("type") == "title" and name_prop.get("title"):
            if name_prop["title"]:  # Check if title array is not empty
                return name_prop["title"][0].get("plain_text", "")

    for _, prop_value in properties.items():
        if prop_value.get("type") == "title" and prop_value.get("title"):
            if prop_value["title"]:
                return prop_value["title"][0].get("plain_text", "")

    return "Untitled"


def delete_page(notion, page_id):
    """Archive a Notion page"""
    notion.pages.update(page_id=page_id, archived=True)


def main():
    """Main function"""
    if not NOTION_TOKEN or not DATABASE_ID:
        print(
            "Error: Please ensure NOTION_TOKEN and NOTION_DATABASE_ID are in your .env file"
        )
        return

    notion = Client(auth=NOTION_TOKEN)

    print("Fetching database result...")
    try:
        result = return_database_chunk(notion, DATABASE_ID).get("results", [])
    except (RequestTimeoutError, APIResponseError, HTTPResponseError) as e:
        print(f"\nError fetching database: {e}")
        print("Progress has been saved. Run the script again to resume.")
        return
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user.")
        print(f"Progress has been saved to {PROGRESS_FILE}")
        print("Run the script again to resume from where you left off.")
        return

    print(f"Found {len(result)} total result")

    if len(result) == 0:
        print("No pages found in the list. Stopping...")
        return

    print("Searching for duplicates...")
    duplicates = find_duplicate_pages(result)

    if not duplicates:
        print("No duplicate result found!")
        return

    total_duplicates = sum(len(pages) - 1 for pages in duplicates.values())
    print(
        f"\nFound {len(duplicates)} groups of duplicates ({total_duplicates} \
          total duplicate pages to delete)"
    )

    print("\nDuplicate groups found:")
    for i, (key, duplicate_pages) in enumerate(duplicates.items(), 1):
        dup_type = "Phone" if key.startswith("phone:") else "Content"
        identifier = key.split(":", 1)[1][:20] if ":" in key else key[:20]
        print(
            f"\nGroup {i} - {dup_type} match ({identifier}...) - {len(duplicate_pages)} duplicates:"
        )
        for page in duplicate_pages:
            phone_info = (
                f" | Phone: {page.get('phone', 'N/A')}" if page.get("phone") else ""
            )
            print(
                f"  - {page['title']}{phone_info} (Created: {page['created_time'][:10]})"
            )

    print(f"\nTotal pages that will be kept: {len(duplicates)}")
    print(f"Total pages that will be deleted: {total_duplicates}")

    # Ask for confirmation before deleting
    confirm = (
        input("\nDo you want to proceed with deletion? (yes/no): ").strip().lower()
    )
    if confirm not in ["yes", "y"]:
        print("Deletion cancelled.")
        return

    print("\nDeleting duplicates...")
    deleted_count = 0

    for key, duplicate_pages in duplicates.items():
        # Sort by created time - keep the oldest one (first created)
        duplicate_pages.sort(key=lambda x: x["created_time"])
        pages_to_delete = duplicate_pages[1:]

        for page in pages_to_delete:
            try:
                delete_page(notion, page["id"])
                deleted_count += 1
                print(
                    f"Deleted: {page['title']} (Created: {page['created_time'][:10]})"
                )
                time.sleep(0.3)  # Rate limiting
            except (RequestTimeoutError, APIResponseError, HTTPResponseError) as e:
                print(f"Failed to delete {page['title']} ({page['id']}): {e}")

    print(f"\nSuccessfully deleted {deleted_count} duplicate pages")
    print("Note: Pages are archived and can be restored from Notion's trash if needed")


if __name__ == "__main__":
    main()


# docker build -f notion/Dockerfile -t notion-app .
