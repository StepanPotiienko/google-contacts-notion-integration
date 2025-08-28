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
    """ Connect to a notion database (id is loaded from JSON) and return tasks list. """
    tasks_list: list = []

    print("Listing tasks from Notion database...")

    results = NOTION_CLIENT.databases.query(database_id=database_id)

    for page in results["results"]: # type: ignore
        props = page["properties"]

        title_prop = props["Name"]["title"]
        title = title_prop[0]["plain_text"] if title_prop else "Untitled"

        tasks_list.append(title)

    return tasks_list
