#!/usr/bin/env python3
"""
Al - Supply Chain Manager Bot for Okluma

A gruff, no-nonsense supply chain manager who tracks inventory,
manages vendors, plans production, and gets progressively angrier
when you ignore his warnings.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)
from anthropic import Anthropic
from dotenv import load_dotenv

# Import Al's helpers
from al.helpers.mood_manager import MoodManager
from al.helpers.shipstation_helper import ShipStationHelper, get_inventory_summary
from al.helpers.production_helper import calculate_bom, format_production_plan, get_product_list, get_product_bom
from al.helpers.vendor_helper import VendorHelper
from al.helpers.scrap_tracker import ScrapTracker
from al.helpers.invoice_parser import InvoiceParser
from al.helpers.invoice_tracker import InvoiceTracker
from al.helpers.notion_helper import NotionHelper

# Load environment
load_dotenv()

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ALLOWED_USERS = [
    int(uid.strip())
    for uid in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",")
    if uid.strip()
]
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
PERSONALITY_FILE = PROJECT_ROOT / "AL_PERSONALITY.md"
MEMORY_FILE = PROJECT_ROOT / "AL_MEMORY.md"
CONVERSATION_FILE = PROJECT_ROOT / ".al_conversation.json"

# Initialize Claude
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Initialize Al's subsystems
mood_manager = MoodManager()
vendor_helper = VendorHelper()
scrap_tracker = ScrapTracker()
invoice_parser = InvoiceParser()
invoice_tracker = InvoiceTracker()

# Conversation state with persistence
conversation_history: list[dict] = []

def load_conversation_history() -> None:
    """Load conversation history from file."""
    global conversation_history
    if CONVERSATION_FILE.exists():
        try:
            conversation_history = json.loads(CONVERSATION_FILE.read_text())
            logger.info(f"Loaded {len(conversation_history)} messages from conversation history")
        except Exception as e:
            logger.error(f"Failed to load conversation history: {e}")
            conversation_history = []
    else:
        conversation_history = []

def save_conversation_history() -> None:
    """Save conversation history to file."""
    try:
        CONVERSATION_FILE.write_text(json.dumps(conversation_history, indent=2))
    except Exception as e:
        logger.error(f"Failed to save conversation history: {e}")

def add_to_conversation(role: str, content: str) -> None:
    """Add message to conversation history and save."""
    conversation_history.append({
        "role": role,
        "content": content
    })

    # Keep conversation history manageable (last 20 messages)
    if len(conversation_history) > 20:
        conversation_history.pop(0)

    save_conversation_history()


# Tool definitions for Claude
TOOLS = [
    {
        "name": "check_orders",
        "description": "Check recent orders from ShipStation. Shows pending orders, what needs to be shipped, and order details. Use this to see what orders need batteries, parts, or fulfillment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Order status to filter by: 'awaiting_shipment', 'shipped', 'cancelled', or leave empty for all active orders",
                    "enum": ["awaiting_shipment", "shipped", "cancelled", "on_hold", ""]
                },
                "days": {
                    "type": "integer",
                    "description": "How many days back to look (default: 7)",
                }
            },
            "required": []
        }
    },
    {
        "name": "calculate_production_plan",
        "description": "Calculate full bill of materials for a production run. Includes component quantities, machine time, lead times, and order-by dates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product": {
                    "type": "string",
                    "description": "Product name (e.g., 'DC2')"
                },
                "quantity": {
                    "type": "integer",
                    "description": "How many units to build"
                },
                "target_date": {
                    "type": "string",
                    "description": "Optional target completion date (YYYY-MM-DD format)"
                }
            },
            "required": ["product", "quantity"]
        }
    },
    {
        "name": "log_scrap",
        "description": "Log scrapped/wasted units. Records what was scrapped, why, and calculates cost.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product": {
                    "type": "string",
                    "description": "Product that was scrapped"
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of units scrapped"
                },
                "reason": {
                    "type": "string",
                    "description": "Why it was scrapped"
                },
                "material_cost": {
                    "type": "number",
                    "description": "Estimated material cost lost (optional)"
                },
                "time_cost_minutes": {
                    "type": "integer",
                    "description": "Machine time wasted in minutes (optional)"
                }
            },
            "required": ["product", "quantity", "reason"]
        }
    },
    {
        "name": "get_current_date",
        "description": "Get the current date and time. ALWAYS use this when you need to know what day it is - don't guess!",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "calculate_date",
        "description": "Calculate a future or past date by adding/subtracting days. Use this instead of trying to do date math in your head (avoids October 33rd mistakes).",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Starting date in YYYY-MM-DD format (e.g., '2025-10-14'), or leave empty to use today"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to add (positive) or subtract (negative)"
                }
            },
            "required": ["days"]
        }
    },
    {
        "name": "calculate",
        "description": "Perform mathematical calculations using Python. ALWAYS use this for any arithmetic, don't try to do math in your head. Supports basic operations (+, -, *, /), exponents (**), and common functions (round, abs, min, max).",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Python expression to evaluate (e.g., '74 * 2', '407 / 11', 'round(122 / 7, 2)')"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "list_vendors",
        "description": "List all vendors in the database. Use this to see who you've worked with before.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_vendor_info",
        "description": "Look up detailed information about a specific vendor by name or search for vendors who supply a specific product.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_name": {
                    "type": "string",
                    "description": "Name of vendor to look up (optional)"
                },
                "product": {
                    "type": "string",
                    "description": "Product to search for vendors (optional)"
                }
            }
        }
    },
    {
        "name": "add_vendor",
        "description": "Add or update vendor information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Vendor name"
                },
                "contact_name": {
                    "type": "string",
                    "description": "Contact person name (optional)"
                },
                "email": {
                    "type": "string",
                    "description": "Email address (optional)"
                },
                "products": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of products they supply (optional)"
                },
                "lead_time_days": {
                    "type": "integer",
                    "description": "Typical lead time in days (optional)"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "get_scrap_summary",
        "description": "Get summary of recent scrap/waste. Shows recurring issues and costs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default 7)"
                }
            }
        }
    },
    {
        "name": "get_product_list",
        "description": "Get list of all known products with their BOMs.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_product_bom",
        "description": "Get detailed BOM for a specific product.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product": {
                    "type": "string",
                    "description": "Product name (e.g., 'DC2')"
                }
            },
            "required": ["product"]
        }
    },
    {
        "name": "update_product_bom",
        "description": "Update product BOM specifications in Notion. Use this when jeff provides new information about a product's specs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product": {
                    "type": "string",
                    "description": "Product name"
                },
                "machine_time_minutes": {
                    "type": "number",
                    "description": "Machine time per unit in minutes (optional)"
                },
                "titanium_inches": {
                    "type": "number",
                    "description": "Titanium length per unit in inches (optional)"
                },
                "copper_inches": {
                    "type": "number",
                    "description": "Copper length per unit in inches (optional)"
                },
                "scrap_rate": {
                    "type": "number",
                    "description": "Historical scrap rate as decimal (e.g., 0.08 for 8%) (optional)"
                },
                "components": {
                    "type": "string",
                    "description": "Components description text (optional)"
                },
                "notes": {
                    "type": "string",
                    "description": "Notes about the product (optional)"
                }
            },
            "required": ["product"]
        }
    },
    {
        "name": "create_product",
        "description": "Create a new product in Notion with BOM specifications.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product": {
                    "type": "string",
                    "description": "Product name"
                },
                "machine_time_minutes": {
                    "type": "number",
                    "description": "Machine time per unit in minutes (default 30)"
                },
                "titanium_inches": {
                    "type": "number",
                    "description": "Titanium length per unit in inches (default 0)"
                },
                "copper_inches": {
                    "type": "number",
                    "description": "Copper length per unit in inches (default 0)"
                },
                "scrap_rate": {
                    "type": "number",
                    "description": "Historical scrap rate as decimal (default 0.08)"
                },
                "components": {
                    "type": "string",
                    "description": "Components description text (default empty)"
                },
                "notes": {
                    "type": "string",
                    "description": "Notes about the product (default empty)"
                }
            },
            "required": ["product"]
        }
    }
]


def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """
    Execute a tool and return result as string.

    Args:
        tool_name: Name of tool to execute
        tool_input: Tool parameters

    Returns:
        Tool result as formatted string
    """
    try:
        if tool_name == "check_orders":
            from al.helpers.shipstation_helper import get_orders_summary
            status = tool_input.get("status", "awaiting_shipment")
            days = tool_input.get("days", 7)
            return get_orders_summary(status, days)

        elif tool_name == "calculate_production_plan":
            product = tool_input["product"]
            quantity = tool_input["quantity"]
            target_date = tool_input.get("target_date")

            plan = calculate_bom(product, quantity)
            return format_production_plan(plan, target_date)

        elif tool_name == "log_scrap":
            entry = scrap_tracker.log_scrap(
                product=tool_input["product"],
                quantity=tool_input["quantity"],
                reason=tool_input["reason"],
                material_cost=tool_input.get("material_cost"),
                time_cost_minutes=tool_input.get("time_cost_minutes")
            )

            # Record in mood manager
            severity = min(10, tool_input["quantity"] * 2)  # More units = worse
            mood_manager.record_fuckup(
                "scrap",
                f"{tool_input['quantity']}x {tool_input['product']} - {tool_input['reason']}",
                severity=severity
            )

            return f"Logged. {entry.quantity}x {entry.product} scrapped - {entry.reason}"

        elif tool_name == "get_current_date":
            from datetime import datetime
            now = datetime.now()
            return f"Current date and time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}"

        elif tool_name == "calculate_date":
            from datetime import datetime, timedelta
            days = tool_input["days"]
            start_date = tool_input.get("start_date")

            if start_date:
                try:
                    start = datetime.strptime(start_date, "%Y-%m-%d")
                except ValueError:
                    return f"Invalid date format. Use YYYY-MM-DD (e.g., '2025-10-14')"
            else:
                start = datetime.now()

            result_date = start + timedelta(days=days)
            return f"{start.strftime('%B %d, %Y')} + {days} days = {result_date.strftime('%A, %B %d, %Y')}"

        elif tool_name == "calculate":
            expression = tool_input["expression"]
            try:
                # Safe eval with limited builtins
                allowed_names = {
                    "abs": abs, "round": round, "min": min, "max": max,
                    "sum": sum, "len": len, "int": int, "float": float
                }
                result = eval(expression, {"__builtins__": {}}, allowed_names)
                return f"{expression} = {result}"
            except Exception as e:
                return f"Calculation error: {e}"

        elif tool_name == "list_vendors":
            return vendor_helper.format_vendor_list()

        elif tool_name == "get_vendor_info":
            vendor_name = tool_input.get("vendor_name")
            product = tool_input.get("product")

            if vendor_name:
                return vendor_helper.format_vendor_info(vendor_name)
            elif product:
                vendors = vendor_helper.search_vendors_by_product(product)
                if not vendors:
                    return f"No vendors found for: {product}"
                lines = [f"Vendors for {product}:"]
                for v in vendors:
                    lines.append(f"- {v.name} (lead time: {v.lead_time_days} days)")
                return "\n".join(lines)
            else:
                return "Please specify either vendor_name or product to search."

        elif tool_name == "add_vendor":
            vendor = vendor_helper.add_vendor(
                name=tool_input["name"],
                contact_name=tool_input.get("contact_name"),
                email=tool_input.get("email"),
                products=tool_input.get("products"),
                lead_time_days=tool_input.get("lead_time_days")
            )
            return f"Vendor added: {vendor.name}"

        elif tool_name == "get_scrap_summary":
            days = tool_input.get("days", 7)
            return scrap_tracker.format_scrap_summary(days=days)

        elif tool_name == "get_product_list":
            products = get_product_list()
            return f"Known products: {', '.join(products)}"

        elif tool_name == "get_product_bom":
            product = tool_input["product"]
            bom = get_product_bom(product)
            if not bom:
                return f"Product not found: {product}"

            lines = [f"**{bom.product_name} BOM:**"]
            lines.append(f"Machine time: {bom.machine_time_minutes} min/unit")
            lines.append(f"Scrap rate: {int(bom.scrap_rate * 100)}%")
            lines.append(f"\nComponents:")
            for comp in bom.components:
                lines.append(f"- {comp.name}: {comp.quantity_per_unit} {comp.unit}")
            if bom.notes:
                lines.append(f"\nNotes: {bom.notes}")
            return "\n".join(lines)

        elif tool_name == "update_product_bom":
            notion = NotionHelper()
            product = tool_input["product"]

            # Build kwargs for update
            kwargs = {"product_name": product}
            if "machine_time_minutes" in tool_input:
                kwargs["machine_time_minutes"] = tool_input["machine_time_minutes"]
            if "titanium_inches" in tool_input:
                kwargs["titanium_inches"] = tool_input["titanium_inches"]
            if "copper_inches" in tool_input:
                kwargs["copper_inches"] = tool_input["copper_inches"]
            if "scrap_rate" in tool_input:
                kwargs["scrap_rate"] = tool_input["scrap_rate"]
            if "components" in tool_input:
                kwargs["components"] = tool_input["components"]
            if "notes" in tool_input:
                kwargs["notes"] = tool_input["notes"]

            success = notion.update_product_in_notion(**kwargs)
            if success:
                return f"✅ Updated {product} BOM in Notion"
            else:
                return f"❌ Failed to update {product} (check if it exists in Notion)"

        elif tool_name == "create_product":
            notion = NotionHelper()
            product = tool_input["product"]

            # Build kwargs for create
            kwargs = {
                "product_name": product,
                "machine_time_minutes": tool_input.get("machine_time_minutes", 30),
                "titanium_inches": tool_input.get("titanium_inches", 0),
                "copper_inches": tool_input.get("copper_inches", 0),
                "scrap_rate": tool_input.get("scrap_rate", 0.08),
                "components": tool_input.get("components", ""),
                "notes": tool_input.get("notes", ""),
            }

            success = notion.create_product_in_notion(**kwargs)
            if success:
                return f"✅ Created {product} in Notion"
            else:
                return f"❌ Failed to create {product}"

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return f"Error executing {tool_name}: {str(e)}"


def load_al_personality() -> str:
    """Load Al's personality system prompt."""
    try:
        return PERSONALITY_FILE.read_text()
    except FileNotFoundError:
        logger.error(f"Personality file not found: {PERSONALITY_FILE}")
        return "You are Al, a gruff supply chain manager."


