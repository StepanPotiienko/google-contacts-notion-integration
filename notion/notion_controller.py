"""Notion related stuff"""

import os
import time
import dotenv
import httpx
from notion_client import Client
from notion_client.errors import RequestTimeoutError

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
            except (
                RequestTimeoutError,
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
            ) as e:
                last_exception = e
                if attempt == max_retries - 1:
                    break

                delay = initial_delay * (2**attempt)  # Exponential backoff
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

        except Exception as e:
            print(f"Error connecting to Notion database: {e}")
            return tasks_list

    def get_title_property_name(self, database_id):
        """Parse the name of the title property"""

        def retrieve_database():
            return self.notion_client.databases.retrieve(database_id=database_id)

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
        except Exception as e:
            print(f"Error debugging database schema: {e}")

    def check_contact_exists(self, database_id, contact_name):
        """Check if a contact already exists in the database"""

        def query_contact():
            return self.notion_client.databases.query(
                database_id=database_id,
                filter={
                    "property": "Name",
                    "title": {"equals": contact_name},
                },
            )

        try:
            response = self.notion_request_with_retry(query_contact)
            return len(response.get("results", [])) > 0  # type: ignore
        except Exception as e:
            print(f"Error checking contact {contact_name}: {e}")
            return False  # Assume it doesn't exist if we can't check

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

    def delete_name_duplicates(self, database_id: str):
        """Delete duplicates in database based on Name property with batching to avoid 502 errors"""
        print(f"Checking for duplicates in database: {database_id}")

        all_pages = []
        start_cursor = None
        has_more = True

        print("Fetching all pages from database...")
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
            print(f"Fetched {len(response['results'])} pages...")  # type: ignore

        print(f"Total pages in database: {len(all_pages)}")

        name_to_pages = {}

        for page in all_pages:
            props = page["properties"]
            title_prop = props.get("Name", {}).get("title", [])
            name = title_prop[0]["plain_text"] if title_prop else "Untitled"
            page_id = page["id"]

            if name not in name_to_pages:
                name_to_pages[name] = []

            name_to_pages[name].append(
                {
                    "page_id": page_id,
                    "created_time": page.get("created_time", ""),
                    "last_edited_time": page.get("last_edited_time", ""),
                }
            )

        duplicates = {
            name: pages for name, pages in name_to_pages.items() if len(pages) > 1
        }

        if not duplicates:
            print("No duplicates found!")
            return

        print(f"Found {len(duplicates)} duplicate entries:")
        for name, pages in duplicates.items():
            print(f"  '{name}': {len(pages)} instances")

        all_pages_to_delete = []
        for name, pages in duplicates.items():
            pages.sort(key=lambda x: x["last_edited_time"], reverse=True)
            all_pages_to_delete.extend(pages[1:])

        print(f"\nStarting deletion of {len(all_pages_to_delete)} pages in batches...")

        batch_size = 5
        deleted_count = 0
        batch_count = 0

        for i, page_info in enumerate(all_pages_to_delete):
            try:

                def delete_page():
                    return self.notion_client.pages.update(
                        page_id=page_info["page_id"], archived=True
                    )

                self.notion_request_with_retry(delete_page)
                deleted_count += 1
                print(
                    f"Deleted {i+1}/{len(all_pages_to_delete)}: {page_info['page_id']}"
                )

                if (i + 1) % batch_size == 0:
                    batch_count += 1
                    print(
                        f"\nBatch {batch_count} completed ({batch_size} pages).\
                            Waiting 5 seconds before next batch..."
                    )
                    time.sleep(5)
                else:
                    time.sleep(0.3)

            except Exception as e:
                print(f"Failed to delete page {page_info['page_id']}: {e}")

            print(
                f"\nDeletion completed! Successfully removed \
                    {deleted_count}/{len(all_pages_to_delete)} duplicate pages."
            )

    def delete_duplicate_contacts_in_database(self, database_id, contacts_list):
        """Remove contacts that already exist in the database"""
        print("Checking for duplicates...")
        filtered_contacts = []

        for i, contact in enumerate(contacts_list):
            contact_name = contact[0]
            print(f"Checking {i+1}/{len(contacts_list)}: {contact_name}")

            if not self.check_contact_exists(database_id, contact_name):
                filtered_contacts.append(contact)
            else:
                print(f"Removed duplicate: {contact_name}")

            # Rate limiting
            time.sleep(0.1)

        print(f"{len(filtered_contacts)} contacts remaining after cleaning up")
        return filtered_contacts

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

        existing_tasks = self.get_all_existing_tasks()

        # Do not exist in the database yet
        new_contacts = [
            contact for contact in contacts_list if contact[0] not in existing_tasks
        ]

        print(f"Found {len(new_contacts)} new contacts to create")

        success_count = 0
        for i, contact in enumerate(new_contacts):
            contact_name = contact[0]
            print(f"Creating {i+1}/{len(new_contacts)}: {contact_name}")

            if self.create_contact_page(contact):
                success_count += 1

            # Rate limiting
            time.sleep(0.5)

        print(
            f"Sync completed! Successfully created {success_count}/{len(new_contacts)} contacts"
        )


notion_controller = NotionController()


def connect_to_notion_database():
    """Global access function to connect to Notion database"""
    return notion_controller.connect_to_notion_database_and_return_tasks_list()


def get_title_property_name(database_id):
    """Global access function to get title property name"""
    return notion_controller.get_title_property_name(database_id)


def debug_database_schema(database_id):
    """Global access function to debug database schema"""
    notion_controller.debug_database_schema(database_id)


def delete_duplicates_in_database(database_id, contacts_list):
    """Global access function to delete duplicate contacts in database"""
    return notion_controller.delete_duplicate_contacts_in_database(
        database_id, contacts_list
    )


def find_missing_tasks(contacts_list):
    """Global access function to find missing tasks"""
    notion_controller.find_missing_tasks(contacts_list)


def delete_duplicates():
    """Global access function to delete duplicates from a database"""
    database_id = str(input("Enter database id: "))
    notion_controller.delete_name_duplicates(database_id=database_id)
