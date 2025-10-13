"""
Scrap Tracker - Log manufacturing waste and track patterns

When jeff scraps parts, Al needs to know:
- What was scrapped and how much
- Why it was scrapped
- Material and time costs
- Whether scrap rates are trending up

This helps Al warn about recurring problems and adjust production planning.
Stores data in Notion for visibility, falls back to JSON if Notion is offline.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging
from al.helpers.notion_helper import NotionHelper

logger = logging.getLogger(__name__)


@dataclass
class ScrapEntry:
    """A single scrap event."""
    timestamp: str  # ISO format
    product: str
    quantity: int
    reason: str
    material_cost: Optional[float] = None
    time_cost_minutes: Optional[int] = None
    materials_lost: Optional[Dict[str, float]] = None  # material -> quantity
    notes: Optional[str] = None

    def __post_init__(self):
        """Initialize mutable defaults."""
        if self.materials_lost is None:
            self.materials_lost = {}


class ScrapTracker:
    """
    Track manufacturing waste and analyze patterns.

    Stores scrap history in Notion for visibility, falls back to JSON if Notion is offline.
    """

    def __init__(self, scrap_file: Optional[Path] = None, notion_helper: Optional[NotionHelper] = None):
        """
        Initialize scrap tracker.

        Args:
            scrap_file: Path to scrap history JSON file (fallback storage)
            notion_helper: NotionHelper instance (optional, will create if not provided)
        """
        self.scrap_file = scrap_file or Path(__file__).parent.parent.parent / ".al_scrap_history.json"
        self.notion = notion_helper or NotionHelper()
        self.scrap_history: List[ScrapEntry] = self._load_history()

    def _load_history(self, days: int = 30) -> List[ScrapEntry]:
        """
        Load scrap history from Notion first, fallback to JSON.

        Args:
            days: Number of days of history to load

        Returns:
            List of ScrapEntry objects
        """
        # Try Notion first
        if self.notion.is_available:
            notion_scrap = self.notion.get_scrap_history_from_notion(days=days)
            if notion_scrap is not None:
                logger.info(f"Loaded {len(notion_scrap)} scrap entries from Notion")
                return [ScrapEntry(**entry) for entry in notion_scrap]

        # Fallback to local JSON
        if self.scrap_file.exists():
            try:
                data = json.loads(self.scrap_file.read_text())
                logger.info(f"Loaded {len(data)} scrap entries from local JSON (Notion unavailable)")
                return [ScrapEntry(**entry) for entry in data]
            except Exception as e:
                logger.error(f"Failed to load scrap history from JSON: {e}")

        return []

    def _save_history(self) -> None:
        """Save scrap history to JSON (fallback only)."""
        try:
            data = [asdict(entry) for entry in self.scrap_history]
            self.scrap_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save scrap history to JSON: {e}")

    def log_scrap(
        self,
        product: str,
        quantity: int,
        reason: str,
        material_cost: Optional[float] = None,
        time_cost_minutes: Optional[int] = None,
        materials_lost: Optional[Dict[str, float]] = None,
        notes: Optional[str] = None
    ) -> ScrapEntry:
        """
        Log a scrap event.

        Saves to Notion first, falls back to JSON if Notion unavailable.

        Args:
            product: Product that was scrapped
            quantity: Number of units scrapped
            reason: Why it was scrapped
            material_cost: Estimated material cost lost
            time_cost_minutes: Machine time wasted
            materials_lost: Dict of material -> quantity lost
            notes: Additional notes

        Returns:
            ScrapEntry object
        """
        timestamp = datetime.now()

        entry = ScrapEntry(
            timestamp=timestamp.isoformat(),
            product=product,
            quantity=quantity,
            reason=reason,
            material_cost=material_cost,
            time_cost_minutes=time_cost_minutes,
            materials_lost=materials_lost or {},
            notes=notes
        )

        # Try to save to Notion first
        saved_to_notion = self.notion.add_scrap_to_notion(
            product=product,
            quantity=quantity,
            reason=reason,
            material_cost=material_cost,
            time_cost_minutes=time_cost_minutes,
            materials_lost=materials_lost,
            timestamp=timestamp
        )

        if saved_to_notion:
            logger.info(f"Scrap entry for {quantity}x {product} saved to Notion")
        else:
            logger.warning(f"Scrap entry saved to local JSON only (Notion unavailable)")

        # Always save to local JSON as backup
        self.scrap_history.append(entry)
        self._save_history()

        return entry

    def get_recent_scrap(self, days: int = 7) -> List[ScrapEntry]:
        """
        Get scrap entries from last N days.

        Args:
            days: Number of days to look back

        Returns:
            List of recent scrap entries
        """
        cutoff = datetime.now() - timedelta(days=days)

        recent = []
        for entry in self.scrap_history:
            entry_time = datetime.fromisoformat(entry.timestamp)
            if entry_time >= cutoff:
                recent.append(entry)

        return recent

    def get_scrap_by_product(self, product: str, days: Optional[int] = None) -> List[ScrapEntry]:
        """
        Get scrap entries for specific product.

        Args:
            product: Product name
            days: Optional number of days to look back

        Returns:
            List of scrap entries for that product
        """
        entries = self.scrap_history

        if days:
            cutoff = datetime.now() - timedelta(days=days)
            entries = [e for e in entries if datetime.fromisoformat(e.timestamp) >= cutoff]

        return [e for e in entries if e.product.lower() == product.lower()]

    def calculate_scrap_rate(self, product: str, days: int = 30) -> Optional[float]:
        """
        Calculate scrap rate for product over time period.

        Note: This is a simplified calculation. In reality, you'd need to know
        total units produced to get an accurate rate. This just gives a rough idea.

        Args:
            product: Product name
            days: Days to analyze

        Returns:
            Average scrap rate (units per day) or None if no data
        """
        scrap_entries = self.get_scrap_by_product(product, days=days)

        if not scrap_entries:
            return None

        total_scrapped = sum(e.quantity for e in scrap_entries)
        return total_scrapped / days

    def get_scrap_reasons(self, product: Optional[str] = None, days: int = 30) -> Dict[str, int]:
        """
        Get breakdown of scrap reasons.

        Args:
            product: Optional product filter
            days: Days to analyze

        Returns:
            Dict of reason -> count
        """
        recent = self.get_recent_scrap(days=days)

        if product:
            recent = [e for e in recent if e.product.lower() == product.lower()]

        reasons: Dict[str, int] = {}
        for entry in recent:
            reason = entry.reason
            reasons[reason] = reasons.get(reason, 0) + entry.quantity

        return reasons

    def calculate_total_waste(self, days: int = 30) -> Dict[str, Any]:
        """
        Calculate total waste over period.

        Args:
            days: Days to analyze

        Returns:
            Dict with total_units, total_cost, total_time
        """
        recent = self.get_recent_scrap(days=days)

        total_units = sum(e.quantity for e in recent)
        total_cost = sum(e.material_cost for e in recent if e.material_cost)
        total_time = sum(e.time_cost_minutes for e in recent if e.time_cost_minutes)

        return {
            "total_units": total_units,
            "total_cost": total_cost,
            "total_time_minutes": total_time,
            "total_time_hours": round(total_time / 60, 2) if total_time else 0,
        }

    def detect_recurring_issues(self, threshold: int = 3, days: int = 30) -> List[str]:
        """
        Detect recurring scrap reasons.

        Args:
            threshold: Minimum occurrences to flag as recurring
            days: Days to analyze

        Returns:
            List of recurring issue descriptions
        """
        reasons = self.get_scrap_reasons(days=days)

        recurring = []
        for reason, count in reasons.items():
            if count >= threshold:
                recurring.append(f"{reason} ({count} times)")

        return recurring

    def format_scrap_summary(self, days: int = 7) -> str:
        """
        Format scrap summary as readable text.

        Args:
            days: Days to summarize

        Returns:
            Human-readable scrap summary
        """
        recent = self.get_recent_scrap(days=days)

        if not recent:
            return f"No scrap in the last {days} days."

        waste = self.calculate_total_waste(days=days)
        reasons = self.get_scrap_reasons(days=days)

        lines = [f"**Scrap Summary (last {days} days):**\n"]

        lines.append(f"Total units scrapped: {waste['total_units']}")

        if waste['total_cost']:
            lines.append(f"Material cost: ${waste['total_cost']:.2f}")

        if waste['total_time_hours']:
            lines.append(f"Time wasted: {waste['total_time_hours']} hours")

        lines.append("\n**Reasons:**")
        for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {reason}: {count} units")

        # Check for recurring issues
        recurring = self.detect_recurring_issues(threshold=3, days=days)
        if recurring:
            lines.append("\n**⚠️ RECURRING ISSUES:**")
            for issue in recurring:
                lines.append(f"- {issue}")

        return "\n".join(lines)


def log_scrap_event(
    product: str,
    quantity: int,
    reason: str,
    material_cost: Optional[float] = None,
    time_cost_minutes: Optional[int] = None
) -> ScrapEntry:
    """
    Convenience function to log scrap.

    Args:
        product: Product scrapped
        quantity: Number of units
        reason: Why
        material_cost: Cost lost
        time_cost_minutes: Time wasted

    Returns:
        ScrapEntry
    """
    tracker = ScrapTracker()
    return tracker.log_scrap(
        product=product,
        quantity=quantity,
        reason=reason,
        material_cost=material_cost,
        time_cost_minutes=time_cost_minutes
    )


def get_scrap_summary(days: int = 7) -> str:
    """
    Convenience function to get scrap summary.

    Args:
        days: Days to summarize

    Returns:
        Formatted summary
    """
    tracker = ScrapTracker()
    return tracker.format_scrap_summary(days=days)