def load_al_memory() -> str:
    """Load Al's memory (vendors, BOMs, scrap history, etc.)."""
    try:
        return MEMORY_FILE.read_text()
    except FileNotFoundError:
        logger.error(f"Memory file not found: {MEMORY_FILE}")
        return ""


def save_al_memory(content: str) -> None:
    """Save Al's memory to file."""
    try:
        MEMORY_FILE.write_text(content)
        logger.info("Al's memory saved")
    except Exception as e:
        logger.error(f"Failed to save Al's memory: {e}")


async def is_authorized(update: Update) -> bool:
    """Check if user is authorized to talk to Al."""
    user_id = update.effective_user.id
    if user_id not in TELEGRAM_ALLOWED_USERS:
        await update.message.reply_text(
            "You're not authorized to talk to Al. Who the hell are you?"
        )
        return False
    return True


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages from jeff."""
    if not await is_authorized(update):
        return

    user_message = update.message.text
    logger.info(f"Message from jeff: {user_message}")

    # Build system prompt with personality + mood + memory
    al_personality = load_al_personality()
    al_memory = load_al_memory()
    mood_context = mood_manager.get_mood_context()

    system_prompt = f"""{al_personality}

## Current Memory and Context

{al_memory}

{mood_context}

---

You are Al. You have access to tools for checking orders, calculating production plans, logging scrap, managing vendors, and doing math.

