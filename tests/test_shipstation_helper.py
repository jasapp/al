"""Tests for shipstation_helper.py"""

import pytest
from unittest.mock import Mock, patch
from al.helpers.shipstation_helper import (
    ShipStationHelper,
    InventoryItem,
    get_inventory_summary,
    get_low_stock,
)


@pytest.fixture
def mock_api_response():
    """Mock ShipStation API response."""
    return {
        "items": [
            {
                "sku": "LENS-21MM",
                "name": "Sapphire Lens 21mm",
                "quantity": 15,
                "reorderPoint": 20,
                "warehouseLocation": "A1"
            },
            {
                "sku": "GASKET-PTFE",
                "name": "PTFE Gasket",
                "quantity": 200,
                "reorderPoint": 50,
                "warehouseLocation": "B2"
            },
            {
                "sku": "DRIVER-MCR20S",
                "name": "MCR20S Driver",
                "quantity": 0,
                "reorderPoint": 10,
                "warehouseLocation": "C3"
            },
            {
                "sku": "BODY-DC2",
                "name": "DC2 Body Blank",
                "quantity": 3,
                "reorderPoint": 20,
                "warehouseLocation": "D4"
            },
        ]
    }


@pytest.fixture
def helper_with_mock():
    """Create ShipStationHelper with mocked API key."""
    with patch.dict('os.environ', {'SHIPSTATION_V2_API_KEY': 'test_key'}):
        helper = ShipStationHelper()
    return helper


def test_initialization_with_key():
    """Test that ShipStationHelper initializes with API key."""
    with patch.dict('os.environ', {'SHIPSTATION_V2_API_KEY': 'test_key'}):
        helper = ShipStationHelper()
        assert helper.api_key == 'test_key'


def test_initialization_without_key():
    """Test that initialization fails without API key."""
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(ValueError, match="SHIPSTATION_V2_API_KEY not set"):
            ShipStationHelper()


def test_get_all_inventory(helper_with_mock, mock_api_response):
    """Test fetching all inventory items."""
    with patch.object(helper_with_mock, '_request', return_value=mock_api_response):
        items = helper_with_mock.get_all_inventory()

        assert len(items) == 4
        assert items[0].sku == "LENS-21MM"
        assert items[0].name == "Sapphire Lens 21mm"
        assert items[0].quantity == 15
        assert items[0].reorder_point == 20


def test_get_inventory_by_sku(helper_with_mock):
    """Test fetching specific item by SKU."""
    mock_response = {
        "sku": "LENS-21MM",
        "name": "Sapphire Lens 21mm",
        "quantity": 15,
        "reorderPoint": 20,
        "warehouseLocation": "A1"
    }

    with patch.object(helper_with_mock, '_request', return_value=mock_response):
        item = helper_with_mock.get_inventory_by_sku("LENS-21MM")

        assert item is not None
        assert item.sku == "LENS-21MM"
        assert item.quantity == 15


def test_get_low_stock_items(helper_with_mock, mock_api_response):
    """Test identifying low stock items."""
    with patch.object(helper_with_mock, '_request', return_value=mock_api_response):
        low_items = helper_with_mock.get_low_stock_items()

        # LENS-21MM (15 <= 20) and BODY-DC2 (3 <= 20) should be low
        # DRIVER-MCR20S is out (0 <= 10)
        skus = [item.sku for item in low_items]

        assert "LENS-21MM" in skus
        assert "BODY-DC2" in skus
        assert "DRIVER-MCR20S" in skus
        assert "GASKET-PTFE" not in skus  # 200 > 50


def test_get_critical_items(helper_with_mock, mock_api_response):
    """Test identifying critically low items."""
    with patch.object(helper_with_mock, '_request', return_value=mock_api_response):
        critical_items = helper_with_mock.get_critical_items()

        # Critical = <= 25% of reorder point
        # LENS-21MM: 15 > (20 * 0.25 = 5) - NOT critical
        # BODY-DC2: 3 <= (20 * 0.25 = 5) - CRITICAL
        # DRIVER-MCR20S: 0 <= (10 * 0.25 = 2.5) - CRITICAL

        skus = [item.sku for item in critical_items]

        assert "BODY-DC2" in skus
        assert "DRIVER-MCR20S" in skus
        assert "LENS-21MM" not in skus


def test_get_out_of_stock_items(helper_with_mock, mock_api_response):
    """Test identifying out of stock items."""
    with patch.object(helper_with_mock, '_request', return_value=mock_api_response):
        out_items = helper_with_mock.get_out_of_stock_items()

        assert len(out_items) == 1
        assert out_items[0].sku == "DRIVER-MCR20S"
        assert out_items[0].quantity == 0


def test_format_inventory_summary(helper_with_mock, mock_api_response):
    """Test formatting inventory as readable summary."""
    with patch.object(helper_with_mock, '_request', return_value=mock_api_response):
        summary = helper_with_mock.format_inventory_summary()

        assert "OUT OF STOCK" in summary
        assert "CRITICAL" in summary
        assert "LOW" in summary
        assert "MCR20S Driver" in summary
        assert "DC2 Body Blank" in summary


def test_format_inventory_summary_empty(helper_with_mock):
    """Test summary when no inventory items exist."""
    with patch.object(helper_with_mock, '_request', return_value={"items": []}):
        summary = helper_with_mock.format_inventory_summary()

        assert "no inventory items" in summary.lower()


def test_get_inventory_summary_convenience():
    """Test convenience function for getting summary."""
    mock_response = {"items": []}

    with patch.dict('os.environ', {'SHIPSTATION_V2_API_KEY': 'test_key'}):
        with patch('al.helpers.shipstation_helper.ShipStationHelper._request', return_value=mock_response):
            summary = get_inventory_summary()
            assert isinstance(summary, str)


def test_get_low_stock_convenience():
    """Test convenience function for getting low stock."""
    mock_response = {
        "items": [
            {
                "sku": "TEST",
                "name": "Test Item",
                "quantity": 5,
                "reorderPoint": 20,
            }
        ]
    }

    with patch.dict('os.environ', {'SHIPSTATION_V2_API_KEY': 'test_key'}):
        with patch('al.helpers.shipstation_helper.ShipStationHelper._request', return_value=mock_response):
            items = get_low_stock()
            assert len(items) == 1
            assert items[0].sku == "TEST"


def test_inventory_item_dataclass():
    """Test InventoryItem dataclass."""
    item = InventoryItem(
        sku="TEST-SKU",
        name="Test Item",
        quantity=100,
        reorder_point=50,
        warehouse_location="A1"
    )

    assert item.sku == "TEST-SKU"
    assert item.name == "Test Item"
    assert item.quantity == 100
    assert item.reorder_point == 50
    assert item.warehouse_location == "A1"


def test_inventory_item_optional_fields():
    """Test InventoryItem with optional fields."""
    item = InventoryItem(
        sku="TEST-SKU",
        name="Test Item",
        quantity=100
    )

    assert item.reorder_point is None
    assert item.warehouse_location is None
