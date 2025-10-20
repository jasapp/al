"""
Data safety layer for Al's Notion operations.

Provides:
- Duplicate detection with fuzzy matching
- Write verification (ensure data was saved correctly)
- Audit logging with rotation
- Safe wrappers for all database operations
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import Levenshtein
import logging

logger = logging.getLogger(__name__)


@dataclass
class DuplicateMatch:
    """Represents a potential duplicate record."""
    record_id: str
    similarity_score: float
    matched_fields: List[str]
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationResult:
    """Result of verifying a write operation."""
    passed: bool
    mismatches: List[Dict[str, Any]]
    record_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditEntry:
    """Single audit log entry."""
    timestamp: str
    operation: str
    entity_type: str  # vendor, invoice, scrap
    user: str
    intended_data: Dict[str, Any]
    duplicates_found: int
    duplicate_details: List[Dict[str, Any]]
    user_confirmed: Optional[bool]
    confirmation_choice: Optional[str]
    result: str  # success, failed, cancelled, pending
    verification: Optional[Dict[str, Any]]
    notion_record_id: Optional[str]
    actual_data: Optional[Dict[str, Any]]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DuplicateChecker:
    """Check for duplicate records using fuzzy matching."""

    # Moderate matching thresholds
    NAME_SIMILARITY_THRESHOLD = 0.75  # 75% similar
    MAX_LEVENSHTEIN_DISTANCE = 3

    @staticmethod
    def normalize_string(s: Optional[str]) -> str:
        """Normalize string for comparison (trim, lowercase)."""
        if s is None:
            return ""
        return s.strip().lower()

    @staticmethod
    def normalize_phone(phone: Optional[str]) -> str:
        """Normalize phone number (remove spaces, dashes, parentheses)."""
        if phone is None:
            return ""
        return "".join(c for c in phone if c.isdigit())

    @staticmethod
    def string_similarity(s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings (0.0 to 1.0)."""
        s1_norm = DuplicateChecker.normalize_string(s1)
        s2_norm = DuplicateChecker.normalize_string(s2)

        if not s1_norm or not s2_norm:
            return 0.0

        # Levenshtein ratio
        distance = Levenshtein.distance(s1_norm, s2_norm)
        max_len = max(len(s1_norm), len(s2_norm))

        if max_len == 0:
            return 1.0

        return 1.0 - (distance / max_len)

    @staticmethod
    def contains_same_words(s1: str, s2: str) -> bool:
        """Check if strings contain the same significant words."""
        words1 = set(DuplicateChecker.normalize_string(s1).split())
        words2 = set(DuplicateChecker.normalize_string(s2).split())

        # Remove common words that don't matter
        common_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for"}
        words1 -= common_words
        words2 -= common_words

        if not words1 or not words2:
            return False

        # Check if one is subset of the other, or significant overlap
        intersection = words1 & words2
        union = words1 | words2

        if len(intersection) == 0:
            return False

        # If 80% of words match, consider it same
        overlap_ratio = len(intersection) / len(union)
        return overlap_ratio >= 0.8

    @classmethod
    def check_vendor_duplicates(
        cls,
        name: str,
        email: Optional[str],
        phone: Optional[str],
        existing_vendors: List[Dict[str, Any]]
    ) -> List[DuplicateMatch]:
        """
        Check for duplicate vendors.

        Matches on:
        - Name similarity (Levenshtein < 3 OR contains same words)
        - Email exact match
        - Phone exact match
        """
        duplicates = []

        for vendor in existing_vendors:
            matched_fields = []
            similarity_score = 0.0

            # Check name similarity
            vendor_name = vendor.get("name", "")
            name_similarity = cls.string_similarity(name, vendor_name)
            name_distance = Levenshtein.distance(
                cls.normalize_string(name),
                cls.normalize_string(vendor_name)
            )

            if name_similarity >= cls.NAME_SIMILARITY_THRESHOLD:
                matched_fields.append("name_similarity")
                similarity_score = max(similarity_score, name_similarity)
            elif name_distance <= cls.MAX_LEVENSHTEIN_DISTANCE:
                matched_fields.append("name_close")
                similarity_score = max(similarity_score, 0.7)
            elif cls.contains_same_words(name, vendor_name):
                matched_fields.append("name_words")
                similarity_score = max(similarity_score, 0.8)

            # Check email exact match
            if email and vendor.get("email"):
                if cls.normalize_string(email) == cls.normalize_string(vendor["email"]):
                    matched_fields.append("email")
                    similarity_score = 1.0  # Exact email match is definitive

            # Check phone exact match
            if phone and vendor.get("phone"):
                if cls.normalize_phone(phone) == cls.normalize_phone(vendor["phone"]):
                    matched_fields.append("phone")
                    similarity_score = 1.0  # Exact phone match is definitive

            # If any field matched, add as potential duplicate
            if matched_fields:
                duplicates.append(DuplicateMatch(
                    record_id=vendor.get("id", ""),
                    similarity_score=similarity_score,
                    matched_fields=matched_fields,
                    data=vendor
                ))

        # Sort by similarity score (highest first)
        duplicates.sort(key=lambda x: x.similarity_score, reverse=True)

        return duplicates

    @classmethod
    def check_invoice_duplicates(
        cls,
        vendor_name: str,
        amount: float,
        order_date: str,
        order_number: Optional[str],
        existing_invoices: List[Dict[str, Any]]
    ) -> List[DuplicateMatch]:
        """
        Check for duplicate invoices.

        Matches on:
        - Same vendor + date within 7 days + amount within 10%
        - Same vendor + same order number
        """
        from datetime import datetime, timedelta

        duplicates = []

        try:
            target_date = datetime.fromisoformat(order_date.replace('Z', '+00:00'))
        except:
            target_date = None

        for invoice in existing_invoices:
            matched_fields = []
            similarity_score = 0.0

            invoice_vendor = invoice.get("vendor_name", "")
            invoice_amount = invoice.get("total_amount", 0)
            invoice_date_str = invoice.get("order_date", "")
            invoice_order_num = invoice.get("order_number", "")

            # Check if same vendor (fuzzy match)
            vendor_similarity = cls.string_similarity(vendor_name, invoice_vendor)

            if vendor_similarity < 0.8:
                continue  # Different vendor, skip

            # Check order number exact match
            if order_number and invoice_order_num:
                if cls.normalize_string(order_number) == cls.normalize_string(invoice_order_num):
                    matched_fields.append("order_number")
                    similarity_score = 1.0

            # Check date + amount proximity
            if target_date and invoice_date_str:
                try:
                    invoice_date = datetime.fromisoformat(invoice_date_str.replace('Z', '+00:00'))
                    days_diff = abs((target_date - invoice_date).days)

                    if days_diff <= 7:
                        # Within 7 days - check amount
                        amount_diff_pct = abs(amount - invoice_amount) / max(amount, invoice_amount) if amount > 0 else 0

                        if amount_diff_pct <= 0.10:  # Within 10%
                            matched_fields.append("date_and_amount")
                            similarity_score = max(similarity_score, 0.9)
                except:
                    pass

            if matched_fields:
                duplicates.append(DuplicateMatch(
                    record_id=invoice.get("id", ""),
                    similarity_score=similarity_score,
                    matched_fields=matched_fields,
                    data=invoice
                ))

        duplicates.sort(key=lambda x: x.similarity_score, reverse=True)
        return duplicates

    @classmethod
    def check_scrap_duplicates(
        cls,
        product: str,
        quantity: int,
        date: str,
        existing_scrap: List[Dict[str, Any]]
    ) -> List[DuplicateMatch]:
        """
        Check for duplicate scrap entries.

        Matches on:
        - Same product + same date + similar quantity (within 20%)
        """
        from datetime import datetime

        duplicates = []

        try:
            target_date = datetime.fromisoformat(date.replace('Z', '+00:00')).date()
        except:
            target_date = None

        for scrap in existing_scrap:
            matched_fields = []
            similarity_score = 0.0

            scrap_product = scrap.get("product", "")
            scrap_quantity = scrap.get("quantity", 0)
            scrap_date_str = scrap.get("date", "")

            # Check product match (fuzzy)
            product_similarity = cls.string_similarity(product, scrap_product)

            if product_similarity < 0.8:
                continue  # Different product

            # Check date (same day)
            if target_date and scrap_date_str:
                try:
                    scrap_date = datetime.fromisoformat(scrap_date_str.replace('Z', '+00:00')).date()

                    if target_date == scrap_date:
                        # Same day - check quantity
                        qty_diff_pct = abs(quantity - scrap_quantity) / max(quantity, scrap_quantity) if quantity > 0 else 0

                        if qty_diff_pct <= 0.20:  # Within 20%
                            matched_fields.append("date_and_quantity")
                            similarity_score = 0.95
                except:
                    pass

            if matched_fields:
                duplicates.append(DuplicateMatch(
                    record_id=scrap.get("id", ""),
                    similarity_score=similarity_score,
                    matched_fields=matched_fields,
                    data=scrap
                ))

        duplicates.sort(key=lambda x: x.similarity_score, reverse=True)
        return duplicates


