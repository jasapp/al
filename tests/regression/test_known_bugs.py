"""
Regression tests for Al's known bugs.

These tests ensure bugs don't come back. Each test represents a bug that actually happened.
"""

import pytest
from datetime import datetime, timedelta
import json


class TestMemoryBug:
    """
    BUG: Al had 147+ "Failed to save conversation history" errors.
    ROOT CAUSE: Anthropic TextBlock/ToolUseBlock objects not JSON serializable.
    FIX: Serialize blocks to dicts before saving.
    """

    def test_conversation_with_tool_use_serializes(self):
        """Ensure conversation with tool_use blocks can be saved to JSON."""
        # Simulate Anthropic response structure
        conversation = [
            {"role": "user", "content": "Check inventory"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "toolu_123", "name": "check_orders", "input": {}},
                    {"type": "text", "text": "Let me check that"}
                ]
            },
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_123", "content": "No orders"}]},
            {"role": "assistant", "content": "You have no orders."}
        ]

        # This should NOT raise an exception
        try:
            json_str = json.dumps(conversation)
            reloaded = json.loads(json_str)
            assert len(reloaded) == len(conversation)
        except TypeError as e:
            pytest.fail(f"Conversation should be JSON serializable: {e}")

    def test_text_block_objects_fail_serialization(self):
        """Document that raw Anthropic objects fail - this is what we're protecting against."""
        # This is a mock of what Anthropic returns (simplified)
        class TextBlock:
            def __init__(self, text):
                self.type = "text"
                self.text = text

        # This SHOULD fail to serialize
        with pytest.raises(TypeError):
            json.dumps({"role": "assistant", "content": TextBlock("hi")})


class TestDateConfusion:
    """
    BUG: Al repeatedly got current date wrong (Oct 14 → "Oct 12", Oct 13 → "Oct 11").
    ROOT CAUSE: Al was guessing from conversation context.
    FIX: Added get_current_date tool.
    """

    def test_get_current_date_returns_actual_date(self):
        """Ensure get_current_date returns actual system date, not guessed."""
        from al.bot import execute_tool

        result = execute_tool("get_current_date", {})
        # Should contain actual current date
        now = datetime.now()
        assert str(now.year) in result
        assert now.strftime("%B") in result  # Month name
        assert str(now.day) in result


class TestOctober33rd:
    """
    BUG: Al calculated "October 12 + 21 days = October 33rd"
    ROOT CAUSE: Did arithmetic (12+21=33) but then manual date math.
    FIX: Added calculate_date tool.
    """

    def test_calculate_date_handles_month_boundaries(self):
        """Ensure date calculation handles month boundaries correctly."""
        from al.bot import execute_tool

        # October 12 + 21 days should be November 2, NOT October 33
        result = execute_tool("calculate_date", {"start_date": "2025-10-12", "days": 21})

        assert "November" in result
        assert "02" in result or "2" in result
        assert "October 33" not in result

    def test_calculate_date_handles_leap_years(self):
        """Ensure date calculation handles February correctly."""
        from al.bot import execute_tool

        # Feb 28, 2024 (leap year) + 1 day = Feb 29
        result = execute_tool("calculate_date", {"start_date": "2024-02-28", "days": 1})
        assert "February 29" in result

        # Feb 28, 2025 (non-leap) + 1 day = March 1
        result = execute_tool("calculate_date", {"start_date": "2025-02-28", "days": 1})
        assert "March" in result
        assert "01" in result or "1" in result


class TestMathErrors:
    """
    BUG: LLMs can hallucinate math (2+2=5).
    ROOT CAUSE: Pattern matching instead of actual computation.
    FIX: Added calculate tool with safe eval.
    """

    def test_calculator_basic_arithmetic(self):
        """Ensure calculator does actual math, not LLM pattern matching."""
        from al.bot import execute_tool

        assert "4" in execute_tool("calculate", {"expression": "2 + 2"})
        assert "148" in execute_tool("calculate", {"expression": "74 * 2"})
        assert "37" in execute_tool("calculate", {"expression": "407 / 11"})

    def test_calculator_prevents_code_injection(self):
        """Ensure calculator blocks malicious code."""
        from al.bot import execute_tool

        # Should fail safely, not execute dangerous code
        result = execute_tool("calculate", {"expression": "__import__('os').system('ls')"})
        assert "error" in result.lower() or "invalid" in result.lower()


class TestEmptyDatabase:
    """
    BUG: Al said "database is empty" when it had 11 vendors.
    ROOT CAUSE: Responded from memory without checking actual data.
    FIX: Added list_vendors tool.
    """

    def test_list_vendors_checks_actual_data(self, monkeypatch):
        """Ensure list_vendors returns actual vendor data, not hallucination."""
        from al.bot import execute_tool

        # Mock vendor helper to return test data
        class MockVendorHelper:
            def format_vendor_list(self):
                return "**Vendors:**\\n\\nTest Vendor 1\\nTest Vendor 2"

        # Patch vendor_helper
        import al.bot
        original_helper = al.bot.vendor_helper
        al.bot.vendor_helper = MockVendorHelper()

        result = execute_tool("list_vendors", {})

        # Should include actual vendor data
        assert "Test Vendor 1" in result
        assert "Test Vendor 2" in result
        assert result != "database is empty"

        # Restore
        al.bot.vendor_helper = original_helper


class TestShipStationV2Failure:
    """
    BUG: ShipStation V2 API returned 401 "Failed to parse bearer token".
    ROOT CAUSE: Using V2 API with Bearer token instead of V1 with Basic Auth.
    FIX: Switched to V1 API (ssapi.shipstation.com) with Basic Auth.
    """

    def test_shipstation_uses_basic_auth_not_bearer(self):
        """Ensure ShipStation helper uses Basic Auth, not Bearer token."""
        from al.helpers.shipstation_helper import ShipStationHelper
        import os

        # Mock environment
        os.environ["SHIPSTATION_API_KEY"] = "test_key:test_secret"

        helper = ShipStationHelper()

        # Should have auth tuple, not Authorization header with Bearer
        assert hasattr(helper, "auth")
        assert helper.auth == ("test_key", "test_secret")
        assert "Authorization" not in helper.headers or "Bearer" not in helper.headers.get("Authorization", "")

    def test_shipstation_uses_v1_endpoint(self):
        """Ensure ShipStation uses V1 API endpoint."""
        from al.helpers.shipstation_helper import ShipStationHelper
        import os

        os.environ["SHIPSTATION_API_KEY"] = "test_key:test_secret"
        helper = ShipStationHelper()

        # Should use ssapi.shipstation.com, NOT api.shipstation.com/v2
        assert helper.base_url == "https://ssapi.shipstation.com"
        assert "v2" not in helper.base_url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
