#!/usr/bin/env python3
"""
Sync Al's memory (products, BOMs) to Notion.

Creates a Products database and populates it with information from AL_MEMORY.md
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")

def create_products_database():
    """Create a Products database in Notion."""

    client = Client(auth=NOTION_API_KEY)

    print("Creating Al - Products database...\n")

    # Create database
    try:
        search_results = client.search(filter={"property": "object", "value": "page"}, page_size=1)
        if search_results["results"]:
            parent_id = search_results["results"][0]["id"]
            parent = {"type": "page_id", "page_id": parent_id}
        else:
            parent = {"type": "workspace", "workspace": True}
    except:
        parent = {"type": "workspace", "workspace": True}

    products_db = client.databases.create(
        parent=parent,
        title=[{"type": "text", "text": {"content": "Al - Products & BOMs"}}],
        properties={
            "Product Name": {"title": {}},
            "Machine Time (min)": {"number": {}},
            "Titanium (inches)": {"number": {}},
            "Copper (inches)": {"number": {}},
            "Historical Scrap Rate": {"number": {}},
            "Components": {"rich_text": {}},
            "Notes": {"rich_text": {}},
        }
    )

    db_id = products_db["id"]
    print(f"✅ Products database created: {db_id}\n")

    return client, db_id


def add_dc2_product(client, db_id):
    """Add DC2 product from memory."""

    print("Adding DC2 product to Notion...")

    # DC2 data from AL_MEMORY.md
    components = """- 1x 21mm sapphire lens
- 1x 21mm PTFE gasket
- 1x MCR20S driver
- 1x DC2 body (machined from titanium stock)
- 1x tailcap
- 1x battery (18650)
- Misc hardware (screws, O-rings)"""

    notes = "DC2 engine assembly has intermittent reliability issues (added 2025-10-11)"

    client.pages.create(
        parent={"database_id": db_id},
        properties={
            "Product Name": {"title": [{"text": {"content": "DC2"}}]},
            "Machine Time (min)": {"number": 30},
            "Titanium (inches)": {"number": 5.5},
            "Copper (inches)": {"number": 1.0},
            "Historical Scrap Rate": {"number": 0.08},
            "Components": {"rich_text": [{"text": {"content": components}}]},
            "Notes": {"rich_text": [{"text": {"content": notes}}]},
        }
    )

    print("✅ DC2 added to Products database\n")


def create_raw_materials_database():
    """Create a Raw Materials database."""

    client = Client(auth=NOTION_API_KEY)

    print("Creating Al - Raw Materials database...\n")

    try:
        search_results = client.search(filter={"property": "object", "value": "page"}, page_size=1)
        if search_results["results"]:
            parent_id = search_results["results"][0]["id"]
            parent = {"type": "page_id", "page_id": parent_id}
        else:
            parent = {"type": "workspace", "workspace": True}
    except:
        parent = {"type": "workspace", "workspace": True}

    materials_db = client.databases.create(
        parent=parent,
        title=[{"type": "text", "text": {"content": "Al - Raw Materials"}}],
        properties={
            "Material": {"title": {}},
            "Reorder Point": {"number": {}},
            "Typical Order": {"number": {}},
            "Unit": {"select": {
                "options": [
                    {"name": "inches", "color": "blue"},
                    {"name": "pounds", "color": "green"},
                    {"name": "pieces", "color": "orange"},
                ]
            }},
            "Vendor": {"rich_text": {}},
            "Lead Time (days)": {"number": {}},
            "Notes": {"rich_text": {}},
        }
    )

    db_id = materials_db["id"]
    print(f"✅ Raw Materials database created: {db_id}\n")

    return client, db_id


def add_raw_materials(client, db_id):
    """Add raw materials from memory."""

    print("Adding raw materials to Notion...")

    # Titanium
    client.pages.create(
        parent={"database_id": db_id},
        properties={
            "Material": {"title": [{"text": {"content": "Titanium Stock (1\" round)"}}]},
            "Reorder Point": {"number": 200},
            "Typical Order": {"number": 500},
            "Unit": {"select": {"name": "inches"}},
            "Vendor": {"rich_text": [{"text": {"content": "TBD"}}]},
            "Notes": {"rich_text": [{"text": {"content": "Used for DC2 body machining"}}]},
        }
    )

    # Copper
    client.pages.create(
        parent={"database_id": db_id},
        properties={
            "Material": {"title": [{"text": {"content": "Copper C145 (7/8\" round)"}}]},
            "Reorder Point": {"number": 100},
            "Typical Order": {"number": 200},
            "Unit": {"select": {"name": "inches"}},
            "Vendor": {"rich_text": [{"text": {"content": "TBD"}}]},
            "Notes": {"rich_text": [{"text": {"content": "Used for DC2 engine"}}]},
        }
    )

    print("✅ Titanium and Copper added to Raw Materials database\n")


if __name__ == "__main__":
    print("="*60)
    print("Syncing Al's Memory to Notion")
    print("="*60 + "\n")

    try:
        # Create and populate Products database
        client, products_db_id = create_products_database()
        add_dc2_product(client, products_db_id)

        # Create and populate Raw Materials database
        client, materials_db_id = create_raw_materials_database()
        add_raw_materials(client, materials_db_id)

        print("="*60)
        print("✅ Memory sync complete!")
        print("="*60)

        print("\nNew databases created:")
        print(f"  Products: https://notion.so/{products_db_id.replace('-', '')}")
        print(f"  Raw Materials: https://notion.so/{materials_db_id.replace('-', '')}")

        print("\nAdd these to Al's .env (optional):")
        print(f"NOTION_PRODUCTS_DB_ID={products_db_id}")
        print(f"NOTION_MATERIALS_DB_ID={materials_db_id}")

        # Save IDs to file
        with open("/home/jasapp/src/al/.notion_db_ids.txt", "a") as f:
            f.write(f"NOTION_PRODUCTS_DB_ID={products_db_id}\n")
            f.write(f"NOTION_MATERIALS_DB_ID={materials_db_id}\n")

        print("\n✅ Database IDs appended to .notion_db_ids.txt")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
