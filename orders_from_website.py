"""Notify the user when a new order is placed"""

import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]
TOKEN_FILE = "sync_token.txt"


def get_google_service():
    """Authenticate and return Google People API service."""
    creds_info = {
        "token": os.getenv("GOOGLE_TOKEN"),
        "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN"),
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "token_uri": os.getenv(
            "GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"
        ),
    }

    creds = Credentials.from_authorized_user_info(creds_info, SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds.valid:
        raise RuntimeError("❌ Google credentials invalid even after refresh")

    return build("people", "v1", credentials=creds)


def load_sync_token():
    """Load sync token from file if available."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="UTF-8") as f:
            return f.read().strip()
    return None


def save_sync_token(token: str):
    """Save sync token to file."""
    if token:
        with open(TOKEN_FILE, "w", encoding="UTF-8") as f:
            f.write(token)
        print("💾 Saved new sync token.")


def delete_sync_token():
    """Delete expired sync token file."""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
        print("🗑️ Deleted expired sync token.")


def incremental_sync(service, sync_token: str | None):
    """
    Perform incremental sync if token available,
    otherwise perform full sync.
    """
    try:
        if sync_token:
            print("🔄 Running incremental sync...")
            results = (
                service.people()
                .connections()
                .list(
                    resourceName="people/me",
                    personFields="metadata,names,emailAddresses,phoneNumbers",
                    syncToken=sync_token,
                )
                .execute()
            )
        else:
            print("📥 Running full sync (no token)...")
            results = (
                service.people()
                .connections()
                .list(
                    resourceName="people/me",
                    personFields="metadata,names,emailAddresses,phoneNumbers",
                )
                .execute()
            )

        return results

    except HttpError as err:
        if err.resp.status == 400 and "EXPIRED_SYNC_TOKEN" in str(err):
            print("⚠️ Sync token expired. Resetting...")
            delete_sync_token()
            # Retry with full sync
            results = (
                service.people()
                .connections()
                .list(
                    resourceName="people/me",
                    personFields="metadata,names,emailAddresses,phoneNumbers",
                )
                .execute()
            )
            return results
        else:
            raise


def main():
    """Run the script"""
    service = get_google_service()
    sync_token = load_sync_token()

    results = incremental_sync(service, sync_token)

    connections = results.get("connections", [])
    print(f"✅ Synced {len(connections)} contacts.")

    new_token = results.get("nextSyncToken")
    save_sync_token(new_token)


if __name__ == "__main__":
    main()
