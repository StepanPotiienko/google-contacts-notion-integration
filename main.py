""" Main logic of AgroprideOS """

import os
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import notion_controller

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]
SYNC_TOKEN_FILE = "sync_token.txt"

contacts_list = []


def get_credentials():
    """Load credentials from environment variables (no JSON files)."""
    google_creds = Credentials(
        None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=SCOPES,
    )

    if not google_creds.valid or google_creds.expired:
        google_creds.refresh(Request())

    return google_creds


def update_sync_token(token: str | None = None) -> str | None:
    """Either write to a file if token exists, or read from a file."""
    if token is not None:
        with open(SYNC_TOKEN_FILE, "w", encoding="UTF-8") as f:
            f.write(token)
            return None
    else:
        if os.path.exists(SYNC_TOKEN_FILE):
            with open(SYNC_TOKEN_FILE, "r", encoding="UTF-8") as f:
                return f.read().strip()
        return None


def full_sync(sync_service):
    """Perform a full sync and store the sync token."""
    print("Performing full sync...")
    results = (
        sync_service.people()
        .connections()
        .list(
            resourceName="people/me",
            personFields="metadata,names,emailAddresses,phoneNumbers",
            requestSyncToken=True,
        )
        .execute()
    )

    for person in results.get("connections", []):
        get_contacts_list(person)

    while "nextPageToken" in results:
        results = (
            sync_service.people()
            .connections()
            .list(
                resourceName="people/me",
                personFields="metadata,names,emailAddresses,phoneNumbers",
                requestSyncToken=True,
                pageToken=results["nextPageToken"],
            )
            .execute()
        )
        for person in results.get("connections", []):
            get_contacts_list(person)

    next_sync_token = results.get("nextSyncToken")
    if next_sync_token:
        update_sync_token(next_sync_token)


def incremental_sync(sync_service, google_sync_token):
    """Fetch changes since last sync."""
    print("Checking for changes...")
    try:
        results = (
            sync_service.people()
            .connections()
            .list(
                resourceName="people/me",
                personFields="metadata,names,emailAddresses,phoneNumbers",
                syncToken=google_sync_token,
            )
            .execute()
        )

        if "connections" in results:
            for person in results["connections"]:
                handle_person(person)

        while "nextPageToken" in results:
            results = (
                sync_service.people()
                .connections()
                .list(
                    resourceName="people/me",
                    personFields="metadata,names,emailAddresses,phoneNumbers",
                    syncToken=google_sync_token,
                    pageToken=results["nextPageToken"],
                )
                .execute()
            )
            if "connections" in results:
                for person in results["connections"]:
                    handle_person(person)

        new_token = results.get("nextSyncToken")
        if new_token:
            update_sync_token(new_token)

    except HttpError as e:
        if e.resp.status == 410:
            print("Sync token expired. Running full sync...")
            full_sync(sync_service)
        else:
            raise


def handle_person(person):
    """Checks if the contact is deleted or not."""
    metadata = person.get("metadata", {})
    if metadata.get("deleted"):
        print("Deleted contact:", person.get("resourceName"))
    else:
        get_contacts_list(person)


def get_contacts_list(person):
    """Nicely outputs contact info."""
    names = person.get("names", [])
    emails = person.get("emailAddresses", [])
    phones = person.get("phoneNumbers", [])

    display_name = names[0].get("displayName") if names else "Unnamed"
    email = emails[0].get("value") if emails else "No email"
    phone = phones[0].get("value") if phones else "No phone"

    contacts_list.append([display_name, email, phone])


if __name__ == "__main__":
    creds = get_credentials()
    service = build("people", "v1", credentials=creds)

    sync_token = update_sync_token()
    if sync_token:
        incremental_sync(service, sync_token)
    else:
        full_sync(service)

    notion_controller.connect_to_notion_database()
    notion_controller.find_missing_tasks(contacts_list)
