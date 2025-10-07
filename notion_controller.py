"""Notion related stuff"""

import os
import time
import dotenv
from notion_client import Client
from notion_client.errors import RequestTimeoutError

dotenv.load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
CRM_DATABASE_ID = os.getenv("CRM_DATABASE_ID")
PRODUCTION_DATABASE_ID = os.getenv("PRODUCTION_DATABASE_ID")

# Configure client with longer timeout and retry settings
NOTION_CLIENT = Client(
    auth=NOTION_API_KEY, timeout=30  # 30 seconds timeout instead of default
)


def notion_request_with_retry(func, max_retries=3, delay=2):
    """Wrapper function to retry Notion API calls with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func()
        except RequestTimeoutError as e:
            if attempt == max_retries - 1:
                raise e
            print(
                f"Notion API request failed (attempt {attempt + 1}/{max_retries}): {e}"
            )
            time.sleep(delay * (2**attempt))


def connect_to_notion_database():
    """Connect to a notion database and return tasks list (filtered by Status)."""
    tasks_list: list = []

    print("Listing tasks from Notion database...")

    def query_database():
        return NOTION_CLIENT.databases.query(database_id=CRM_DATABASE_ID)  # type: ignore

    results = notion_request_with_retry(query_database)

    for page in results["results"]:  # type: ignore
        props = page["properties"]
        title_prop = props["Name"]["title"]
        title = title_prop[0]["plain_text"] if title_prop else "Untitled"
        tasks_list.append(title)

    return tasks_list


def get_title_property_name(database_id):
    """Parse the name of the property."""

    def retrieve_database():
        return NOTION_CLIENT.databases.retrieve(database_id=database_id)

    db = notion_request_with_retry(retrieve_database)
    for prop_name, prop in db["properties"].items():  # type: ignore
        if prop["type"] == "title":
            return prop_name
    raise ValueError("No title property found in database")


def debug_database_schema(database_id):
    """Display properties of a database with the database_id."""

    def retrieve_database():
        return NOTION_CLIENT.databases.retrieve(database_id=database_id)

    db = notion_request_with_retry(retrieve_database)
    print("Database schema:")
    for name, prop in db["properties"].items():  # type: ignore
        print(f"- {name}: {prop['type']}")


def delete_duplicates_in_database(database_id: str | None, contacts_list: list) -> list:
    """
    Check whether a page with the given title already exists in the specified database.
    Returns True if found, otherwise False.
    """
    for contact in contacts_list[
        :
    ]:  # Use slice copy to avoid modification during iteration

        def query_contact():
            return NOTION_CLIENT.databases.query(
                database_id=database_id,  # type: ignore
                filter={
                    "property": "Name",
                    "title": {"equals": contact[0]},
                },
            )

        response = notion_request_with_retry(query_contact)

        if len(response.get("results", [])) > 0:  # type: ignore
            contacts_list.remove(contact)
            print("Removed:", contact[0])

    return contacts_list


def find_missing_tasks(contacts_list: list):
    """Create a page for a new contact"""
    print("Creating pages for the tasks...")

    # Get all existing tasks in one go
    def query_all_pages():
        all_results = []
        has_more = True
        start_cursor = None

        while has_more:
            query_params = {"database_id": CRM_DATABASE_ID, "page_size": 100}
            if start_cursor:
                query_params["start_cursor"] = start_cursor

            response = notion_request_with_retry(
                lambda: NOTION_CLIENT.databases.query(**query_params)
            )

            all_results.extend(response["results"])  # type: ignore
            has_more = response.get("has_more", False)  # type: ignore
            start_cursor = response.get("next_cursor")  # type: ignore

        return all_results

    all_pages = notion_request_with_retry(query_all_pages)
    existing_tasks = set()

    for page in all_pages:  # type: ignore
        props = page["properties"]
        title_prop = props["Name"]["title"]
        title = title_prop[0]["plain_text"] if title_prop else "Untitled"
        existing_tasks.add(title)

    new_contacts = [
        contact for contact in contacts_list if contact[0] not in existing_tasks
    ]

    print(f"Found {len(new_contacts)} new contacts to create")

    for contact in new_contacts:
        contact_name = contact[0]
        print(f"Creating new task for: {contact_name}")

        def create_page():
            return NOTION_CLIENT.pages.create(
                parent={"database_id": CRM_DATABASE_ID},
                properties={
                    "Name": {"title": [{"text": {"content": contact_name}}]},
                    "Email": {
                        "email": contact[1] if contact[1] != "No email" else None
                    },
                    "Phone": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": (
                                        contact[2] if contact[2] != "No phone" else ""
                                    )
                                }
                            }
                        ]
                    },
                },
            )

        notion_request_with_retry(create_page)
