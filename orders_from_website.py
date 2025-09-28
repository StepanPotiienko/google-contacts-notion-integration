"""Module for fetching Gmail messages and notifying via Telegram about new orders."""

import os
import ssl
import time
import base64
import requests
import dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

dotenv.load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_IDS_FILE = "seen_ids.txt"
SEEN_ORDERS_FILE = "seen_orders.txt"


def load_set(filename: str) -> set:
    """Load seen_ids and seen_orders"""
    if not os.path.exists(filename):
        return set()
    with open(filename, "r", encoding="UTF-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_set(filename: str, data: set):
    """Save seen_ids_ and seen_orders to a file"""
    with open(filename, "w", encoding="UTF-8") as f:
        for item in data:
            f.write(item + "\n")


def send_telegram_message(text: str):
    """Send a message to multiple Telegram chats via bot."""
    if not check_telegram_credentials():
        return

    chat_ids = [cid.strip() for cid in str(TELEGRAM_CHAT_ID).split(",") if cid.strip()]
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    for chat_id in chat_ids:
        payload = {"chat_id": chat_id, "text": text}
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                print(f"❌ Failed to send message to {chat_id}: {response.text}")
        except requests.RequestException as e:
            print(f"❌ Telegram request failed for {chat_id}: {e}")


def check_telegram_credentials():
    """Check whether Bot Token and Chat ID are set."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Missing Telegram credentials. Check your .env or GitHub Secrets.")
        return False
    return True


def get_gmail_service():
    """Connect to Gmail API using env credentials."""
    required_vars = [
        "GMAIL_TOKEN",
        "GMAIL_REFRESH_TOKEN",
        "GMAIL_CLIENT_ID",
        "GMAIL_CLIENT_SECRET",
    ]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        raise RuntimeError(f"❌ Missing Gmail secrets: {missing}")

    creds_info = {
        "token": os.getenv("GMAIL_TOKEN"),
        "refresh_token": os.getenv("GMAIL_REFRESH_TOKEN"),
        "client_id": os.getenv("GMAIL_CLIENT_ID"),
        "client_secret": os.getenv("GMAIL_CLIENT_SECRET"),
        "token_uri": os.getenv(
            "GMAIL_TOKEN_URI", "https://oauth2.googleapis.com/token"
        ),
    }
    creds = Credentials.from_authorized_user_info(creds_info, SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds.valid:
        raise RuntimeError("❌ Gmail credentials invalid even after refresh")

    return build("gmail", "v1", credentials=creds)


# TODO: Proper fetching. Now it just fetches HTML code.
def extract_body(msg_data: dict) -> str:
    """Extract and decode plain text body from Gmail message."""
    body = ""
    payload = msg_data.get("payload", {})

    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part["body"].get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode(
                        "utf-8", errors="ignore"
                    )
                    break
    else:
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    return body.strip()


def fetch_last_messages(gmail_service, n=15, seen_ids_set=None, seen_orders_set=None):
    """Fetch the last n Gmail messages and notify about new orders."""
    if seen_ids_set is None:
        seen_ids_set = set()
    if seen_orders_set is None:
        seen_orders_set = set()

    try:
        results = (
            gmail_service.users()
            .messages()
            .list(userId="me", maxResults=n, labelIds=["INBOX"])
            .execute()
        )
        messages = results.get("messages", [])

        if not messages:
            print("No messages found.")
            return seen_ids_set, seen_orders_set

        for msg in messages:
            if msg["id"] in seen_ids_set:
                continue  # Skip already processed messages

            msg_data = (
                gmail_service.users()
                .messages()
                .get(userId="me", id=msg["id"], format="full")
                .execute()
            )

            headers = {h["name"]: h["value"] for h in msg_data["payload"]["headers"]}
            subject = headers.get("Subject", "(No subject)")
            sender = headers.get("From", "(Unknown sender)")
            body = extract_body(msg_data)

            # Extract order_id safely
            cropped_subject = subject.split(" ")
            order_id = cropped_subject[2][1:] if len(cropped_subject) > 2 else None

            if (
                sender == "info@agropride.com.ua"
                and "Нове замовлення" in subject
                and order_id
                and order_id not in seen_orders_set
            ):
                text = (
                    f"📩 New Order!\n"
                    f"From: {sender}\n"
                    f"Subject: {subject}\n\n"
                    f"📝 Message:\n{body[:1000]}"
                )
                print(text)
                send_telegram_message(text)
                seen_orders_set.add(order_id)

            seen_ids_set.add(msg["id"])

        return seen_ids_set, seen_orders_set

    except (HttpError, BrokenPipeError, ssl.SSLEOFError) as error:
        print(f"⚠️ Connection error: {error}.")
        time.sleep(15)
        return seen_ids_set, seen_orders_set


if __name__ == "__main__":
    service = get_gmail_service()
    seen_ids = load_set(SEEN_IDS_FILE)
    seen_orders = load_set(SEEN_ORDERS_FILE)

    print("Checking the mail...\n")
    seen_ids, seen_orders = fetch_last_messages(
        service, n=5, seen_ids_set=seen_ids, seen_orders_set=seen_orders
    )

    save_set(SEEN_IDS_FILE, seen_ids)
    save_set(SEEN_ORDERS_FILE, seen_orders)

    print("Done.")
