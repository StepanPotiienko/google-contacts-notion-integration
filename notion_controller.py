"""Notion related stuff"""

import os
import dotenv
from notion_client import Client

dotenv.load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
CRM_DATABASE_ID = os.getenv("CRM_DATABASE_ID")
PRODUCTION_DATABASE_ID = os.getenv("PRODUCTION_DATABASE_ID")

NOTION_CLIENT = Client(auth=NOTION_API_KEY)


def connect_to_notion_database():
    """Connect to a notion database and return tasks list (filtered by Status)."""
    tasks_list: list = []

    print("Listing tasks from Notion database...")

    results = NOTION_CLIENT.databases.query(
        database_id=CRM_DATABASE_ID  # type: ignore
        # In case I need to filter something.
        # filter={
        #     "property": "Status",
        #     "status": {
        #         "equals": "Name of the property"
        #     }
        # }
    )

    for page in results["results"]:  # type: ignore
        props = page["properties"]
        title_prop = props["Name"]["title"]
        title = title_prop[0]["plain_text"] if title_prop else "Untitled"
        tasks_list.append(title)

    return tasks_list


def get_title_property_name(database_id):
    """Parse the name of the property."""
    db = NOTION_CLIENT.databases.retrieve(database_id=database_id)
    for prop_name, prop in db["properties"].items():  # type: ignore
        if prop["type"] == "title":
            return prop_name
    raise ValueError("No title property found in database")


def debug_database_schema(database_id):
    """Display properties of a database with the database_id."""
    db = NOTION_CLIENT.databases.retrieve(database_id=database_id)
    print("Database schema:")
    for name, prop in db["properties"].items():  # type: ignore
        print(f"- {name}: {prop['type']}")


def page_exists_in_database(database_id: str, page_name: str) -> bool:
    """
    Check whether a page with the given title already exists in the specified database.
    Returns True if found, otherwise False.
    """
    try:
        response = NOTION_CLIENT.databases.query(
            database_id=database_id,
            filter={
                "property": "Name",  # must match the title property in your DB
                "title": {"equals": page_name},
            },
        )
        return len(response.get("results", [])) > 0  # type: ignore
    except Exception as e:
        print(f"Error while checking for existing page: {e}")
        return False


def find_missing_tasks(contacts_list: list):
    """If a task with the name of the client is missing, create it in Notion."""
    print("Creating pages for the tasks...")

    results = NOTION_CLIENT.databases.query(database_id=CRM_DATABASE_ID)  # type: ignore
    existing_tasks = set()

    debug_database_schema(database_id=CRM_DATABASE_ID)

    for page in results["results"]:  # type: ignore
        props = page["properties"]
        title_prop = props["Name"]["title"]
        title = title_prop[0]["plain_text"] if title_prop else "Untitled"
        existing_tasks.add(title)

        for contact in contacts_list:
            contact_name = contact[0]

            if page_exists_in_database(CRM_DATABASE_ID, contact_name):  # type: ignore
                print(f"Task already exists for: {contact_name}")
                continue

            print(f"Creating new task for: {contact_name}")
            crm_page = NOTION_CLIENT.pages.create(
                parent={"database_id": CRM_DATABASE_ID},
                properties={
                    "Name": {"title": [{"text": {"content": contact_name}}]},
                    "Funel": {"status": {"name": "Leads. Чого так мало?"}},
                    "Email": {
                        "email": contact[1] if contact[1] != "No email" else None
                    },
                    "Phone": {
                        "phone_number": contact[2] if contact[2] != "No phone" else None
                    },
                },
            )
            CRM_PAGE_ID = crm_page["id"]  # type: ignore

            # TODO: Implement adding a task to Production database.
            # print("Creating a page in Production Tasks database...")
            # NOTION_CLIENT.pages.create(
            #     parent={"database_id": PRODUCTION_DATABASE_ID},
            #     properties={
            #         "Name": {
            #             "title": [
            #                 {
            #                     "text": {"content": contact_name}
            #                 }
            #             ]
            #         },
            #         "Status": {
            #             "status": {"name": "Нова задача"}
            #         },
            #         "Relation": [{
            #             "id": crm_page_id
            #         }]
            #     }
            # )
