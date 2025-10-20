"""Tests for data safety layer - duplicate detection and verification."""

import pytest
from al.helpers.data_safety import (
    DuplicateChecker,
    ChangeVerifier,
    AuditLogger,
    AuditEntry
)


class TestDuplicateChecker:
    """Test duplicate detection with fuzzy matching."""

    def test_string_similarity(self):
        """Test string similarity calculation."""
        # Exact match
        assert DuplicateChecker.string_similarity("test", "test") == 1.0

        # Similar strings
        assert DuplicateChecker.string_similarity("Kesu Group", "KESU") > 0.7

        # Different strings
        assert DuplicateChecker.string_similarity("ABC", "XYZ") < 0.3

    def test_normalize_string(self):
        """Test string normalization."""
        assert DuplicateChecker.normalize_string("  Test  ") == "test"
        assert DuplicateChecker.normalize_string("CAPS") == "caps"
        assert DuplicateChecker.normalize_string(None) == ""

    def test_normalize_phone(self):
        """Test phone normalization."""
        assert DuplicateChecker.normalize_phone("555-1234") == "5551234"
        assert DuplicateChecker.normalize_phone("(555) 123-4567") == "5551234567"
        assert DuplicateChecker.normalize_phone(None) == ""

    def test_contains_same_words(self):
        """Test word matching."""
        assert DuplicateChecker.contains_same_words("TMZ Sheet Metal", "TMZ") == True
        assert DuplicateChecker.contains_same_words("Kesu Group Inc", "KESU GROUP") == True
        assert DuplicateChecker.contains_same_words("ABC Corp", "XYZ Inc") == False

    def test_check_vendor_duplicates_exact_email(self):
        """Test vendor duplicate detection with exact email match."""
        existing_vendors = [
            {
                "id": "vendor1",
                "name": "Kesu Group",
                "email": "test@kesu.com",
                "phone": "555-1234",
                "products": ["batteries"]
            }
        ]

        duplicates = DuplicateChecker.check_vendor_duplicates(
            name="KESU",
            email="test@kesu.com",  # Exact match
            phone=None,
            existing_vendors=existing_vendors
        )

        assert len(duplicates) == 1
        assert duplicates[0].similarity_score == 1.0
        assert "email" in duplicates[0].matched_fields

    def test_check_vendor_duplicates_similar_name(self):
        """Test vendor duplicate detection with similar name."""
        existing_vendors = [
            {
                "id": "vendor1",
                "name": "TMZ Sheet Metal",
                "email": "tmz@example.com",
                "phone": None,
                "products": []
            }
        ]

        duplicates = DuplicateChecker.check_vendor_duplicates(
            name="TMZ",  # Similar to "TMZ Sheet Metal"
            email=None,
            phone=None,
            existing_vendors=existing_vendors
        )

        assert len(duplicates) == 1
        assert duplicates[0].similarity_score > 0.7

    def test_check_vendor_duplicates_no_match(self):
        """Test vendor duplicate detection with no matches."""
        existing_vendors = [
            {
                "id": "vendor1",
                "name": "ABC Corp",
                "email": "abc@example.com",
                "phone": None,
                "products": []
            }
        ]

        duplicates = DuplicateChecker.check_vendor_duplicates(
            name="XYZ Inc",
            email="xyz@example.com",
            phone=None,
            existing_vendors=existing_vendors
        )

        assert len(duplicates) == 0

    def test_check_invoice_duplicates_same_order_number(self):
        """Test invoice duplicate detection with same order number."""
        existing_invoices = [
            {
                "id": "inv1",
                "vendor_name": "TMZ Sheet Metal",
                "total_amount": 425.00,
                "order_date": "2024-10-14",
                "order_number": "INV-2024-001"
            }
        ]

        duplicates = DuplicateChecker.check_invoice_duplicates(
            vendor_name="TMZ Sheet Metal",
            amount=425.00,
            order_date="2024-10-15",
            order_number="INV-2024-001",  # Same order number
            existing_invoices=existing_invoices
        )

        assert len(duplicates) == 1
        assert "order_number" in duplicates[0].matched_fields

    def test_check_invoice_duplicates_close_date_amount(self):
        """Test invoice duplicate detection with close date and amount."""
        existing_invoices = [
            {
                "id": "inv1",
                "vendor_name": "TMZ Sheet Metal",
                "total_amount": 420.00,  # Within 10% of 425
                "order_date": "2024-10-12",  # Within 7 days of 2024-10-14
                "order_number": None
            }
        ]

        duplicates = DuplicateChecker.check_invoice_duplicates(
            vendor_name="TMZ Sheet Metal",
            amount=425.00,
            order_date="2024-10-14",
            order_number=None,
            existing_invoices=existing_invoices
        )

        assert len(duplicates) == 1
        assert "date_and_amount" in duplicates[0].matched_fields


