"""Delete duplicates in Notion database"""

import hashlib
import itertools
import os
import time
from collections import defaultdict

from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_API_KEY")
DATABASE_ID = os.getenv("CRM_DATABASE_ID")

def print_first_n_entries_of_a_dict(n: int, iterable) -> list:
    return list(itertools.islice(iterable, n))

def return_database_chunk(notion, database_id: str) -> dict:
    data = notion.databases.query(database_id)
    database_object = data['object']
    has_more = data['has_more']
    next_cursor = data['next_cursor']

    buffer_size = 300
    buffer = []

    while has_more:
        data_while = notion.databases.query(database_id, start_cursor=next_cursor)

        for row in data_while['results']:
            data['results'].append(row)

        has_more = data_while['has_more']
        next_cursor = data_while['next_cursor']

        print(f"Fetched {len(data['results'])} pages so far...")
        buffer.extend(data['results'])

        if len(buffer) > buffer_size:
            print(f"Buffer is full. Returning {buffer_size} pages... ")
            break

    return {
        "object": database_object,
        "results": data["results"],
        "next_cursor": next_cursor,
        "has_more": has_more
    }


def get_page_content_hash(page):
    """
    Create a hash of the page's content by serializing all properties.
    This helps identify duplicates by comparing the entire content.
    """

    # TODO: #properties = page.get("title").get("text").get("content")
    # TODO: AttributeError: 'NoneType' object has no attribute  'get'

    properties = page.get("title").get("text").get("content")

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


def find_duplicate_pages(pages):
    """Find duplicate pages by comparing content hashes"""
    hash_groups = defaultdict(list)

    for page in pages:
        content_hash = get_page_content_hash(page)
        page_title = get_page_title(page)

        retries = 3
        while retries > 0:
            try:
                page_title = get_page_title(page)
                break
            except Exception as e:
                retries -= 1
                if retries == 0:
                    raise e
            time.sleep(1)
        hash_groups[content_hash].append(
            {
                "id": page["id"],
                "title": page_title,
                "created_time": page["created_time"],
                "last_edited_time": page["last_edited_time"],
            }
        )

    duplicates = {
        hash_val: pages for hash_val, pages in hash_groups.items() if len(pages) > 1
    }
    return duplicates


def get_page_title(page):
    """Extract page title from properties"""
    properties = page.get("properties", {})

    # Check if 'Name' property exists and has content
    if 'Name' in properties:
        name_prop = properties['Name']
        if name_prop.get('type') == 'title' and name_prop.get('title'):
            if name_prop['title']:  # Check if title array is not empty
                return name_prop['title'][0].get('plain_text', '')

    for prop_name, prop_value in properties.items():
        if prop_value.get('type') == 'title' and prop_value.get('title'):
            if prop_value['title']:
                return prop_value['title'][0].get('plain_text', '')

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
    result = return_database_chunk(notion, DATABASE_ID).get("results", [])

    # LOGIC
    # Work with a slice from the database
    # Archive duplicates
    # Move on to the next chunk

    print(f"Found {len(result)} total result")

    print(print_first_n_entries_of_a_dict(15, result))

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
          total duplicate result to delete)"
    )

    print("\nDuplicate groups found:")
    for i, (hash_val, duplicate_pages) in enumerate(duplicates.items(), 1):
        print(f"\nGroup {i} ({len(duplicate_pages)} duplicates):")
        for page in duplicate_pages:
            print(
                f"  - {page['title']} (ID: {page['id']}, Created: {page['created_time'][:10]})"
            )

    print(f"\nTotal result that will be kept: {len(duplicates)}")
    print(f"Total result that will be deleted: {total_duplicates}")

    print("\nDeleting duplicates...")
    deleted_count = 0

    for hash_val, duplicate_pages in duplicates.items():
        duplicate_pages.sort(key=lambda x: x["created_time"])
        pages_to_delete = duplicate_pages[1:]

        for page in pages_to_delete:
            try:
                delete_page(notion, page["id"])
                deleted_count += 1
                print(f"Deleted: {page['title']} (ID: {page['id']})")
            except Exception as e:
                print(f"Error deleting page {page['id']}: {e}")

    print(f"\nSuccessfully deleted {deleted_count} duplicate result")
    print("Note: Pages are archived and can be restored from Notion's trash if needed")


if __name__ == "__main__":
    main()
