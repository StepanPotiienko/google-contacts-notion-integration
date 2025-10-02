"""Module for fetching Gmail messages and notifying via Telegram about new orders."""

import os
import re
import ssl
import time
import base64
import json
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

TRACKING_FILE = "order_tracking.json"


def load_tracking_data():
    """Load tracking data from JSON file"""
    if not os.path.exists(TRACKING_FILE):
        return {"seen_ids": set(), "seen_orders": set()}

    try:
        with open(TRACKING_FILE, "r", encoding="UTF-8") as f:
            data = json.load(f)
            return {
                "seen_ids": set(data.get("seen_ids", [])),
                "seen_orders": set(data.get("seen_orders", [])),
            }
    except (json.JSONDecodeError, KeyError):
        return {"seen_ids": set(), "seen_orders": set()}


def save_tracking_data(data):
    """Save tracking data to JSON file"""
    with open(TRACKING_FILE, "w", encoding="UTF-8") as f:
        json.dump(
            {
                "seen_ids": list(data["seen_ids"]),
                "seen_orders": list(data["seen_orders"]),
            },
            f,
            indent=2,
        )


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


def find_order_div(soup):
    """Find the order div with dynamic ID"""
    div = soup.find("div", id=re.compile(r"^m_.*body$"))
    if div:
        return div

    potential_divs = soup.find_all("div")
    for div in potential_divs:
        if (
            div.find("strong", string=re.compile("Номер замовлення"))
            and div.find("th", string="Товар")
            and div.find("th", string="Кількість")
        ):
            return div

    return None


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
            if part.get("parts"):
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


def extract_products_from_table(soup):
    """Extract multiple products from the order table"""
    products = []

    tables = soup.find_all("table")
    product_table = None

    for table in tables:
        headers = table.find_all("th")
        header_texts = [header.get_text(strip=True) for header in headers]
        if (
            "Товар" in header_texts
            and "Кількість" in header_texts
            and "Сума" in header_texts
        ):
            product_table = table
            break

    if not product_table:
        print("❌ Could not find product table")
        return products

    print("✅ Found product table")

    rows = []
    if product_table.find("tbody"):
        rows = product_table.find("tbody").find_all("tr")
    else:
        all_rows = product_table.find_all("tr")
        rows = [row for row in all_rows if not row.find("th")]

    print(f"📊 Found {len(rows)} product rows")

    for row in rows:
        cols = row.find_all("td")
        if len(cols) == 3:
            # Column 0: Product info (name, article, unit price)
            # Column 1: Quantity
            # Column 2: Total price

            product_col = cols[0]
            quantity_col = cols[1]
            price_col = cols[2]

            product_text = product_col.get_text(" ", strip=True)
            product_name = product_text.split("Артикул:")[0].strip()

            if any(
                keyword in product_name for keyword in ["Товар", "Кількість", "Сума"]
            ):
                print("⏩ Skipping header row")
                continue

            quantity = quantity_col.get_text(" ", strip=True)

            total_price = price_col.get_text(" ", strip=True)

            article = None
            if "Артикул:" in product_text:
                article_part = product_text.split("Артикул:")[1]
                article = (
                    article_part.split()[0].strip() if article_part.split() else None
                )

            unit_price = None
            if "Ціна за одиницю:" in product_text:
                price_part = product_text.split("Ціна за одиницю:")[1]
                unit_price = (
                    price_part.split("грн")[0].strip()
                    if "грн" in price_part
                    else price_part.strip()
                )

            product_data = {
                "name": product_name,
                "quantity": quantity,
                "total_price": total_price,
                "article": article,
                "unit_price": unit_price,
            }
            products.append(product_data)

    return products


def parse_order_email(html: str) -> dict:
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
    result["Оплата"] = extract_bold("Оплата:")
    result["Сума замовлення"] = extract_bold("Сума замовлення:")
    result["Доставка"] = extract_bold("Доставка:")
    result["Разом до оплати"] = extract_bold("Разом до оплати:")

    order_info = soup.find("p")
    if order_info and order_info.find("strong"):
        order_text = order_info.get_text()
        order_match = re.search(r"#(\d+)\s*\((.*?)\)", order_text)
        if order_match:
            result["Номер замовлення"] = order_match.group(1)
            result["Дата замовлення"] = order_match.group(2)

    result["products"] = extract_products_from_table(soup)

    return result


