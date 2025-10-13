"""Tests for production_helper.py"""

import pytest
from al.helpers.production_helper import (
    calculate_bom,
    format_production_plan,
    get_product_list,
    get_product_bom,
    estimate_scrap_for_run,
    ProductBOM,
    Component,
)


def test_get_product_list():
    """Test getting list of known products."""
    products = get_product_list()

    assert "DC2" in products
    assert len(products) >= 1


def test_get_product_bom():
    """Test getting BOM for specific product."""
    bom = get_product_bom("DC2")

    assert bom is not None
    assert bom.product_name == "DC2"
    assert len(bom.components) > 0
    assert bom.machine_time_minutes == 30
    assert bom.scrap_rate == 0.08


def test_get_product_bom_nonexistent():
    """Test getting BOM for nonexistent product."""
    bom = get_product_bom("FAKE_PRODUCT")

    assert bom is None


def test_calculate_bom_basic():
    """Test basic BOM calculation."""
    plan = calculate_bom("DC2", 100)

    assert plan.product_name == "DC2"
    assert plan.target_quantity == 100
    assert plan.adjusted_quantity == 108  # 100 * 1.08 for 8% scrap
    assert len(plan.components_needed) > 0


def test_calculate_bom_with_scrap_rate():
    """Test BOM calculation with custom scrap rate."""
    plan = calculate_bom("DC2", 100, scrap_rate=0.10)

    assert plan.adjusted_quantity == 110  # 100 * 1.10 for 10% scrap


def test_calculate_bom_component_quantities():
    """Test that component quantities are calculated correctly."""
    plan = calculate_bom("DC2", 100)

    # Find sapphire lens component
    lens_comp = next(c for c in plan.components_needed if "sapphire lens" in c["name"].lower())

    # Should need 108 lenses (100 units + 8% scrap buffer)
    assert lens_comp["total_needed"] == 108

    # Find titanium stock
    titanium_comp = next(c for c in plan.components_needed if "titanium" in c["name"].lower())

    # Should need 5.5 inches * 108 units = 594 inches
    assert titanium_comp["total_needed"] == pytest.approx(594.0, rel=0.01)


def test_calculate_bom_with_inventory():
    """Test BOM calculation accounting for current inventory."""
    current_inventory = {
        "21mm sapphire lens": 50,
        "titanium 1\" round stock": 200,
    }

    plan = calculate_bom("DC2", 100, current_inventory=current_inventory)

    # Find lens component
    lens_comp = next(c for c in plan.components_needed if "sapphire lens" in c["name"].lower())

    # Need 108 total, have 50, so need to order 58
    assert lens_comp["on_hand"] == 50
    assert lens_comp["need_to_order"] == 58

    # Find titanium
    titanium_comp = next(c for c in plan.components_needed if "titanium" in c["name"].lower())

    # Need 594, have 200, need to order 394
    assert titanium_comp["on_hand"] == 200
    assert titanium_comp["need_to_order"] == pytest.approx(394.0, rel=0.01)


def test_calculate_bom_machine_time():
    """Test machine time calculation."""
    plan = calculate_bom("DC2", 100)

    # 108 units * 30 minutes = 3240 minutes = 54 hours
    assert plan.machine_time_hours == pytest.approx(54.0, rel=0.01)


def test_calculate_bom_lead_time_warnings():
    """Test that lead time warnings are generated."""
    plan = calculate_bom("DC2", 100)

    # Should have warnings for components with long lead times
    # MCR20S driver has 42 day lead time
    assert len(plan.lead_time_warnings) > 0

    warning_text = "\n".join(plan.lead_time_warnings)
    assert "MCR20S" in warning_text or "driver" in warning_text.lower()


def test_calculate_bom_order_by_dates():
    """Test that order-by dates are calculated."""
    plan = calculate_bom("DC2", 100)

    # Should have order-by dates for components that need ordering
    assert len(plan.order_by_dates) > 0


def test_calculate_bom_unknown_product():
    """Test that unknown product raises error."""
    with pytest.raises(ValueError, match="Unknown product"):
        calculate_bom("FAKE_PRODUCT", 100)


def test_format_production_plan():
    """Test formatting production plan as text."""
    plan = calculate_bom("DC2", 100)
    formatted = format_production_plan(plan)

    assert "Production Plan" in formatted
    assert "DC2" in formatted
    assert "100x" in formatted
    assert "Components needed" in formatted
    assert "Machine time" in formatted


def test_format_production_plan_with_target_date():
    """Test formatting with target completion date."""
    plan = calculate_bom("DC2", 100)
    formatted = format_production_plan(plan, target_date="2025-12-15")

    assert "2025-12-15" in formatted


def test_estimate_scrap_for_run():
    """Test estimating scrap quantity."""
    scrap = estimate_scrap_for_run("DC2", 100)

    # 8% of 100 = 8 units
    assert scrap == 8


def test_estimate_scrap_with_custom_rate():
    """Test estimating scrap with custom rate."""
    scrap = estimate_scrap_for_run("DC2", 100, historical_scrap_rate=0.15)

    # 15% of 100 = 15 units
    assert scrap == 15


def test_estimate_scrap_unknown_product():
    """Test that scrap estimation fails for unknown product."""
    with pytest.raises(ValueError, match="Unknown product"):
        estimate_scrap_for_run("FAKE_PRODUCT", 100)


def test_component_dataclass():
    """Test Component dataclass."""
    comp = Component(
        name="Test Component",
        quantity_per_unit=2.5,
        unit="inches",
        sku="TEST-SKU"
    )

    assert comp.name == "Test Component"
    assert comp.quantity_per_unit == 2.5
    assert comp.unit == "inches"
    assert comp.sku == "TEST-SKU"


def test_product_bom_dataclass():
    """Test ProductBOM dataclass."""
    bom = ProductBOM(
        product_name="Test Product",
        components=[
            Component("Part A", 1, "each"),
            Component("Part B", 2, "inches"),
        ],
        machine_time_minutes=45,
        scrap_rate=0.10,
        notes="Test notes"
    )

    assert bom.product_name == "Test Product"
    assert len(bom.components) == 2
    assert bom.machine_time_minutes == 45
    assert bom.scrap_rate == 0.10
    assert bom.notes == "Test notes"
