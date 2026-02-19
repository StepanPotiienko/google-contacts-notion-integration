#!/usr/bin/env python3
"""
Quick script to delete duplicates from CRM database
Usage: python run_duplicate_cleanup.py
"""
import os
import sys

from notion.delete_duplicates import main

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


if __name__ == "__main__":
    print("=" * 60)
    print("CRM Database Duplicate Cleanup Tool")
    print("=" * 60)
    print()
    print("This tool will:")
    print("  1. Scan your CRM database for duplicate contacts")
    print("  2. Identify duplicates by phone number and content")
    print("  3. Archive duplicate entries (keeping the oldest)")
    print()
    print("Note: Archived pages can be restored from Notion trash")
    print("=" * 60)
    print()

    main()