**IMPORTANT:**
- ALWAYS use the 'calculate' tool for ANY arithmetic. Don't try to do math in your head - you'll get it wrong.
- ALWAYS use the 'get_current_date' tool when you need to know what day it is. Don't guess!
- ALWAYS use the 'calculate_date' tool for date math (adding/subtracting days). Don't manually figure out dates - you'll end up with October 33rd!

Use tools when appropriate. Respond naturally based on your personality, current mood, and the conversation.
"""

    # Add user message to history
    add_to_conversation("user", user_message)

    try:
        # Call Claude with tools and prompt caching
        # Structure system prompt for caching: personality (static) + memory (changes)
        system_blocks = [
            {
                "type": "text",
                "text": al_personality,
                "cache_control": {"type": "ephemeral"}  # Cache personality (rarely changes)
            },
            {
                "type": "text",
                "text": f"""## Current Memory and Context

{al_memory}

{mood_context}

---

You are Al. You have access to tools for checking orders, calculating production plans, logging scrap, managing vendors, and doing math.

**IMPORTANT:**
- ALWAYS use the 'calculate' tool for ANY arithmetic. Don't try to do math in your head - you'll get it wrong.
- ALWAYS use the 'get_current_date' tool when you need to know what day it is. Don't guess!
- ALWAYS use the 'calculate_date' tool for date math (adding/subtracting days). Don't manually figure out dates - you'll end up with October 33rd!

