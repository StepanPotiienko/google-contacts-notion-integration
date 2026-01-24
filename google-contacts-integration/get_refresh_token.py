"""Helper script to generate a Google OAuth refresh token for Contacts scope."""

import os

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]


def main():
    """Run a one-time OAuth flow and print the refresh token."""
    load_dotenv()
    client_id = os.getenv("GOOGLE_CLIENT_ID") or None
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET") or None

    if client_id is None or client_secret is None:
        raise SystemExit(
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables first."
        )

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [
                "http://localhost",
                "urn:ietf:wg:oauth:2.0:oob",
            ],
        }
    }

    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=SCOPES,
    )

    creds = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )

    with open("sync_token.txt", "w", encoding="UTF-8") as sync_token_file:
        sync_token_file.write(str(creds.refresh_token))
        print("Refresh token saved to sync_token.txt.")

    # TODO: Updating .env file does not work.
    os.environ.update({"GOOGLE_REFRESH_TOKEN": str(creds.refresh_token)})
    print(".env file was updated.")


if __name__ == "__main__":
    main()
