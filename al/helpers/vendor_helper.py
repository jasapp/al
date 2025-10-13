"""
Vendor Helper - Track vendors, contacts, and lead times

Keeps vendor information organized so Al never loses a supplier.
Stores data in Notion for visibility, falls back to JSON if Notion is offline.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import logging
from datetime import datetime
from al.helpers.notion_helper import NotionHelper

logger = logging.getLogger(__name__)


@dataclass
class Vendor:
    """Vendor information."""
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    products: List[str] = None
    lead_time_days: Optional[int] = None
    notes: Optional[str] = None
    last_order_date: Optional[str] = None
    last_order_details: Optional[str] = None

    def __post_init__(self):
        """Initialize mutable defaults."""
        if self.products is None:
            self.products = []


class VendorHelper:
    """
    Manage vendor database.

    Stores vendor info in Notion for visibility, falls back to JSON if Notion is offline.
    """

    def __init__(self, vendors_file: Optional[Path] = None, notion_helper: Optional[NotionHelper] = None):
        """
        Initialize vendor helper.

        Args:
            vendors_file: Path to vendors JSON file (fallback storage)
            notion_helper: NotionHelper instance (optional, will create if not provided)
        """
        self.vendors_file = vendors_file or Path(__file__).parent.parent.parent / ".al_vendors.json"
        self.notion = notion_helper or NotionHelper()
        self.vendors = self._load_vendors()

    def _load_vendors(self) -> Dict[str, Vendor]:
        """
        Load vendors from Notion first, fallback to JSON.

        Returns:
            Dict of vendor name -> Vendor object
        """
        # Try Notion first
        if self.notion.is_available:
            notion_vendors = self.notion.get_all_vendors_from_notion()
            if notion_vendors is not None:
                logger.info(f"Loaded {len(notion_vendors)} vendors from Notion")
                return {v["name"]: Vendor(**v) for v in notion_vendors if v.get("name")}

        # Fallback to local JSON
        if self.vendors_file.exists():
            try:
                data = json.loads(self.vendors_file.read_text())
                logger.info(f"Loaded {len(data)} vendors from local JSON (Notion unavailable)")
                return {name: Vendor(**vendor_data) for name, vendor_data in data.items()}
            except Exception as e:
                logger.error(f"Failed to load vendors from JSON: {e}")

        return {}

    def _save_vendors(self) -> None:
        """Save vendors to JSON (fallback only)."""
        try:
            data = {name: asdict(vendor) for name, vendor in self.vendors.items()}
            self.vendors_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save vendors to JSON: {e}")

    def add_vendor(
        self,
        name: str,
        contact_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        products: Optional[List[str]] = None,
        lead_time_days: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Vendor:
        """
        Add or update vendor.

        Saves to Notion first, falls back to JSON if Notion unavailable.

        Args:
            name: Vendor name
            contact_name: Contact person name
            email: Email address
            phone: Phone number
            products: List of products they supply
            lead_time_days: Typical lead time in days
            notes: Additional notes

        Returns:
            Vendor object
        """
        vendor = Vendor(
            name=name,
            contact_name=contact_name,
            email=email,
            phone=phone,
            products=products or [],
            lead_time_days=lead_time_days,
            notes=notes
        )

        # Try to save to Notion first
        saved_to_notion = self.notion.add_vendor_to_notion(
            name=name,
            contact_name=contact_name,
            email=email,
            phone=phone,
            products=products,
            lead_time_days=lead_time_days,
            notes=notes
        )

        if saved_to_notion:
            logger.info(f"Vendor '{name}' saved to Notion")
        else:
            logger.warning(f"Vendor '{name}' saved to local JSON only (Notion unavailable)")

        # Always save to local JSON as backup
        self.vendors[name] = vendor
        self._save_vendors()

        return vendor

    def update_vendor(self, name: str, **kwargs) -> Optional[Vendor]:
        """
        Update existing vendor fields.

        Args:
            name: Vendor name
            **kwargs: Fields to update

        Returns:
            Updated Vendor or None if not found
        """
        if name not in self.vendors:
            return None

        vendor = self.vendors[name]

        for key, value in kwargs.items():
            if hasattr(vendor, key) and value is not None:
                setattr(vendor, key, value)

        self._save_vendors()
        return vendor

    def get_vendor(self, name: str) -> Optional[Vendor]:
        """
        Get vendor by name.

        Args:
            name: Vendor name

        Returns:
            Vendor or None if not found
        """
        return self.vendors.get(name)

    def get_all_vendors(self) -> List[Vendor]:
        """
        Get all vendors.

        Returns:
            List of all vendors
        """
        return list(self.vendors.values())

    def record_order(self, vendor_name: str, order_details: str) -> Optional[Vendor]:
        """
        Record that an order was placed with vendor.

        Args:
            vendor_name: Name of vendor
            order_details: Description of what was ordered

        Returns:
            Updated Vendor or None if not found
        """
        if vendor_name not in self.vendors:
            return None

        vendor = self.vendors[vendor_name]
        vendor.last_order_date = datetime.now().isoformat()
        vendor.last_order_details = order_details

        self._save_vendors()
        return vendor

    def search_vendors_by_product(self, product: str) -> List[Vendor]:
        """
        Find vendors who supply a specific product.

        Args:
            product: Product name to search for

        Returns:
            List of vendors who supply that product
        """
        product_lower = product.lower()
        matches = []

        for vendor in self.vendors.values():
            if any(product_lower in p.lower() for p in vendor.products):
                matches.append(vendor)

        return matches

    def format_vendor_list(self) -> str:
        """
        Format all vendors as readable text.

        Returns:
            Human-readable vendor list
        """
        if not self.vendors:
            return "No vendors registered yet."

        lines = ["**Vendors:**\n"]

        for vendor in sorted(self.vendors.values(), key=lambda v: v.name):
            lines.append(f"**{vendor.name}**")

            if vendor.contact_name:
                lines.append(f"  Contact: {vendor.contact_name}")
            if vendor.email:
                lines.append(f"  Email: {vendor.email}")
            if vendor.phone:
                lines.append(f"  Phone: {vendor.phone}")
            if vendor.products:
                lines.append(f"  Products: {', '.join(vendor.products)}")
            if vendor.lead_time_days:
                lines.append(f"  Lead time: {vendor.lead_time_days} days")
            if vendor.notes:
                lines.append(f"  Notes: {vendor.notes}")
            if vendor.last_order_date:
                lines.append(f"  Last order: {vendor.last_order_date}")

            lines.append("")

        return "\n".join(lines)

    def format_vendor_info(self, vendor_name: str) -> str:
        """
        Format single vendor info as readable text.

        Args:
            vendor_name: Name of vendor

        Returns:
            Human-readable vendor info or error message
        """
        vendor = self.get_vendor(vendor_name)

        if not vendor:
            return f"No vendor found with name: {vendor_name}"

        lines = [f"**{vendor.name}**\n"]

        if vendor.contact_name:
            lines.append(f"Contact: {vendor.contact_name}")
        if vendor.email:
            lines.append(f"Email: {vendor.email}")
        if vendor.phone:
            lines.append(f"Phone: {vendor.phone}")
        if vendor.products:
            lines.append(f"Products: {', '.join(vendor.products)}")
        if vendor.lead_time_days:
            lines.append(f"Lead time: {vendor.lead_time_days} days")
        if vendor.notes:
            lines.append(f"Notes: {vendor.notes}")
        if vendor.last_order_date:
            lines.append(f"Last order: {vendor.last_order_date}")
            if vendor.last_order_details:
                lines.append(f"  Details: {vendor.last_order_details}")

        return "\n".join(lines)


def get_vendors() -> List[Vendor]:
    """
    Convenience function to get all vendors.

    Returns:
        List of all vendors
    """
    helper = VendorHelper()
    return helper.get_all_vendors()


def find_vendor_for_product(product: str) -> List[Vendor]:
    """
    Convenience function to find vendors for a product.

    Args:
        product: Product name

    Returns:
        List of matching vendors
    """
    helper = VendorHelper()
    return helper.search_vendors_by_product(product)
