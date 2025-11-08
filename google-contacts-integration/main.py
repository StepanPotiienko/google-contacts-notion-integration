"""Main logic of AgroprideOS"""

import os
import time
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import notion.notion_controller as notion_controller

load_dotenv()
SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]
SYNC_TOKEN_FILE = "sync_token.txt"
contacts_list: list[list[str]] = []


def get_credentials():
    """Retrieve or refresh Google API credentials."""
    required_env = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"]
    for var in required_env:
        if not os.environ.get(var):
            raise ValueError(f"Missing required environment variable: {var}")

    creds = Credentials(
        None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=SCOPES,
    )

    if not creds.valid or creds.expired:
        creds.refresh(Request())

    return creds


def update_sync_token(token: str | None = None) -> str | None:
    """Save sync token to file or retrieve existing one."""
    if token is not None:
        # Validate token before saving
        if not token or not isinstance(token, str):
            print(f"Warning: Invalid sync token received: {token}")
            return None

        try:
            with open(SYNC_TOKEN_FILE, "w", encoding="UTF-8") as f:
                f.write(token)
            print(f"Sync token saved successfully")
        except IOError as e:
            print(f"Error saving sync token: {e}")
        return None

    if os.path.exists(SYNC_TOKEN_FILE):
        try:
            with open(SYNC_TOKEN_FILE, "r", encoding="UTF-8") as f:
                token = f.read().strip()
                if token:
                    print(f"Using existing sync token")
                    return token
                print("Sync token file is empty")
        except IOError as e:
            print(f"Error reading sync token: {e}")

    return None


def full_sync(service):
    """Perform a full sync and update local token."""
    print("Performing full sync...")
    results = _fetch_connections(service, request_sync_token=True)

    for person in results.get("connections", []):
        handle_person(person)

    while "nextPageToken" in results:
        results = _fetch_connections(
            service,
            request_sync_token=True,
            page_token=results["nextPageToken"],
        )
        for person in results.get("connections", []):
            handle_person(person)

    next_token = results.get("nextSyncToken")
    if next_token:
        update_sync_token(next_token)
        print("Full sync complete. Token updated.")


def incremental_sync(service, token: str):
    """Perform incremental sync with stored token."""
    print("Checking for changes...")
    try:
        results = _fetch_connections(service, sync_token=token)

        if "connections" in results:
            print(f"Found {len(results['connections'])} changed contacts")
            for person in results["connections"]:
                handle_person(person)

        while "nextPageToken" in results:
            results = _fetch_connections(
                service,
                sync_token=token,
                page_token=results["nextPageToken"],
            )
            if "connections" in results:
                for person in results["connections"]:
                    handle_person(person)

        new_token = results.get("nextSyncToken")
        if new_token and new_token != token:
            update_sync_token(new_token)
            print("Incremental sync complete. Token updated.")
        else:
            print("Incremental sync complete. No token update needed.")

    except HttpError as e:
        if e.resp.status in (400, 410):  # invalid/expired sync token
            print("Sync token expired or invalid. Running full sync...")
            # Delete the old token file
            if os.path.exists(SYNC_TOKEN_FILE):
                os.remove(SYNC_TOKEN_FILE)
            full_sync(service)
        else:
            raise


def _fetch_connections(
    service,
    sync_token: str | None = None,
    page_token: str | None = None,
    request_sync_token: bool = False,
):
    """Request Google People connections with correct params."""
    return (
        service.people()
        .connections()
        .list(
            resourceName="people/me",
            personFields="metadata,names,emailAddresses,phoneNumbers",
            syncToken=sync_token,
            pageToken=page_token,
            requestSyncToken=request_sync_token,
        )
        .execute()
    )


def handle_person(person: dict):
    """Process a person record: add or mark deleted."""
    metadata = person.get("metadata", {})
    if metadata.get("deleted"):
        print(f"Deleted contact: {person.get('resourceName')}")
    else:
        get_contacts_list(person)


def get_contacts_list(person: dict):
    """Extract name, email, and phone into contacts_list."""
    names = person.get("names", [])
    emails = person.get("emailAddresses", [])
    phones = person.get("phoneNumbers", [])

    display_name = names[0].get("displayName") if names else "Unnamed"
    email = emails[0].get("value") if emails else "No email"
    phone = phones[0].get("value") if phones else "No phone"

    contacts_list.append([display_name, email, phone])


def main():
    """Run the script"""
    try:
        creds = get_credentials()
        service = build("people", "v1", credentials=creds)

        token = update_sync_token()
        if token:
            incremental_sync(service, token)
        else:
            full_sync(service)

        time.sleep(2)

        notion_controller.delete_duplicates_in_database(
            database_id=os.environ["CRM_DATABASE_ID"],
            contacts_list=contacts_list,
        )
        notion_controller.connect_to_notion_database()
        notion_controller.find_missing_tasks(contacts_list)

    except Exception as e:
        print(f"Script failed with error: {e}")
        raise


if __name__ == "__main__":
    main()
