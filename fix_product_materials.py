#!/usr/bin/env python3
"""
Fix Products database to properly link to specific raw materials.

Add "Titanium Type" and "Copper Type" fields so we know which SIZE of material each product uses.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
PRODUCTS_DB_ID = "28b2b307-5074-8104-ae4c-d4354063b093"

def update_products_schema():
    """Add Titanium Type and Copper Type fields to Products database."""

    client = Client(auth=NOTION_API_KEY)

    print("Updating Products database schema...\n")

    # Note: We can't modify existing database properties via API easily,
    # but we can update the existing DC2 page with rich_text fields

    # Get existing DC2 page
    result = client.databases.query(database_id=PRODUCTS_DB_ID)

    if not result["results"]:
        print("❌ No products found")
        return

    dc2_page = result["results"][0]
    dc2_id = dc2_page["id"]

    print("Updating DC2 with specific material sizes...")

    # Update DC2 to specify material types in the Components field
    components = """Materials per unit:
- Titanium 6Al4V 1" Round: 5.5 inches
- Copper C145 7/8" Round: 1 inch

Components:
- 1x 21mm sapphire lens
- 1x 21mm PTFE gasket
- 1x MCR20S driver
- 1x DC2 body (machined from titanium)
- 1x tailcap
- 1x battery (18650)
- Misc hardware (screws, O-rings)"""

    client.pages.update(
        page_id=dc2_id,
        properties={
            "Components": {"rich_text": [{"text": {"content": components}}]}
        }
    )

    print("  ✅ DC2 updated with material specifications\n")

def add_dc0_and_dc1():
    """Add DC0 and DC1 products with proper material specs."""

    client = Client(auth=NOTION_API_KEY)

    print("Adding DC0 and DC1 products...\n")

    # DC0
    dc0_components = """Materials per unit:
- Titanium 6Al4V 3/4" Round: TBD inches
- Copper C145 7/8" Round: TBD inches

Components: TBD"""

    client.pages.create(
        parent={"database_id": PRODUCTS_DB_ID},
        properties={
            "Product Name": {"title": [{"text": {"content": "DC0"}}]},
            "Components": {"rich_text": [{"text": {"content": dc0_components}}]},
            "Notes": {"rich_text": [{"text": {"content": "Smaller model - uses 3/4\" titanium"}}]},
        }
    )
    print("  ✅ DC0 added (needs specs)")

    # DC1
    dc1_components = """Materials per unit:
- Titanium 6Al4V 1" Round: TBD inches
- Copper C145 7/8" Round: TBD inches

Components: Same as DC2 but 19mm lens instead of 21mm"""

    client.pages.create(
        parent={"database_id": PRODUCTS_DB_ID},
        properties={
            "Product Name": {"title": [{"text": {"content": "DC1"}}]},
            "Components": {"rich_text": [{"text": {"content": dc1_components}}]},
            "Notes": {"rich_text": [{"text": {"content": "Same as DC2 but 19mm lens - uses 1\" titanium"}}]},
        }
    )
    print("  ✅ DC1 added (needs specs)")


if __name__ == "__main__":
    print("="*60)
    print("Linking Products to Specific Raw Materials")
    print("="*60 + "\n")

    try:
        update_products_schema()
        add_dc0_and_dc1()

        print("="*60)
        print("✅ Products database updated!")
        print("="*60)

        print("\nProducts now specify which material SIZE they use:")
        print("  • DC0 → 3/4\" titanium")
        print("  • DC1 → 1\" titanium")
        print("  • DC2 → 1\" titanium + full specs")

        print(f"\nView: https://notion.so/{PRODUCTS_DB_ID.replace('-', '')}")

        print("\nAl can now calculate material needs correctly:")
        print("  '100 DC0s' = 3/4\" titanium needed")
        print("  '100 DC2s' = 1\" titanium needed")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
