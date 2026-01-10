"""Test script to demonstrate multi-purchase row splitting"""

import csv
import json
import re
from pathlib import Path


def _expand_multi_purchase_row(row: dict[str, str]) -> list[dict[str, str]]:
    """Split a row with multiple purchases into individual transaction records.

    Handles comma-separated values in:
    - ДАТА ПРОДАЖУ (dates)
    - ТОВАР (products)
    - Кіл-ть штук (quantities)
    - ЦІНА (prices)
    """
    # Split comma-separated values
    dates = [d.strip() for d in row.get("ДАТА ПРОДАЖУ", "").split(",") if d.strip()]
    products = [p.strip() for p in row.get("ТОВАР", "").split(",") if p.strip()]
    quantities = [q.strip() for q in row.get("Кіл-ть штук", "").split(",") if q.strip()]
    prices = [p.strip() for p in row.get("ЦІНА", "").split(",") if p.strip()]

    # If no multi-purchase data, return original row
    if not dates and not products and not quantities and not prices:
        return [row]

    # Determine max length for padding
    max_len = max(len(dates), len(products), len(quantities), len(prices))

    # If all are single values or empty, return original
    if max_len <= 1:
        return [row]

    # Pad lists to same length (use empty string for missing values)
    dates = dates + [""] * (max_len - len(dates))
    products = products + [""] * (max_len - len(products))
    quantities = quantities + [""] * (max_len - len(quantities))
    prices = prices + [""] * (max_len - len(prices))

    # Create individual transaction records
    transactions = []
    for i in range(max_len):
        transaction = row.copy()
        transaction["ДАТА ПРОДАЖУ"] = dates[i]
        transaction["ТОВАР"] = products[i]
        transaction["Кіл-ть штук"] = quantities[i]
        transaction["ЦІНА"] = prices[i]
        transactions.append(transaction)

    return transactions


def parse_csv_with_expansion(file_path: str):
    """Parse CSV and expand multi-purchase rows"""
    results = []

    with open(file_path, mode="r", encoding="UTF-8-SIG", newline="") as file:
        reader = csv.DictReader(
            file,
            delimiter=";",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            skipinitialspace=True,
        )

        for row in reader:
            if not row:
                continue

            cleaned = {}
            for k, v in row.items():
                val = (v or "").strip().replace("\\n", "\n")
                cleaned[k] = val

            # Expand multi-purchase rows
            expanded = _expand_multi_purchase_row(cleaned)
            results.extend(expanded)

    return results


def main():
    csv_path = (
        Path(__file__).parent.parent / "Widget Generator Tool" / "clients_20-22.csv"
    )

    print("📊 Testing Multi-Purchase Row Splitting\n")
    print("=" * 80)

    rows = parse_csv_with_expansion(str(csv_path))

    # Show first client with multiple purchases
    first_client_rows = [r for r in rows if r.get("ПОКУПЕЦЬ") == "ТОВ Креатив-Агромаш"][
        :5
    ]

    print(
        f"\nExample: {first_client_rows[0].get('ПОКУПЕЦЬ')} - Split into {len(first_client_rows)} transactions:\n"
    )

    for i, transaction in enumerate(first_client_rows, 1):
        print(f"Transaction #{i}:")
        print(f"  📅 Date: {transaction.get('ДАТА ПРОДАЖУ', 'N/A')}")
        print(f"  📦 Product: {transaction.get('ТОВАР', 'N/A')[:60]}...")
        print(f"  🔢 Quantity: {transaction.get('Кіл-ть штук', 'N/A')}")
        print(f"  💰 Price: {transaction.get('ЦІНА', 'N/A')}")
        print(f"  📍 Address: {transaction.get('АДРЕСА', 'N/A')[:50]}...")
        print()

    print("=" * 80)
    print(f"\n✅ Total rows in CSV: ~18 clients")
    print(f"✅ Total transactions after expansion: {len(rows)}")
    print(f"\n💡 Each transaction will become a separate Notion page")
    print(
        f"💡 Map will show one marker per unique address (same address = same marker)"
    )


if __name__ == "__main__":
    main()