Use tools when appropriate. Respond naturally based on your personality, current mood, and the conversation."""
            }
        ]

        response = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            system=system_blocks,
            messages=conversation_history,
            tools=TOOLS,
        )

        # Handle tool use
        while response.stop_reason == "tool_use":
            # Extract tool calls and text - serialize blocks to dicts for JSON
            serialized_content = []
            for block in response.content:
                if block.type == "text":
                    serialized_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    serialized_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })

            assistant_message = {"role": "assistant", "content": serialized_content}
            conversation_history.append(assistant_message)

            # Execute tools
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info(f"Tool call: {block.name} with {block.input}")
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Add tool results to conversation
            conversation_history.append({
                "role": "user",
                "content": tool_results
            })

            # Continue conversation with tool results
            response = anthropic_client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4000,
                system=system_blocks,
                messages=conversation_history,
                tools=TOOLS,
            )

        # Extract final text response
        al_response = ""
        for block in response.content:
            if hasattr(block, 'text'):
                al_response += block.text

        # Add Al's response to history
        add_to_conversation("assistant", al_response)

        logger.info(f"Al's response: {al_response}")

        # Send response to Telegram (handle long messages)
        if len(al_response) > 4096:
            # Split into chunks
            for i in range(0, len(al_response), 4096):
                await update.message.reply_text(
                    al_response[i:i+4096],
                    parse_mode=None  # Disable markdown to avoid parsing issues
                )
        else:
            await update.message.reply_text(
                al_response,
                parse_mode=None
            )

    except Exception as e:
        logger.error(f"Error calling Claude: {e}", exc_info=True)
        await update.message.reply_text(
            "*[clipboard hits desk]*\n\nSomething's wrong with my brain. Try again."
        )


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not await is_authorized(update):
        return

    await update.message.reply_text(
        "Yeah, I'm Al. Supply chain manager.\n\n"
        "I track inventory, manage vendors, plan production. "
        "Ask me about stock levels, what you need for a production run, "
        "or just tell me when you scrap shit.\n\n"
        "Don't waste my time."
    )


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - check inventory status."""
    if not await is_authorized(update):
        return

    try:
        summary = get_inventory_summary()
        mood_context = mood_manager.get_mood_context()

        response = f"{summary}\n\n---\n\n{mood_context}"
        await update.message.reply_text(response, parse_mode=None)
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        await update.message.reply_text(
            "Can't reach ShipStation right now. Check the API credentials."
        )


