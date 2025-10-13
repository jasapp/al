"""
Mood Manager - Tracks Al's anger levels and emotional state

Al's mood is cumulative and contextual, like a real person. He gets angrier based on:
- How many inventory items are low/critical
- How long problems have been ignored
- Recent mistakes (scrapping materials, ordering wrong parts)
- Whether jeff is focusing on side projects while urgent stuff burns

This module doesn't enforce rigid state machines - it provides context to Claude
so Al's personality can naturally express appropriate levels of rage.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json


class MoodManager:
    """
    Tracks Al's emotional state based on operational context.

    Provides mood context to Claude rather than generating responses directly.
    Al's personality (via Claude) handles the actual rage expression.
    """

    def __init__(self, state_file: Optional[Path] = None):
        """
        Initialize mood manager.

        Args:
            state_file: Path to persistent state file (JSON)
        """
        self.state_file = state_file or Path(__file__).parent.parent.parent / ".al_mood_state.json"
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load mood state from file."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except Exception:
                pass

        # Default state
        return {
            "warnings": {},  # item_name -> {first_warned: timestamp, last_warned: timestamp, count: int}
            "recent_fuckups": [],  # List of {type, description, timestamp, severity}
            "last_positive": None,  # Timestamp of last good thing (order placed, problem fixed)
        }

    def _save_state(self) -> None:
        """Save mood state to file."""
        try:
            self.state_file.write_text(json.dumps(self.state, indent=2))
        except Exception as e:
            # Don't crash if we can't save - just log it
            print(f"Warning: Failed to save mood state: {e}")

    def record_warning(self, item_name: str, severity: str = "low") -> None:
        """
        Record that Al warned about low inventory.

        Args:
            item_name: Name of the inventory item
            severity: "low", "critical", or "out"
        """
        now = datetime.now().isoformat()

        if item_name not in self.state["warnings"]:
            self.state["warnings"][item_name] = {
                "first_warned": now,
                "last_warned": now,
                "count": 1,
                "severity": severity,
            }
        else:
            self.state["warnings"][item_name]["last_warned"] = now
            self.state["warnings"][item_name]["count"] += 1
            self.state["warnings"][item_name]["severity"] = severity

        self._save_state()

    def clear_warning(self, item_name: str) -> None:
        """
        Clear a warning (jeff ordered the thing).

        Args:
            item_name: Name of the inventory item
        """
        if item_name in self.state["warnings"]:
            del self.state["warnings"][item_name]

        self.state["last_positive"] = datetime.now().isoformat()
        self._save_state()

    def record_fuckup(self, fuckup_type: str, description: str, severity: int = 5) -> None:
        """
        Record a mistake/problem.

        Args:
            fuckup_type: Type of mistake ("scrap", "wrong_order", "delay", etc.)
            description: What happened
            severity: 1-10, how bad it is
        """
        self.state["recent_fuckups"].append({
            "type": fuckup_type,
            "description": description,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
        })

        # Keep only last 10 fuckups
        if len(self.state["recent_fuckups"]) > 10:
            self.state["recent_fuckups"] = self.state["recent_fuckups"][-10:]

        self._save_state()

    def record_positive(self, description: str) -> None:
        """
        Record something good happening.

        Args:
            description: What went well
        """
        self.state["last_positive"] = datetime.now().isoformat()
        self._save_state()

    def get_mood_context(self) -> str:
        """
        Generate mood context for Claude.

        Returns:
            Text description of Al's current emotional state based on operational context
        """
        lines = ["## Al's Current Mood Context\n"]

        # Check active warnings
        if self.state["warnings"]:
            lines.append(f"**Active inventory warnings:** {len(self.state['warnings'])}")

            for item, data in self.state["warnings"].items():
                first = datetime.fromisoformat(data["first_warned"])
                days_ago = (datetime.now() - first).days
                count = data["count"]
                severity = data["severity"]

                lines.append(f"- {item}: {severity.upper()} - warned {count} times over {days_ago} days")

            lines.append("")
        else:
            lines.append("**No active inventory warnings** - Everything's stocked.\n")

        # Recent fuckups
        recent = [f for f in self.state["recent_fuckups"]
                  if (datetime.now() - datetime.fromisoformat(f["timestamp"])).days < 7]

        if recent:
            lines.append(f"**Recent problems (last 7 days):** {len(recent)}")
            for fuckup in recent:
                lines.append(f"- {fuckup['type']}: {fuckup['description']} (severity: {fuckup['severity']}/10)")
            lines.append("")

        # Last positive event
        if self.state["last_positive"]:
            last_good = datetime.fromisoformat(self.state["last_positive"])
            days_since = (datetime.now() - last_good).days

            if days_since == 0:
                lines.append("**Last good thing:** Today (jeff actually did something right)")
            elif days_since == 1:
                lines.append("**Last good thing:** Yesterday")
            else:
                lines.append(f"**Last good thing:** {days_since} days ago")
        else:
            lines.append("**Last good thing:** Never (or it's been so long Al forgot)")

        lines.append("\n---\n")

        # Suggested anger level (guidance for Claude)
        anger_score = self._calculate_anger_score()

        if anger_score <= 2:
            lines.append("**Suggested mood:** Calm, professional (maybe slightly gruff)")
        elif anger_score <= 4:
            lines.append("**Suggested mood:** Annoyed, terse responses")
        elif anger_score <= 6:
            lines.append("**Suggested mood:** Openly irritated, swearing more")
        elif anger_score <= 8:
            lines.append("**Suggested mood:** Angry, hostile, throwing things")
        elif anger_score <= 9:
            lines.append("**Suggested mood:** LOSING CONTROL, flipping tables, screaming")
        else:
            lines.append("**Suggested mood:** COLD FURY - the disaster happened, maximum contempt")

        return "\n".join(lines)

    def _calculate_anger_score(self) -> float:
        """
        Calculate anger level 0-10.

        This is guidance for Claude, not rigid state control.
        """
        score = 0.0

        # Base score from active warnings
        for item, data in self.state["warnings"].items():
            first = datetime.fromisoformat(data["first_warned"])
            days = (datetime.now() - first).days
            count = data["count"]
            severity = data["severity"]

            # More warnings = angrier
            score += count * 0.3

            # Longer ignored = angrier
            if days > 7:
                score += 3
            elif days > 5:
                score += 2
            elif days > 3:
                score += 1

            # Critical/out items = much angrier
            if severity == "critical":
                score += 2
            elif severity == "out":
                score += 4  # Already out = maximum rage

        # Recent fuckups add anger
        recent = [f for f in self.state["recent_fuckups"]
                  if (datetime.now() - datetime.fromisoformat(f["timestamp"])).days < 7]

        for fuckup in recent:
            score += fuckup["severity"] / 10.0

        # Long time since anything positive = angrier baseline
        if self.state["last_positive"]:
            days_since_good = (datetime.now() - datetime.fromisoformat(self.state["last_positive"])).days
            if days_since_good > 14:
                score += 2
            elif days_since_good > 7:
                score += 1
        else:
            score += 1  # Never had anything good

        return min(score, 10.0)

    def get_anger_level(self) -> int:
        """
        Get current anger level 0-10.

        Returns:
            Integer anger level for easy logic branching
        """
        return int(round(self._calculate_anger_score()))
