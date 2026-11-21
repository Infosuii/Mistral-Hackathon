"""Mediator attribution bugs from a live game (offline, no model calls):
(a) a demand of the leader ("Hold your ships") is not a player promise;
(b) why() gets the call's promises as plain facts and is told to cite only those;
(c) the historian is told a mediator ran no nation and Valdoria was AI-run.

    pytest agents/test_attribution.py -q
"""
from __future__ import annotations

import asyncio

from contracts.models import CallTurn, Seat
from engine.game import Game

from . import fixtures, leaders


def _crisis_state(seat: Seat | None = None):
    g = Game(seed=7, use_agents=False)
    if seat is not None:
        g.state = g.state.model_copy(update={"seat": seat})
    g.start_crisis("one_berth")
    return g.state


def _promises(nation: str, said: str, model_promises: list[dict], history=None, seat=None) -> list[dict]:
    st = _crisis_state(seat)
    v = fixtures.call_view(nation, said, s=st, history=history)
    return leaders._parse_promises({"promises": model_promises}, v, leaders._dump(st))


MEDIATOR = Seat(role="mediator", nation=None)


def test_demand_of_the_leader_is_not_a_player_promise():
    got = _promises("ostrava", "Hold your ships, General.", [{"what": "wait", "when": "now"}], seat=MEDIATOR)
    assert got == []


def test_move_asked_for_with_an_offer_is_still_recorded():
    line = "I need your tugs at Port Kessar today. Valdoria pays the full cost of the tow."
    got = _promises("nordhaven", line, [{"what": "send tugs", "when": "now"}])
    assert [p["what"] for p in got] == ["send_tugs"]
    # and the code-side request detection still fires when the model records nothing
    assert [p["what"] for p in _promises("nordhaven", line, [])] == ["send_tugs"]


def test_the_demo_tug_request_is_still_recorded():
    """e2e/demo_path.py's Nordhaven line offers no payment in so many words."""
    line = ("Chancellor Lindqvist, Port Kessar is about to erupt into war unless we open a second berth. "
            "Valdoria guarantees port stability if Nordhaven agrees to send tugs before your deadline.")
    got = _promises("nordhaven", line, [{"what": "send tugs", "when": "now"}])
    assert [p["what"] for p in got] == ["send_tugs"]


def test_offer_made_earlier_in_the_call_still_counts():
    history = [CallTurn(role="player", text="The mediation fund will cover your losses if you wait."),
               CallTurn(role="leader", text="Go on.")]
    got = _promises("ostrava", "So hold your ships until evening.", [{"what": "wait", "when": "now"}],
                    history=history, seat=MEDIATOR)
    assert [p["what"] for p in got] == ["wait"]


def test_berth_promise_unchanged():
    got = _promises("ostrava", "General, the berth is yours in the morning.", [{"what": "the berth", "when": "morning"}])
    assert got == [{"to": "ostrava", "what": "berth", "when": "morning", "condition": None}]


def _capture(monkeypatch):
    seen = {}

    async def fake(system, user, field, timeout, max_tokens=200):
        seen.update(system=system, user=user)
        return "ok"
    monkeypatch.setattr(leaders, "_one_field", fake)
    return seen


def test_why_payload_states_the_promise_and_forbids_inventions(monkeypatch):
    seen = _capture(monkeypatch)
    change = {"nation": "ostrava", "was": "wait", "now": "dock", "shift_ticks": 3, "inputs": {
        "original_decision_tick": 4, "deadline_tick": 8,
        "calls": [{"to": "ostrava", "original_tick": 2, "shifted_tick": 5, "interrupted": False, "actions": [],
                   "promises": [{"to": "ostrava", "what": "wait", "when": "now",
                                 "condition": "mediation fund covers the delay"}]}]}}
    assert asyncio.run(leaders.why(change)) == "ok"
    assert "In it the player promised Ostrava: wait (now, on condition: mediation fund covers the delay)." in seen["user"]
    assert "moved from tick 2 to tick 5" in seen["user"]
    assert "Use ONLY the facts listed" in seen["system"]


def test_historian_mediator_is_told_valdoria_was_ai(monkeypatch):
    seen = _capture(monkeypatch)
    st = _crisis_state(MEDIATOR)
    log = [{"turn": 2, "type": "action", "by": "valdoria", "action": "reject_trade"},
           {"turn": 2, "type": "news", "text": "Valdoria coldly rejects the trade offer."}]
    assert asyncio.run(leaders.historian(log, state=st)) == "ok"
    assert "controlled NO nation" in seen["system"] and "including Valdoria" in seen["system"]
    assert "judging the player's time as a leader" not in seen["system"]
    assert '"actor":"valdoria (AI leader, not the player)"' in seen["user"]
    assert '"the_player":"an independent mediator"' in seen["user"]


def test_historian_president_owns_their_nation(monkeypatch):
    seen = _capture(monkeypatch)
    st = _crisis_state(Seat(role="president", nation="valdoria"))
    log = [{"turn": 2, "type": "action", "by": "valdoria"}, {"turn": 2, "type": "action", "by": "ostrava"}]
    asyncio.run(leaders.historian(log, state=st))
    assert "controlled NO nation" not in seen["system"]
    assert '"by":"valdoria","actor":"the player"' in seen["user"]
    assert '"by":"ostrava","actor":"ostrava (AI leader, not the player)"' in seen["user"]


def test_historian_never_shows_a_bracketed_placeholder(monkeypatch):
    async def fake(system, user, field, timeout, max_tokens=200):
        assert "never write a bracketed placeholder" in system
        return "President [Player]'s single month in office was brief."
    monkeypatch.setattr(leaders, "_one_field", fake)
    st = _crisis_state(Seat(role="president", nation="valdoria"))
    assert asyncio.run(leaders.historian([], state=st)) == "President's single month in office was brief."
