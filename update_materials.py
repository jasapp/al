#!/usr/bin/env python3
"""
Update Raw Materials database with correct sizes and alloys.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
MATERIALS_DB_ID = "28b2b307-5074-81f2-8e75-c366be5550e9"

def clear_existing_materials():
    """Delete existing material entries."""

    client = Client(auth=NOTION_API_KEY)

    print("Clearing existing materials...")

    # Query all pages
    results = client.databases.query(database_id=MATERIALS_DB_ID)

    for page in results["results"]:
        client.pages.update(page_id=page["id"], archived=True)
        print(f"  ✅ Archived old entry")

    print()

def add_updated_materials():
    """Add materials with correct sizes and alloys."""

    client = Client(auth=NOTION_API_KEY)

    print("Adding updated materials with sizes...\n")

    materials = [
        {
            "name": "Titanium 6Al4V - 1\" Round",
            "reorder": 200,
            "typical": 500,
            "unit": "inches",
            "notes": "Used for DC1 and DC2 body machining"
        },
        {
            "name": "Titanium 6Al4V - 3/4\" Round",
            "reorder": 100,
            "typical": 200,
            "unit": "inches",
            "notes": "Used for DC0 body machining"
        },
        {
            "name": "Copper C145 - 7/8\" Round",
            "reorder": 100,
            "typical": 200,
            "unit": "inches",
            "notes": "Used for DC series engines"
        }
    ]

    for mat in materials:
        client.pages.create(
            parent={"database_id": MATERIALS_DB_ID},
            properties={
                "Material": {"title": [{"text": {"content": mat["name"]}}]},
                "Reorder Point": {"number": mat["reorder"]},
                "Typical Order": {"number": mat["typical"]},
                "Unit": {"select": {"name": mat["unit"]}},
                "Vendor": {"rich_text": [{"text": {"content": "TBD"}}]},
                "Notes": {"rich_text": [{"text": {"content": mat["notes"]}}]},
            }
        )
        print(f"  ✅ Added: {mat['name']}")

    print()

if __name__ == "__main__":
    print("="*60)
    print("Updating Raw Materials with correct sizes")
    print("="*60 + "\n")

    try:
        clear_existing_materials()
        add_updated_materials()

        print("="*60)
        print("✅ Materials updated successfully!")
        print("="*60)

        print("\nRaw Materials now includes:")
        print("  • Titanium 6Al4V - 1\" Round (DC1, DC2)")
        print("  • Titanium 6Al4V - 3/4\" Round (DC0)")
        print("  • Copper C145 - 7/8\" Round (DC engines)")

        print(f"\nView: https://notion.so/{MATERIALS_DB_ID.replace('-', '')}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
