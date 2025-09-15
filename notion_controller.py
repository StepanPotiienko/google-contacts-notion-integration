""" Notion related stuff """

import os
import dotenv
from notion_client import Client

dotenv.load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
CRM_DATABASE_ID = os.getenv("CRM_DATABASE_ID")
PRODUCTION_DATABASE_ID = os.getenv("PRODUCTION_DATABASE_ID")

NOTION_CLIENT = Client(auth=NOTION_API_KEY)

def connect_to_notion_database():
    """ Connect to a notion database and return tasks list (filtered by Status). """
    tasks_list: list = []

    print("Listing tasks from Notion database...")

    results = NOTION_CLIENT.databases.query(
        database_id=CRM_DATABASE_ID # type: ignore
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


def find_missing_tasks(contacts_list: list):
    """If a task with the name of the client is missing, create it in Notion."""

    results = NOTION_CLIENT.databases.query(database_id=CRM_DATABASE_ID) # type: ignore
    existing_tasks = set()

    for page in results["results"]:  # type: ignore
        props = page["properties"]
        title_prop = props["Name"]["title"]
        title = title_prop[0]["plain_text"] if title_prop else "Untitled"
        existing_tasks.add(title)

    for contact in contacts_list:
        contact_name = contact[0]
        if contact_name not in existing_tasks:
            print(f"Creating new task for: {contact_name}")

            NOTION_CLIENT.pages.create(
                parent={"database_id": CRM_DATABASE_ID},
                properties={
                    "Name": {
                        "title": [
                            {
                                "text": {"content": contact_name}
                            }
                        ]
                    },
                    "Funel": {
                        "status": {"name": "Leads. Чого так мало?"}
                    },
                    "Email": {
                        "email": contact[1]
                    },
                    "Phone": {
                        "phone": contact[2]
                    }
                }
            )

            NOTION_CLIENT.pages.create(
                parent={"database_id": PRODUCTION_DATABASE_ID},
                properties={
                    "Name": {
                        "title": [
                            {
                                "text": {"content": contact_name}
                            }
                        ]
                    },
                    "Status": {
                        "status": {"name": "Нова задача"}
                    },
                    "Relation": {
                        "id": contact_name
                    }
                }
            )
