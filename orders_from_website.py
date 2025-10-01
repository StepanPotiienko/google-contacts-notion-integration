"""Module for fetching Gmail messages and notifying via Telegram about new orders."""

import os
import ssl
import time
import base64
import requests
import dotenv
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

dotenv.load_dotenv()

DEBUG = os.getenv("DEBUG", "False").lower() in ("1", "true", "yes")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_IDS_FILE = "seen_ids.txt"
SEEN_ORDERS_FILE = "seen_orders.txt"


def load_set(filename: str) -> set:
    """Load information from a file"""
    if not os.path.exists(filename):
        return set()
    with open(filename, "r", encoding="UTF-8") as load_file:
        return set(line.strip() for line in load_file if line.strip())


def save_set(filename: str, data: set):
    """Save information to a file"""
    with open(filename, "w", encoding="UTF-8") as save_file:
        for item in data:
            save_file.write(item + "\n")


def check_telegram_credentials():
    """Check if Telegram credentials are correct"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Missing Telegram credentials. Check your .env or GitHub Secrets.")
        return False
    return True


def send_telegram_message(text: str):
    """Send a message to multiple Telegram accounts"""
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


def get_gmail_service():
    """Connect to gmail service"""
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


def extract_body(msg_data: dict) -> str:
    """Extract only HTML body from Gmail message."""
    payload = msg_data.get("payload", {})

    def decode_data(data: str) -> str:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    def walk_parts(parts):
        for part in parts:
            mime = part.get("mimeType", "")
            data = part.get("body", {}).get("data", "")
            if mime == "text/html" and data:
                return decode_data(data)
            if part.get("parts"):  # recursive search
                html = walk_parts(part["parts"])
                if html:
                    return html
        return ""

    if "parts" in payload:
        return walk_parts(payload["parts"]).strip()
    else:
        data = payload.get("body", {}).get("data", "")
        if data and payload.get("mimeType") == "text/html":
            return decode_data(data).strip()

    return ""


def parse_order_email(html: str) -> dict:  # type: ignore
    """Parse Agropride order email and extract structured data."""
    soup = BeautifulSoup(html, "html.parser")
    result = {}

    def extract_bold(label: str):
        """Extract text after a <b> label in HTML email."""
        el = soup.find("b", string=lambda t: t and label in t)  # type: ignore
        if not el:
            return "-"

        if el.next_sibling and isinstance(el.next_sibling, str):
            text = el.next_sibling.strip()
            if text:
                return text

        parent_text = el.parent.get_text(" ", strip=True)
        text = parent_text.replace(label, "").strip()

        return text if text else "-"

    result["Ім'я одержувача"] = extract_bold("Ім'я одержувача:")
    result["Телефон"] = extract_bold("Телефон:")
    result["Адреса доставки"] = extract_bold("За адресою:")
    result["Оплата"] = extract_bold("Оплата:")
    result["Сума замовлення"] = extract_bold("Сума замовлення:")
    result["Доставка"] = extract_bold("Доставка:")
    result["Разом до оплати"] = extract_bold("Разом до оплати:")

    product_table = soup.find("table", {"style": "width:100%;border-collapse:collapse"})
    if product_table:
        row = product_table.find("tbody").find("tr")  # type: ignore
        cols = row.find_all("td")  # type: ignore
        if len(cols) >= 3:
            product_info = cols[0].get_text(" ", strip=True)
            qty = cols[1].get_text(" ", strip=True)
            price = cols[2].get_text(" ", strip=True)
            result["Товар"] = product_info
            result["Кількість"] = qty
            result["Сума"] = price

            if "Артикул:" in product_info:
                result["Артикул"] = product_info.split("Артикул:")[1].split()[0]
            if "Ціна за одиницю:" in product_info:
                result["Ціна за одиницю"] = product_info.split("Ціна за одиницю:")[
                    1
                ].strip()

    return result


def format_order_for_telegram(data: dict, subject: str) -> str:
    """Format parsed order data for Telegram message."""
    return f"""📦 Нове замовлення!
Subject: {subject}

👤 {data.get("Ім'я одержувача", '-')}
📞 {data.get('Телефон', '-')}
📍 {data.get('Адреса доставки', '-')}
💳 Оплата: {data.get('Оплата', '-')}
💰 Сума: {data.get('Сума замовлення', '-')}
🚚 Доставка: {data.get('Доставка', '-')}
✅ Разом: {data.get('Разом до оплати', '-')}

🛒 {data.get('Товар', '-')}
📦 Кількість: {data.get('Кількість', '-') if data.get('Кількість') else '-'}
💵 Ціна за од.: {data.get('Ціна за одиницю', '-') if data.get('Ціна за одиницю') else '-'}
📑 Артикул: {data.get('Артикул', '-') if data.get('Артикул') else '-'}
"""


def fetch_last_messages(gmail_service, n=15, seen_ids_set=None, seen_orders_set=None):
    """Fetch last n messages from Gmail that match Agropride order conditions."""
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

        matching_messages = []
        for msg in messages:
            msg_data = (
                gmail_service.users()
                .messages()
                .get(userId="me", id=msg["id"], format="full")
                .execute()
            )
            headers = {h["name"]: h["value"] for h in msg_data["payload"]["headers"]}
            sender = headers.get("From", "")
            subject = headers.get("Subject", "")

            if sender != "info@agropride.com.ua" and not "Нове замовлення" in subject:
                continue

            cropped_subject = subject.split(" ")
            print("Cropped subject:", cropped_subject)
            order_id = cropped_subject[2][1:] if len(cropped_subject) > 2 else None
            print("Order id:", order_id)

            if order_id in seen_orders_set or order_id in seen_ids_set:
                print(f"⚠️ Order {order_id} already processed, skipping.")
                return

            if sender == "info@agropride.com.ua" and "Нове замовлення" in subject:
                matching_messages.append((msg, subject, msg_data, order_id))

        if not matching_messages:
            print("No matching Agropride orders found.")
            return seen_ids_set, seen_orders_set

        msg, subject, msg_data, order_id = matching_messages[-1]

        body_html = extract_body(msg_data)
        if body_html and order_id and order_id not in seen_orders_set:
            order_data = parse_order_email(body_html)
            text = format_order_for_telegram(order_data, subject)
            send_telegram_message(text)
            print(f"✅ Sent order {order_id} to Telegram")

        if order_id:
            seen_orders_set.add(order_id)

        seen_ids_set.add(msg["id"])

        return seen_ids_set, seen_orders_set

    except (HttpError, BrokenPipeError, ssl.SSLEOFError) as error:
        print(f"⚠️ Connection error: {error}.")
        time.sleep(15)
        return seen_ids_set, seen_orders_set


if __name__ == "__main__":
    for file in (SEEN_IDS_FILE, SEEN_ORDERS_FILE):
        if not os.path.exists(file):
            with open(file, "w", encoding="UTF-8") as f:
                f.write("")

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
