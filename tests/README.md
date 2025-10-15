# Al Test Suite

## Why Tests?

**Al has shown he can't be trusted without tests:**
- 147+ memory save failures (forgetfulness)
- Wrong dates repeatedly (Oct 14 → "Oct 12")
- October 33rd date math
- Said database was empty (11 vendors existed)
- ShipStation auth failures

**If Al can't be relied on, he's useless. Tests ensure reliability.**

## Running Tests

### Quick Start
```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=al --cov-report=term-missing

# Run specific test category
pytest tests/regression/  # Known bugs
pytest tests/unit/        # Individual components
pytest tests/integration/ # End-to-end workflows
```

### Important: Regression Tests MUST Pass

```bash
# These tests prevent known bugs from returning
pytest tests/regression/test_known_bugs.py -v

# If these fail, known bugs have returned!
```

## Test Categories

### 1. Regression Tests (`tests/regression/`)
**Purpose**: Prevent known bugs from coming back.

**Critical Tests**:
- `test_conversation_with_tool_use_serializes` - Memory bug
- `test_get_current_date_returns_actual_date` - Date confusion
- `test_calculate_date_handles_month_boundaries` - October 33rd
- `test_list_vendors_checks_actual_data` - Empty database hallucination
- `test_shipstation_uses_basic_auth` - V2 API failure

**Rule**: If regression tests fail, **DO NOT DEPLOY**.

### 2. Unit Tests (`tests/unit/`)
**Purpose**: Test individual components in isolation.

**Coverage**:
- Helper modules (vendor, invoice, scrap, shipstation, etc.)
- Tool functions (calculate, get_current_date, list_vendors, etc.)
- Utility functions

### 3. Integration Tests (`tests/integration/`)
**Purpose**: Test complete workflows end-to-end.

**Workflows**:
- Conversation persistence
- Invoice processing
- Order checking
- Vendor management
- Date calculations

## Writing New Tests

### When to Write Tests

**ALWAYS write tests for:**
1. Any new feature
2. Any bug fix (regression test)
3. Any critical path code
4. Any code that touches data persistence

**Example**: If you add a new tool, write:
- Unit test for the tool function
- Integration test for the workflow
- Regression test if it fixes a bug

### Test Template

```python
def test_feature_does_what_expected():
    """Clear description of what's being tested."""
    # Arrange: Set up test data
    input_data = {"key": "value"}

    # Act: Execute the function
    result = function_under_test(input_data)

    # Assert: Verify the result
    assert result == expected_value
```

## CI/CD Integration

### GitHub Actions
Tests run automatically on every push:
- All tests must pass
- Coverage must be ≥80%
- Regression tests have extra scrutiny

### Pre-commit Hook (Optional)
```bash
# Add to .git/hooks/pre-commit
#!/bin/bash
pytest tests/regression/
if [ $? -ne 0 ]; then
    echo "❌ Regression tests failed - commit blocked"
    exit 1
fi
```

## Coverage Requirements

**Minimum Coverage**: 50% (current baseline)

**Target Coverage** (future goal): 80%

**Critical Modules** (priority for testing):
- `al/bot.py` - Core bot logic
- `al/helpers/vendor_helper.py` - Vendor management
- `al/helpers/invoice_tracker.py` - Invoice processing
- `al/helpers/shipstation_helper.py` - Order checking

## Monitoring in Production

### Health Checks
Run daily automated checks:
```bash
# Can Al list vendors?
python -c "from al.bot import execute_tool; print(execute_tool('list_vendors', {}))"

# Can Al get the date?
python -c "from al.bot import execute_tool; print(execute_tool('get_current_date', {}))"

# Can Al do math?
python -c "from al.bot import execute_tool; print(execute_tool('calculate', {'expression': '2+2'}))"
```

### Alert Thresholds
- Conversation save failures: >3 in 24 hours
- Tool call failures: >10 in 24 hours
- API failures: >20 in 24 hours

## Trust Metrics

**Al is reliable when:**
- ✅ All regression tests pass
- ✅ Coverage ≥50% (target: 80%)
- ✅ Zero memory save failures (7 days)
- ✅ Zero date confusion (7 days)
- ✅ Zero math errors (7 days)
- ✅ Can list vendors on demand (100% success)

**Current Status**: See GitHub Actions badge in main README

## Common Issues

### Tests fail with "Module not found"
```bash
# Make sure you're in the al/ directory
cd /home/jasapp/src/al
export PYTHONPATH=$PYTHONPATH:$(pwd)
pytest
```

### Tests fail with "API key not set"
```bash
# Mock keys for testing
export SHIPSTATION_API_KEY=test_key:test_secret
export NOTION_API_KEY=test_notion_key
pytest
```

### Coverage is below 50%
Find untested code:
```bash
pytest --cov=al --cov-report=html
# Open htmlcov/index.html to see what's missing
```

Note: Current target is 50%, with a future goal of 80%.

## Next Steps

1. **Run existing regression tests**: `pytest tests/regression/`
2. **Check results**: All should pass (they test fixed bugs)
3. **Add unit tests**: Start with most critical helpers
4. **Add integration tests**: Test full workflows
5. **Enable CI/CD**: Automatic testing on every commit
6. **Monitor production**: Set up health checks

**Bottom line**: No more "Al was forgetful" excuses. Tests prove reliability.
