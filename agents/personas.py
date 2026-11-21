"""Load persona cards from agents/personas/*.md. The cards are the design file for
leader personalities (MASTER_PLAN.md section 8c): edit them, not the code."""
import json
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).parent / "personas"
_WEIGHTS = Path(__file__).resolve().parent.parent / "data" / "weights.json"


def _proud() -> frozenset[str]:
    """Interruption is an insult to these leaders (ideas.md 6b); shared with the engine."""
    try:
        return frozenset(json.loads(_WEIGHTS.read_text())["call"]["proud"])
    except Exception:  # noqa: BLE001
        return frozenset({"ostrava", "zarnia"})


PROUD = _proud()


@lru_cache(maxsize=None)
def card(nation: str) -> str:
    path = DIR / f"{nation}.md"
    return path.read_text() if path.exists() else f"Leader of {nation}."


@lru_cache(maxsize=None)
def temper(nation: str) -> float:
    """Chance per decision that this leader's instinct pulls against the advisers."""
    try:
        return float(json.loads((DIR / "temper.json").read_text()).get(nation, 0.2))
    except Exception:  # noqa: BLE001
        return 0.2


def defies_when(nation: str) -> str:
    """The persona card's 'Defies advice when' line, as plain text."""
    for line in card(nation).splitlines():
        if "defies advice when" in line.lower():
            return line.split(":", 1)[-1].strip(" *")
    return "your gut says the advisers are wrong."
