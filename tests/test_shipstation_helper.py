"""Tests for shipstation_helper.py"""

import pytest
from unittest.mock import Mock, patch
from al.helpers.shipstation_helper import (
    ShipStationHelper,
    InventoryItem,
)


def test_initialization_with_key():
    """Test that ShipStationHelper initializes with API key (V1 format)."""
    with patch.dict('os.environ', {'SHIPSTATION_API_KEY': 'test_key:test_secret'}):
        helper = ShipStationHelper()
        assert helper.api_key == 'test_key'
        assert helper.api_secret == 'test_secret'
        assert helper.base_url == "https://ssapi.shipstation.com"


def test_initialization_without_key():
    """Test that initialization fails without API key."""
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(ValueError, match="SHIPSTATION_API_KEY not set"):
            ShipStationHelper()


def test_initialization_with_key_no_colon():
    """Test initialization with key that doesn't have colon separator."""
    with patch.dict('os.environ', {'SHIPSTATION_API_KEY': 'test_key'}):
        helper = ShipStationHelper()
        assert helper.api_key == 'test_key'
        assert helper.api_secret == ''


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
