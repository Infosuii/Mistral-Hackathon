"""Verify leaders vary their spoken openings across repeated calls (#28).

    pytest agents/test_openings.py -q        # offline unit check of avoid_openings
    python -m agents.test_openings           # live 6-turn Kessaria check (outside quiet windows)
"""
from __future__ import annotations

import asyncio

from contracts.models import CallTurn, CallView, Seat
from engine.core import new_game
from agents.leaders import _call_context, _opening_words, _parse_voice, speak_fast


def test_call_context_passes_last_two_openings():
    st = new_game(7, Seat(role="president", nation="valdoria"))
    history = [
        CallTurn(role="player", text="Your Majesty, let's talk trade."),
        CallTurn(role="leader", text="President, how delightful to hear from Valdoria."),
        CallTurn(role="player", text="We can offer chips for food."),
        CallTurn(role="leader", text="How charming of you to bring chips to the table."),
        CallTurn(role="player", text="Will you sign today?"),
        CallTurn(role="leader", text="Charming offers always deserve a modest toll."),
    ]
    v = CallView(nation="kessaria", transcript="Name your price.", interrupted=False, state=st, history=history)
    system, user, _ = _call_context(v)
    assert "avoid_openings" in system
    assert user["avoid_openings"] == ["How charming", "Charming offers"]


def test_fresh_game_empty_history_has_no_carried_over_openings():
    """A new game on the same seed with history=None must never inherit prior openings."""
    st_a = new_game(7, Seat(role="president", nation="valdoria"))
    v_a = CallView(nation="kessaria", transcript="Hello.", interrupted=False, state=st_a, history=None)
    _parse_voice({"reply_text": "First session greeting from Kessaria.", "emotion": "warm"}, v_a)

    st_b = new_game(7, Seat(role="president", nation="valdoria"))
    v_b = CallView(nation="kessaria", transcript="Hello again.", interrupted=False, state=st_b, history=None)
    _, user_b, _ = _call_context(v_b)
    assert "avoid_openings" not in user_b

    v_empty = CallView(nation="kessaria", transcript="Hello again.", interrupted=False, state=st_b, history=[])
    _, user_empty, _ = _call_context(v_empty)
    assert "avoid_openings" not in user_empty


LINES = [
    "Your Majesty, Valdoria would like to discuss trade through the strait.",
    "We can offer ten units of chips for food this month.",
    "What toll would Kessaria want to keep the strait open?",
    "Ostrava is rattling sabres—can we count on Kessaria staying neutral?",
    "If we sign a trade deal today, will Port Kessar prioritise Valdorian grain?",
    "Fair enough, let us revisit the tariff rate next month.",
]


async def live_check() -> int:
    from pathlib import Path
    from voice.audio import _load_env

    _load_env(Path(__file__).resolve().parent.parent / ".env")
    st = new_game(7, Seat(role="president", nation="valdoria"))
    history: list[CallTurn] = []
    openings: list[str] = []
    starts_with_president = 0

    for i, line in enumerate(LINES, start=1):
        v = CallView(nation="kessaria", transcript=line, interrupted=False, state=st, history=list(history) or None)
        out = await speak_fast(v)
        reply = out["reply_text"]
        op = _opening_words(reply).lower()
        openings.append(op)
        if reply.lstrip().lower().startswith("president"):
            starts_with_president += 1
        print(f"turn {i}: [{out['emotion']:<10}] {reply}")
        history.append(CallTurn(role="player", text=line))
        history.append(CallTurn(role="leader", text=reply))

    unique = len(set(openings))
    print(f"unique 2-word openings: {unique}/{len(LINES)}; starts_with_president: {starts_with_president}/{len(LINES)}")
    if unique < 4 or starts_with_president > 2:
        print("FAIL: openings still too repetitive")
        return 1
    print("PASS: openings varied across 6 live Kessaria turns")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(live_check()))
