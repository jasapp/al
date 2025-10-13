"""
Production Helper - Calculate BOMs and plan production runs

When jeff says "I want to build 100 DC2s next month", this module calculates:
- Exact component quantities needed
- Raw material requirements
- Machine time
- When to order based on lead times
- Scrap rate adjustments

Now reads product specs from Notion for up-to-date BOMs.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from al.helpers.notion_helper import NotionHelper

logger = logging.getLogger(__name__)


@dataclass
class Component:
    """A component used in production."""
    name: str
    quantity_per_unit: float
    unit: str = "each"  # "each", "inches", "feet", etc.
    sku: Optional[str] = None


@dataclass
class ProductBOM:
    """Bill of Materials for a product."""
    product_name: str
    components: List[Component]
    machine_time_minutes: float
    scrap_rate: float = 0.08  # Default 8% scrap rate
    notes: Optional[str] = None


@dataclass
class ProductionPlan:
    """Complete production plan with materials, timing, and costs."""
    product_name: str
    target_quantity: int
    adjusted_quantity: int  # Including scrap buffer
    components_needed: List[Dict[str, Any]]
    machine_time_hours: float
    estimated_material_cost: float
    lead_time_warnings: List[str]
    order_by_dates: Dict[str, str]  # component_name -> ISO date string


# Product definitions (hardcoded for now, could move to AL_MEMORY.md)
PRODUCTS: Dict[str, ProductBOM] = {
    "DC2": ProductBOM(
        product_name="DC2",
        components=[
            Component("21mm sapphire lens", 1, "each", "LENS-21MM"),
            Component("21mm PTFE gasket", 1, "each", "GASKET-PTFE-21MM"),
            Component("MCR20S driver", 1, "each", "DRIVER-MCR20S"),
            Component("titanium 1\" round stock", 5.5, "inches", "TITANIUM-1IN"),
            Component("copper 7/8\" C145 stock", 1, "inches", "COPPER-7/8-C145"),
            Component("18650 battery", 1, "each", "BATTERY-18650"),
            Component("tailcap", 1, "each", "TAILCAP-DC2"),
            Component("misc hardware", 1, "kit", "HARDWARE-KIT"),
        ],
        machine_time_minutes=30,
        scrap_rate=0.08,
        notes="DC2 engine assembly has intermittent reliability issues"
    ),
}


# Vendor lead times (days) - could be populated from AL_MEMORY.md
LEAD_TIMES: Dict[str, int] = {
    "MCR20S driver": 42,  # 6 weeks
    "21mm sapphire lens": 21,  # 3 weeks
    "21mm PTFE gasket": 21,  # 3 weeks
    "titanium 1\" round stock": 14,  # 2 weeks
    "copper 7/8\" C145 stock": 14,  # 2 weeks
    "18650 battery": 21,  # 3 weeks
    "tailcap": 14,  # 2 weeks
    "misc hardware": 7,  # 1 week
}


def _load_product_from_notion(product_name: str) -> Optional[ProductBOM]:
    """
    Load product BOM from Notion database.

    Args:
        product_name: Product name (e.g., "DC2")

    Returns:
        ProductBOM if found, None otherwise
    """
    notion = NotionHelper()

    if not notion.is_available:
        logger.warning("Notion unavailable, using hardcoded BOMs")
        return None

    product_data = notion.get_product_from_notion(product_name)

    if not product_data:
        logger.warning(f"Product {product_name} not found in Notion")
        return None

    # Parse components from the rich text field
    # Format: "Materials per unit:\n- Material: X inches\n\nComponents:\n- ..."
    components = []

    # Extract material quantities from components text
    components_text = product_data.get("components", "")

    # Add titanium if specified
    if product_data.get("titanium_inches"):
        # Determine titanium size from components text
        if "1\" Round" in components_text or "1 inch" in components_text.lower():
            titanium_name = "titanium 6Al4V 1\" round stock"
            titanium_sku = "TITANIUM-1IN-6AL4V"
        elif "3/4\" Round" in components_text or "3/4 inch" in components_text.lower():
            titanium_name = "titanium 6Al4V 3/4\" round stock"
            titanium_sku = "TITANIUM-3/4IN-6AL4V"
        else:
            titanium_name = "titanium stock"
            titanium_sku = "TITANIUM"

        components.append(Component(
            titanium_name,
            product_data["titanium_inches"],
            "inches",
            titanium_sku
        ))

    # Add copper if specified
    if product_data.get("copper_inches"):
        components.append(Component(
            "copper C145 7/8\" round stock",
            product_data["copper_inches"],
            "inches",
            "COPPER-7/8-C145"
        ))

    # Add standard components for DC series (these don't change)
    if product_name.startswith("DC"):
        lens_size = "21mm" if product_name == "DC2" else "19mm" if product_name == "DC1" else "TBD"

        components.extend([
            Component(f"{lens_size} sapphire lens", 1, "each", f"LENS-{lens_size.upper()}"),
            Component(f"{lens_size} PTFE gasket", 1, "each", f"GASKET-PTFE-{lens_size.upper()}"),
            Component("MCR20S driver", 1, "each", "DRIVER-MCR20S"),
            Component("18650 battery", 1, "each", "BATTERY-18650"),
            Component(f"tailcap", 1, "each", f"TAILCAP-{product_name}"),
            Component("misc hardware", 1, "kit", "HARDWARE-KIT"),
        ])

    return ProductBOM(
        product_name=product_data["product_name"],
        components=components,
        machine_time_minutes=product_data.get("machine_time_minutes", 30),
        scrap_rate=product_data.get("scrap_rate", 0.08),
        notes=product_data.get("notes"),
    )


def calculate_bom(
    product: str,
    quantity: int,
    scrap_rate: Optional[float] = None,
    current_inventory: Optional[Dict[str, int]] = None
) -> ProductionPlan:
    """
    Calculate full Bill of Materials for a production run.

    Tries to load product specs from Notion first, falls back to hardcoded BOMs.

    Args:
        product: Product name (e.g., "DC2")
        quantity: How many units to build
        scrap_rate: Override default scrap rate (optional)
        current_inventory: Dict of component_name -> quantity_on_hand (optional)

    Returns:
        ProductionPlan with all materials, timing, and warnings

    Raises:
        ValueError: If product not found
    """
    # Try to load from Notion first
    bom = _load_product_from_notion(product)

    # Fall back to hardcoded if Notion fails
    if bom is None:
        if product not in PRODUCTS:
            raise ValueError(f"Unknown product: {product}. Known products: {list(PRODUCTS.keys())}")
        bom = PRODUCTS[product]
        logger.info(f"Using hardcoded BOM for {product}")
    else:
        logger.info(f"Loaded BOM for {product} from Notion")

    scrap = scrap_rate if scrap_rate is not None else bom.scrap_rate

    # Calculate quantity including scrap buffer
    adjusted_qty = int(quantity * (1 + scrap))

    # Calculate components needed
    components_needed = []
    lead_time_warnings = []
    order_by_dates = {}

    for component in bom.components:
        total_needed = component.quantity_per_unit * adjusted_qty
        on_hand = current_inventory.get(component.name, 0) if current_inventory else 0
        need_to_order = max(0, total_needed - on_hand)

        components_needed.append({
            "name": component.name,
            "sku": component.sku,
            "unit": component.unit,
            "quantity_per_unit": component.quantity_per_unit,
            "total_needed": total_needed,
            "on_hand": on_hand,
            "need_to_order": need_to_order,
        })

        # Calculate order-by date based on lead time
        if need_to_order > 0 and component.name in LEAD_TIMES:
            lead_days = LEAD_TIMES[component.name]
            order_by = datetime.now() + timedelta(days=-lead_days)  # How many days ago should have ordered
            order_by_dates[component.name] = order_by.strftime("%Y-%m-%d")

            # Warning if lead time is long
            if lead_days >= 30:
                lead_time_warnings.append(
                    f"{component.name}: {lead_days} day lead time - order ASAP"
                )
            elif lead_days >= 14:
                lead_time_warnings.append(
                    f"{component.name}: {lead_days} day lead time - order soon"
                )

    # Calculate machine time
    total_minutes = bom.machine_time_minutes * adjusted_qty
    machine_hours = total_minutes / 60

    # Rough material cost estimate (could be more sophisticated)
    # For now, just a placeholder
    estimated_cost = 0.0  # TODO: Add material costs to component definitions

    return ProductionPlan(
        product_name=product,
        target_quantity=quantity,
        adjusted_quantity=adjusted_qty,
        components_needed=components_needed,
        machine_time_hours=round(machine_hours, 2),
        estimated_material_cost=estimated_cost,
        lead_time_warnings=lead_time_warnings,
        order_by_dates=order_by_dates,
    )


def format_production_plan(plan: ProductionPlan, target_date: Optional[str] = None) -> str:
    """
    Format production plan as readable text for Al.

    Args:
        plan: ProductionPlan object
        target_date: Optional target completion date (ISO format)

    Returns:
        Human-readable production plan summary
    """
    lines = []

    lines.append(f"**Production Plan: {plan.target_quantity}x {plan.product_name}**\n")

    if target_date:
        lines.append(f"Target date: {target_date}")

    lines.append(f"Build quantity (with {int((plan.adjusted_quantity / plan.target_quantity - 1) * 100)}% scrap buffer): {plan.adjusted_quantity} units")
    lines.append(f"Machine time: {plan.machine_time_hours} hours\n")

    # Components
    lines.append("**Components needed:**")
    for comp in plan.components_needed:
        name = comp["name"]
        total = comp["total_needed"]
        on_hand = comp["on_hand"]
        need = comp["need_to_order"]
        unit = comp["unit"]

        if need > 0:
            lines.append(f"- {name}: need {total:.1f} {unit}, have {on_hand:.1f} → **ORDER {need:.1f} {unit}**")
        else:
            lines.append(f"- {name}: need {total:.1f} {unit}, have {on_hand:.1f} → ✅ good")

    # Lead time warnings
    if plan.lead_time_warnings:
        lines.append("\n**⚠️ LEAD TIME WARNINGS:**")
        for warning in plan.lead_time_warnings:
            lines.append(f"- {warning}")

    # Order by dates
    if plan.order_by_dates:
        lines.append("\n**Order by dates:**")
        for component, date in plan.order_by_dates.items():
            lines.append(f"- {component}: order by {date}")

    return "\n".join(lines)


def get_product_list() -> List[str]:
    """
    Get list of known products.

    Tries Notion first, falls back to hardcoded list.

    Returns:
        List of product names
    """
    notion = NotionHelper()

    if notion.is_available:
        products = notion.get_all_products_from_notion()
        if products:
            product_names = [p["product_name"] for p in products if p.get("product_name")]
            logger.info(f"Loaded {len(product_names)} products from Notion")
            return product_names

    logger.info("Using hardcoded product list")
    return list(PRODUCTS.keys())


def get_product_bom(product: str) -> Optional[ProductBOM]:
    """
    Get BOM for a specific product.

    Tries Notion first, falls back to hardcoded.

    Args:
        product: Product name

    Returns:
        ProductBOM or None if not found
    """
    # Try Notion first
    bom = _load_product_from_notion(product)
    if bom:
        return bom

    # Fall back to hardcoded
    return PRODUCTS.get(product)


def estimate_scrap_for_run(
    product: str,
    quantity: int,
    historical_scrap_rate: Optional[float] = None
) -> int:
    """
    Estimate how many units will be scrapped in a production run.

    Args:
        product: Product name
        quantity: Target quantity
        historical_scrap_rate: Override default scrap rate (optional)

    Returns:
        Estimated number of scrapped units
    """
    if product not in PRODUCTS:
        raise ValueError(f"Unknown product: {product}")

    scrap_rate = historical_scrap_rate if historical_scrap_rate is not None else PRODUCTS[product].scrap_rate
    return int(quantity * scrap_rate)
