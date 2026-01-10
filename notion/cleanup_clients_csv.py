#!/usr/bin/env python3
"""
CSV Cleanup Script for clients.csv
Fixes formatting issues, properly quotes fields, removes duplicates, and normalizes data.
"""

import csv
import re
import sys
from typing import List, Tuple


def fix_email_field(line: str, email_col_idx: int) -> str:
    """Fix email fields that contain multiple emails with improper quoting."""
    # Pattern to match email addresses
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

    # Split by semicolon
    parts = line.split(";")

    # Check if we have enough parts and the email column
    if len(parts) > email_col_idx:
        email_field = parts[email_col_idx]

        # Check if next field looks like it could be a continuation of emails (malformed quote)
        if len(parts) > email_col_idx + 1:
            next_field = parts[email_col_idx + 1]

            # If the next field starts with a quote and contains an email, it's likely a split email field
            if next_field.strip().startswith('"') and re.search(
                email_pattern, next_field
            ):
                # Extract all emails from both fields
                emails_found = []
                emails_found.extend(re.findall(email_pattern, email_field))
                emails_found.extend(re.findall(email_pattern, next_field))

                if len(emails_found) > 1:
                    # Replace the email field with properly formatted multiple emails
                    parts[email_col_idx] = '"' + ", ".join(emails_found) + '"'
                    # Remove the next field and shift everything else
                    parts.pop(email_col_idx + 1)

    return ";".join(parts)


def read_raw_csv(file_path: str) -> Tuple[List[str], List[List[str]]]:
    """Read CSV with proper handling of quoted multi-line fields."""
    headers = []
    rows = []

    # First pass: fix email fields in raw text
    fixed_lines = []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    # Find the email column index from header
    if lines:
        header_parts = lines[0].strip().split(";")
        email_col_idx = -1
        for i, h in enumerate(header_parts):
            if h.strip() in ("ЕЛ.АДРЕСА", "Email"):
                email_col_idx = i
                break

        fixed_lines.append(lines[0])  # Keep header as-is

        # Fix each data line
        for line in lines[1:]:
            if email_col_idx >= 0:
                line = fix_email_field(line, email_col_idx)
            fixed_lines.append(line)

    # Now parse the fixed CSV
    import io

    csv_text = "".join(fixed_lines)
    f = io.StringIO(csv_text)

    reader = csv.reader(f, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
    for i, row in enumerate(reader):
        if i == 0:
            headers = row
        else:
            rows.append(row)

    return headers, rows


def normalize_row(
    row: List[str], expected_cols: int, headers: List[str] = None  # type: ignore
) -> List[str]:
    """Normalize row to have correct number of columns."""
    # Pad or trim to match header count
    if len(row) < expected_cols:
        row.extend([""] * (expected_cols - len(row)))
    elif len(row) > expected_cols:
        row = row[:expected_cols]

    # Clean each field
    cleaned = []
    for i, field in enumerate(row):
        # Remove extra quotes and whitespace
        field = field.strip()
        # Normalize newlines
        field = re.sub(r"\s*[\r\n]+\s*", " ", field)
        # Remove duplicate quotes
        field = re.sub(r'"{2,}', '"', field)
        # Clean up quotes at edges
        if field.startswith('"') and field.endswith('"'):
            field = field[1:-1]

        # Special handling for email field (ЕЛ.АДРЕСА)
        # Check if this is the email column by matching header
        if headers and i < len(headers) and headers[i] in ("ЕЛ.АДРЕСА", "Email"):
            # Replace semicolons within emails with commas to prevent CSV parsing issues
            # Multiple emails should be separated by comma or space, not semicolon
            field = field.replace(";", ", ")

        cleaned.append(field)

    return cleaned


def is_valid_row(row: List[str]) -> bool:
    """Check if row contains meaningful data (not just empty fields)."""
    # Check for at least 2 non-empty fields
    non_empty = [f for f in row if f.strip()]
    return len(non_empty) >= 2


def is_duplicate_row(row: List[str], seen: set) -> bool:
    """Check if row is a duplicate (based on ID and client name)."""
    # Use first two columns as unique identifier
    key = (row[0].strip(), row[1].strip()) if len(row) >= 2 else ()
    if not key[0] and not key[1]:  # type: ignore
        return True
    if key in seen:
        return True
    seen.add(key)
    return False


def clean_clients_csv(input_file: str, output_file: str = None) -> None:  # type: ignore
    """Main cleanup function."""
    if output_file is None:
        output_file = input_file.replace(".csv", "_cleaned.csv")

    print(f"Reading from: {input_file}")
    headers, rows = read_raw_csv(input_file)

    print(f"Original headers: {len(headers)}")
    print(f"Original rows: {len(rows)}")

    # Normalize all rows
    normalized_rows = []
    for i, row in enumerate(rows):
        try:
            normalized = normalize_row(row, len(headers), headers)
            normalized_rows.append(normalized)
        except Exception as e:
            print(f"Warning: Error normalizing row {i+2}: {e}")

    # Remove duplicates and invalid rows
    seen = set()
    cleaned_rows = []
    duplicates_removed = 0
    invalid_removed = 0

    for row in normalized_rows:
        if not is_valid_row(row):
            invalid_removed += 1
            continue
        if is_duplicate_row(row, seen):
            duplicates_removed += 1
            continue
        cleaned_rows.append(row)

    print(f"Cleaned rows: {len(cleaned_rows)}")
    print(f"Invalid rows removed: {invalid_removed}")
    print(f"Duplicate rows removed: {duplicates_removed}")

    # Write cleaned CSV with proper quoting
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(
            f,
            delimiter=";",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        writer.writerow(headers)
        writer.writerows(cleaned_rows)

    print(f"\nCleaned CSV written to: {output_file}")
    print(f"Total records: {len(cleaned_rows)}")

    # Show sample
    print(f"\nFirst 3 rows:")
    for i, row in enumerate(cleaned_rows[:3], 1):
        print(f"  Row {i}: {row[0]} | {row[1]}")


if __name__ == "__main__":
    input_path = "clients.csv"
    output_path = "clients_cleaned.csv"

    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_path = sys.argv[2]

    clean_clients_csv(input_path, output_path)
