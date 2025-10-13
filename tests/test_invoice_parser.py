"""Tests for invoice_parser.py"""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch
from al.helpers.invoice_parser import (
    InvoiceParser,
    ParsedInvoice,
    parse_invoice,
)


@pytest.fixture
def mock_claude_response():
    """Mock Claude API response for invoice parsing."""
    return {
        "vendor_name": "TMZ Sheet Metal",
        "contact_name": "Tom Martinez",
        "email": "tom@tmzsheet.com",
        "phone": "555-1234",
        "website": "tmzsheet.com",
        "order_number": "INV-2024-001",
        "order_date": "2024-10-13",
        "items": [
            {
                "product": "Stainless Steel Clips",
                "quantity": 500,
                "unit_price": 0.25,
                "total": 125.00
            },
            {
                "product": "Aluminum Brackets",
                "quantity": 200,
                "unit_price": 1.50,
                "total": 300.00
            }
        ],
        "total_amount": 425.00,
        "notes": "2-3 week lead time for custom orders"
    }


@pytest.fixture
def temp_image_file():
    """Create a temporary image file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        # Write some dummy image data
        f.write(b'\xff\xd8\xff\xe0')  # JPEG header
        temp_path = Path(f.name)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


def test_parsed_invoice_dataclass():
    """Test ParsedInvoice dataclass."""
    invoice = ParsedInvoice(
        vendor_name="Test Vendor",
        email="test@test.com",
        total_amount=100.00,
        items=[{"product": "Widget", "quantity": 10}]
    )

    assert invoice.vendor_name == "Test Vendor"
    assert invoice.email == "test@test.com"
    assert invoice.total_amount == 100.00
    assert len(invoice.items) == 1


def test_parsed_invoice_default_items():
    """Test that ParsedInvoice initializes empty items list."""
    invoice = ParsedInvoice(vendor_name="Test")

    assert invoice.items == []


def test_invoice_parser_initialization():
    """Test InvoiceParser initializes with API key."""
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_key'}):
        parser = InvoiceParser()
        assert parser.api_key == 'test_key'


def test_invoice_parser_initialization_without_key():
    """Test initialization fails without API key."""
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not set"):
            InvoiceParser()


def test_get_media_type():
    """Test media type detection from file extension."""
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_key'}):
        parser = InvoiceParser()

        assert parser._get_media_type(Path("test.jpg")) == "image/jpeg"
        assert parser._get_media_type(Path("test.jpeg")) == "image/jpeg"
        assert parser._get_media_type(Path("test.png")) == "image/png"
        assert parser._get_media_type(Path("test.gif")) == "image/gif"
        assert parser._get_media_type(Path("test.webp")) == "image/webp"
        assert parser._get_media_type(Path("test.unknown")) == "image/jpeg"  # Default


def test_parse_invoice_from_bytes_success(mock_claude_response):
    """Test parsing invoice from bytes with successful response."""
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_key'}):
        parser = InvoiceParser()

        # Mock the Claude API response
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = f'```json\n{str(mock_claude_response).replace("'", '"')}\n```'

        with patch.object(parser.client.messages, 'create', return_value=mock_response):
            invoice = parser.parse_invoice_from_bytes(b'fake_image_data', 'image/jpeg')

            assert invoice.vendor_name == "TMZ Sheet Metal"
            assert invoice.contact_name == "Tom Martinez"
            assert invoice.email == "tom@tmzsheet.com"
            assert invoice.phone == "555-1234"
            assert invoice.total_amount == 425.00
            assert len(invoice.items) == 2


def test_parse_invoice_from_path_success(temp_image_file, mock_claude_response):
    """Test parsing invoice from file path."""
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_key'}):
        parser = InvoiceParser()

        # Mock the parse_invoice_from_bytes method
        mock_parsed = ParsedInvoice(vendor_name="Test Vendor")

        with patch.object(parser, 'parse_invoice_from_bytes', return_value=mock_parsed):
            invoice = parser.parse_invoice_from_path(temp_image_file)

            assert invoice.vendor_name == "Test Vendor"


def test_parse_invoice_from_path_file_not_found():
    """Test that parsing nonexistent file raises error."""
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_key'}):
        parser = InvoiceParser()

        with pytest.raises(FileNotFoundError):
            parser.parse_invoice_from_path(Path("/nonexistent/file.jpg"))


def test_parse_invoice_json_decode_error():
    """Test handling of invalid JSON response."""
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_key'}):
        parser = InvoiceParser()

        # Mock response with invalid JSON
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "This is not JSON"

        with patch.object(parser.client.messages, 'create', return_value=mock_response):
            invoice = parser.parse_invoice_from_bytes(b'fake_image_data', 'image/jpeg')

            # Should return ParsedInvoice with error note
            assert "Failed to parse" in invoice.notes


def test_parse_invoice_api_error():
    """Test handling of API errors."""
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_key'}):
        parser = InvoiceParser()

        with patch.object(parser.client.messages, 'create', side_effect=Exception("API Error")):
            invoice = parser.parse_invoice_from_bytes(b'fake_image_data', 'image/jpeg')

            # Should return ParsedInvoice with error note
            assert "Error" in invoice.notes


def test_format_parsed_invoice():
    """Test formatting parsed invoice as text."""
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_key'}):
        parser = InvoiceParser()

        invoice = ParsedInvoice(
            vendor_name="TMZ Sheet Metal",
            contact_name="Tom Martinez",
            email="tom@tmzsheet.com",
            phone="555-1234",
            order_number="INV-001",
            order_date="2024-10-13",
            items=[
                {"product": "Clips", "quantity": 500, "unit_price": 0.25, "total": 125.00}
            ],
            total_amount=125.00,
            notes="2-3 week lead time"
        )

        formatted = parser.format_parsed_invoice(invoice)

        assert "TMZ Sheet Metal" in formatted
        assert "Tom Martinez" in formatted
        assert "tom@tmzsheet.com" in formatted
        assert "INV-001" in formatted
        assert "Clips" in formatted
        assert "$125.00" in formatted
        assert "2-3 week lead time" in formatted


def test_format_parsed_invoice_minimal():
    """Test formatting invoice with minimal data."""
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_key'}):
        parser = InvoiceParser()

        invoice = ParsedInvoice(vendor_name="Test Vendor")

        formatted = parser.format_parsed_invoice(invoice)

        assert "Test Vendor" in formatted
        assert "Invoice Parsed" in formatted


def test_convenience_function():
    """Test parse_invoice convenience function."""
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_key'}):
        mock_parsed = ParsedInvoice(vendor_name="Test")

        with patch('al.helpers.invoice_parser.InvoiceParser.parse_invoice_from_path', return_value=mock_parsed):
            invoice = parse_invoice(Path("/fake/path.jpg"))

            assert invoice.vendor_name == "Test"


def test_parse_invoice_without_markdown_wrapper(mock_claude_response):
    """Test parsing response that doesn't have markdown code block."""
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_key'}):
        parser = InvoiceParser()

        # Mock response without markdown wrapper
        import json
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = json.dumps(mock_claude_response)

        with patch.object(parser.client.messages, 'create', return_value=mock_response):
            invoice = parser.parse_invoice_from_bytes(b'fake_image_data', 'image/jpeg')

            assert invoice.vendor_name == "TMZ Sheet Metal"
            assert invoice.total_amount == 425.00
