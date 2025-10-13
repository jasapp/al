"""
ShipStation Helper - Fetch inventory data from ShipStation V2 API

Provides clean functions to query ShipStation inventory levels so Al can
track what's in stock, what's low, and what needs ordering.

Uses ShipStation V2 API for inventory management.
"""

import os
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class InventoryItem:
    """Represents a single inventory item from ShipStation."""
    sku: str
    name: str
    quantity: int
    reorder_point: Optional[int] = None
    warehouse_location: Optional[str] = None


class ShipStationHelper:
    """
    Interface to ShipStation V2 API for inventory management.

    Handles authentication and provides clean methods for querying inventory.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize ShipStation helper.

        Args:
            api_key: ShipStation V2 API key (defaults to SHIPSTATION_V2_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("SHIPSTATION_V2_API_KEY")
        if not self.api_key:
            raise ValueError("SHIPSTATION_V2_API_KEY not set")

        self.base_url = "https://api.shipstation.com/v2"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        Make authenticated request to ShipStation API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/inventory")
            **kwargs: Additional arguments for requests.request()

        Returns:
            JSON response as dict

        Raises:
            requests.HTTPError: If request fails
        """
        url = f"{self.base_url}{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_all_inventory(self) -> List[InventoryItem]:
        """
        Fetch all inventory items from ShipStation.

        Returns:
            List of InventoryItem objects

        Raises:
            requests.HTTPError: If API call fails
        """
        try:
            data = self._request("GET", "/inventory")

            items = []
            for item_data in data.get("items", []):
                items.append(InventoryItem(
                    sku=item_data.get("sku", ""),
                    name=item_data.get("name", ""),
                    quantity=item_data.get("quantity", 0),
                    reorder_point=item_data.get("reorderPoint"),
                    warehouse_location=item_data.get("warehouseLocation"),
                ))

            return items

        except requests.HTTPError as e:
            # Log error but don't crash
            print(f"ShipStation API error: {e}")
            return []

    def get_inventory_by_sku(self, sku: str) -> Optional[InventoryItem]:
        """
        Fetch specific inventory item by SKU.

        Args:
            sku: Product SKU to look up

        Returns:
            InventoryItem or None if not found
        """
        try:
            data = self._request("GET", f"/inventory/{sku}")

            return InventoryItem(
                sku=data.get("sku", ""),
                name=data.get("name", ""),
                quantity=data.get("quantity", 0),
                reorder_point=data.get("reorderPoint"),
                warehouse_location=data.get("warehouseLocation"),
            )

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            print(f"ShipStation API error: {e}")
            return None

    def get_low_stock_items(self, threshold: Optional[int] = None) -> List[InventoryItem]:
        """
        Get items that are low on stock.

        Args:
            threshold: Optional quantity threshold (defaults to reorder point)

        Returns:
            List of InventoryItem objects below threshold
        """
        all_items = self.get_all_inventory()

        low_stock = []
        for item in all_items:
            # Use reorder point if available, otherwise use threshold
            limit = item.reorder_point if item.reorder_point else threshold

            if limit and item.quantity <= limit:
                low_stock.append(item)

        return low_stock

    def get_critical_items(self) -> List[InventoryItem]:
        """
        Get items that are critically low (less than 25% of reorder point).

        Returns:
            List of critically low inventory items
        """
        all_items = self.get_all_inventory()

        critical = []
        for item in all_items:
            if item.reorder_point:
                critical_threshold = item.reorder_point * 0.25
                if item.quantity <= critical_threshold:
                    critical.append(item)

        return critical

    def get_out_of_stock_items(self) -> List[InventoryItem]:
        """
        Get items that are completely out of stock.

        Returns:
            List of items with quantity <= 0
        """
        all_items = self.get_all_inventory()
        return [item for item in all_items if item.quantity <= 0]

    def format_inventory_summary(self) -> str:
        """
        Format inventory status as text for Al to read.

        Returns:
            Human-readable inventory summary
        """
        all_items = self.get_all_inventory()

        if not all_items:
            return "Can't reach ShipStation or no inventory items found."

        lines = ["**Current Inventory:**\n"]

        # Out of stock (CRITICAL)
        out = self.get_out_of_stock_items()
        if out:
            lines.append("🔴 **OUT OF STOCK:**")
            for item in out:
                lines.append(f"  - {item.name} ({item.sku}): ZERO")
            lines.append("")

        # Critical (very low)
        critical = [item for item in self.get_critical_items() if item.quantity > 0]
        if critical:
            lines.append("🟠 **CRITICAL (order NOW):**")
            for item in critical:
                reorder = item.reorder_point or "?"
                lines.append(f"  - {item.name} ({item.sku}): {item.quantity} (reorder at {reorder})")
            lines.append("")

        # Low stock
        low = [item for item in self.get_low_stock_items() if item not in critical and item.quantity > 0]
        if low:
            lines.append("🟡 **LOW (order soon):**")
            for item in low:
                reorder = item.reorder_point or "?"
                lines.append(f"  - {item.name} ({item.sku}): {item.quantity} (reorder at {reorder})")
            lines.append("")

        # Good stock (just count)
        good = len([item for item in all_items if item not in out and item not in critical and item not in low])
        if good:
            lines.append(f"✅ **Good stock:** {good} items\n")

        return "\n".join(lines)


def get_inventory_summary() -> str:
    """
    Convenience function to get inventory summary quickly.

    Returns:
        Formatted inventory summary string
    """
    try:
        helper = ShipStationHelper()
        return helper.format_inventory_summary()
    except Exception as e:
        return f"Error fetching inventory: {e}"


def get_low_stock() -> List[InventoryItem]:
    """
    Convenience function to get low stock items quickly.

    Returns:
        List of low stock items
    """
    try:
        helper = ShipStationHelper()
        return helper.get_low_stock_items()
    except Exception as e:
        print(f"Error fetching low stock: {e}")
        return []
