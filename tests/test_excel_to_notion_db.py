import os
import sys
import types
import unittest

# Ensure project root on sys.path for local 'notion' package
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Stub notion_client module before importing controller/excel module
stub_notion_client = types.ModuleType("notion_client")
stub_errors = types.SimpleNamespace(
    RequestTimeoutError=Exception, APIResponseError=Exception
)
setattr(stub_notion_client, "errors", stub_errors)
setattr(stub_notion_client, "Client", lambda *a, **k: None)  # basic stub
sys.modules.setdefault("notion_client", stub_notion_client)

# Import target module
from notion import excel_to_notion_db  # noqa: E402


class DummyDatabases:
    def __init__(self):
        self.update_calls = []

    def update(self, database_id, properties):  # noqa: D401
        self.update_calls.append({"database_id": database_id, "properties": properties})
        return {"ok": True}


class DummyPages:
    def __init__(self):
        self.create_calls = []

    def create(self, parent, properties):  # noqa: D401
        self.create_calls.append({"parent": parent, "properties": properties})
        return {"id": "stub-page"}


class DummyNotionClient:
    def __init__(self):
        self.databases = DummyDatabases()
        self.pages = DummyPages()


class DummyController:
    def __init__(self, existing_props=None):
        self.notion_client = DummyNotionClient()
        self._existing_props = existing_props or {"Name": {"type": "title"}}

    def retrieve_database(self, _database_id):  # unused arg
        return {"properties": self._existing_props}

    def notion_request_with_retry(self, func):
        return func()

    def entry_exists_in_database(self, **_kwargs):  # always return False for tests
        return False


class TestExcelToNotionMigration(unittest.TestCase):
    def setUp(self):
        self.temp_csv_path = "tests/temp_clients.csv"
        sample_csv = (
            "ПОКУПЕЦЬ;АДРЕСА;ДАТА ПРОДАЖУ;ТОВАР;Кіл-ть штук;ЦІНА\n"
            "Client A;Street 1;31.12.2025;Item One\\nItem Two;10;1 234,50\n"
        )
        os.makedirs("tests", exist_ok=True)
        with open(self.temp_csv_path, "w", encoding="utf-8") as f:
            f.write(sample_csv)

    def tearDown(self):
        try:
            os.remove(self.temp_csv_path)
        except OSError:
            pass

    def test_parse_excel_returns_rows_and_headers(self):
        rows, headers = excel_to_notion_db.parse_excel(self.temp_csv_path)
        self.assertIn("ПОКУПЕЦЬ", headers)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ПОКУПЕЦЬ"], "Client A")
        self.assertEqual(rows[0]["Source"], "БАЗА")  # defaulted

    def test_property_creation_for_special_columns(self):
        rows, headers = excel_to_notion_db.parse_excel(self.temp_csv_path)
        controller = DummyController(existing_props={"Name": {"type": "title"}})
        excel_to_notion_db.ensure_properties(controller, "dummy_db", headers)  # type: ignore[arg-type]
        created = controller.notion_client.databases.update_calls
        # Collect property names created
        created_props = set()
        for call in created:
            created_props.update(call["properties"].keys())
        self.assertIn("Place", created_props)  # derived from АДРЕСА
        self.assertIn("ДАТА ПРОДАЖУ", created_props)
        self.assertIn("ТОВАР", created_props)
        self.assertIn("Кіл-ть штук", created_props)
        self.assertIn("ЦІНА", created_props)
        self.assertIn("Source", created_props)

    def test_page_properties_mapping(self):
        rows, headers = excel_to_notion_db.parse_excel(self.temp_csv_path)
        controller = DummyController(
            existing_props={
                "Name": {"type": "title"},
                "Place": {"type": "rich_text"},
                "ДАТА ПРОДАЖУ": {"type": "date"},
                "ТОВАР": {"type": "multi_select", "multi_select": {"options": []}},
                "Кіл-ть штук": {"type": "number"},
                "ЦІНА": {"type": "number"},
                "Source": {"type": "select", "select": {"options": [{"name": "БАЗА"}]}},
            }
        )
        os.environ["CRM_DATABASE_ID"] = "dummy_db"
        # Ensure props exist
        excel_to_notion_db.ensure_properties(controller, "dummy_db", headers)  # type: ignore[arg-type]
        # Simulate main loop logic for one row
        row = rows[0]
        name = row.get("ПОКУПЕЦЬ") or row.get("Name") or ""
        page_properties: dict[str, object] = {"Name": {"title": [{"text": {"content": name}}]}}  # type: ignore[arg-type]
        # emulate section from script (simplified)
        # Prepare multi-select options
        product_val = row.get("ТОВАР", "").strip()
        items = [i.strip() for i in product_val.splitlines() if i.strip()]
        if items:
            # Ensure options added
            controller.notion_client.databases.update(
                "dummy_db",
                {"ТОВАР": {"multi_select": {"options": [{"name": i} for i in items]}}},
            )
        # Map fields
        import re

        for key, value in row.items():
            if key in ("ПОКУПЕЦЬ", "Name"):
                continue
            if key == "Source":
                page_properties["Source"] = {"select": {"name": value or "БАЗА"}}  # type: ignore[index]
                continue
            if key in ("Адреса", "АДРЕСА"):
                page_properties["Place"] = {"rich_text": [{"text": {"content": value or ""}}]}  # type: ignore[index]
                continue
            if key == "ДАТА ПРОДАЖУ":
                val = (value or "").strip()
                m = re.search(r"^(\d{2})\.(\d{2})\.(\d{4})$", val)
                if m:
                    dd, mm, yyyy = m.groups()
                    iso = f"{yyyy}-{mm}-{dd}"
                else:
                    iso = val
                page_properties[key] = {"date": {"start": iso}}  # type: ignore[index]
                continue
            if key == "ТОВАР":
                page_properties[key] = {"multi_select": [{"name": i} for i in items]}  # type: ignore[index]
                continue
            if key in ("Кіл-ть штук", "ЦІНА"):
                try:
                    num = float((value or "").replace(" ", "").replace(",", "."))
                except ValueError:
                    num = 0
                page_properties[key] = {"number": num}  # type: ignore[index]
                continue
            page_properties[key] = {"rich_text": [{"text": {"content": value or ""}}]}  # type: ignore[index]

        controller.notion_client.pages.create(
            parent={"database_id": "dummy_db"}, properties=page_properties
        )
        created = controller.notion_client.pages.create_calls[-1]["properties"]
        # Assertions
        self.assertEqual(
            created["Place"]["rich_text"][0]["text"]["content"], "Street 1"
        )
        self.assertEqual(created["ДАТА ПРОДАЖУ"]["date"]["start"], "2025-12-31")
        self.assertEqual(len(created["ТОВАР"]["multi_select"]), 2)
        self.assertEqual(created["ТОВАР"]["multi_select"][0]["name"], "Item One")
        self.assertEqual(created["ТОВАР"]["multi_select"][1]["name"], "Item Two")
        self.assertEqual(created["Кіл-ть штук"]["number"], 10.0)
        self.assertAlmostEqual(created["ЦІНА"]["number"], 1234.50)
        self.assertEqual(created["Source"]["select"]["name"], "БАЗА")


if __name__ == "__main__":
    unittest.main()
