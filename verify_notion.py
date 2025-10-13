#!/usr/bin/env python3
"""
Verify Al's Notion integration is working.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from al.helpers.notion_helper import NotionHelper
from dotenv import load_dotenv

load_dotenv()

def verify_notion():
    """Verify Notion connection and data."""

    print("="*60)
    print("Verifying Al's Notion Integration")
    print("="*60 + "\n")

    notion = NotionHelper()

    if not notion.is_available:
        print("❌ Notion is not available")
        print("Check your NOTION_API_KEY in .env")
        return False

    print("✅ Notion connected successfully\n")

    # Check vendors
    print("Checking Vendors database...")
    vendors = notion.get_all_vendors_from_notion()

    if vendors is None:
        print("❌ Could not query vendors database")
        return False

    print(f"✅ Found {len(vendors)} vendors:")
    for v in vendors:
        print(f"  - {v.get('name')}")
        if v.get('products'):
            print(f"    Products: {', '.join(v.get('products', []))}")
        if v.get('lead_time_days'):
            print(f"    Lead time: {v.get('lead_time_days')} days")

    # Check scrap history
    print("\nChecking Scrap History database...")
    scrap = notion.get_scrap_history_from_notion(days=30)

    if scrap is None:
        print("❌ Could not query scrap database")
        return False

    print(f"✅ Found {len(scrap)} scrap entries:")
    for s in scrap:
        print(f"  - {s.get('product')}: {s.get('quantity')} units - {s.get('reason')}")

    print("\n" + "="*60)
    print("✅ Notion integration verified successfully!")
    print("="*60)

    print("\nView your databases in Notion:")
    print(f"  Vendors: https://notion.so/28b2b3075074817db3f9f9e678ac37fb")
    print(f"  Scrap:   https://notion.so/28b2b3075074817f9deee119cb1369e5")
    print(f"  Invoices: https://notion.so/28b2b307507481be8565c60f3389e6a4")
    print(f"  Alerts:  https://notion.so/28b2b30750748151ade2cec3ac7b1318")

    return True

if __name__ == "__main__":
    success = verify_notion()
    sys.exit(0 if success else 1)
