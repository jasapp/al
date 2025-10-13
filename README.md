# Al - Supply Chain Management for Okluma

**"I've been doing this since before you were born, kid."**

Al is your gruff, no-nonsense supply chain manager. Inspired by the old-school manufacturing guys who actually knew their shit, Al keeps track of inventory, vendors, and production planning so you can focus on making great flashlights.

## What Al Does

### Inventory Management
- Monitors ShipStation inventory levels
- Warns when components are running low (and gets progressively more annoyed if you ignore him)
- Tracks raw materials (titanium stock, copper, etc.)
- Manages reorder points with intelligent snoozing

### Production Planning
- "I want to sell 500 DC2s in December. What do we need?"
- Calculates full Bill of Materials (BOM) for production runs
- Accounts for scrap rates and manufacturing time
- Provides order-by dates based on vendor lead times

### Vendor Management
- Never lose a vendor again
- Send Al a screenshot of an invoice → he extracts and saves vendor info
- Tracks lead times, contact info, and ordering history
- Logs incoming inventory from orders

### Scrap Tracking
- Records manufacturing waste and reasons
- Adjusts production planning based on historical scrap rates
- Alerts if scrap rates spike unexpectedly

## Project Structure

```
al/
├── al/                          # Main package
│   ├── bot.py                   # Telegram bot (main entry point)
│   ├── helpers/
│   │   ├── shipstation_helper.py    # ShipStation V2 API integration
│   │   ├── vendor_helper.py         # Vendor tracking and management
│   │   ├── invoice_parser.py        # OCR + Claude vision for invoices
│   │   ├── production_helper.py     # BOM calculations and planning
│   │   ├── scrap_tracker.py         # Manufacturing waste tracking
│   │   └── mood_manager.py          # Al's grumpiness levels
│   └── __init__.py
├── tests/                       # Unit tests
│   ├── test_shipstation_helper.py
│   ├── test_vendor_helper.py
│   ├── test_production_helper.py
│   └── __init__.py
├── AL_MEMORY.md                 # Al's knowledge base (vendors, BOMs, notes)
├── .env.example                 # Environment template
├── .gitignore
├── requirements.txt
├── run_al.sh                    # Startup script
└── README.md                    # This file
```

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and add your API keys:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
ANTHROPIC_API_KEY=your_claude_api_key
SHIPSTATION_API_KEY=your_shipstation_v2_key
SHIPSTATION_API_SECRET=your_shipstation_secret
TELEGRAM_ALLOWED_USERS=your_user_id
```

### 3. Set Up ShipStation

Enable ShipStation's inventory management (paid add-on required):
1. Go to ShipStation Settings → Inventory
2. Enable inventory tracking
3. Add your SKUs for components and raw materials

### 4. Run Al

```bash
./run_al.sh
# Or manually:
venv/bin/python al/bot.py
```

## Features

### Conversational Interface

Everything is conversational - no commands to remember:

```
You: "Al, I'm low on sapphire lenses"
Al: "I know. Been at 15 for three days. Want to order or wait?"

You: "Wait till Friday, I'm broke"
Al: "Fine. I'll check back Friday. Don't say I didn't warn you."

You: "I want to sell 500 DC2s in December. What do we need?"
Al: [Provides full materials list, lead times, and order-by dates]

You: [Sends screenshot of Alibaba invoice]
Al: "Logged. 200 PTFE gaskets from supplier 'Shenzhen FooBar'.
     Tracking as incoming. When's it arriving?"
