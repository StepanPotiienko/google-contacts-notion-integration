"""Module for fetching the last 5 Gmail messages every 15 minutes."""

import os.path
import time
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None
    if os.path.exists("token_gmail.json"):
        creds = Credentials.from_authorized_user_file("token_gmail.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token_gmail.json", "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def fetch_last_messages(service, n=5):
    """Fetch the last n Gmail messages and print basic info."""

    orders_list: list = []

    try:
        # pylint: disable=E1101
        results = service.users().messages().list(
            userId="me", maxResults=n, labelIds=["INBOX"]
        ).execute()
        messages = results.get("messages", [])

        if not messages:
            print("No messages found.")
            return

        print(f"\nLast {n} messages:")
        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()

            headers = {h["name"]: h["value"] for h in msg_data["payload"]["headers"]}
            subject = headers.get("Subject", "(No subject)")
            sender = headers.get("From", "(Unknown sender)")
            # date = headers.get("Date", "(No date)")

            if sender == 'info@agropride.com.ua' and 'Нове замовлення' in subject:
                orders_list.append([headers])

            # TODO: Check tomorrow if this works.
            print(orders_list)


    except HttpError as error:
        print(f"An error occurred: {error}")


def main():
    """Run the Gmail fetcher every 15 minutes."""
    service = get_gmail_service()
    is_running: bool= True
    # FOR DEBUG: 0. PROD: 900
    # FIXME: DO NOT FORGET TO CHANGE ON PROD
    time_interval: int = 0

    try:
        while is_running:
            fetch_last_messages(service, n=5)
            print("Waiting 15 minutes before next check...\n")

            # FOR DEBUG PURPOSES
            if time_interval == 0:
                break

            time.sleep(time_interval)
    except KeyboardInterrupt:
        print("Stopping...")


if __name__ == "__main__":
    main()
