#!/usr/bin/env python3
"""
Test production planning with Notion data.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from al.helpers.production_helper import calculate_bom, format_production_plan, get_product_list
from dotenv import load_dotenv

load_dotenv()

print("="*60)
print("Testing Production Planning with Notion")
print("="*60 + "\n")

# Test 1: Get product list
print("Test 1: Get product list from Notion")
products = get_product_list()
print(f"✅ Found {len(products)} products: {', '.join(products)}\n")

# Test 2: Calculate BOM for DC2
print("Test 2: Calculate BOM for 100 DC2s")
try:
    plan = calculate_bom("DC2", 100)
    output = format_production_plan(plan)
    print(output)
    print()

    # Check if correct titanium size is used
    titanium_components = [c for c in plan.components_needed if "titanium" in c["name"].lower()]
    if titanium_components:
        titanium = titanium_components[0]
        print(f"✅ Titanium spec: {titanium['name']}")
        print(f"   Total needed: {titanium['total_needed']} inches")
        if "1\" round" in titanium['name'].lower():
            print(f"   ✅ Correct! DC2 uses 1\" titanium")
        else:
            print(f"   ❌ Wrong size!")
    print()

except Exception as e:
    print(f"❌ Error: {e}\n")

# Test 3: Calculate BOM for DC0 (uses 3/4" titanium)
print("Test 3: Calculate BOM for 100 DC0s")
try:
    plan = calculate_bom("DC0", 100)
    output = format_production_plan(plan)
    print(output)
    print()

    # Check if correct titanium size is used
    titanium_components = [c for c in plan.components_needed if "titanium" in c["name"].lower()]
    if titanium_components:
        titanium = titanium_components[0]
        print(f"✅ Titanium spec: {titanium['name']}")
        if "3/4\" round" in titanium['name'].lower():
            print(f"   ✅ Correct! DC0 uses 3/4\" titanium")
        else:
            print(f"   ❌ Wrong size!")
    print()

except Exception as e:
    print(f"❌ Error: {e}\n")

print("="*60)
print("✅ Production planning test complete!")
print("="*60)
