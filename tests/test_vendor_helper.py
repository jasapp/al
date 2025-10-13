"""Tests for vendor_helper.py"""

import pytest
from pathlib import Path
import tempfile
from al.helpers.vendor_helper import (
    VendorHelper,
    Vendor,
    get_vendors,
    find_vendor_for_product,
)


@pytest.fixture
def temp_vendors_file():
    """Create temporary vendors file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = Path(f.name)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


def test_vendor_dataclass():
    """Test Vendor dataclass."""
    vendor = Vendor(
        name="Test Supplier",
        contact_name="John Doe",
        email="john@test.com",
        phone="555-1234",
        products=["lenses", "gaskets"],
        lead_time_days=21,
        notes="Reliable supplier"
    )

    assert vendor.name == "Test Supplier"
    assert vendor.contact_name == "John Doe"
    assert vendor.email == "john@test.com"
    assert vendor.products == ["lenses", "gaskets"]
    assert vendor.lead_time_days == 21


def test_vendor_helper_initialization(temp_vendors_file):
    """Test VendorHelper initializes properly."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    assert helper.vendors == {}


def test_add_vendor(temp_vendors_file):
    """Test adding a vendor."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    vendor = helper.add_vendor(
        name="Shenzhen Precision",
        contact_name="Li Wei",
        email="liwei@example.com",
        products=["PTFE gaskets", "O-rings"],
        lead_time_days=21
    )

    assert vendor.name == "Shenzhen Precision"
    assert "Shenzhen Precision" in helper.vendors
    assert helper.vendors["Shenzhen Precision"].contact_name == "Li Wei"


def test_get_vendor(temp_vendors_file):
    """Test retrieving a vendor."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    helper.add_vendor(name="Test Vendor", email="test@test.com")

    vendor = helper.get_vendor("Test Vendor")

    assert vendor is not None
    assert vendor.name == "Test Vendor"
    assert vendor.email == "test@test.com"


def test_get_vendor_nonexistent(temp_vendors_file):
    """Test getting nonexistent vendor returns None."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    vendor = helper.get_vendor("Nonexistent")

    assert vendor is None


def test_get_all_vendors(temp_vendors_file):
    """Test getting all vendors."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    helper.add_vendor(name="Vendor A")
    helper.add_vendor(name="Vendor B")
    helper.add_vendor(name="Vendor C")

    all_vendors = helper.get_all_vendors()

    assert len(all_vendors) == 3
    names = [v.name for v in all_vendors]
    assert "Vendor A" in names
    assert "Vendor B" in names
    assert "Vendor C" in names


def test_update_vendor(temp_vendors_file):
    """Test updating vendor fields."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    helper.add_vendor(name="Test Vendor", email="old@email.com")

    updated = helper.update_vendor("Test Vendor", email="new@email.com", phone="555-1234")

    assert updated is not None
    assert updated.email == "new@email.com"
    assert updated.phone == "555-1234"


def test_update_vendor_nonexistent(temp_vendors_file):
    """Test updating nonexistent vendor returns None."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    result = helper.update_vendor("Nonexistent", email="test@test.com")

    assert result is None


def test_record_order(temp_vendors_file):
    """Test recording an order with vendor."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    helper.add_vendor(name="Test Vendor")

    vendor = helper.record_order("Test Vendor", "200x PTFE gaskets @ $0.45/unit")

    assert vendor is not None
    assert vendor.last_order_date is not None
    assert vendor.last_order_details == "200x PTFE gaskets @ $0.45/unit"


def test_record_order_nonexistent(temp_vendors_file):
    """Test recording order for nonexistent vendor returns None."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    result = helper.record_order("Nonexistent", "Test order")

    assert result is None


def test_search_vendors_by_product(temp_vendors_file):
    """Test searching vendors by product."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    helper.add_vendor(name="Vendor A", products=["sapphire lenses", "gaskets"])
    helper.add_vendor(name="Vendor B", products=["drivers", "batteries"])
    helper.add_vendor(name="Vendor C", products=["lenses", "optics"])

    # Search for "lens"
    matches = helper.search_vendors_by_product("lens")

    names = [v.name for v in matches]
    assert "Vendor A" in names  # Has "sapphire lenses"
    assert "Vendor C" in names  # Has "lenses"
    assert "Vendor B" not in names


def test_search_vendors_case_insensitive(temp_vendors_file):
    """Test that product search is case-insensitive."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    helper.add_vendor(name="Vendor A", products=["Sapphire Lenses"])

    matches = helper.search_vendors_by_product("sapphire")

    assert len(matches) == 1
    assert matches[0].name == "Vendor A"


def test_format_vendor_list(temp_vendors_file):
    """Test formatting vendor list as text."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    helper.add_vendor(
        name="Test Vendor",
        email="test@test.com",
        products=["lenses", "gaskets"],
        lead_time_days=21
    )

    formatted = helper.format_vendor_list()

    assert "Test Vendor" in formatted
    assert "test@test.com" in formatted
    assert "lenses" in formatted
    assert "21 days" in formatted


def test_format_vendor_list_empty(temp_vendors_file):
    """Test formatting when no vendors exist."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    formatted = helper.format_vendor_list()

    assert "No vendors" in formatted


def test_format_vendor_info(temp_vendors_file):
    """Test formatting single vendor info."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    helper.add_vendor(
        name="Test Vendor",
        contact_name="John Doe",
        email="john@test.com",
        products=["parts"]
    )

    formatted = helper.format_vendor_info("Test Vendor")

    assert "Test Vendor" in formatted
    assert "John Doe" in formatted
    assert "john@test.com" in formatted


def test_format_vendor_info_nonexistent(temp_vendors_file):
    """Test formatting info for nonexistent vendor."""
    helper = VendorHelper(vendors_file=temp_vendors_file)

    formatted = helper.format_vendor_info("Nonexistent")

    assert "No vendor found" in formatted


def test_persistence(temp_vendors_file):
    """Test that vendors persist across instances."""
    helper1 = VendorHelper(vendors_file=temp_vendors_file)
    helper1.add_vendor(name="Persistent Vendor", email="persist@test.com")

    # Create new instance with same file
    helper2 = VendorHelper(vendors_file=temp_vendors_file)

    vendor = helper2.get_vendor("Persistent Vendor")
    assert vendor is not None
    assert vendor.email == "persist@test.com"


def test_convenience_functions(temp_vendors_file):
    """Test convenience functions."""
    # Note: These use default file path, so we'll just test they don't crash
    # In real usage they'd work with the actual vendors file

    vendors = get_vendors()
    assert isinstance(vendors, list)

    matches = find_vendor_for_product("test")
    assert isinstance(matches, list)