def format_order_for_telegram(data: dict, subject: str) -> str:
    """Format parsed order data for Telegram message."""
    message_parts = [
        "📦 Нове замовлення!",
        f"Тема: {subject}",
        "",
        f"👤 {data.get("Ім\'я одержувача", '-')}",
        f"📞 {data.get('Телефон', '-')}",
        f"💳 Оплата: {data.get('Оплата', '-')}",
        f"💰 Сума: {data.get('Сума замовлення', '-')}",
        f"🚚 Доставка: {data.get('Доставка', '-')}",
        f"✅ Разом: {data.get('Разом до оплати', '-')}",
        "",
    ]

    if "Номер замовлення" in data:
        message_parts.insert(1, f"Номер: #{data['Номер замовлення']}")

    if data.get("products"):
        message_parts.append("🛒 Товари:")
        for i, product in enumerate(data["products"], 1):
            message_parts.append(f"{i}. {product['name']}")
            message_parts.append(f"   📦 Кількість: {product['quantity']}")
            message_parts.append(f"   💵 Сума: {product['total_price']}")

            if product.get("article"):
                message_parts.append(f"   📑 Артикул: {product['article']}")
            if product.get("unit_price"):
                message_parts.append(f"   🏷️ Ціна за од.: {product['unit_price']} грн")

            message_parts.append("")
    else:
        message_parts.append("❌ Не вдалося отримати інформацію про товари")

    return "\n".join(message_parts)


def extract_order_id(subject: str) -> str:
    """Extract order ID from subject line"""
    try:
        parts = subject.split()
        for part in parts:
            if part.startswith("#"):
                return part[1:]
        numbers = re.findall(r"\d+", subject)
        return numbers[0] if numbers else subject
    except:
        return subject


def fetch_last_messages(gmail_service, tracking_data_list, n=15):
    """Fetch last n messages and process new orders"""
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
            return tracking_data_list

        new_orders_found = 0

        for msg in messages:
            msg_id = msg["id"]

            if msg_id in tracking_data_list["seen_ids"]:
                continue

            msg_data = (
                gmail_service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )

            headers = {h["name"]: h["value"] for h in msg_data["payload"]["headers"]}
            sender = headers.get("From", "")
            subject = headers.get("Subject", "")

            if "info@agropride.com.ua" in sender and "Нове замовлення" in subject:
                order_id = extract_order_id(subject)

                if order_id in tracking_data_list["seen_orders"]:
                    print(f"⚠️ Order {order_id} already processed, skipping.")
                    tracking_data_list["seen_ids"].add(msg_id)  # Mark message as seen
                    continue

                print(f"🆕 New order found: {order_id}")
                body_html = extract_body(msg_data)

                if body_html:
                    order_data = parse_order_email(body_html)
                    text = format_order_for_telegram(order_data, subject)
                    send_telegram_message(text)

                    tracking_data_list["seen_ids"].add(msg_id)
                    tracking_data_list["seen_orders"].add(order_id)
                    new_orders_found += 1

                    print(f"✅ Sent order {order_id} to Telegram")

                    if DEBUG:
                        print(
                            f"📧 Products found: {len(order_data.get('products', []))}"
                        )
                        for product in order_data.get("products", []):
                            print(f"   - {product['name']}")
                else:
                    print(f"❌ Could not extract body for order {order_id}")
            else:
                tracking_data_list["seen_ids"].add(msg_id)

        print(f"📊 Found {new_orders_found} new orders")
        return tracking_data_list

    except (HttpError, BrokenPipeError, ssl.SSLEOFError) as error:
        print(f"⚠️ Connection error: {error}")
        time.sleep(15)
        return tracking_data_list


if __name__ == "__main__":
    if not os.path.exists(TRACKING_FILE):
        save_tracking_data({"seen_ids": set(), "seen_orders": set()})

    service = get_gmail_service()
    tracking_data = load_tracking_data()

    print(
        f"📊 Previously seen: {len(tracking_data['seen_ids'])} messages, {len(tracking_data['seen_orders'])} orders"
    )
    print("🔍 Checking for new orders...")

    tracking_data = fetch_last_messages(service, tracking_data, n=5)
    save_tracking_data(tracking_data)

    print(
        f"✅ Done. Now tracking {len(tracking_data['seen_ids'])} messages and {len(tracking_data['seen_orders'])} orders"
    )