class ChangeVerifier:
    """Verify that database writes succeeded with exact data."""

    @staticmethod
    def normalize_value(value: Any) -> Any:
        """Normalize value for comparison (trim strings, handle None)."""
        if isinstance(value, str):
            return value.strip()
        if value is None:
            return ""
        return value

    @classmethod
    def verify_record(
        cls,
        intended_data: Dict[str, Any],
        actual_data: Dict[str, Any],
        fields_to_check: Optional[List[str]] = None
    ) -> VerificationResult:
        """
        Verify that actual data matches intended data.

        Args:
            intended_data: What we tried to write
            actual_data: What's actually in the database
            fields_to_check: List of fields to verify (None = check all)

        Returns:
            VerificationResult with pass/fail and any mismatches
        """
        mismatches = []

        # If no specific fields specified, check all intended fields
        if fields_to_check is None:
            fields_to_check = list(intended_data.keys())

        for field in fields_to_check:
            intended_value = cls.normalize_value(intended_data.get(field))
            actual_value = cls.normalize_value(actual_data.get(field))

            if intended_value != actual_value:
                mismatches.append({
                    "field": field,
                    "intended": intended_value,
                    "actual": actual_value
                })

        return VerificationResult(
            passed=len(mismatches) == 0,
            mismatches=mismatches,
            record_id=actual_data.get("id")
        )


