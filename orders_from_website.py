"""Fetch Gmail messages and send Telegram alerts for new orders"""

import logging
import os
import ssl
import time
from typing import Any, Dict, Set

import dotenv
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

dotenv.load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CHECK_INTERVAL = 5 if DEBUG else 900
MESSAGES_LIMIT = 5

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.DEBUG if DEBUG else logging.INFO,
)
logger = logging.getLogger(__name__)


def send_telegram_message(text: str) -> None:
    """Send a message to the user via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Missing Telegram credentials. Check your .env or GitHub Secrets.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("✅ Telegram message sent.")
    except requests.RequestException as e:
        logger.error("Telegram request failed: %s", e)


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
        raise RuntimeError(f"Missing Gmail secrets: {missing}")

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
        logger.info("🔄 Refreshing Gmail credentials...")
        creds.refresh(Request())

    if not creds.valid:
        raise RuntimeError("Gmail credentials invalid even after refresh")

    return build("gmail", "v1", credentials=creds)


def fetch_last_messages(service, n: int, seen_ids: Set[str]) -> Set[str]:
    """Fetch the last n Gmail messages and notify about new orders."""
    try:
        results = (
            service.users()
            .messages()
            .list(userId="me", maxResults=n, labelIds=["INBOX"])
            .execute()
        )
        messages = results.get("messages", [])
        if not messages:
            logger.info("📭 No messages found.")
            return seen_ids

        for msg in messages:
            if msg["id"] in seen_ids:
                continue

            msg_data: Dict[str, Any] = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From", "Date"],
                )
                .execute()
            )

            headers = {h["name"]: h["value"] for h in msg_data["payload"]["headers"]}
            subject = headers.get("Subject", "(No subject)")
            sender = headers.get("From", "(Unknown sender)")

            if sender == "info@agropride.com.ua" and "Нове замовлення" in subject:
                text = f"📩 New Order!\nFrom: {sender}\nSubject: {subject}"
                logger.info(text)
                send_telegram_message(text)

            seen_ids.add(msg["id"])

        return seen_ids

    except (HttpError, BrokenPipeError, ssl.SSLEOFError) as error:
        logger.warning("⚠️ Connection error: %s. Retrying in 15s...", error)
        time.sleep(15)
        return seen_ids


def main() -> None:
    """Run the Gmail fetcher every CHECK_INTERVAL seconds and notify on new orders."""
    service = get_gmail_service()
    seen_ids: Set[str] = set()

    try:
        while True:
            seen_ids = fetch_last_messages(service, n=MESSAGES_LIMIT, seen_ids=seen_ids)
            logger.info("⏳ Waiting before next check...\n")
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("🛑 Stopping...")


if __name__ == "__main__":
    main()
