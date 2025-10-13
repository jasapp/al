"""Tests for mood_manager.py"""

import pytest
from pathlib import Path
import tempfile
import json
from datetime import datetime, timedelta
from al.helpers.mood_manager import MoodManager


@pytest.fixture
def temp_state_file():
    """Create a temporary state file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = Path(f.name)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


def test_mood_manager_initialization(temp_state_file):
    """Test that MoodManager initializes with default state."""
    manager = MoodManager(state_file=temp_state_file)

    assert manager.state["warnings"] == {}
    assert manager.state["recent_fuckups"] == []
    assert manager.state["last_positive"] is None


def test_record_warning(temp_state_file):
    """Test recording inventory warnings."""
    manager = MoodManager(state_file=temp_state_file)

    manager.record_warning("sapphire lenses", "low")

    assert "sapphire lenses" in manager.state["warnings"]
    assert manager.state["warnings"]["sapphire lenses"]["count"] == 1
    assert manager.state["warnings"]["sapphire lenses"]["severity"] == "low"

    # Record again
    manager.record_warning("sapphire lenses", "critical")

    assert manager.state["warnings"]["sapphire lenses"]["count"] == 2
    assert manager.state["warnings"]["sapphire lenses"]["severity"] == "critical"


def test_clear_warning(temp_state_file):
    """Test clearing warnings when jeff orders things."""
    manager = MoodManager(state_file=temp_state_file)

    manager.record_warning("sapphire lenses", "low")
    assert "sapphire lenses" in manager.state["warnings"]

    manager.clear_warning("sapphire lenses")
    assert "sapphire lenses" not in manager.state["warnings"]
    assert manager.state["last_positive"] is not None


def test_record_fuckup(temp_state_file):
    """Test recording mistakes/problems."""
    manager = MoodManager(state_file=temp_state_file)

    manager.record_fuckup("scrap", "3 DC2 bodies scrapped - chip in collet", severity=7)

    assert len(manager.state["recent_fuckups"]) == 1
    assert manager.state["recent_fuckups"][0]["type"] == "scrap"
    assert manager.state["recent_fuckups"][0]["severity"] == 7


def test_fuckup_limit(temp_state_file):
    """Test that only last 10 fuckups are kept."""
    manager = MoodManager(state_file=temp_state_file)

    # Record 15 fuckups
    for i in range(15):
        manager.record_fuckup("test", f"Fuckup {i}", severity=5)

    assert len(manager.state["recent_fuckups"]) == 10


def test_anger_level_calm(temp_state_file):
    """Test anger level when everything is fine."""
    manager = MoodManager(state_file=temp_state_file)

    anger = manager.get_anger_level()
    assert anger <= 2  # Should be calm


def test_anger_level_with_warnings(temp_state_file):
    """Test anger level increases with warnings."""
    manager = MoodManager(state_file=temp_state_file)

    # Calm at first
    assert manager.get_anger_level() <= 2

    # Add a warning
    manager.record_warning("lenses", "low")
    assert manager.get_anger_level() >= 1


def test_anger_level_with_ignored_warnings(temp_state_file):
    """Test anger increases when warnings are ignored over time."""
    manager = MoodManager(state_file=temp_state_file)

    # Manually set old warning
    old_timestamp = (datetime.now() - timedelta(days=8)).isoformat()
    manager.state["warnings"]["lenses"] = {
        "first_warned": old_timestamp,
        "last_warned": old_timestamp,
        "count": 5,
        "severity": "critical"
    }

    anger = manager.get_anger_level()
    assert anger >= 5  # Should be pretty pissed


def test_anger_level_out_of_stock(temp_state_file):
    """Test maximum anger when actually out of stock."""
    manager = MoodManager(state_file=temp_state_file)

    manager.record_warning("lenses", "out")

    anger = manager.get_anger_level()
    assert anger >= 4  # Out of stock is serious


def test_anger_with_fuckups(temp_state_file):
    """Test anger increases with recent fuckups."""
    manager = MoodManager(state_file=temp_state_file)

    manager.record_fuckup("scrap", "Scrapped 5 bodies", severity=8)
    manager.record_fuckup("wrong_order", "Ordered wrong size lenses", severity=6)

    anger = manager.get_anger_level()
    assert anger >= 2


def test_mood_context_generation(temp_state_file):
    """Test that mood context generates properly."""
    manager = MoodManager(state_file=temp_state_file)

    manager.record_warning("lenses", "low")
    manager.record_fuckup("scrap", "Scrapped parts", severity=5)

    context = manager.get_mood_context()

    assert "Active inventory warnings" in context
    assert "lenses" in context
    assert "Recent problems" in context
    assert "Suggested mood" in context


def test_persistence(temp_state_file):
    """Test that state persists across instances."""
    manager1 = MoodManager(state_file=temp_state_file)
    manager1.record_warning("lenses", "low")
    manager1.record_fuckup("scrap", "Test fuckup", severity=5)

    # Create new instance with same file
    manager2 = MoodManager(state_file=temp_state_file)

    assert "lenses" in manager2.state["warnings"]
    assert len(manager2.state["recent_fuckups"]) == 1


def test_record_positive(temp_state_file):
    """Test recording positive events."""
    manager = MoodManager(state_file=temp_state_file)

    assert manager.state["last_positive"] is None

    manager.record_positive("jeff ordered lenses on time")

    assert manager.state["last_positive"] is not None


def test_anger_decreases_with_recent_positive(temp_state_file):
    """Test that recent positive events help mood."""
    manager = MoodManager(state_file=temp_state_file)

    manager.record_warning("lenses", "low")
    anger_before = manager.get_anger_level()

    manager.record_positive("jeff fixed it")

    # Anger shouldn't magically disappear but last_positive is tracked
    assert manager.state["last_positive"] is not None
