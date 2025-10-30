"""Export Excel to Notion dabatase"""

import argparse
import csv


def prepare_to_paste(values: list) -> list:
    """Prepare Excel values to paste into Notion database"""
    return values


def parse_excel(file_name: str) -> list:
    """Parse values from Excel and return a list"""
    results = []
    with open(file_name, mode="r", encoding="UTF-8", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")

        for row in reader:
            if row["ПОКУПЕЦЬ"] != "" and row["АДРЕСА"] != "":
                results.append({"name": row["ПОКУПЕЦЬ"], "address": row["АДРЕСА"]})
    return results


def main() -> None:
    """Main run function"""

    parser = argparse.ArgumentParser(description="Export Excel to Notion database")
    parser.add_argument(
        "file_name",
        type=str,
        help="Path to the Excel file (CSV format)",
    )

    args = parser.parse_args()

    excel_values = parse_excel(args.file_name)
    notion_values = prepare_to_paste(excel_values)

    for item in notion_values:
        print(item)


if __name__ == "__main__":
    main()
