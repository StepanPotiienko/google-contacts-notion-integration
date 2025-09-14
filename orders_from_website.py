"""Module for fetching Gmail messages and notifying via Telegram about new orders."""

import os
import time
import requests
import dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

dotenv.load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DEBUG = False

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_message(text: str):
    """Send a message to the user via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Missing Telegram credentials. Check your .env or GitHub Secrets.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"❌ Failed to send Telegram message: {response.text}")
    except requests.RequestException as e:
        print(f"❌ Telegram request failed: {e}")


def get_gmail_service():
    """Connect to Gmail API."""
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


def fetch_last_messages(service, n=5, seen_ids=None):
    """Fetch the last n Gmail messages and notify about new orders."""
    if seen_ids is None:
        seen_ids = set()

    try:
        results = service.users().messages().list(
            userId="me", maxResults=n, labelIds=["INBOX"]
        ).execute()
        messages = results.get("messages", [])

        if not messages:
            print("📭 No messages found.")
            return seen_ids

        for msg in messages:
            if msg["id"] in seen_ids:
                continue  # Skip already processed messages

            msg_data = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()

            headers = {h["name"]: h["value"] for h in msg_data["payload"]["headers"]}
            subject = headers.get("Subject", "(No subject)")
            sender = headers.get("From", "(Unknown sender)")

            if sender == "info@agropride.com.ua" and "Нове замовлення" in subject:
                text = f"📩 New Order!\nFrom: {sender}\nSubject: {subject}"
                print(text)
                send_telegram_message(text)

            seen_ids.add(msg["id"])

        return seen_ids

    except (HttpError, BrokenPipeError) as error:
        print(f"⚠️ Connection error: {error}. Retrying in 5s...")
        time.sleep(5)
        return seen_ids


def main():
    """Run the Gmail fetcher every 15 minutes and notify on new orders."""
    service = get_gmail_service()
    seen_ids: set = set()

    # FOR DEBUG: 5s. PROD: 900s (15 minutes)
    time_interval: int = 5 if DEBUG else 900

    try:
        while True:
            seen_ids = fetch_last_messages(service, n=5, seen_ids=seen_ids)
            print("⏳ Waiting before next check...\n")

            if DEBUG:
                break

            time.sleep(time_interval)
    except KeyboardInterrupt:
        print("🛑 Stopping...")


if __name__ == "__main__":
    main()