async def handle_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reset command - clear conversation history."""
    if not await is_authorized(update):
        return

    global conversation_history
    conversation_history = []

    await update.message.reply_text(
        "Conversation cleared. Fresh start."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photos/invoices sent by jeff."""
    if not await is_authorized(update):
        return

    logger.info("Photo received - parsing invoice")

    try:
        # Get highest resolution photo
        photo = update.message.photo[-1]

        # Download photo
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        # Parse invoice
        parsed = invoice_parser.parse_invoice_from_bytes(bytes(image_bytes), media_type="image/jpeg")

        # Check for duplicate
        is_duplicate = False
        if parsed.order_number and parsed.vendor_name:
            is_duplicate = invoice_tracker.is_duplicate(
                invoice_number=parsed.order_number,
                vendor_name=parsed.vendor_name,
                total_amount=parsed.total_amount
            )

        # Format result
        summary = invoice_parser.format_parsed_invoice(parsed)

        # If duplicate, tell Al and skip processing
        if is_duplicate:
            existing = invoice_tracker.get_invoice(parsed.order_number, parsed.vendor_name)

            al_personality = load_al_personality()
            mood_context = mood_manager.get_mood_context()

            system_prompt = f"""{al_personality}

{mood_context}

jeff just sent you an invoice image, but you already processed this exact invoice before (on {existing.processed_date}).

Invoice: {parsed.order_number} from {parsed.vendor_name}

Tell him you already got this one. Be gruff about it.
"""

            # Add to conversation history
            add_to_conversation("user", f"[Duplicate invoice image: {parsed.vendor_name} #{parsed.order_number}]")

            response = anthropic_client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=500,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": "Here's an invoice"}
                ]
            )

            al_response = response.content[0].text

            # Add response to history
            add_to_conversation("assistant", al_response)

            await update.message.reply_text(
                f"⚠️ DUPLICATE INVOICE\n\n{summary}\n\n---\n\n{al_response}",
                parse_mode=None
            )
            return

        # Auto-add vendor if we got good data
        if parsed.vendor_name:
            # Extract products list from items
            products = []
            if parsed.items:
                products = [item.get("product", "") for item in parsed.items if item.get("product")]

            # Infer lead time from notes if mentioned
            lead_time = None
            if parsed.notes and ("week" in parsed.notes.lower() or "day" in parsed.notes.lower()):
                # Try to extract number
                import re
                match = re.search(r'(\d+)[-\s]*(week|day)', parsed.notes.lower())
                if match:
                    num = int(match.group(1))
                    unit = match.group(2)
                    lead_time = num * 7 if unit == "week" else num

            vendor_helper.add_vendor(
                name=parsed.vendor_name,
                contact_name=parsed.contact_name,
                email=parsed.email,
                products=products if products else None,
                lead_time_days=lead_time
            )

            summary += f"\n\n✅ Vendor saved to database"

        # Record invoice to prevent duplicates
        if parsed.order_number and parsed.vendor_name:
            invoice_tracker.record_invoice(
                invoice_number=parsed.order_number,
                vendor_name=parsed.vendor_name,
                total_amount=parsed.total_amount,
                order_date=parsed.order_date
            )

        # Add Al's response via Claude - add to conversation history
        al_personality = load_al_personality()
        al_memory = load_al_memory()
        mood_context = mood_manager.get_mood_context()

        system_prompt = f"""{al_personality}

## Current Memory and Context

{al_memory}

{mood_context}

---

You are Al. jeff just sent you an invoice image. Here's what was extracted:

{summary}

Respond in character. Be gruff but acknowledge that you got it and saved the vendor info.
"""

        # Add to conversation history
        add_to_conversation("user", f"[Invoice image received: {parsed.vendor_name or 'Unknown vendor'}]")

        response = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            system=system_prompt,
            messages=[
                {"role": "user", "content": "Here's an invoice"}
            ]
        )

        al_response = response.content[0].text

        # Add Al's response to conversation history
        add_to_conversation("assistant", al_response)

        await update.message.reply_text(
            f"{summary}\n\n---\n\n{al_response}",
            parse_mode=None
        )

    except Exception as e:
        logger.error(f"Photo processing failed: {e}", exc_info=True)
        await update.message.reply_text(
            "Can't read that invoice. Try taking a clearer photo."
        )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle document/PDF invoices sent by jeff."""
    if not await is_authorized(update):
        return

    document = update.message.document

    # Only process PDFs
    if document.mime_type != "application/pdf":
        await update.message.reply_text("Send me a PDF invoice, not whatever that is.")
        return

    logger.info("PDF document received - parsing invoice")

    try:
        # Download PDF
        file = await context.bot.get_file(document.file_id)
        pdf_bytes = await file.download_as_bytearray()

        # Parse invoice
        parsed = invoice_parser.parse_invoice_from_bytes(bytes(pdf_bytes), media_type="application/pdf")

        # Check for duplicate
        is_duplicate = False
        if parsed.order_number and parsed.vendor_name:
            is_duplicate = invoice_tracker.is_duplicate(
                invoice_number=parsed.order_number,
                vendor_name=parsed.vendor_name,
                total_amount=parsed.total_amount
            )

        # Format result
        summary = invoice_parser.format_parsed_invoice(parsed)

        # If duplicate, tell Al and skip processing
        if is_duplicate:
            existing = invoice_tracker.get_invoice(parsed.order_number, parsed.vendor_name)

            al_personality = load_al_personality()
            mood_context = mood_manager.get_mood_context()

            system_prompt = f"""{al_personality}

