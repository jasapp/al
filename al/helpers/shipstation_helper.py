"""
ShipStation Helper - Fetch inventory data from ShipStation V2 API

Provides clean functions to query ShipStation inventory levels so Al can
track what's in stock, what's low, and what needs ordering.

Uses ShipStation V2 API for inventory management.
"""

import os
import requests
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize ShipStation helper.

        Args:
            api_key: ShipStation V1 API key (defaults to SHIPSTATION_API_KEY env var)
            api_secret: ShipStation V1 API secret (parsed from SHIPSTATION_API_KEY if not provided)
        """
        # V1 API uses key:secret format
        api_creds = api_key or os.getenv("SHIPSTATION_API_KEY")
        if not api_creds:
            raise ValueError("SHIPSTATION_API_KEY not set")

        # Parse key:secret format
        if ":" in api_creds:
            self.api_key, self.api_secret = api_creds.split(":", 1)
        else:
            self.api_key = api_creds
            self.api_secret = api_secret or ""

        # V1 API uses Basic Auth, not Bearer token
        self.base_url = "https://ssapi.shipstation.com"
        self.auth = (self.api_key, self.api_secret)
        self.headers = {
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
        logger.info(f"ShipStation API request: {method} {url}")

        try:
            # Add Basic Auth to request
            response = requests.request(method, url, headers=self.headers, auth=self.auth, **kwargs)
            logger.info(f"ShipStation response: {response.status_code}")
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            logger.error(f"ShipStation API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"ShipStation request failed: {e}")
            raise

    def get_all_inventory(self) -> List[InventoryItem]:
        """
        Fetch all inventory items from ShipStation.

        Returns:
            List of InventoryItem objects

        Raises:
            requests.HTTPError: If API call fails
        """
        try:
            # V1 API endpoint for products (which includes inventory)
            data = self._request("GET", "/products")

            logger.info(f"ShipStation response type: {type(data)}, data: {str(data)[:200]}")

            items = []

            # Handle different response formats
            if data is None:
                logger.warning("ShipStation returned None")
                return []

            # V1 API returns products array at top level or in a "products" key
            products = data if isinstance(data, list) else data.get("products", [])

            logger.info(f"Found {len(products)} products")

            for item_data in products:
                # Handle warehouseLocation being None
                warehouse_loc = item_data.get("warehouseLocation")
                if warehouse_loc and isinstance(warehouse_loc, dict):
                    quantity = warehouse_loc.get("quantity", 0)
                    location_name = warehouse_loc.get("name")
                else:
                    quantity = 0
                    location_name = None

                items.append(InventoryItem(
                    sku=item_data.get("sku", ""),
                    name=item_data.get("name", ""),
                    quantity=quantity,
                    reorder_point=item_data.get("reorderPoint"),
                    warehouse_location=location_name,
                ))

            return items

        except requests.HTTPError as e:
            logger.error(f"Failed to get all inventory: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting inventory: {e}", exc_info=True)
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
            # V1 API doesn't have a direct SKU lookup, so we search all products
            all_items = self.get_all_inventory()
            for item in all_items:
                if item.sku == sku:
                    return item

            logger.info(f"SKU not found: {sku}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error getting SKU {sku}: {e}")
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
        logger.error(f"Error fetching inventory summary: {e}")
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
        logger.error(f"Error fetching low stock: {e}")
        return []


def get_orders_summary(status: str = "awaiting_shipment", days: int = 7) -> str:
    """
    Get summary of orders from ShipStation.

    Args:
        status: Order status filter (awaiting_shipment, shipped, etc.)
        days: How many days back to look

    Returns:
        Formatted orders summary
    """
    try:
        from datetime import datetime, timedelta

        helper = ShipStationHelper()

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Format for ShipStation API (ISO 8601)
        params = {
            "orderStatus": status,
            "createDateStart": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
            "createDateEnd": end_date.strftime("%Y-%m-%dT%H:%M:%S"),
            "pageSize": 500,  # Get up to 500 orders per page
            "page": 1
        }

        logger.info(f"Fetching orders with params: {params}")

        data = helper._request("GET", "/orders", params=params)

        orders = data.get("orders", [])
        total = data.get("total", len(orders))
        logger.info(f"Found {len(orders)} orders (total: {total})")

        if not orders:
            return f"No {status} orders found in the last {days} days."

        lines = [f"**{status.replace('_', ' ').title()} Orders (last {days} days):**\n"]

        # Show all orders, not just first 20
        for order in orders:
            order_num = order.get("orderNumber", "Unknown")
            order_date = order.get("orderDate", "")[:10]  # Just date part
            customer = order.get("shipTo", {}).get("name", "Unknown")
            order_total = order.get("orderTotal", 0)

            # Get items
            items = order.get("items", [])
            item_summary = []
            for item in items[:3]:  # Show first 3 items
                qty = item.get("quantity", 0)
                name = item.get("name", "Unknown")
                item_summary.append(f"{qty}x {name}")

            items_text = ", ".join(item_summary)
            if len(items) > 3:
                items_text += f" (+{len(items)-3} more)"

            lines.append(f"**#{order_num}** - {customer} - ${order_total:.2f}")
            lines.append(f"  Date: {order_date}")
            lines.append(f"  Items: {items_text}")
            lines.append("")

        lines.append(f"**Total: {total} orders**")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error fetching orders: {e}", exc_info=True)
        return f"Error fetching orders: {e}"
