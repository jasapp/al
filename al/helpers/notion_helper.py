"""
Notion integration for Al's data storage.

Stores vendors, scrap history, invoices, and inventory alerts in Notion databases.
Falls back to local JSON storage if Notion is offline or unavailable.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from notion_client import Client
from notion_client.errors import APIResponseError

logger = logging.getLogger(__name__)


class NotionHelper:
    """
    Helper for interacting with Notion databases.

    Provides graceful fallback to local storage if Notion is unavailable.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        vendors_db_id: Optional[str] = None,
        scrap_db_id: Optional[str] = None,
        invoices_db_id: Optional[str] = None,
        alerts_db_id: Optional[str] = None,
    ):
        """
        Initialize Notion client.

        Args:
            api_key: Notion integration token
            vendors_db_id: Notion database ID for vendors
            scrap_db_id: Notion database ID for scrap history
            invoices_db_id: Notion database ID for invoices
            alerts_db_id: Notion database ID for inventory alerts
        """
        self.api_key = api_key or os.getenv("NOTION_API_KEY")
        self.vendors_db_id = vendors_db_id or os.getenv("NOTION_VENDORS_DB_ID")
        self.scrap_db_id = scrap_db_id or os.getenv("NOTION_SCRAP_DB_ID")
        self.invoices_db_id = invoices_db_id or os.getenv("NOTION_INVOICES_DB_ID")
        self.alerts_db_id = alerts_db_id or os.getenv("NOTION_ALERTS_DB_ID")

        self.client: Optional[Client] = None
        self.is_available = False

        if self.api_key:
            try:
                self.client = Client(auth=self.api_key)
                # Test connection
                self.client.users.me()
                self.is_available = True
                logger.info("Notion integration initialized successfully")
            except Exception as e:
                logger.warning(f"Notion not available: {e}. Will use local storage.")
                self.is_available = False
        else:
            logger.info("Notion API key not configured. Using local storage only.")

    def _safe_notion_call(self, func, *args, **kwargs) -> Optional[Any]:
        """
        Safely execute a Notion API call with error handling.

        Returns None if call fails, allowing fallback to local storage.
        """
        if not self.is_available or not self.client:
            return None

        try:
            return func(*args, **kwargs)
        except APIResponseError as e:
            logger.error(f"Notion API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Notion call failed: {e}")
            return None

    # === VENDORS ===

    def add_vendor_to_notion(
        self,
        name: str,
        contact_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        products: Optional[List[str]] = None,
        lead_time_days: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Add vendor to Notion database.

        Returns True if successful, False if failed (triggering local fallback).
        """
        if not self.vendors_db_id:
            logger.debug("Vendors DB ID not configured")
            return False

        properties: Dict[str, Any] = {
            "Name": {"title": [{"text": {"content": name}}]},
        }

        if contact_name:
            properties["Contact"] = {"rich_text": [{"text": {"content": contact_name}}]}

        if email:
            properties["Email"] = {"email": email}

        if phone:
            properties["Phone"] = {"phone_number": phone}

        if products:
            properties["Products"] = {"multi_select": [{"name": p} for p in products]}

        if lead_time_days is not None:
            properties["Lead Time (days)"] = {"number": lead_time_days}

        if notes:
            properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

        result = self._safe_notion_call(
            self.client.pages.create,
            parent={"database_id": self.vendors_db_id},
            properties=properties,
        )

        return result is not None

    def get_vendor_from_notion(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve vendor from Notion by name.

        Returns None if not found or Notion unavailable.
        """
        if not self.vendors_db_id:
            return None

        result = self._safe_notion_call(
            self.client.databases.query,
            database_id=self.vendors_db_id,
            filter={
                "property": "Name",
                "title": {"equals": name}
            }
        )

        if not result or not result.get("results"):
            return None

        return self._parse_vendor_page(result["results"][0])

    def get_all_vendors_from_notion(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get all vendors from Notion.

        Returns None if Notion unavailable.
        """
        if not self.vendors_db_id:
            return None

        result = self._safe_notion_call(
            self.client.databases.query,
            database_id=self.vendors_db_id,
        )

        if not result:
            return None

        return [self._parse_vendor_page(page) for page in result.get("results", [])]

    def _parse_vendor_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Notion page into vendor dict."""
        props = page.get("properties", {})

        return {
            "name": self._get_title(props.get("Name")),
            "contact_name": self._get_rich_text(props.get("Contact")),
            "email": self._get_email(props.get("Email")),
            "phone": self._get_phone(props.get("Phone")),
            "products": self._get_multi_select(props.get("Products")),
            "lead_time_days": self._get_number(props.get("Lead Time (days)")),
            "notes": self._get_rich_text(props.get("Notes")),
        }

    # === SCRAP HISTORY ===

    def add_scrap_to_notion(
        self,
        product: str,
        quantity: int,
        reason: str,
        material_cost: Optional[float] = None,
        time_cost_minutes: Optional[int] = None,
        materials_lost: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Add scrap entry to Notion database.

        Returns True if successful, False if failed.
        """
        if not self.scrap_db_id:
            return False

        if timestamp is None:
            timestamp = datetime.now()

        properties: Dict[str, Any] = {
            "Product": {"title": [{"text": {"content": product}}]},
            "Quantity": {"number": quantity},
            "Reason": {"rich_text": [{"text": {"content": reason}}]},
            "Date": {"date": {"start": timestamp.isoformat()}},
        }

        if material_cost is not None:
            properties["Material Cost"] = {"number": material_cost}

        if time_cost_minutes is not None:
            properties["Time Lost (min)"] = {"number": time_cost_minutes}

        if materials_lost:
            materials_text = ", ".join([f"{v} {k}" for k, v in materials_lost.items()])
            properties["Materials Lost"] = {"rich_text": [{"text": {"content": materials_text}}]}

        result = self._safe_notion_call(
            self.client.pages.create,
            parent={"database_id": self.scrap_db_id},
            properties=properties,
        )

        return result is not None

    def get_scrap_history_from_notion(self, days: int = 7) -> Optional[List[Dict[str, Any]]]:
        """
        Get scrap history from Notion for the last N days.

        Returns None if Notion unavailable.
        """
        if not self.scrap_db_id:
            return None

        from datetime import timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        result = self._safe_notion_call(
            self.client.databases.query,
            database_id=self.scrap_db_id,
            filter={
                "property": "Date",
                "date": {"on_or_after": cutoff_date}
            },
            sorts=[{"property": "Date", "direction": "descending"}]
        )

        if not result:
            return None

        return [self._parse_scrap_page(page) for page in result.get("results", [])]

    def _parse_scrap_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Notion page into scrap dict."""
        props = page.get("properties", {})

        return {
            "product": self._get_title(props.get("Product")),
            "quantity": self._get_number(props.get("Quantity")),
            "reason": self._get_rich_text(props.get("Reason")),
            "timestamp": self._get_date(props.get("Date")),
            "material_cost": self._get_number(props.get("Material Cost")),
            "time_cost_minutes": self._get_number(props.get("Time Lost (min)")),
            "materials_lost": self._get_rich_text(props.get("Materials Lost")),
        }

    # === INVOICES ===

    def add_invoice_to_notion(
        self,
        invoice_number: str,
        vendor_name: str,
        total_amount: Optional[float] = None,
        order_date: Optional[str] = None,
        processed_date: Optional[datetime] = None,
    ) -> bool:
        """
        Add invoice to Notion database.

        Returns True if successful, False if failed.
        """
        if not self.invoices_db_id:
            return False

        if processed_date is None:
            processed_date = datetime.now()

        properties: Dict[str, Any] = {
            "Invoice Number": {"title": [{"text": {"content": invoice_number}}]},
            "Vendor": {"rich_text": [{"text": {"content": vendor_name}}]},
            "Processed Date": {"date": {"start": processed_date.isoformat()}},
        }

        if total_amount is not None:
            properties["Total Amount"] = {"number": total_amount}

        if order_date:
            properties["Order Date"] = {"date": {"start": order_date}}

        result = self._safe_notion_call(
            self.client.pages.create,
            parent={"database_id": self.invoices_db_id},
            properties=properties,
        )

        return result is not None

    def check_duplicate_invoice_in_notion(
        self,
        invoice_number: str,
        vendor_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if invoice already exists in Notion.

        Returns invoice data if found, None if not found or Notion unavailable.
        """
        if not self.invoices_db_id:
            return None

        result = self._safe_notion_call(
            self.client.databases.query,
            database_id=self.invoices_db_id,
            filter={
                "and": [
                    {
                        "property": "Invoice Number",
                        "title": {"equals": invoice_number}
                    },
                    {
                        "property": "Vendor",
                        "rich_text": {"equals": vendor_name}
                    }
                ]
            }
        )

        if not result or not result.get("results"):
            return None

        return self._parse_invoice_page(result["results"][0])

    def _parse_invoice_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Notion page into invoice dict."""
        props = page.get("properties", {})

        return {
            "invoice_number": self._get_title(props.get("Invoice Number")),
            "vendor_name": self._get_rich_text(props.get("Vendor")),
            "total_amount": self._get_number(props.get("Total Amount")),
            "order_date": self._get_date(props.get("Order Date")),
            "processed_date": self._get_date(props.get("Processed Date")),
        }

    # === HELPER FUNCTIONS FOR PARSING NOTION PROPERTIES ===

    def _get_title(self, prop: Optional[Dict]) -> Optional[str]:
        """Extract title from Notion property."""
        if not prop or not prop.get("title"):
            return None
        return prop["title"][0]["text"]["content"] if prop["title"] else None

    def _get_rich_text(self, prop: Optional[Dict]) -> Optional[str]:
        """Extract rich text from Notion property."""
        if not prop or not prop.get("rich_text"):
            return None
        return prop["rich_text"][0]["text"]["content"] if prop["rich_text"] else None

    def _get_number(self, prop: Optional[Dict]) -> Optional[float]:
        """Extract number from Notion property."""
        if not prop:
            return None
        return prop.get("number")

    def _get_email(self, prop: Optional[Dict]) -> Optional[str]:
        """Extract email from Notion property."""
        if not prop:
            return None
        return prop.get("email")

    def _get_phone(self, prop: Optional[Dict]) -> Optional[str]:
        """Extract phone from Notion property."""
        if not prop:
            return None
        return prop.get("phone_number")

    def _get_date(self, prop: Optional[Dict]) -> Optional[str]:
        """Extract date from Notion property."""
        if not prop or not prop.get("date"):
            return None
        return prop["date"].get("start")

    def _get_multi_select(self, prop: Optional[Dict]) -> Optional[List[str]]:
        """Extract multi-select values from Notion property."""
        if not prop or not prop.get("multi_select"):
            return None
        return [item["name"] for item in prop["multi_select"]]

    # === PRODUCTS & BOMs ===

    def get_all_products_from_notion(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get all products from Notion.

        Returns None if Notion unavailable.
        """
        if not os.getenv("NOTION_PRODUCTS_DB_ID"):
            return None

        products_db_id = os.getenv("NOTION_PRODUCTS_DB_ID")

        result = self._safe_notion_call(
            self.client.databases.query,
            database_id=products_db_id,
        )

        if not result:
            return None

        return [self._parse_product_page(page) for page in result.get("results", [])]

    def get_product_from_notion(self, product_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific product by name.

        Returns None if not found or Notion unavailable.
        """
        if not os.getenv("NOTION_PRODUCTS_DB_ID"):
            return None

        products_db_id = os.getenv("NOTION_PRODUCTS_DB_ID")

        result = self._safe_notion_call(
            self.client.databases.query,
            database_id=products_db_id,
            filter={
                "property": "Product Name",
                "title": {"equals": product_name}
            }
        )

        if not result or not result.get("results"):
            return None

        return self._parse_product_page(result["results"][0])

    def _parse_product_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Notion page into product dict."""
        props = page.get("properties", {})

        return {
            "page_id": page.get("id"),
            "product_name": self._get_title(props.get("Product Name")),
            "machine_time_minutes": self._get_number(props.get("Machine Time (min)")),
            "titanium_inches": self._get_number(props.get("Titanium (inches)")),
            "copper_inches": self._get_number(props.get("Copper (inches)")),
            "scrap_rate": self._get_number(props.get("Historical Scrap Rate")),
            "components": self._get_rich_text(props.get("Components")),
            "notes": self._get_rich_text(props.get("Notes")),
        }

    def update_product_in_notion(
        self,
        product_name: str,
        machine_time_minutes: Optional[float] = None,
        titanium_inches: Optional[float] = None,
        copper_inches: Optional[float] = None,
        scrap_rate: Optional[float] = None,
        components: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Update product BOM in Notion.

        Args:
            product_name: Product to update
            machine_time_minutes: Machine time per unit (optional)
            titanium_inches: Titanium length per unit (optional)
            copper_inches: Copper length per unit (optional)
            scrap_rate: Historical scrap rate (optional)
            components: Components description (optional)
            notes: Notes (optional)

        Returns:
            True if successful, False if failed
        """
        if not os.getenv("NOTION_PRODUCTS_DB_ID"):
            return False

        # First get the product to find its page_id
        product = self.get_product_from_notion(product_name)
        if not product or not product.get("page_id"):
            logger.warning(f"Product {product_name} not found in Notion")
            return False

        page_id = product["page_id"]
        properties: Dict[str, Any] = {}

        # Only update fields that were provided
        if machine_time_minutes is not None:
            properties["Machine Time (min)"] = {"number": machine_time_minutes}

        if titanium_inches is not None:
            properties["Titanium (inches)"] = {"number": titanium_inches}

        if copper_inches is not None:
            properties["Copper (inches)"] = {"number": copper_inches}

        if scrap_rate is not None:
            properties["Historical Scrap Rate"] = {"number": scrap_rate}

        if components is not None:
            properties["Components"] = {"rich_text": [{"text": {"content": components}}]}

        if notes is not None:
            properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

        if not properties:
            logger.warning("No fields to update")
            return False

        result = self._safe_notion_call(
            self.client.pages.update,
            page_id=page_id,
            properties=properties,
        )

        return result is not None

    def create_product_in_notion(
        self,
        product_name: str,
        machine_time_minutes: float = 30,
        titanium_inches: float = 0,
        copper_inches: float = 0,
        scrap_rate: float = 0.08,
        components: str = "",
        notes: str = "",
    ) -> bool:
        """
        Create new product in Notion.

        Args:
            product_name: Product name
            machine_time_minutes: Machine time per unit
            titanium_inches: Titanium length per unit
            copper_inches: Copper length per unit
            scrap_rate: Historical scrap rate
            components: Components description
            notes: Notes

        Returns:
            True if successful, False if failed
        """
        if not os.getenv("NOTION_PRODUCTS_DB_ID"):
            return False

        products_db_id = os.getenv("NOTION_PRODUCTS_DB_ID")

        properties: Dict[str, Any] = {
            "Product Name": {"title": [{"text": {"content": product_name}}]},
            "Machine Time (min)": {"number": machine_time_minutes},
            "Titanium (inches)": {"number": titanium_inches},
            "Copper (inches)": {"number": copper_inches},
            "Historical Scrap Rate": {"number": scrap_rate},
            "Components": {"rich_text": [{"text": {"content": components}}]},
            "Notes": {"rich_text": [{"text": {"content": notes}}]},
        }

        result = self._safe_notion_call(
            self.client.pages.create,
            parent={"database_id": products_db_id},
            properties=properties,
        )

        return result is not None
