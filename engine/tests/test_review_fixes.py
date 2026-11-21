"""Reviewer's findings on #27 (13:19)."""

from __future__ import annotations

import asyncio

from contracts.models import Action, Advice, Decision, Seat
from engine.core import new_game
from engine.crisis import rerun_crisis, start_crisis
from engine.game import Game
from engine.run_crisis import SCRIPTS


def _tick7_line(script: str) -> tuple[str, bool]:
    async def go():
        g = Game(seed=7, use_agents=False, needle=False)
        g.start_crisis("one_berth")
        line, pending = None, False
        while g.state.phase == "crisis":
            s = await g.turn()
            if s.crisis and s.crisis.tick == 7:
                line, pending = s.incoming_call.opening_line, g.pending_announce is not None
            for t, to, out, intr in SCRIPTS[script]:
                if s.crisis and t == s.crisis.tick:
                    g.apply_call(to, out.model_copy(deep=True), interrupted=intr)
        return line, pending
    return asyncio.run(go())


def test_tick7_accuses_only_after_a_contradiction():
    line, threat = _tick7_line("bluff")
    assert "same berth" in line and threat
    line, threat = _tick7_line("honest")
    assert "Confirm it is ours" in line and not threat
    line, threat = _tick7_line("silent")
    assert "Confirm it is ours" in line and not threat


def test_defiant_leader_keeps_its_choice_when_only_scores_move():
    start = start_crisis(new_game(7, Seat(role="president", nation="valdoria")), "one_berth")
    # The rerun's advisers will put blockade on top for a silent player. Originally they also
    # put blockade on top (different scores), and Ostrava defied them and docked.
    cached_advice = {"ostrava": [Advice(action=Action(type="blockade", by="ostrava"), score=9.0),
                                 Advice(action=Action(type="dock", by="ostrava"), score=1.0)]}
    _, now = rerun_crisis(start, [], {"ostrava": Decision(action="dock", tick=8)}, cached_advice, [], 7)
    assert now["ostrava"] == "dock"
    # When the advisers' top itself changes, the leader follows the new advice.
    cached_advice["ostrava"][0] = Advice(action=Action(type="wait", by="ostrava"), score=9.0)
    _, now = rerun_crisis(start, [], {"ostrava": Decision(action="dock", tick=8)}, cached_advice, [], 7)
    assert now["ostrava"] == "blockade"
