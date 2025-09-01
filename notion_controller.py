""" Notion related stuff """

import json
from notion_client import Client

with open("notion_api.json", "r", encoding="UTF-8") as file:
    data = json.load(file)
    notion_token = data["token"]
    database_id = data["database_id"]

if not notion_token:
    raise ValueError("ERROR: Notion token is not valid.")

NOTION_CLIENT = Client(auth=notion_token)

def connect_to_notion_database():
    """ Connect to a notion database and return tasks list (filtered by Status). """
    tasks_list: list = []

    print("Listing tasks from Notion database...")

    results = NOTION_CLIENT.databases.query(
        database_id=database_id,
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

    print(tasks_list)
    return tasks_list


def find_missing_tasks(contacts_list: list):
    """If a task with the name of the client is missing, create it in Notion."""

    results = NOTION_CLIENT.databases.query(database_id=database_id)
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
                parent={"database_id": database_id},
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
                    # Optional: also store email if you have a property for it
                    # "Email": {
                    #     "email": contact[1]
                    # }
                }
            )
