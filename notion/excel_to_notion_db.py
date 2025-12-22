"""Export Excel to Notion dabatase"""

import argparse

# TODO: Do I really want to convert Excel to CSV every time I need to add new clients?
import csv
import re
import json
import os
import sys
import types
from pathlib import Path
from typing import cast

import dotenv

if __package__ in (None, ""):
    # Add project root to sys.path for absolute package import
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:  # try absolute import after path fix
        import notion.notion_controller as notion_controller  # type: ignore
    except ModuleNotFoundError as e:  # fallback to relative-like import
        print(f"Error: Failed to import notion_controller: {e}")
        print("Please install required dependencies: pip install -r requirements.txt")
        sys.exit(1)
else:
    from . import notion_controller  # type: ignore

dotenv.load_dotenv()


def parse_excel(file_name: str) -> tuple[list[dict[str, str]], list[str]]:
    """Parse values from CSV and return (rows, headers)"""
    results: list[dict[str, str]] = []

    with open(file_name, mode="r", encoding="UTF-8-SIG", newline="") as file:
        reader = csv.DictReader(
            file,
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
            # Normalize keys/values; skip empty Name-like rows
            if not row:
                continue
            # Default Source tag for imported contacts
            row.setdefault("Source", "БАЗА")
            cleaned = {}
            for k, v in row.items():
                # Handle cases where v might be a list or other type
                if isinstance(v, list):
                    val = " ".join(str(item) for item in v).strip()
                else:
                    val = (v or "").strip().replace("\\n", "\n")
                cleaned[k] = val
            # ensure Source present even if not in original row
            cleaned.setdefault("Source", "БАЗА")
            results.append(cleaned)

    return results, headers


def ensure_properties(
    notion_client: notion_controller.NotionController,
    database_id: str,
    headers: list[str],
) -> None:
    """Ensure all CSV headers exist as properties in the Notion database.

    - Existing properties are left untouched.
    - Missing properties are created as `rich_text` by default.
    - Special cases: `Name` -> title, `Source` -> select (ensure option 'БАЗА').
    """
    db = notion_client.notion_request_with_retry(
        lambda: notion_client.retrieve_database(database_id)
    )
    db_dict = cast(dict, db)
    existing_props = db_dict.get("properties", {})

    def add_property(prop_name: str, prop_def: dict):
        notion_client.notion_request_with_retry(
            lambda: notion_client.notion_client.databases.update(  # type: ignore
                database_id=database_id,
                properties={prop_name: prop_def},
            )
        )

    for h in headers:
        if not h:
            continue
        if h in existing_props:
            # For Source select, ensure option 'БАЗА' exists
            if h == "Source" and existing_props[h].get("type") == "select":
                options = existing_props[h].get("select", {}).get("options", [])
                if not any(opt.get("name") == "БАЗА" for opt in options):
                    # Update to include option
                    new_options = options + [{"name": "БАЗА"}]
                    add_property(
                        "Source",
                        {"select": {"options": new_options}},
                    )
            # Ensure special property types exist
            if h == "ДАТА ПРОДАЖУ" and existing_props[h].get("type") != "date":
                add_property(h, {"date": {}})
            if h == "ТОВАР" and existing_props[h].get("type") != "multi_select":
                add_property(h, {"multi_select": {"options": []}})
            if (
                h in ("Кіл-ть штук", "ЦІНА")
                and existing_props[h].get("type") != "number"
            ):
                add_property(h, {"number": {}})
            # Ensure address text property exists; avoid touching Notion 'place' type
            if h in ("Адреса", "АДРЕСА") and "Адреса" not in existing_props:
                add_property("Адреса", {"rich_text": {}})
            continue

        # Create missing property
        if h == "Name":
            add_property("Name", {"title": {}})
        elif h == "Source":
            add_property("Source", {"select": {"options": [{"name": "БАЗА"}]}})
        elif h in ("Адреса", "АДРЕСА"):
            # Create explicit 'Адреса' rich_text; do not attempt to create 'Place' to avoid conflicts
            add_property("Адреса", {"rich_text": {}})
        elif h == "ДАТА ПРОДАЖУ":
            add_property(h, {"date": {}})
        elif h == "ТОВАР":
            add_property(h, {"multi_select": {"options": []}})
        elif h in ("Кіл-ть штук", "ЦІНА"):
            add_property(h, {"number": {}})
        else:
            add_property(h, {"rich_text": {}})


def main() -> None:
    """Main run function supporting dry-run and limit."""

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
                help="Maximum number of new pages to create (omit for all).",
            )
            parser.add_argument(
                "--show-payload",
                action="store_true",
                help="Print JSON payload for each page (use with --dry-run to audit).",
            )
            parser.add_argument(
                "--confirm",
                action="store_true",
                help="Required to run in non-dry mode when database already has entries.",
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
    file_name = parsed.file_name  # type: ignore
    dry_run = bool(parsed.dry_run)  # type: ignore
    limit = parsed.limit if parsed.limit and parsed.limit > 0 else None  # type: ignore
    show_payload = bool(parsed.show_payload)  # type: ignore
    confirm = bool(parsed.confirm)  # type: ignore

    client_rows, headers = parse_excel(file_name=file_name)  # type: ignore

    notion_client = notion_controller.NotionController()

    # Ensure properties unless dry-run
    if dry_run:
        print("[DRY-RUN] Would ensure properties for headers:", headers)
    else:
        ensure_properties(notion_client, os.environ["CRM_DATABASE_ID"], headers)

    created_count = 0

    for row in client_rows:
        name = row.get("ПОКУПЕЦЬ") or row.get("Name") or ""
        name = name.strip()
        # Skip rows without a name or with only numeric values (like serial numbers)
        if not name or re.fullmatch(r"[\d\s.,]+", name):
            continue

        exists = notion_client.entry_exists_in_database(
            database_id=os.environ["CRM_DATABASE_ID"],
            property_name="Name",
            value=name,
            property_type="title",
        )
        if exists:
            print(f"Client '{name}' already exists. Skipping.")
            continue
        if limit is not None and created_count >= limit:
            print(f"Reached creation limit ({limit}); stopping.")
            break

        # Build dynamic properties mapping from row
        page_properties: dict = {
            "Name": {"title": [{"text": {"content": name}}]},
        }

        # Prepare multi-select options for ТОВАР
        product_val = row.get("ТОВАР", "").strip()
        if product_val:
            raw_items = [i.strip() for i in product_val.splitlines() if i.strip()]
            # Sanitize: Notion multi_select option names cannot include commas
            sanitized_items = [re.sub(r",+", " ", i).strip() for i in raw_items]
            # Filter out numeric-like tokens (misparsed values like prices)
            items = [i for i in sanitized_items if not re.fullmatch(r"[\d\s.,]+", i)]
            if items:
                # fetch current options
                db = notion_client.notion_request_with_retry(
                    lambda: notion_client.retrieve_database(
                        os.environ["CRM_DATABASE_ID"]
                    )
                )
                db_dict = cast(dict, db)
                props = db_dict.get("properties", {})
                current_options = []
                if (
                    props.get("ТОВАР", {})
                    and props["ТОВАР"].get("type") == "multi_select"
                ):
                    current_options = (
                        props["ТОВАР"].get("multi_select", {}).get("options", [])
                    )
                missing = [
                    i
                    for i in items
                    if not any(o.get("name") == i for o in current_options)
                ]
                if missing:
                    new_options = current_options + [{"name": i} for i in missing]
                    notion_client.notion_request_with_retry(
                        lambda: notion_client.notion_client.databases.update(  # type: ignore
                            database_id=os.environ["CRM_DATABASE_ID"],
                            properties={
                                "ТОВАР": {"multi_select": {"options": new_options}}
                            },
                        )
                    )

        for key, value in row.items():
            if key in ("ПОКУПЕЦЬ", "Name"):
                continue
            if key == "Source":
                page_properties["Source"] = {"select": {"name": value or "БАЗА"}}
                continue
            if key in ("Адреса", "АДРЕСА"):
                # Always set 'Адреса' rich_text
                page_properties["Адреса"] = {
                    "rich_text": [{"text": {"content": value or ""}}]
                }
                # Optionally set 'Place' only if database property exists and is rich_text
                db = notion_client.notion_request_with_retry(
                    lambda: notion_client.retrieve_database(
                        os.environ["CRM_DATABASE_ID"]
                    )
                )
                db_props = cast(dict, db).get("properties", {})
                if "Place" in db_props and db_props["Place"].get("type") == "rich_text":
                    page_properties["Place"] = {
                        "rich_text": [{"text": {"content": value or ""}}]
                    }
                continue
            if key == "ДАТА ПРОДАЖУ":
                val = (value or "").strip()
                if not val:
                    # Skip empty date to satisfy Notion validation
                    continue
                # Expect DD.MM.YYYY; convert to YYYY-MM-DD
                m = re.search(r"^(\d{2})\.(\d{2})\.(\d{4})$", val)
                if m:
                    dd, mm, yyyy = m.groups()
                    date_str = f"{yyyy}-{mm}-{dd}"
                else:
                    date_str = val
                page_properties[key] = {"date": {"start": date_str}}
                continue
            if key == "ТОВАР":
                raw_items = [i.strip() for i in (value or "").splitlines() if i.strip()]
                # Sanitize: replace commas which are invalid in Notion multi_select names
                sanitized_items = [re.sub(r",+", " ", i).strip() for i in raw_items]
                # Filter out numeric-like tokens (misparsed values like prices)
                items = [
                    i for i in sanitized_items if not re.fullmatch(r"[\d\s.,]+", i)
                ]
                page_properties[key] = {"multi_select": [{"name": i} for i in items]}
                continue
            if key in ("Кіл-ть штук", "ЦІНА"):
                try:
                    num = float((value or "").replace(" ", "").replace(",", "."))
                except ValueError:
                    num = 0
                page_properties[key] = {"number": num}
                continue
            # Use rich_text for other fields
            page_properties[key] = {"rich_text": [{"text": {"content": value or ""}}]}

        if show_payload:
            print("[PAYLOAD]", json.dumps(page_properties, ensure_ascii=False))

        if dry_run:
            created_count += 1
            continue

        if not confirm:
            print(
                "Refusing to create pages without --confirm \
                    (safety guard). Re-run with --confirm to proceed."
            )
            break

        try:
            notion_client.notion_request_with_retry(
                lambda: notion_client.notion_client.pages.create(
                    parent={"database_id": os.environ["CRM_DATABASE_ID"]},
                    properties=page_properties,
                )
            )
            created_count += 1
            print(f"Added client: {name} (properties: {len(page_properties)})")
        except (
            notion_controller.APIResponseError,
            notion_controller.RequestTimeoutError,
        ) as e:  # type: ignore[attr-defined]
            print(f"Failed to add client {name}: {e}")

    print(
        f"Finished. New pages {'planned' if dry_run else 'created'}: \
            {created_count}. Headers processed: {len(headers)}."
    )


if __name__ == "__main__":
    main()
