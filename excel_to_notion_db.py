"""Export Excel to Notion dabatase"""

import argparse

import notion_controller
import dotenv
import os

# TODO: Do I really want to convert Excel to CSV every time I need to add new clients?
import csv

dotenv.load_dotenv()


def parse_excel(file_name: str) -> list:
    """Parse values from Excel and return a list"""
    results = []

    with open(file_name, mode="r", encoding="UTF-8", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")

        headers = reader.fieldnames
        print("Available columns:", headers)

        for row in reader:
            try:
                client = row["ПОКУПЕЦЬ"]
                address = row["АДРЕСА"]

                if client != "" and address != "":
                    results.append({"name": client, "address": address})

            except KeyError as e:
                print(f"Warning: Column {e} not found in the CSV file")
                continue

    return results


def main() -> None:
    """Main run function"""

    def args_parser():
        """Get path to excel file from command line args"""
        if os.environ.get("DEBUG") is False:
            parser = argparse.ArgumentParser(
                description="Export Excel to Notion database"
            )
            parser.add_argument(
                "file_name",
                type=str,
                help="Path to the Excel file (CSV format)",
                default="clients.csv",
            )

            args = parser.parse_args()

            return args.file_name

    file_name = args_parser() if os.environ.get("DEBUG") is False else "clients.csv"
    client_address_list = parse_excel(file_name=file_name)  # type: ignore

    notion_client = notion_controller.NotionController()

    for client in client_address_list:
        if notion_client.entry_exists_in_database(
            database_id=os.environ["CRM_DATABASE_ID"],
            property_name="Name",
            value=client["name"],
            property_type="title",
        ):
            print(
                f"Client '{client['name']}' already exists in the database. Skipping."
            )
        else:
            # placeholder
            print("Adding client:", client["name"])


if __name__ == "__main__":
    main()
