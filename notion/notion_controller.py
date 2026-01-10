"""Notion related stuff"""

import os
import time
import dotenv
import httpx
from typing import Optional
from notion_client import Client

try:
    from notion_client.errors import RequestTimeoutError, APIResponseError
except Exception:  # Fallback for test stubs that don't expose errors submodule

    class RequestTimeoutError(Exception):
        pass

    class APIResponseError(Exception):
        pass


dotenv.load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
CRM_DATABASE_ID = os.getenv("CRM_DATABASE_ID")
PRODUCTION_DATABASE_ID = os.getenv("PRODUCTION_DATABASE_ID")


class NotionController:
    """Main Notion controller class"""

    def __init__(self):
        self.notion_client = self._create_client()

    def _create_client(self):
        """Create Notion client with proper timeout settings"""
        http_client = httpx.Client(timeout=httpx.Timeout(30.0))
        return Client(auth=NOTION_API_KEY, client=http_client)

    def notion_request_with_retry(self, func, max_retries=3, initial_delay=2):
        """Wrapper function to retry Notion API calls with exponential backoff"""
        last_exception = None
        for attempt in range(max_retries):
            try:
                return func()
            except (RequestTimeoutError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                last_exception = e
                if attempt == max_retries - 1:
                    break
                delay = initial_delay * (2**attempt)
                print(
                    f"Notion API request failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
        print(f"All retries failed. Last error: {last_exception}")
        raise last_exception  # type: ignore

    def connect_to_notion_database_and_return_tasks_list(self):
        """Connect to a notion database and return tasks list"""
        tasks_list = []

        print("Listing tasks from Notion database...")

        def query_database():
            return self.notion_client.databases.query(database_id=CRM_DATABASE_ID)  # type: ignore

        try:
            results = self.notion_request_with_retry(query_database)

            for page in results["results"]:  # type: ignore
                props = page["properties"]
                title_prop = props["Name"]["title"]
                title = title_prop[0]["plain_text"] if title_prop else "Untitled"
                tasks_list.append(title)

            print(f"Found {len(tasks_list)} tasks in database")
            return tasks_list

        except (RequestTimeoutError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            print(f"Error connecting to Notion database: {e}")
            return tasks_list

    def get_title_property_name(self, database_id):
        """Parse the name of the title property"""

        def retrieve_database():
            return self.notion_client.databases.retrieve(database_id=database_id)  # type: ignore

        try:
            db = self.notion_request_with_retry(retrieve_database)
            for prop_name, prop in db["properties"].items():  # type: ignore
                if prop["type"] == "title":
                    return prop_name
            raise ValueError("No title property found in database")
        except Exception as e:
            print(f"Error getting title property: {e}")
            raise

    def retrieve_database(self, database_id):
        """Retrieve database data"""
        return self.notion_client.databases.retrieve(database_id=database_id)

    def debug_database_schema(self, database_id):
        """Display properties of a database"""
        try:
            db = self.notion_request_with_retry(self.retrieve_database(database_id))
            print("Database schema:")
            for name, prop in db["properties"].items():  # type: ignore
                print(f"- {name}: {prop['type']}")
        except (RequestTimeoutError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            print(f"Error debugging database schema: {e}")

    def check_contact_exists(self, database_id, contact_name, phone=None):
        """Check if a contact already exists in the database by name or phone"""

        # First check by name
        def query_by_name():
            return self.notion_client.databases.query(
                database_id=database_id,
                filter={
                    "property": "Name",
                    "title": {"equals": contact_name},
                },
            )

        try:
            response = self.notion_request_with_retry(query_by_name)
            if len(response.get("results", [])) > 0:  # type: ignore
                return True
        except (RequestTimeoutError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            print(f"Error checking contact {contact_name} by name: {e}")

        # If phone is provided, also check by phone number
        if phone and phone != "No phone":
            # Normalize phone number
            normalized_phone = "".join(c for c in phone if c.isdigit() or c == "+")

            # Try checking with Phone property (rich_text type)
            def query_by_phone():
                return self.notion_client.databases.query(
                    database_id=database_id,
                    filter={
                        "property": "Phone",
                        "rich_text": {
                            "contains": normalized_phone[-10:]
                        },  # Last 10 digits
                    },
                    page_size=100,
                )

            try:
                response = self.notion_request_with_retry(query_by_phone)
                results = response.get("results", [])  # type: ignore

                # Check if any result has the same normalized phone
                for page in results:
                    props = page.get("properties", {})
                    phone_prop = props.get("Phone", {})

                    if phone_prop.get("type") == "rich_text":
                        texts = phone_prop.get("rich_text", [])
                        if texts:
                            existing_phone = texts[0].get("plain_text", "")
                            existing_normalized = "".join(
                                c for c in existing_phone if c.isdigit() or c == "+"
                            )
                            if existing_normalized == normalized_phone:
                                print(
                                    f"Found duplicate by phone: {contact_name} ({phone})"
                                )
                                return True

            except (RequestTimeoutError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                print(f"Error checking contact by phone {phone}: {e}")

        return False  # Contact doesn't exist

    def entry_exists_in_database(
        self, database_id, property_name, value, property_type="title"
    ):
        """Generic check if an entry with a given property value exists in a database."""
        try:
            if property_type == "checkbox":
                # Normalize checkbox value to boolean
                if isinstance(value, str):
                    val_bool = value.lower() in ("true", "1", "yes")
                else:
                    val_bool = bool(value)
                filter_obj = {
                    "property": property_name,
                    "checkbox": {"equals": val_bool},
                }
            elif property_type == "number":
                filter_obj = {"property": property_name, "number": {"equals": value}}
            else:
                # title, rich_text, email, phone_number, select
                filter_obj = {
                    "property": property_name,
                    property_type: {"equals": value},
                }

            def query():
                return self.notion_client.databases.query(
                    database_id=database_id, filter=filter_obj, page_size=1
                )

            response = self.notion_request_with_retry(query)
            return len(response.get("results", [])) > 0  # type: ignore

        except (
            RequestTimeoutError,
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
            KeyError,
            ValueError,
        ):
            return False

    def delete_name_duplicates(
        self, database_id: str, max_minutes: Optional[int] = None
    ):
        """Stream through the database and archive duplicate pages as encountered.

        Efficient approach:
        - Paginate instead of loading entire DB into memory.
        - Maintain a set of seen names (canonical = first occurrence).
        - Archive subsequent pages with same Name immediately (duplicate).
        - Periodically checkpoint (cursor + seen names + stats) to allow resume.
        - Respect optional time budget during both fetch and delete phases.
        """
        print(f"Streaming duplicate cleanup for database: {database_id}")

        start_time = time.time()
        deadline = (
            start_time + max_minutes * 60
            if isinstance(max_minutes, int) and max_minutes > 0
            else None
        )

        checkpoint_path = "dedup_checkpoint.json"
        seen_names: set[str] = set()
        deleted_count = 0
        failed_count = 0
        pages_scanned = 0
        resume_cursor = None

        # Load checkpoint if exists
        if os.path.exists(checkpoint_path):
            import json

            try:
                with open(checkpoint_path, "r", encoding="UTF-8") as f:
                    data = json.load(f)
                    seen_names = set(data.get("seen_names", []))
                    resume_cursor = data.get("cursor")
                    deleted_count = int(data.get("deleted_count", 0))
                    pages_scanned = int(data.get("pages_scanned", 0))
                    print(
                        f"Resuming: {pages_scanned} pages scanned, {deleted_count} duplicates deleted."
                    )
            except Exception as e:  # noqa: BLE001
                print(f"Could not load checkpoint: {e}. Continuing without resume.")

        def save_checkpoint(next_cursor):
            import json

            try:
                with open(checkpoint_path, "w", encoding="UTF-8") as f:
                    json.dump(
                        {
                            "seen_names": list(seen_names),
                            "cursor": next_cursor,
                            "deleted_count": deleted_count,
                            "pages_scanned": pages_scanned,
                            "timestamp": time.time(),
                        },
                        f,
                    )
            except Exception as e:  # noqa: BLE001
                print(f"Warning: failed to save checkpoint: {e}")

        batch_delete_interval = 0  # no artificial delay unless rate limiting needed
        checkpoint_every_pages = 500  # reduce write overhead

        next_cursor = resume_cursor
        has_more = True
        page_size = 100
        early_exit = False

        while has_more:
            if deadline is not None and time.time() >= deadline:
                early_exit = True
                print("Time budget reached mid-stream. Saving checkpoint and exiting.")
                save_checkpoint(next_cursor)
                break

            def query_page():
                params = {"database_id": database_id, "page_size": page_size}
                if next_cursor:
                    params["start_cursor"] = next_cursor
                return self.notion_client.databases.query(**params)

            try:
                response = self.notion_request_with_retry(query_page)
            except APIResponseError as e:  # Handle invalid/expired cursor
                msg = str(e)
                if "start_cursor" in msg and "invalid" in msg:
                    print(
                        "Notion returned invalid start_cursor. Clearing checkpoint and restarting from beginning."
                    )
                    # Clear cursor and checkpoint, then retry from the beginning next loop
                    next_cursor = None
                    resume_cursor = None
                    # Clear seen set to avoid misclassifying early canonical pages as duplicates
                    seen_names = set()
                    if os.path.exists(checkpoint_path):
                        try:
                            os.remove(checkpoint_path)
                            print("Checkpoint removed due to invalid cursor.")
                        except OSError as rem_err:
                            print(f"Failed to remove checkpoint: {rem_err}")
                    # Start next iteration which will query without start_cursor
                    continue
                # Re-raise if it's a different API error
                raise
            results = response.get("results", [])  # type: ignore
            has_more = response.get("has_more", False)  # type: ignore
            next_cursor = response.get("next_cursor")  # type: ignore

            for page in results:
                pages_scanned += 1
                props = page.get("properties", {})
                title_prop = props.get("Name", {}).get("title", [])
                name = (
                    title_prop[0].get("plain_text", "Untitled")
                    if title_prop
                    else "Untitled"
                )
                page_id = page.get("id")

                if name in seen_names:
                    # Duplicate: archive immediately
                    try:

                        def archive_page(pid=page_id):
                            return self.notion_client.pages.update(
                                page_id=pid, archived=True
                            )

                        self.notion_request_with_retry(archive_page)
                        deleted_count += 1
                    except Exception as e:  # noqa: BLE001
                        failed_count += 1
                        print(f"Failed to archive duplicate page {page_id}: {e}")
                else:
                    seen_names.add(name)

                # Progress output every 500 pages
                if pages_scanned % 500 == 0:
                    elapsed = time.time() - start_time
                    rate = pages_scanned / elapsed if elapsed > 0 else 0
                    print(
                        f"Scanned {pages_scanned} pages | Duplicates deleted: {deleted_count} | "
                        f"Failures: {failed_count} | Rate: {rate:.1f} pages/sec"
                    )

                # Save checkpoint periodically
                if pages_scanned % checkpoint_every_pages == 0:
                    save_checkpoint(next_cursor)

                if deadline is not None and time.time() >= deadline:
                    early_exit = True
                    print(
                        "Time budget reached during page processing. Saving checkpoint."
                    )
                    save_checkpoint(next_cursor)
                    break

            if early_exit:
                break

            # Optional small sleep for rate limit smoothing
            if batch_delete_interval > 0:
                time.sleep(batch_delete_interval)

        if not early_exit:
            # Completed scan of database
            if os.path.exists(checkpoint_path):
                os.remove(checkpoint_path)
                print("Checkpoint removed (completed scan).")

        print(
            f"Duplicate cleanup finished. Scanned {pages_scanned} pages. "
            f"Deleted {deleted_count} duplicates (failed {failed_count})."
        )

    def delete_duplicate_contacts_in_database(self, database_id, contacts_list):
        """Remove contacts that already exist in the database using batch fetch approach"""
        print("Checking for duplicates...")

        if not contacts_list:
            return []

        # Fetch all existing contacts once (batch approach)
        print("Fetching existing contacts from database...")
        existing_contacts = self._get_all_contacts_map(database_id)
        print(f"Found {len(existing_contacts)} existing contacts in database")

        filtered_contacts = []
        duplicate_count = 0

        for i, contact in enumerate(contacts_list):
            contact_name = contact[0]
            phone = contact[2] if len(contact) > 2 else None
            normalized_phone = (
                self._normalize_phone(phone) if phone and phone != "No phone" else None
            )

            # Check in-memory against fetched data
            is_duplicate = False

            # Check by name
            if contact_name in existing_contacts["by_name"]:
                is_duplicate = True
            # Check by phone if available
            elif normalized_phone and normalized_phone in existing_contacts["by_phone"]:
                is_duplicate = True

            if not is_duplicate:
                filtered_contacts.append(contact)
            else:
                duplicate_count += 1
                if (i + 1) % 100 == 0 or (i + 1) == len(contacts_list):
                    print(
                        f"Progress: {i+1}/{len(contacts_list)} checked, {duplicate_count} duplicates found"
                    )

        print(f"Removed {duplicate_count} duplicates")
        print(f"{len(filtered_contacts)} new contacts remaining after cleanup")
        return filtered_contacts

    def _normalize_phone(self, phone):
        """Normalize phone number by removing non-digit characters except +"""
        if not phone:
            return ""
        return "".join(c for c in phone if c.isdigit() or c == "+")

    def _get_all_contacts_map(self, database_id):
        """Fetch all contacts from database and create lookup maps by name and phone"""
        all_pages = []
        start_cursor = None
        has_more = True

        while has_more:

            def query_page():
                params = {"database_id": database_id, "page_size": 100}
                if start_cursor:
                    params["start_cursor"] = start_cursor
                return self.notion_client.databases.query(**params)

            response = self.notion_request_with_retry(query_page)
            all_pages.extend(response["results"])  # type: ignore
            has_more = response.get("has_more", False)  # type: ignore
            start_cursor = response.get("next_cursor")  # type: ignore

            if len(all_pages) % 1000 == 0:
                print(f"Fetched {len(all_pages)} pages...")

        # Build lookup maps
        by_name = set()
        by_phone = set()

        for page in all_pages:
            props = page.get("properties", {})

            # Extract name
            title_prop = props.get("Name", {}).get("title", [])
            if title_prop:
                name = title_prop[0].get("plain_text", "")
                if name:
                    by_name.add(name)

            # Extract phone
            phone_prop = props.get("Phone", {})
            if phone_prop.get("type") == "rich_text":
                texts = phone_prop.get("rich_text", [])
                if texts:
                    phone = texts[0].get("plain_text", "")
                    normalized = self._normalize_phone(phone)
                    if normalized:
                        by_phone.add(normalized)

        return {"by_name": by_name, "by_phone": by_phone}

    def get_all_existing_tasks(self):
        """Get all existing tasks from the database with pagination"""
        all_results = []
        start_cursor = None
        has_more = True

        print("Fetching all existing tasks...")

        while has_more:

            def query_page():
                params = {"database_id": CRM_DATABASE_ID, "page_size": 100}
                if start_cursor:
                    params["start_cursor"] = start_cursor
                return self.notion_client.databases.query(**params)

            try:
                response = self.notion_request_with_retry(query_page)
                all_results.extend(response["results"])  # type: ignore
                has_more = response.get("has_more", False)  # type: ignore
                start_cursor = response.get("next_cursor")  # type: ignore

                print(f"Fetched {len(response['results'])} tasks...")  # type: ignore

            except Exception as e:
                print(f"Error fetching page: {e}")
                break

        existing_tasks = set()
        for page in all_results:
            props = page["properties"]
            title_prop = props["Name"]["title"]
            title = title_prop[0]["plain_text"] if title_prop else "Untitled"
            existing_tasks.add(title)

        print(f"Total existing tasks: {len(existing_tasks)}")
        return existing_tasks

    def create_contact_page(self, contact):
        """Create a new page for a contact"""
        contact_name, email, phone = contact

        def create_page():
            properties = {"Name": {"title": [{"text": {"content": contact_name}}]}}

            # Only add email if it's valid
            if email and email != "No email":
                properties["Email"] = {"email": email}

            # Only add phone if it's valid
            if phone and phone != "No phone":
                properties["Phone"] = {"rich_text": [{"text": {"content": phone}}]}

            return self.notion_client.pages.create(
                parent={"database_id": CRM_DATABASE_ID},
                properties=properties,
            )

        try:
            self.notion_request_with_retry(create_page)
            print(f"✓ Successfully created: {contact_name}")
            return True
        except Exception as e:
            print(f"✗ Failed to create {contact_name}: {e}")
            return False

    def find_missing_tasks(self, contacts_list):
        """Create pages for contacts that don't exist in the database"""
        if not contacts_list:
            print("No contacts to process")
            return

        print(f"Starting sync with {len(contacts_list)} contacts...")

        # Note: contacts_list is already filtered by delete_duplicate_contacts_in_database
        # No need to fetch all existing tasks again - that would take 2+ hours!

        success_count = 0
        failed_count = 0

        for i, contact in enumerate(contacts_list):
            # Show progress every 10 contacts
            if (i + 1) % 10 == 0 or (i + 1) == len(contacts_list):
                print(
                    f"Progress: {i+1}/{len(contacts_list)} ({success_count} created, {failed_count} failed)"
                )

            if self.create_contact_page(contact):
                success_count += 1
            else:
                failed_count += 1

            # Rate limiting - reduced from 0.5s to 0.1s
            time.sleep(0.1)

        print(
            f"Sync completed! Successfully created {success_count}/{len(contacts_list)} contacts "
            f"({failed_count} failed)"
        )


notion_controller = NotionController()


def connect_to_notion_database():
    return notion_controller.connect_to_notion_database_and_return_tasks_list()


def get_title_property_name(database_id):
    return notion_controller.get_title_property_name(database_id)


def debug_database_schema(database_id):
    notion_controller.debug_database_schema(database_id)


def delete_duplicates_in_database(database_id, contacts_list):
    return notion_controller.delete_duplicate_contacts_in_database(
        database_id, contacts_list
    )


def find_missing_tasks(contacts_list):
    notion_controller.find_missing_tasks(contacts_list)


def delete_duplicates():
    database_id = str(input("Enter database id: "))
    notion_controller.delete_name_duplicates(database_id=database_id)
