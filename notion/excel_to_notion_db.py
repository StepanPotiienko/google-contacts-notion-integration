"""Export CSV client data to Notion."""

import argparse
import csv
import json
import os
import re
import sys
import types
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional, cast

import dotenv

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        import notion_controller
    except ModuleNotFoundError as exc:
        print(f"Error: Failed to import notion_controller: {exc}")
        print("Please install required dependencies: pip install -r requirements.txt")
        sys.exit(1)
else:
    import notion_controller

dotenv.load_dotenv()

DEFAULT_SOURCE_VALUE = "БАЗА"
TRANSACTION_COLUMNS = {
    "ДАТА ПРОДАЖУ",
    "ТОВАР",
    "Кіл-ть штук",
    "ЦІНА",
    "ПРИМІТКА",
}


def parse_clients(file_name: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse CSV and aggregate transactions per client."""

    clients: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    with open(file_name, "r", encoding="UTF-8-SIG", newline="") as handle:
        reader = csv.DictReader(
            handle,
            delimiter=";",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            skipinitialspace=True,
        )

        headers = list(reader.fieldnames or [])
        if "Source" not in headers:
            headers.append("Source")
        print("Available columns:", headers)

        for row in reader:
            if not row:
                continue

            normalized = {key: _normalize_cell(value) for key, value in row.items()}
            normalized.setdefault("Source", DEFAULT_SOURCE_VALUE)

            name = (normalized.get("ПОКУПЕЦЬ") or normalized.get("Name") or "").strip()
            if not name or re.fullmatch(r"[\d\s.,]+", name):
                continue

            info_payload = {
                key: value
                for key, value in normalized.items()
                if key not in TRANSACTION_COLUMNS
            }
            info_payload.setdefault("ПОКУПЕЦЬ", name)
            info_payload.setdefault("Source", DEFAULT_SOURCE_VALUE)

            transactions = _extract_transactions(normalized)

            existing = clients.get(name)
            if not existing:
                clients[name] = {
                    "name": name,
                    "info": info_payload,
                    "transactions": transactions,
                }
            else:
                current_info = existing["info"]
                for key, value in info_payload.items():
                    if value and not current_info.get(key):
                        current_info[key] = value
                existing["transactions"].extend(transactions)

    return list(clients.values()), headers


def _normalize_cell(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value).strip()
    return (value or "").strip().replace("\\n", "\n")


def _split_on_comma(raw: str) -> list[str]:
    if not raw:
        return []
    return [segment.strip() for segment in raw.split(",") if segment.strip()]


def _split_prices(raw: str) -> list[str]:
    if not raw:
        return []
    matches = re.findall(r"\d[\d\s]*,\d{2}", raw)
    if matches:
        return [match.strip() for match in matches]
    return _split_on_comma(raw)


def _pad_list(items: list[str], length: int, fill_value: str = "") -> list[str]:
    if length <= 0:
        return []
    padded = list(items)
    if len(padded) >= length:
        return padded[:length]
    padded.extend(fill_value for _ in range(length - len(padded)))
    return padded


def _extract_transactions(row: dict[str, str]) -> list[dict[str, str]]:
    dates = _split_on_comma(row.get("ДАТА ПРОДАЖУ", ""))
    products = _split_on_comma(row.get("ТОВАР", ""))
    quantities = _split_on_comma(row.get("Кіл-ть штук", ""))
    prices = _split_prices(row.get("ЦІНА", ""))

    max_len = max(len(dates), len(products), len(quantities), len(prices))
    if max_len == 0:
        if not any(
            row.get(col) for col in ("ДАТА ПРОДАЖУ", "ТОВАР", "ЦІНА", "Кіл-ть штук")
        ):
            return []
        max_len = 1

    note_value = row.get("ПРИМІТКА", "").strip()

    dates = _pad_list(dates, max_len)
    products = _pad_list(products, max_len)  # Changed from _pad_with_last
    quantities = _pad_list(quantities, max_len)
    prices = _pad_list(prices, max_len)
    notes = _pad_list([note_value] if note_value else [], max_len, note_value)

    transactions: list[dict[str, str]] = []
    for index in range(max_len):
        transactions.append(
            {
                "date": dates[index],
                "product": products[index],
                "quantity": quantities[index],
                "price": prices[index],
                "note": notes[index],
            }
        )

    return transactions


def _parse_number(raw: str) -> Optional[float]:
    if not raw:
        return None
    cleaned = (
        raw.replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace(" ", "")
        .replace(",", ".")
    )
    try:
        return float(cleaned)
    except ValueError:
        return None


def ensure_properties(
    notion_client: notion_controller.NotionController,
    database_id: str,
    headers: list[str],
) -> None:
    db = notion_client.notion_request_with_retry(
        lambda: notion_client.retrieve_database(database_id)
    )
    db_dict = cast(dict, db)
    existing_props = db_dict.get("properties", {})

    def add_property(name: str, definition: dict[str, Any]) -> None:
        notion_client.notion_request_with_retry(
            lambda: notion_client.notion_client.databases.update(  # type: ignore
                database_id=database_id,
                properties={name: definition},
            )
        )

    for header in headers:
        if not header:
            continue
        if header in existing_props:
            if header == "Source" and existing_props[header].get("type") == "select":
                options = existing_props[header].get("select", {}).get("options", [])
                if not any(
                    option.get("name") == DEFAULT_SOURCE_VALUE for option in options
                ):
                    add_property(
                        "Source",
                        {
                            "select": {
                                "options": options + [{"name": DEFAULT_SOURCE_VALUE}],
                            }
                        },
                    )
            continue

        if header == "Source":
            add_property(
                "Source", {"select": {"options": [{"name": DEFAULT_SOURCE_VALUE}]}}
            )
        else:
            add_property(header, {"rich_text": {}})

    # Ensure `Years` multi-select exists on the CRM database for year tags
    if "Years" not in existing_props:
        add_property("Years", {"multi_select": {"options": []}})


def _ensure_client_source_baza(
    notion_client: notion_controller.NotionController,
    page: dict,
) -> None:
    page_id = page.get("id")
    if not page_id:
        return
    props = page.get("properties", {})
    source_prop = props.get("Source")
    if not source_prop or source_prop.get("type") != "select":
        return
    current = source_prop.get("select") or {}
    if current.get("name") == DEFAULT_SOURCE_VALUE:
        return
    notion_client.notion_request_with_retry(
        lambda pid=page_id: notion_client.notion_client.pages.update(  # type: ignore
            page_id=pid,
            properties={"Source": {"select": {"name": DEFAULT_SOURCE_VALUE}}},
        )
    )


def _build_client_creation_properties(
    title_prop: str,
    name: str,
    info: dict[str, str],
) -> dict[str, Any]:
    props: dict[str, Any] = {
        title_prop: {"title": [{"text": {"content": name}}]},
        "ПОКУПЕЦЬ": {"rich_text": [{"text": {"content": name}}]},
    }
    source_value = info.get("Source", DEFAULT_SOURCE_VALUE) or DEFAULT_SOURCE_VALUE
    props["Source"] = {"select": {"name": source_value}}

    for key, value in info.items():
        if not value:
            continue
        if key in ("ПОКУПЕЦЬ", "Name", "Source", title_prop):
            continue
        props[key] = {"rich_text": [{"text": {"content": value}}]}
    return props


def _build_client_update_properties(
    page: dict,
    info: dict[str, str],
    title_prop: str,
) -> dict[str, Any]:
    props: dict[str, Any] = {}
    existing_props = page.get("properties", {})

    for key, value in info.items():
        if not value:
            continue
        if key in ("ПОКУПЕЦЬ", "Name", title_prop):
            continue
        if key == "Source":
            current = (existing_props.get("Source") or {}).get("select") or {}
            if current.get("name") != value:
                props["Source"] = {"select": {"name": value}}
            continue

        existing = existing_props.get(key, {})
        if existing.get("type") == "rich_text":
            texts = existing.get("rich_text", [])
            current_text = texts[0].get("plain_text", "").strip() if texts else ""
            if not current_text:
                props[key] = {"rich_text": [{"text": {"content": value}}]}

    return props


def _ensure_client_page(
    notion_client: notion_controller.NotionController,
    crm_database_id: str,
    title_prop: str,
    entry: dict[str, Any],
    cache: dict[str, str],
) -> tuple[Optional[str], bool]:
    name = entry.get("name", "")
    if not name:
        return None, False
    if name in cache:
        return cache[name], False

    info = entry.get("info", {}) or {}

    try:
        response = notion_client.notion_request_with_retry(
            lambda: notion_client.notion_client.databases.query(  # type: ignore
                database_id=crm_database_id,
                filter={"property": title_prop, "title": {"equals": name}},
                page_size=1,
            )
        )
        results = response.get("results", [])  # type: ignore
        if results:
            page = results[0]
            page_id = page.get("id")
            if page_id:
                _ensure_client_source_baza(notion_client, page)
                update_props = _build_client_update_properties(page, info, title_prop)
                if update_props:
                    notion_client.notion_request_with_retry(
                        lambda payload=update_props, pid=page_id: notion_client.notion_client.pages.update(  # type: ignore
                            page_id=pid,
                            properties=payload,
                        )
                    )
                # Update Years multi-select based on transactions in the entry
                try:
                    txs = entry.get("transactions", []) or []
                    years = set()
                    for t in txs:
                        date_str = (t.get("date") or "").strip()
                        m = re.search(r"(\d{4})", date_str)
                        if m:
                            years.add(m.group(1))
                    if years:
                        yrs_payload = {
                            "Years": {
                                "multi_select": [{"name": y} for y in sorted(years)]
                            }
                        }
                        notion_client.notion_request_with_retry(
                            lambda payload=yrs_payload, pid=page_id: notion_client.notion_client.pages.update(  # type: ignore
                                page_id=pid,
                                properties=payload,
                            )
                        )
                except Exception:
                    pass
                cache[name] = page_id
                return page_id, False
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: failed to query existing client '{name}': {exc}")

    creation_props = _build_client_creation_properties(title_prop, name, info)
    page = notion_client.notion_request_with_retry(
        lambda payload=creation_props: notion_client.notion_client.pages.create(  # type: ignore
            parent={"database_id": crm_database_id},
            properties=payload,
        )
    )
    page_id = page.get("id")
    if page_id:
        # After creating the page, set Years multi-select from transactions
        try:
            txs = entry.get("transactions", []) or []
            years = set()
            for t in txs:
                date_str = (t.get("date") or "").strip()
                m = re.search(r"(\d{4})", date_str)
                if m:
                    years.add(m.group(1))
            if years:
                yrs_payload = {
                    "Years": {"multi_select": [{"name": y} for y in sorted(years)]}
                }
                notion_client.notion_request_with_retry(
                    lambda payload=yrs_payload, pid=page_id: notion_client.notion_client.pages.update(  # type: ignore
                        page_id=pid,
                        properties=payload,
                    )
                )
        except Exception:
            pass
        cache[name] = page_id
    return page_id, True


def _ensure_transactions_database(
    notion_client: notion_controller.NotionController,
    client_page_id: str,
    client_name: str,
) -> tuple[str, bool]:
    existing_id = _find_existing_child_database(notion_client, client_page_id)
    if existing_id:
        _ensure_transaction_database_schema(notion_client, existing_id)
        return existing_id, False

    title = f"{client_name} - Transactions"
    database = notion_client.notion_request_with_retry(
        lambda: notion_client.notion_client.databases.create(  # type: ignore
            parent={"type": "page_id", "page_id": client_page_id},
            title=[{"type": "text", "text": {"content": title}}],
            properties={
                "Name": {"title": {}},
                "ДАТА ПРОДАЖУ": {"date": {}},
                "ТОВАР": {"rich_text": {}},
                "Кіл-ть штук": {"number": {}},
                "ЦІНА": {"number": {}},
                "ПРИМІТКА": {"rich_text": {}},
                "Source": {"select": {"options": [{"name": DEFAULT_SOURCE_VALUE}]}},
            },
        )
    )
    db_id = database.get("id")
    if not db_id:
        raise RuntimeError("Failed to create transactions database")
    _ensure_transaction_database_schema(notion_client, db_id)
    return db_id, True


def _ensure_transaction_database_schema(
    notion_client: notion_controller.NotionController,
    database_id: str,
) -> None:
    database = notion_client.notion_request_with_retry(
        lambda: notion_client.retrieve_database(database_id)
    )
    db_dict = cast(dict, database)

    if not db_dict.get("is_inline", False):
        notion_client.notion_request_with_retry(
            lambda: notion_client.notion_client.databases.update(  # type: ignore
                database_id=database_id,
                is_inline=True,
            )
        )


def _find_existing_child_database(
    notion_client: notion_controller.NotionController,
    page_id: str,
) -> str | None:
    cursor: str | None = None
    while True:
        response = notion_client.notion_request_with_retry(
            lambda cursor_value=cursor: notion_client.notion_client.blocks.children.list(  # type: ignore
                block_id=page_id,
                start_cursor=cursor_value,
                page_size=100,
            )
        )
        for block in response.get("results", []):  # type: ignore[index]
            if block.get("type") == "child_database":
                child_db = block.get("child_database", {})
                title = (child_db.get("title") or "").strip()
                if title and "transactions" in title.lower():
                    return block.get("id")
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")  # type: ignore[assignment]
    return None


def _load_existing_transactions(
    notion_client: notion_controller.NotionController,
    database_id: str,
    title_prop: str,
) -> set[str]:
    titles: set[str] = set()
    cursor: str | None = None

    while True:
        response = notion_client.notion_request_with_retry(
            lambda cursor_value=cursor: notion_client.notion_client.databases.query(  # type: ignore
                database_id=database_id,
                start_cursor=cursor_value,
                page_size=100,
            )
        )
        for page in response.get("results", []):  # type: ignore[index]
            props = page.get("properties", {})
            title_items = props.get(title_prop, {}).get("title", [])
            title_text = (
                title_items[0].get("plain_text", "").strip() if title_items else ""
            )
            if title_text:
                titles.add(title_text)

        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")  # type: ignore[assignment]

    return titles


def _format_transaction_title(transaction: dict[str, str]) -> str:
    date_val = transaction.get("date", "").strip() or "Без дати"
    product_val = transaction.get("product", "").strip() or "Без товару"
    price_val = transaction.get("price", "").strip()
    parts = [date_val, product_val]
    if price_val:
        parts.append(price_val)
    title = " - ".join(parts)
    return title or "Транзакція"


def _build_transaction_properties(
    title_prop: str,
    transaction: dict[str, str],
    title: str,
) -> dict[str, Any]:
    props: dict[str, Any] = {
        title_prop: {
            "title": [
                {
                    "type": "text",
                    "text": {"content": title},
                }
            ]
        },
        "Source": {"select": {"name": DEFAULT_SOURCE_VALUE}},
    }

    price_num = _parse_number(transaction.get("price", ""))
    quantity_num = _parse_number(transaction.get("quantity", ""))

    date_val = transaction.get("date", "").strip()
    if date_val:
        if re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", date_val):
            dd, mm, yyyy = date_val.split(".")
            props["ДАТА ПРОДАЖУ"] = {"date": {"start": f"{yyyy}-{mm}-{dd}"}}
        else:
            props.setdefault("ПРИМІТКА", {"rich_text": []})
            props["ПРИМІТКА"]["rich_text"].append(
                {"text": {"content": f"Дата (текст): {date_val}"}}
            )

    product_val = transaction.get("product", "").strip()
    if product_val:
        props["ТОВАР"] = {"rich_text": [{"text": {"content": product_val}}]}

    if quantity_num is not None:
        props["Кіл-ть штук"] = {"number": quantity_num}
    elif transaction.get("quantity"):
        props.setdefault("ПРИМІТКА", {"rich_text": []})
        props["ПРИМІТКА"]["rich_text"].append(
            {"text": {"content": f"Кількість (текст): {transaction['quantity']}"}}
        )

    if price_num is not None:
        props["ЦІНА"] = {"number": price_num}
    elif transaction.get("price"):
        props.setdefault("ПРИМІТКА", {"rich_text": []})
        props["ПРИМІТКА"]["rich_text"].append(
            {"text": {"content": f"Ціна (текст): {transaction['price']}"}}
        )

    note_val = transaction.get("note", "").strip()
    if note_val:
        props.setdefault("ПРИМІТКА", {"rich_text": []})
        props["ПРИМІТКА"]["rich_text"].append({"text": {"content": note_val}})

    return props


def main() -> None:
    """Entry point for syncing clients and their transactions."""

    def args_parser():
        if not os.environ.get("DEBUG"):
            parser = argparse.ArgumentParser(
                description="Export CSV to Notion with safety features"
            )
            parser.add_argument(
                "file_name",
                type=str,
                help="Path to the CSV file",
                default="clients.csv",
            )
            parser.add_argument(
                "--dry-run",
                action="store_true",
                help="Do not modify Notion. Show intended operations.",
            )
            parser.add_argument(
                "--limit",
                type=int,
                default=None,
                help="Maximum number of clients to process (omit for all).",
            )
            parser.add_argument(
                "--show-payload",
                action="store_true",
                help="Print JSON payload for each transaction page.",
            )
            parser.add_argument(
                "--confirm",
                action="store_true",
                help="Required to run in non-dry mode.",
            )
            return parser.parse_args()

    parsed = (
        args_parser()
        if not os.environ.get("DEBUG")
        else types.SimpleNamespace(
            file_name="clients.csv",
            dry_run=True,
            limit=5,
            show_payload=True,
            confirm=False,
        )
    )
    file_name = parsed.file_name  # type: ignore[attr-defined]
    dry_run = bool(parsed.dry_run)  # type: ignore[attr-defined]
    limit_value = getattr(parsed, "limit", None)
    limit = limit_value if isinstance(limit_value, int) and limit_value > 0 else None
    show_payload = bool(parsed.show_payload)  # type: ignore[attr-defined]
    confirm = bool(parsed.confirm)  # type: ignore[attr-defined]

    client_entries, headers = parse_clients(file_name=file_name)  # type: ignore[arg-type]

    if not client_entries:
        print("No clients found in the provided file.")
        return

    crm_database_id = os.environ.get("CRM_DATABASE_ID")
    if not crm_database_id:
        print("Error: CRM_DATABASE_ID is not set in environment or .env")
        sys.exit(1)

    notion_client = notion_controller.NotionController()

    if dry_run:
        print("[DRY-RUN] Clients parsed:", len(client_entries))
        processed = 0
        for entry in client_entries:
            if limit is not None and processed >= limit:
                print(f"[DRY-RUN] Reached client limit ({limit}); stopping.")
                break
            print(
                f"[DRY-RUN] Would sync client '{entry['name']}' with "
                f"{len(entry.get('transactions', []))} transactions"
            )
            processed += 1
        return

    if not confirm:
        print("Refusing to create pages without --confirm (safety guard).")
        return

    ensure_properties(notion_client, crm_database_id, headers)

    try:
        client_title_prop = notion_client.get_title_property_name(crm_database_id)
    except Exception:
        client_title_prop = "Name"

    processed_clients = 0
    new_client_pages = 0
    new_transaction_databases = 0
    new_transactions = 0

    client_page_cache: dict[str, str] = {}
    transaction_title_prop_cache: dict[str, str] = {}

    for entry in client_entries:
        if limit is not None and processed_clients >= limit:
            print(f"Reached client limit ({limit}); stopping.")
            break

        page_id, page_created = _ensure_client_page(
            notion_client,
            crm_database_id,
            client_title_prop,
            entry,
            client_page_cache,
        )
        if not page_id:
            print(f"Skipping client '{entry.get('name', '')}' (no page id).")
            continue
        if page_created:
            new_client_pages += 1

        db_id, db_created = _ensure_transactions_database(
            notion_client,
            page_id,
            entry.get("name", "Client"),
        )
        if db_created:
            new_transaction_databases += 1

        if db_id not in transaction_title_prop_cache:
            try:
                transaction_title_prop_cache[db_id] = (
                    notion_client.get_title_property_name(db_id)
                )
            except Exception:
                transaction_title_prop_cache[db_id] = "Name"
        txn_title_prop = transaction_title_prop_cache[db_id]

        existing_titles = _load_existing_transactions(
            notion_client,
            db_id,
            txn_title_prop,
        )

        for transaction in entry.get("transactions", []):
            title = _format_transaction_title(transaction)
            if title in existing_titles:
                continue

            properties = _build_transaction_properties(
                txn_title_prop,
                transaction,
                title,
            )

            if show_payload:
                print(
                    "[PAYLOAD: TRANSACTION]",
                    json.dumps(properties, ensure_ascii=False),
                )

            notion_client.notion_request_with_retry(
                lambda payload=properties: notion_client.notion_client.pages.create(  # type: ignore
                    parent={"database_id": db_id},
                    properties=payload,
                )
            )
            existing_titles.add(title)
            new_transactions += 1

        processed_clients += 1

    print(
        "Finished. Clients processed:"
        f" {processed_clients}. New client pages: {new_client_pages}."
        f" New transaction databases: {new_transaction_databases}."
        f" Transactions created: {new_transactions}."
    )


if __name__ == "__main__":
    main()
