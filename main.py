""" Main logic of AgroprideOS """

import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import notion_controller


SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]
SYNC_TOKEN_FILE = "sync_token.txt"


def get_credentials():
    """ Grab credentials from Google API, and write them to a file. """
    google_creds = None
    if os.path.exists("token.json"):
        google_creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not google_creds or not google_creds.valid:
        if google_creds and google_creds.expired and google_creds.refresh_token:
            google_creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            google_creds = flow.run_local_server(port=0)
        with open("token.json", "w", encoding="UTF-8") as token:
            token.write(google_creds.to_json())
    return google_creds


def load_sync_token():
    """ Loads sync token from a file. """
    # FIXME: Merge load_sync_token() and save_sync_token() into one function. # pylint: disable=fixme
    if os.path.exists(SYNC_TOKEN_FILE):
        with open(SYNC_TOKEN_FILE, "r", encoding="UTF-8") as f:
            return f.read().strip()
    return None


def save_sync_token(token: str):
    """ Saves sync token to a file. """
    with open(SYNC_TOKEN_FILE, "w", encoding="UTF-8") as f:
        f.write(token)


def full_sync(sync_service):
    """Perform a full sync and store the sync token."""
    print("Performing full sync...")
    results = (
        sync_service.people()
        .connections()
        .list(
            resourceName="people/me",
            personFields="metadata,names,emailAddresses",
            requestSyncToken=True,
        )
        .execute()
    )

    for person in results.get("connections", []):
        print_contact("Initial sync", person)

    while "nextPageToken" in results:
        results = (
            sync_service.people()
            .connections()
            .list(
                resourceName="people/me",
                personFields="metadata,names,emailAddresses",
                requestSyncToken=True,
                pageToken=results["nextPageToken"],
            )
            .execute()
        )
        for person in results.get("connections", []):
            print_contact("Initial sync", person)

    next_sync_token = results.get("nextSyncToken")
    if next_sync_token:
        save_sync_token(next_sync_token)


def incremental_sync(sync_service, google_sync_token):
    """Fetch changes since last sync."""
    print("Checking for changes...")
    try:
        results = (
            sync_service.people()
            .connections()
            .list(
                resourceName="people/me",
                personFields="metadata,names,emailAddresses",
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
                    personFields="metadata,names,emailAddresses",
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
            save_sync_token(new_token)

    except HttpError as e:
        if e.resp.status == 410:
            print("Sync token expired. Running full sync...")
            full_sync(sync_service)
        else:
            raise


def handle_person(person):
    """ Checks if the contact is deleted or not. """
    metadata = person.get("metadata", {})
    if metadata.get("deleted"):
        print("Deleted contact:", person.get("resourceName"))
    else:
        print_contact("Changed contact", person)


def print_contact(prefix, person):
    """ Nicely outputs contact info. """
    # FIXME: Add contacts to a list to then compare with tasks list. # pylint: disable=fixme
    # This way I can check if the task has already been created.
    names = person.get("names", [])
    emails = person.get("emailAddresses", [])
    display_name = names[0].get("displayName") if names else "Unnamed"
    email = emails[0].get("value") if emails else "No email"
    print(f"{prefix}: {display_name} <{email}>")



if __name__ == "__main__":
    creds = get_credentials()
    service = build("people", "v1", credentials=creds)

    sync_token = load_sync_token()
    if sync_token:
        incremental_sync(service, sync_token)
    else:
        full_sync(service)

    notion_controller.connect_to_notion_database()
