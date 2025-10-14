# Al Testing Plan

## The Problem
Al has shown critical reliability issues:
- **Memory failures**: 147+ JSON serialization errors causing forgetfulness
- **Date confusion**: Repeatedly getting wrong dates (Oct 14 → "Oct 12")
- **Math errors**: Risk of 2+2=5 style LLM hallucinations
- **Missing vendor data**: Said database was empty when it had 11 vendors

**Bottom line: If Al can't be trusted, he's useless.**

## Test Strategy

### 1. Unit Tests (Test Individual Components)

#### A. **Helper Modules** (`al/helpers/*.py`)

**vendor_helper.py**
- ✅ Load vendors from Notion
- ✅ Load vendors from JSON fallback
- ✅ Add new vendor
- ✅ Update existing vendor
- ✅ Search vendors by product
- ✅ Format vendor list output
- ✅ Handle duplicate vendor names

**invoice_tracker.py**
- ✅ Parse invoice from image
- ✅ Save invoice to Notion
- ✅ Save invoice to JSON fallback
- ✅ Retrieve invoice by number
- ✅ List all invoices
- ✅ Handle duplicate invoice numbers

**scrap_tracker.py**
- ✅ Log scrap entry
- ✅ Calculate scrap costs
- ✅ Save to Notion
- ✅ Retrieve scrap history
- ✅ Calculate total scrap by product

**shipstation_helper.py**
- ✅ Authenticate with V1 API
- ✅ Fetch orders (awaiting_shipment)
- ✅ Fetch orders with date filtering
- ✅ Handle pagination (500+ orders)
- ✅ Parse order items correctly
- ✅ Handle API errors gracefully

**notion_helper.py**
- ✅ Connect to Notion API
- ✅ Query database
- ✅ Create page
- ✅ Update page
- ✅ Handle rate limits
- ✅ Fallback when offline

**production_helper.py**
- ✅ Calculate BOM for DC2
- ✅ Calculate machine time
- ✅ Calculate lead times
- ✅ Format production plan output

**mood_manager.py**
- ✅ Track mood state
- ✅ Record fuckups
- ✅ Adjust mood based on events
- ✅ Generate mood context for prompts

#### B. **Tool Functions** (in `bot.py`)

**Tool Execution Tests**
- ✅ `calculate` - Basic arithmetic (2+2=4, not 5)
- ✅ `calculate` - Division (407/11 = 37)
- ✅ `calculate` - Complex expressions
- ✅ `calculate` - Safe eval (blocks malicious code)
- ✅ `get_current_date` - Returns actual system date
- ✅ `calculate_date` - Add days (Oct 12 + 21 = Nov 2, NOT Oct 33)
- ✅ `calculate_date` - Subtract days
- ✅ `calculate_date` - Handle month boundaries
- ✅ `list_vendors` - Shows all vendors from database
- ✅ `get_vendor_info` - Lookup by name
- ✅ `get_vendor_info` - Search by product
- ✅ `check_orders` - Fetch from ShipStation
- ✅ `check_orders` - Filter by status
- ✅ `check_orders` - Filter by date range
- ✅ `calculate_production_plan` - Full BOM calculation
- ✅ `log_scrap` - Record scrap and update mood
- ✅ `add_vendor` - Create new vendor

### 2. Integration Tests (Test End-to-End Workflows)

#### A. **Conversation Memory**
- ✅ Save conversation with text blocks
- ✅ Save conversation with tool use blocks
- ✅ Load conversation history on startup
- ✅ Serialize Anthropic objects correctly (prevent JSON errors)
- ✅ Keep history under size limit (20 messages)
- ✅ Verify no data loss after restart

#### B. **Invoice Processing Workflow**
- ✅ Receive invoice image
- ✅ Extract vendor and items
- ✅ Create/update vendor in database
- ✅ Save invoice to Notion
- ✅ Verify data persists after restart

#### C. **Order Checking Workflow**
- ✅ Request order check from ShipStation
- ✅ Parse all 100+ orders
- ✅ Display order details correctly
- ✅ Calculate totals
- ✅ Handle orders with 0 items

#### D. **Date/Time Calculations**
- ✅ Get current date (not guessed from context)
- ✅ Calculate lead times correctly
- ✅ Calculate delivery dates (no October 33rd!)
- ✅ Calculate order age (days since order date)

