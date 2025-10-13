"""Tests for scrap_tracker.py"""

import pytest
from pathlib import Path
import tempfile
from datetime import datetime, timedelta
from al.helpers.scrap_tracker import (
    ScrapTracker,
    ScrapEntry,
    log_scrap_event,
    get_scrap_summary,
)


@pytest.fixture
def temp_scrap_file():
    """Create temporary scrap file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = Path(f.name)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


def test_scrap_entry_dataclass():
    """Test ScrapEntry dataclass."""
    entry = ScrapEntry(
        timestamp="2025-10-13T10:00:00",
        product="DC2",
        quantity=3,
        reason="chip in collet",
        material_cost=90.0,
        time_cost_minutes=90,
        materials_lost={"titanium": 16.5, "copper": 3.0}
    )

    assert entry.product == "DC2"
    assert entry.quantity == 3
    assert entry.reason == "chip in collet"
    assert entry.material_cost == 90.0


def test_scrap_tracker_initialization(temp_scrap_file):
    """Test ScrapTracker initializes properly."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    assert tracker.scrap_history == []


def test_log_scrap(temp_scrap_file):
    """Test logging scrap event."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    entry = tracker.log_scrap(
        product="DC2",
        quantity=3,
        reason="chip in collet",
        material_cost=90.0,
        time_cost_minutes=90
    )

    assert entry.product == "DC2"
    assert entry.quantity == 3
    assert len(tracker.scrap_history) == 1


def test_get_recent_scrap(temp_scrap_file):
    """Test getting recent scrap entries."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    # Add some scrap entries
    tracker.log_scrap("DC2", 2, "test reason 1")
    tracker.log_scrap("DC1", 1, "test reason 2")

    recent = tracker.get_recent_scrap(days=7)

    assert len(recent) == 2


def test_get_recent_scrap_old_entries(temp_scrap_file):
    """Test that old entries are filtered out."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    # Add entry with old timestamp
    old_timestamp = (datetime.now() - timedelta(days=10)).isoformat()
    old_entry = ScrapEntry(
        timestamp=old_timestamp,
        product="DC2",
        quantity=1,
        reason="old scrap"
    )
    tracker.scrap_history.append(old_entry)

    # Add recent entry
    tracker.log_scrap("DC2", 1, "recent scrap")

    recent = tracker.get_recent_scrap(days=7)

    # Should only have the recent one
    assert len(recent) == 1
    assert recent[0].reason == "recent scrap"


def test_get_scrap_by_product(temp_scrap_file):
    """Test getting scrap for specific product."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    tracker.log_scrap("DC2", 3, "reason 1")
    tracker.log_scrap("DC1", 2, "reason 2")
    tracker.log_scrap("DC2", 1, "reason 3")

    dc2_scrap = tracker.get_scrap_by_product("DC2")

    assert len(dc2_scrap) == 2
    assert all(e.product == "DC2" for e in dc2_scrap)


def test_get_scrap_by_product_case_insensitive(temp_scrap_file):
    """Test that product lookup is case-insensitive."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    tracker.log_scrap("DC2", 1, "test")

    scrap = tracker.get_scrap_by_product("dc2")

    assert len(scrap) == 1


def test_calculate_scrap_rate(temp_scrap_file):
    """Test calculating scrap rate."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    # Log 15 units scrapped over 30 days
    for _ in range(5):
        tracker.log_scrap("DC2", 3, "test reason")

    rate = tracker.calculate_scrap_rate("DC2", days=30)

    # 15 units / 30 days = 0.5 units/day
    assert rate == pytest.approx(0.5, rel=0.01)


def test_calculate_scrap_rate_no_data(temp_scrap_file):
    """Test scrap rate returns None when no data."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    rate = tracker.calculate_scrap_rate("DC2", days=30)

    assert rate is None


def test_get_scrap_reasons(temp_scrap_file):
    """Test getting breakdown of scrap reasons."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    tracker.log_scrap("DC2", 3, "chip in collet")
    tracker.log_scrap("DC2", 2, "chip in collet")
    tracker.log_scrap("DC2", 1, "wrong dimensions")

    reasons = tracker.get_scrap_reasons()

    assert reasons["chip in collet"] == 5  # 3 + 2
    assert reasons["wrong dimensions"] == 1


def test_get_scrap_reasons_filtered_by_product(temp_scrap_file):
    """Test getting reasons filtered by product."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    tracker.log_scrap("DC2", 3, "chip in collet")
    tracker.log_scrap("DC1", 2, "chip in collet")

    reasons = tracker.get_scrap_reasons(product="DC2")

    assert reasons["chip in collet"] == 3  # Only DC2


def test_calculate_total_waste(temp_scrap_file):
    """Test calculating total waste."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    tracker.log_scrap("DC2", 3, "test", material_cost=90.0, time_cost_minutes=90)
    tracker.log_scrap("DC2", 2, "test", material_cost=60.0, time_cost_minutes=60)

    waste = tracker.calculate_total_waste(days=7)

    assert waste["total_units"] == 5
    assert waste["total_cost"] == 150.0
    assert waste["total_time_minutes"] == 150
    assert waste["total_time_hours"] == 2.5


def test_detect_recurring_issues(temp_scrap_file):
    """Test detecting recurring scrap issues."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    # Same reason 5 times
    for _ in range(5):
        tracker.log_scrap("DC2", 1, "chip in collet")

    # Different reason once
    tracker.log_scrap("DC2", 1, "wrong size")

    recurring = tracker.detect_recurring_issues(threshold=3, days=30)

    assert len(recurring) >= 1
    assert any("chip in collet" in issue for issue in recurring)


def test_format_scrap_summary(temp_scrap_file):
    """Test formatting scrap summary as text."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    tracker.log_scrap("DC2", 3, "chip in collet", material_cost=90.0, time_cost_minutes=90)
    tracker.log_scrap("DC2", 2, "wrong dimensions", material_cost=60.0, time_cost_minutes=60)

    summary = tracker.format_scrap_summary(days=7)

    assert "Scrap Summary" in summary
    assert "5" in summary  # Total units
    assert "chip in collet" in summary
    assert "wrong dimensions" in summary


def test_format_scrap_summary_no_scrap(temp_scrap_file):
    """Test summary when no scrap exists."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    summary = tracker.format_scrap_summary(days=7)

    assert "No scrap" in summary


def test_format_scrap_summary_with_recurring(temp_scrap_file):
    """Test that recurring issues are highlighted in summary."""
    tracker = ScrapTracker(scrap_file=temp_scrap_file)

    # Same issue multiple times
    for _ in range(4):
        tracker.log_scrap("DC2", 1, "chip in collet")

    summary = tracker.format_scrap_summary(days=7)

    assert "RECURRING ISSUES" in summary
    assert "chip in collet" in summary


def test_persistence(temp_scrap_file):
    """Test that scrap history persists across instances."""
    tracker1 = ScrapTracker(scrap_file=temp_scrap_file)
    tracker1.log_scrap("DC2", 3, "test scrap")

    # Create new instance with same file
    tracker2 = ScrapTracker(scrap_file=temp_scrap_file)

    assert len(tracker2.scrap_history) == 1
    assert tracker2.scrap_history[0].product == "DC2"


def test_convenience_functions(temp_scrap_file):
    """Test convenience functions."""
    # Note: These use default file path, so we'll just test they don't crash

    entry = log_scrap_event("DC2", 1, "test")
    assert isinstance(entry, ScrapEntry)

    summary = get_scrap_summary(days=7)
    assert isinstance(summary, str)