class TestChangeVerifier:
    """Test change verification."""

    def test_normalize_value(self):
        """Test value normalization."""
        assert ChangeVerifier.normalize_value("  test  ") == "test"
        assert ChangeVerifier.normalize_value(None) == ""
        assert ChangeVerifier.normalize_value(123) == 123

    def test_verify_record_exact_match(self):
        """Test verification with exact match."""
        intended = {
            "name": "Test Vendor",
            "email": "test@test.com",
            "phone": "555-1234"
        }

        actual = {
            "id": "abc123",
            "name": "Test Vendor",
            "email": "test@test.com",
            "phone": "555-1234"
        }

        result = ChangeVerifier.verify_record(intended, actual)

        assert result.passed == True
        assert len(result.mismatches) == 0
        assert result.record_id == "abc123"

    def test_verify_record_with_mismatches(self):
        """Test verification with mismatches."""
        intended = {
            "name": "Test Vendor",
            "email": "test@test.com"
        }

        actual = {
            "name": "Test Vendor",
            "email": "wrong@test.com"  # Mismatch
        }

        result = ChangeVerifier.verify_record(intended, actual)

        assert result.passed == False
        assert len(result.mismatches) == 1
        assert result.mismatches[0]["field"] == "email"
        assert result.mismatches[0]["intended"] == "test@test.com"
        assert result.mismatches[0]["actual"] == "wrong@test.com"

    def test_verify_record_normalizes_whitespace(self):
        """Test that verification normalizes whitespace."""
        intended = {
            "name": "Test Vendor",
            "email": "test@test.com"
        }

        actual = {
            "name": "  Test Vendor  ",  # Extra whitespace
            "email": "test@test.com  "
        }

        result = ChangeVerifier.verify_record(intended, actual)

        # Should pass because whitespace is normalized
        assert result.passed == True


class TestAuditLogger:
    """Test audit logging."""

    def test_audit_entry_creation(self):
        """Test creating an audit entry."""
        entry = AuditEntry(
            timestamp="2024-10-20T12:00:00",
            operation="add_vendor",
            entity_type="vendor",
            user="jeff",
            intended_data={"name": "Test"},
            duplicates_found=0,
            duplicate_details=[],
            user_confirmed=True,
            confirmation_choice="create_new",
            result="success",
            verification={"passed": True, "mismatches": []},
            notion_record_id="abc123",
            actual_data={"name": "Test"}
        )

        assert entry.operation == "add_vendor"
        assert entry.result == "success"

        # Should convert to dict
        data = entry.to_dict()
        assert data["operation"] == "add_vendor"

    def test_audit_logger_writes_entries(self, tmp_path):
        """Test that audit logger writes entries to file."""
        logger = AuditLogger(base_path=tmp_path)

        entry = AuditEntry(
            timestamp="2024-10-20T12:00:00",
            operation="add_vendor",
            entity_type="vendor",
            user="jeff",
            intended_data={"name": "Test"},
            duplicates_found=0,
            duplicate_details=[],
            user_confirmed=True,
            confirmation_choice=None,
            result="success",
            verification=None,
            notion_record_id=None,
            actual_data=None
        )

        logger.log(entry)

        # Check file exists and has content
        audit_file = tmp_path / "audit_log.jsonl"
        assert audit_file.exists()

        content = audit_file.read_text()
        assert "add_vendor" in content
        assert "success" in content

    def test_audit_logger_get_recent_entries(self, tmp_path):
        """Test getting recent audit entries."""
        logger = AuditLogger(base_path=tmp_path)

        # Write multiple entries
        for i in range(5):
            entry = AuditEntry(
                timestamp=f"2024-10-20T12:00:0{i}",
                operation=f"operation_{i}",
                entity_type="vendor",
                user="jeff",
                intended_data={},
                duplicates_found=0,
                duplicate_details=[],
                user_confirmed=None,
                confirmation_choice=None,
                result="success",
                verification=None,
                notion_record_id=None,
                actual_data=None
            )
            logger.log(entry)

        # Get recent entries
        recent = logger.get_recent_entries(limit=3)
        assert len(recent) == 3
        assert recent[-1].operation == "operation_4"  # Most recent