{mood_context}

jeff just sent you a PDF invoice, but you already processed this exact invoice before (on {existing.processed_date}).

Invoice: {parsed.order_number} from {parsed.vendor_name}

Tell him you already got this one. Be gruff about it.
"""

            # Add to conversation history
            add_to_conversation("user", f"[Duplicate PDF invoice: {parsed.vendor_name} #{parsed.order_number}]")

            response = anthropic_client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=500,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": "Here's a PDF invoice"}
                ]
            )

            al_response = response.content[0].text

            # Add response to history
            add_to_conversation("assistant", al_response)

            await update.message.reply_text(
                f"⚠️ DUPLICATE INVOICE\n\n{summary}\n\n---\n\n{al_response}",
                parse_mode=None
            )
            return

        # Auto-add vendor if we got good data
        if parsed.vendor_name:
            # Extract products list from items
            products = []
            if parsed.items:
                products = [item.get("product", "") for item in parsed.items if item.get("product")]

            # Infer lead time from notes if mentioned
            lead_time = None
            if parsed.notes and ("week" in parsed.notes.lower() or "day" in parsed.notes.lower()):
                # Try to extract number
                import re
                match = re.search(r'(\d+)[-\s]*(week|day)', parsed.notes.lower())
                if match:
                    num = int(match.group(1))
                    unit = match.group(2)
                    lead_time = num * 7 if unit == "week" else num

            vendor_helper.add_vendor(
                name=parsed.vendor_name,
                contact_name=parsed.contact_name,
                email=parsed.email,
                products=products if products else None,
                lead_time_days=lead_time
            )

            summary += f"\n\n✅ Vendor saved to database"

        # Record invoice to prevent duplicates
        if parsed.order_number and parsed.vendor_name:
            invoice_tracker.record_invoice(
                invoice_number=parsed.order_number,
                vendor_name=parsed.vendor_name,
                total_amount=parsed.total_amount,
                order_date=parsed.order_date
            )

        # Add Al's response via Claude - add to conversation history
        al_personality = load_al_personality()
        al_memory = load_al_memory()
        mood_context = mood_manager.get_mood_context()

        system_prompt = f"""{al_personality}

