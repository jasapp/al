"""
Invoice Tracker - Track processed invoices to detect duplicates

Keeps a record of all invoices we've seen so we don't process them twice.
Uses invoice number, vendor name, and total as unique identifier.
Stores data in Notion for visibility, falls back to JSON if Notion is offline.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from datetime import datetime
from al.helpers.notion_helper import NotionHelper

logger = logging.getLogger(__name__)


@dataclass
class ProcessedInvoice:
    """Record of a processed invoice."""
    invoice_number: str
    vendor_name: str
    total_amount: Optional[float]
    processed_date: str
    order_date: Optional[str] = None


class InvoiceTracker:
    """
    Track processed invoices to detect duplicates.

    Uses invoice number + vendor as unique key.
    Stores in Notion for visibility, falls back to JSON if Notion is offline.
    """

    def __init__(self, storage_path: Optional[Path] = None, notion_helper: Optional[NotionHelper] = None):
        """
        Initialize invoice tracker.

        Args:
            storage_path: Path to JSON storage file (defaults to .al_invoices.json)
            notion_helper: NotionHelper instance (optional, will create if not provided)
        """
        if storage_path is None:
            storage_path = Path.cwd() / ".al_invoices.json"

        self.storage_path = storage_path
        self.notion = notion_helper or NotionHelper()
        self.invoices: Dict[str, ProcessedInvoice] = {}
        self._load_invoices()

    def _load_invoices(self) -> None:
        """Load invoices from storage."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                self.invoices = {
                    key: ProcessedInvoice(**inv)
                    for key, inv in data.items()
                }
            except Exception:
                # If file is corrupted, start fresh
                self.invoices = {}

    def _save_invoices(self) -> None:
        """Save invoices to storage."""
        data = {
            key: asdict(inv)
            for key, inv in self.invoices.items()
        }
        self.storage_path.write_text(json.dumps(data, indent=2))

    def _make_key(self, invoice_number: str, vendor_name: str) -> str:
        """
        Create unique key for invoice.

        Args:
            invoice_number: Invoice/order number
            vendor_name: Vendor name

        Returns:
            Unique key string
        """
        # Normalize both to lowercase and strip whitespace
        inv_norm = invoice_number.lower().strip()
        vendor_norm = vendor_name.lower().strip()
        return f"{vendor_norm}:{inv_norm}"

    def is_duplicate(
        self,
        invoice_number: str,
        vendor_name: str,
        total_amount: Optional[float] = None
    ) -> bool:
        """
        Check if invoice has been processed before.

        Checks Notion first, then local storage.

        Args:
            invoice_number: Invoice/order number
            vendor_name: Vendor name
            total_amount: Optional total amount for additional verification

        Returns:
            True if this invoice was already processed
        """
        if not invoice_number or not vendor_name:
            # Can't determine uniqueness without these
            return False

        # Try Notion first
        if self.notion.is_available:
            notion_invoice = self.notion.check_duplicate_invoice_in_notion(
                invoice_number=invoice_number,
                vendor_name=vendor_name
            )
            if notion_invoice:
                logger.info(f"Found duplicate invoice in Notion: {invoice_number} from {vendor_name}")
                return True

        # Fallback to local check
        key = self._make_key(invoice_number, vendor_name)

        if key not in self.invoices:
            return False

        # Found matching invoice
        existing = self.invoices[key]

        # If total amount is provided, verify it matches
        if total_amount is not None and existing.total_amount is not None:
            # Allow small floating point differences
            if abs(existing.total_amount - total_amount) > 0.01:
                # Same invoice number but different total = not a duplicate
                return False

        return True

    def record_invoice(
        self,
        invoice_number: str,
        vendor_name: str,
        total_amount: Optional[float] = None,
        order_date: Optional[str] = None
    ) -> ProcessedInvoice:
        """
        Record a processed invoice.

        Saves to Notion first, falls back to JSON if Notion unavailable.

        Args:
            invoice_number: Invoice/order number
            vendor_name: Vendor name
            total_amount: Total invoice amount
            order_date: Order/invoice date

        Returns:
            ProcessedInvoice record
        """
        key = self._make_key(invoice_number, vendor_name)
        processed_date = datetime.now()

        invoice = ProcessedInvoice(
            invoice_number=invoice_number,
            vendor_name=vendor_name,
            total_amount=total_amount,
            processed_date=processed_date.isoformat(),
            order_date=order_date
        )

        # Try to save to Notion first
        saved_to_notion = self.notion.add_invoice_to_notion(
            invoice_number=invoice_number,
            vendor_name=vendor_name,
            total_amount=total_amount,
            order_date=order_date,
            processed_date=processed_date
        )

        if saved_to_notion:
            logger.info(f"Invoice {invoice_number} from {vendor_name} saved to Notion")
        else:
            logger.warning(f"Invoice saved to local JSON only (Notion unavailable)")

        # Always save to local JSON as backup
        self.invoices[key] = invoice
        self._save_invoices()

        return invoice

    def get_invoice(
        self,
        invoice_number: str,
        vendor_name: str
    ) -> Optional[ProcessedInvoice]:
        """
        Get existing invoice record.

        Args:
            invoice_number: Invoice/order number
            vendor_name: Vendor name

        Returns:
            ProcessedInvoice if found, None otherwise
        """
        key = self._make_key(invoice_number, vendor_name)
        return self.invoices.get(key)

    def get_recent_invoices(self, limit: int = 10) -> List[ProcessedInvoice]:
        """
        Get most recently processed invoices.

        Args:
            limit: Maximum number to return

        Returns:
            List of recent invoices, newest first
        """
        sorted_invoices = sorted(
            self.invoices.values(),
            key=lambda inv: inv.processed_date,
            reverse=True
        )
        return sorted_invoices[:limit]

    def get_vendor_invoices(self, vendor_name: str) -> List[ProcessedInvoice]:
        """
        Get all invoices from a specific vendor.

        Args:
            vendor_name: Vendor name

        Returns:
            List of invoices from this vendor
        """
        vendor_norm = vendor_name.lower().strip()

        return [
            inv for inv in self.invoices.values()
            if inv.vendor_name.lower().strip() == vendor_norm
        ]