```

### Al's Personality

- Gruff but competent (like the real Al from Mertz Manufacturing)
- Gets progressively annoyed if you ignore warnings
- No hand-holding, just facts
- Slightly rude when you're being an idiot
- But he's never wrong about the inventory

**Mood progression example:**
```
Day 1: "Lenses at 15. Reorder point is 20."
Day 3: "Still waiting on those lenses. 10 days till you're out."
Day 5: "Lenses. 6 days left. You gonna order or what?"
Day 7: "You're gonna be sitting on your ass with no lenses in 2 days."
Day 8: "Out of lenses. Hope you enjoyed ignoring me."
```

### Group Chat Support

Al works in a Telegram group with:
- **Pep** (personal assistant bot)
- **Richard** (developer bot)
- **You** (the boss)

**Bot interaction rules:**
- Al only responds when @mentioned or explicitly told to talk
- Pep can ping Al once per day to share info
- No autonomous chatting (keeps API costs down)

## Usage Examples

### Check Inventory Status

```
You: "@al what's the inventory look like?"
Al: "15 sapphire lenses (low), 200 PTFE gaskets (good),
     8 MCR20S drivers (critical), 36" titanium stock (need more)"
```

### Plan a Production Run

```
You: "@al I want to build 100 DC2s next month"
Al: "100 DC2s, 4 weeks out.

Components needed:
- 85x sapphire lens (have 15) - order by Nov 1
- 8x PTFE gasket (have 200) - good
- 92x MCR20S (have 8) - order NOW, 6 week lead time

Raw materials:
- 550" titanium (have 36") - order 520"
- 100" copper (have 12") - order 90"

Machine time: 50 hours (100 × 30min)
With 8% scrap: make 108 units

Critical: MCR20S. Order today or you're screwed."
```

### Log Scrap

```
You: "@al scrapped 3 DC2 bodies, chip mark got stuck"
Al: "Logged. 3 units scrap, tooling issue.
     16.5" titanium and 90min gone.
     Scrap rate this week: 12% (usually 8%)"
```

### Add Vendor from Invoice

```
You: [Sends photo of Alibaba invoice]
Al: "New vendor: Shenzhen Precision Parts Co
     Contact: Li Wei, liwei@example.com
     200x PTFE gasket ordered at $0.45/unit
     When's it arriving?"

You: "2 weeks"
Al: "Logged. Expecting delivery Oct 25. I'll remind you."
```

### Add New Product

```
You: "@al I need to add DC1 to your system"
Al: "Alright. What's the BOM?"

You: "Same as DC2 but 19mm lens instead of 21mm"
Al: "Got it. Manufacturing time?"

You: "25 minutes, 4.5 inches titanium, 1 inch copper"
Al: "DC1 logged. I'll track it."
```

## Technical Details

### Functional Programming Style

Al is built with functional programming principles:
- Pure functions for data transformation
- Side effects isolated at edges (API calls, file I/O)
- Composition over mutation
- Clear data flow

### Type Safety

All functions use Python type hints:

```python
def calculate_bom(
    product: str,
    quantity: int,
    scrap_rate: float = 0.08
) -> dict[str, Any]:
    """Calculate full bill of materials for production run."""
    ...
```

### Testing

Run the test suite:

```bash
venv/bin/pytest tests/ -v
```

All helper functions have unit tests. No untested code.

### Data Storage

Al stores his memory in `AL_MEMORY.md`:
- Product BOMs
- Vendor information
- Lead times
- Manufacturing specs
- Scrap history
- Reorder warnings and snooze states

ShipStation handles actual inventory counts (Al just reads it).

## Development

### Adding New Features

Al is designed to grow. Common additions:

**New product:**
Just tell Al conversationally - he'll ask for BOM and specs.

**New vendor:**
Send Al an invoice screenshot - he extracts and saves it.

**New component:**
Add to ShipStation inventory, Al will automatically track it.

### Code Style

- Follow functional programming patterns from pep
- Type hints on everything
- Docstrings for all public functions
- Unit tests for new helpers
- Commit regularly with clear messages

## Philosophy

Al is modeled after the old-school manufacturing supply chain managers who:
- Know every part number by heart
- Track everything in their heads (but Al uses a database)
- Get annoyed when you waste materials
- Are never wrong about inventory
- Don't sugarcoat anything

Like Pepper Potts keeps Stark Industries running, Al keeps your supply chain from falling apart while you focus on making flashlights.

## License

MIT

---

**"You gonna order those lenses or just keep reading the README?"** - Al