#### E. **Vendor Management**
- ✅ List all vendors (not "database is empty")
- ✅ Add new vendor
- ✅ Merge duplicate vendors
- ✅ Search vendors by product
- ✅ Update vendor lead times

### 3. System/Regression Tests

#### A. **Known Bug Prevention**
- ✅ Memory bug: TextBlock/ToolUseBlock serialization
- ✅ Date confusion: Getting wrong current date
- ✅ October 33rd: Manual date arithmetic
- ✅ Empty database: Not checking actual data
- ✅ ShipStation auth: V2 → V1 API switch

#### B. **Load/Stress Tests**
- ✅ Handle 500+ ShipStation orders
- ✅ Handle 50+ vendors in database
- ✅ Handle 100+ invoices
- ✅ Handle long conversations (50+ messages)

#### C. **Error Handling**
- ✅ Notion API down → fallback to JSON
- ✅ ShipStation API error → log and return message
- ✅ Invalid calculator expression → return error
- ✅ Invalid date format → return error
- ✅ Missing environment variables → clear error

### 4. Test Implementation

**Framework**: pytest

**Structure**:
```
tests/
├── unit/
│   ├── test_vendor_helper.py
│   ├── test_invoice_tracker.py
│   ├── test_scrap_tracker.py
│   ├── test_shipstation_helper.py
│   ├── test_notion_helper.py
│   ├── test_production_helper.py
│   ├── test_mood_manager.py
│   └── test_tools.py
├── integration/
│   ├── test_conversation_memory.py
│   ├── test_invoice_workflow.py
│   ├── test_order_workflow.py
│   ├── test_vendor_workflow.py
│   └── test_date_calculations.py
├── regression/
│   ├── test_known_bugs.py
│   └── test_error_handling.py
└── conftest.py  # Shared fixtures
```

**Mock Data**:
- Mock Notion API responses
- Mock ShipStation API responses
- Mock invoice images
- Sample conversation histories

**Coverage Target**: 80%+ code coverage

### 5. Continuous Integration

**GitHub Actions Workflow**:
```yaml
name: Al Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - Checkout code
      - Install dependencies
      - Run pytest with coverage
      - Fail if coverage < 80%
      - Fail if any test fails
```

**Pre-commit Hook**:
- Run tests before committing
- Block commit if tests fail
- Run linting (black, flake8)

### 6. Monitoring & Alerting

**Production Monitoring**:
- Log all tool calls with results
- Track conversation save success rate
- Alert if conversation save fails 3+ times
- Alert if ShipStation API fails
- Alert if Notion API fails
- Daily health check: Can Al list vendors?

### 7. Documentation Tests

**Docstring Tests**:
- Test all docstring examples with doctest
- Ensure documentation stays accurate

## Test Execution Plan

### Phase 1: Critical Path (Week 1)
1. ✅ Test conversation memory (prevent forgetfulness)
2. ✅ Test date/time tools (prevent confusion)
3. ✅ Test calculator (prevent math errors)
4. ✅ Test database access (prevent "empty database")

### Phase 2: Core Functionality (Week 2)
1. ✅ Test all helper modules
2. ✅ Test all tool functions
3. ✅ Test API integrations (Notion, ShipStation)

### Phase 3: Edge Cases (Week 3)
1. ✅ Test error handling
2. ✅ Test load/stress scenarios
3. ✅ Test known bug regressions

### Phase 4: Automation (Week 4)
1. ✅ Set up CI/CD pipeline
2. ✅ Set up pre-commit hooks
3. ✅ Set up production monitoring
4. ✅ Write runbook for failures

## Success Criteria

**Al is considered reliable when:**
1. ✅ 100% of critical path tests pass
2. ✅ 80%+ code coverage
3. ✅ Zero conversation save failures in 1 week
4. ✅ Zero date confusion in 1 week
5. ✅ Zero math errors in 1 week
6. ✅ Can list vendors on demand
7. ✅ All ShipStation orders visible
8. ✅ No regression of fixed bugs

**Ongoing Trust Metrics**:
- Conversation save success rate: >99%
- Tool call success rate: >95%
- API call success rate: >90%
- Memory persistence: 100% (no data loss)

## Next Steps

1. Write pytest configuration
2. Create test fixtures (mock data)
3. Start with critical path tests
4. Build out full test suite
5. Set up CI/CD
6. Monitor and iterate
