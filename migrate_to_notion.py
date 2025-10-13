#!/usr/bin/env python3
"""
Migrate existing JSON data to Notion databases.

This is a one-time migration script to move existing vendors and scrap data to Notion.
"""

import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from al.helpers.notion_helper import NotionHelper
from dotenv import load_dotenv

# Load environment
load_dotenv()

def migrate_vendors():
    """Migrate vendors from JSON to Notion."""
    vendors_file = Path(__file__).parent / ".al_vendors.json"

    if not vendors_file.exists():
        print("No vendors file found - nothing to migrate")
        return

    vendors = json.loads(vendors_file.read_text())

    if not vendors:
        print("No vendors to migrate")
        return

    print(f"Migrating {len(vendors)} vendors to Notion...\n")

    notion = NotionHelper()

    if not notion.is_available:
        print("❌ Notion not available - check credentials")
        return

    for name, vendor_data in vendors.items():
        print(f"Migrating vendor: {name}")

        success = notion.add_vendor_to_notion(
            name=vendor_data.get("name"),
            contact_name=vendor_data.get("contact_name"),
            email=vendor_data.get("email"),
            phone=vendor_data.get("phone"),
            products=vendor_data.get("products"),
            lead_time_days=vendor_data.get("lead_time_days"),
            notes=vendor_data.get("notes"),
        )

        if success:
            print(f"  ✅ {name} migrated successfully")
        else:
            print(f"  ❌ Failed to migrate {name}")

    print(f"\n✅ Vendor migration complete!")


def migrate_scrap():
    """Migrate scrap history from JSON to Notion."""
    scrap_file = Path(__file__).parent / ".al_scrap_history.json"

    if not scrap_file.exists():
        print("No scrap history file found - nothing to migrate")
        return

    scrap_history = json.loads(scrap_file.read_text())

    if not scrap_history:
        print("No scrap entries to migrate")
        return

    print(f"\nMigrating {len(scrap_history)} scrap entries to Notion...\n")

    notion = NotionHelper()

    if not notion.is_available:
        print("❌ Notion not available - check credentials")
        return

    from datetime import datetime

    for entry in scrap_history:
        timestamp = datetime.fromisoformat(entry["timestamp"])

        success = notion.add_scrap_to_notion(
            product=entry.get("product"),
            quantity=entry.get("quantity"),
            reason=entry.get("reason"),
            material_cost=entry.get("material_cost"),
            time_cost_minutes=entry.get("time_cost_minutes"),
            materials_lost=entry.get("materials_lost"),
            timestamp=timestamp
        )

        if success:
            print(f"  ✅ {entry['product']} ({entry['quantity']} units) migrated")
        else:
            print(f"  ❌ Failed to migrate scrap entry")

    print(f"\n✅ Scrap history migration complete!")


if __name__ == "__main__":
    print("="*60)
    print("Migrating existing data to Notion")
    print("="*60 + "\n")

    migrate_vendors()
    migrate_scrap()

    print("\n" + "="*60)
    print("Migration complete!")
    print("="*60)
    print("\nYou can now view Al's data in Notion:")
    print("  - Al - Vendors")
    print("  - Al - Scrap History")
    print("  - Al - Invoices")
    print("  - Al - Inventory Alerts")
