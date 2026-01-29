"""Main logic of AgroprideOS"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import notion_controller


_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

load_dotenv()
SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]
SYNC_TOKEN_FILE = "sync_token.txt"
CONTACTS_FILE = "contacts_to_sync.json"
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


def update_sync_token(token: Optional[str] = None) -> Optional[str]:
    """Save sync token to file or retrieve existing one."""
    if token is not None:
        # Validate token before saving
        if not token or not isinstance(token, str):
            print(f"Warning: Invalid sync token received: {token}")
            return None

        try:
            with open(SYNC_TOKEN_FILE, "w", encoding="UTF-8") as f:
                f.write(token)
            print("Sync token saved successfully")
        except IOError as e:
            print(f"Error saving sync token: {e}")
        return None

    if os.path.exists(SYNC_TOKEN_FILE):
        try:
            with open(SYNC_TOKEN_FILE, "r", encoding="UTF-8") as f:
                token = f.read().strip()
                if token:
                    print("Using existing sync token")
                    return token
                print("Sync token file is empty")
        except IOError as e:
            print(f"Error reading sync token: {e}")

    return None


def full_sync(service):
    """Perform a full sync and update local token."""
    print("Performing full sync...")
    results = _fetch_connections(service, request_sync_token=True)

    total_contacts = 0
    for person in results.get("connections", []):
        handle_person(person)
        total_contacts += 1

    print(f"Fetched {total_contacts} contacts...")

    while "nextPageToken" in results:
        results = _fetch_connections(
            service,
            request_sync_token=True,
            page_token=results["nextPageToken"],
        )
        page_count = len(results.get("connections", []))
        for person in results.get("connections", []):
            handle_person(person)
        total_contacts += page_count
        print(f"Fetched {total_contacts} contacts...")

    next_token = results.get("nextSyncToken")
    if next_token:
        update_sync_token(next_token)
        print(f"Full sync complete. Total: {total_contacts} contacts. Token updated.")


def incremental_sync(service, token: str):
    """Perform incremental sync with stored token. Returns True if changes were found."""
    print("Checking for changes...")
    try:
        results = _fetch_connections(service, sync_token=token)
        changes_found = False

        if "connections" in results:
            print(f"Found {len(results['connections'])} changed contacts")
            for person in results["connections"]:
                handle_person(person)
            changes_found = True

        while "nextPageToken" in results:
            results = _fetch_connections(
                service,
                sync_token=token,
                page_token=results["nextPageToken"],
            )
            if "connections" in results:
                for person in results["connections"]:
                    handle_person(person)
                changes_found = True

        new_token = results.get("nextSyncToken")
        if new_token and new_token != token:
            update_sync_token(new_token)
            print("Incremental sync complete. Token updated.")
        else:
            print("Incremental sync complete. No token update needed.")

        return changes_found

    except HttpError as e:
        if e.resp.status in (400, 410):  # invalid/expired sync token
            print("Sync token expired or invalid. Running full sync...")
            if os.path.exists(SYNC_TOKEN_FILE):
                os.remove(SYNC_TOKEN_FILE)
            full_sync(service)
            return True  # Full sync implies changes
        else:
            raise


def _fetch_connections(
    service,
    sync_token: Optional[str] = None,
    page_token: Optional[str] = None,
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


def save_contacts_to_file():
    """Save contacts_list to a JSON file for inter-process persistence."""
    try:
        with open(CONTACTS_FILE, "w", encoding="UTF-8") as f:
            json.dump(contacts_list, f)
        if contacts_list:
            print(f"Saved {len(contacts_list)} contacts to {CONTACTS_FILE}")
    except IOError as e:
        print(f"Error saving contacts: {e}")


def load_contacts_from_file() -> list[list[str]]:
    """Load contacts from file if it exists."""
    if os.path.exists(CONTACTS_FILE):
        try:
            with open(CONTACTS_FILE, "r", encoding="UTF-8") as f:
                loaded = json.load(f)
                if loaded:
                    print(f"Loaded {len(loaded)} contacts from {CONTACTS_FILE}")
                    return loaded
        except IOError as e:
            print(f"Error loading contacts: {e}")
    return []


def main():
    """Run the script"""
    parser = argparse.ArgumentParser(description="Google Contacts ↔ Notion sync")
    parser.add_argument(
        "--phase",
        choices=["google-sync", "dedup", "contacts", "all"],
        default="all",
        help="Which part to run",
    )
    parser.add_argument(
        "--dedup-max-minutes",
        type=int,
        default=int(os.environ.get("DEDUP_MAX_MINUTES", "0") or 0),
        help="Timebox Notion duplicate cleanup to N minutes (0 = unlimited)",
    )
    args = parser.parse_args()
    try:
        creds = get_credentials()
        service = build("people", "v1", credentials=creds)

        changes_detected = False

        # Phase: Google contacts sync
        if args.phase in ("google-sync", "all"):
            token = update_sync_token()
            if token:
                changes_detected = incremental_sync(service, token)
            else:
                full_sync(service)
                changes_detected = True

            # Save contacts to file for inter-process persistence
            save_contacts_to_file()

        # Small pause to be gentle with rate limits
        if args.phase == "all":
            time.sleep(2)

        # Phase: Notion duplicate cleanup (by Name in CRM DB)
        # Skip if no changes detected during incremental sync
        if args.phase in ("dedup", "all") and os.environ.get("CRM_DATABASE_ID"):
            if args.phase == "all" and not changes_detected:
                print("No Google changes detected. Skipping dedup phase.")
            else:
                notion_controller.delete_name_duplicates(
                    database_id=os.environ["CRM_DATABASE_ID"],
                    max_minutes=(
                        args.dedup_max_minutes if args.dedup_max_minutes > 0 else None
                    ),
                )

        # Phase: contacts push into Notion
        if args.phase in ("contacts", "all"):
            # Load contacts from file if running as separate phase
            if args.phase == "contacts":
                contacts_list.extend(load_contacts_from_file())

            contacts_to_create = notion_controller.delete_duplicates_in_database(
                database_id=os.environ.get("CRM_DATABASE_ID", ""),
                contacts_list=contacts_list,
            )
            notion_controller.find_missing_tasks(contacts_to_create)

            # Clean up contacts file after processing
            if os.path.exists(CONTACTS_FILE):
                os.remove(CONTACTS_FILE)

    except Exception as e:
        print(f"Script failed with error: {e}")
        raise


if __name__ == "__main__":
    main()