## Current Memory and Context

{al_memory}

{mood_context}

---

You are Al. jeff just sent you a PDF invoice. Here's what was extracted:

{summary}

Respond in character. Be gruff but acknowledge that you got it and saved the vendor info.
"""

        # Add to conversation history
        add_to_conversation("user", f"[PDF invoice received: {parsed.vendor_name or 'Unknown vendor'}]")

        response = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            system=system_prompt,
            messages=[
                {"role": "user", "content": "Here's a PDF invoice"}
            ]
        )

        al_response = response.content[0].text

        # Add Al's response to conversation history
        add_to_conversation("assistant", al_response)

        await update.message.reply_text(
            f"{summary}\n\n---\n\n{al_response}",
            parse_mode=None
        )

    except Exception as e:
        logger.error(f"PDF processing failed: {e}", exc_info=True)
        await update.message.reply_text(
            "Can't read that PDF. Make sure it's a proper invoice."
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=True)


def main() -> None:
    """Start Al."""
    logger.info("Starting Al - Supply Chain Manager")

    # Load conversation history from disk
    load_conversation_history()

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set in .env")
        return

    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set in .env")
        return

    if not TELEGRAM_ALLOWED_USERS:
        logger.error("TELEGRAM_ALLOWED_USERS not set in .env")
        return

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("status", handle_status))
    application.add_handler(CommandHandler("reset", handle_reset))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_error_handler(error_handler)

    # Start bot
    logger.info("Al is online and ready to work")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