class AuditLogger:
    """Log all database operations to audit file with rotation."""

    MAX_ENTRIES = 10000
    AUDIT_FILE = "audit_log.jsonl"
    ARCHIVE_DIR = "audit_archives"

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize audit logger."""
        if base_path is None:
            # Default to al/ directory
            base_path = Path(__file__).parent.parent

        self.audit_file = base_path / self.AUDIT_FILE
        self.archive_dir = base_path / self.ARCHIVE_DIR
        self.archive_dir.mkdir(exist_ok=True)

        # Create audit file if it doesn't exist
        if not self.audit_file.exists():
            self.audit_file.touch()

    def _count_entries(self) -> int:
        """Count number of entries in current audit file."""
        try:
            with open(self.audit_file, 'r') as f:
                return sum(1 for _ in f)
        except:
            return 0

    def _rotate_if_needed(self):
        """Rotate audit log if it exceeds MAX_ENTRIES."""
        if self._count_entries() >= self.MAX_ENTRIES:
            # Archive current log
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_file = self.archive_dir / f"audit_log_{timestamp}.jsonl"

            self.audit_file.rename(archive_file)
            self.audit_file.touch()

            logger.info(f"Rotated audit log to {archive_file}")

    def log(self, entry: AuditEntry):
        """Write an audit entry to the log."""
        self._rotate_if_needed()

        with open(self.audit_file, 'a') as f:
            f.write(json.dumps(entry.to_dict()) + '\n')

        logger.info(f"Audit log: {entry.operation} on {entry.entity_type} - {entry.result}")

    def get_recent_entries(self, limit: int = 50) -> List[AuditEntry]:
        """Get the most recent audit entries."""
        entries = []

        try:
            with open(self.audit_file, 'r') as f:
                lines = f.readlines()

            for line in lines[-limit:]:
                try:
                    data = json.loads(line)
                    entries.append(AuditEntry(**data))
                except:
                    continue
        except:
            pass

        return entries


class PendingConfirmation:
    """Track operations pending user confirmation."""

    _pending = {}  # In-memory cache of pending operations
    _last_reminder = {}  # Track when we last reminded about pending ops

    @classmethod
    def add(
        cls,
        operation_id: str,
        operation: str,
        entity_type: str,
        intended_data: Dict[str, Any],
        duplicates: List[DuplicateMatch]
    ):
        """Add a pending operation."""
        cls._pending[operation_id] = {
            "timestamp": datetime.now(),
            "operation": operation,
            "entity_type": entity_type,
            "intended_data": intended_data,
            "duplicates": duplicates
        }
        cls._last_reminder[operation_id] = datetime.now()

    @classmethod
    def get(cls, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get a pending operation."""
        return cls._pending.get(operation_id)

    @classmethod
    def remove(cls, operation_id: str):
        """Remove a pending operation."""
        cls._pending.pop(operation_id, None)
        cls._last_reminder.pop(operation_id, None)

    @classmethod
    def needs_reminder(cls, operation_id: str, minutes: int = 10) -> bool:
        """Check if operation needs reminder (10 minutes since last)."""
        from datetime import timedelta

        if operation_id not in cls._last_reminder:
            return False

        last = cls._last_reminder[operation_id]
        return datetime.now() - last > timedelta(minutes=minutes)

    @classmethod
    def get_all_needing_reminders(cls) -> List[str]:
        """Get all operation IDs that need reminders."""
        return [op_id for op_id in cls._pending.keys() if cls.needs_reminder(op_id)]


# Singleton instances
_audit_logger = None

def get_audit_logger() -> AuditLogger:
    """Get the singleton audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
