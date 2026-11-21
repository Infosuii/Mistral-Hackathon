"""snapshot(), fork() and the crisis rerun. Run with: python -m pytest engine/tests -q"""

from __future__ import annotations

import asyncio

import pytest

from contracts.models import NATION_IDS, Seat
from engine.core import advise, new_game, step
from engine.game import Game
from engine.run_crisis import SCRIPTS
from engine.snapshots import fork, load, snapshot

SEAT = Seat(role="president", nation="valdoria")


def test_fork_then_step_equals_step():
    s = new_game(7, SEAT)
    for _ in range(4):
        s = step(s, [advise(s, n)[0].action for n in NATION_IDS], 7)
    actions = [advise(s, n)[0].action for n in NATION_IDS]
    sid = snapshot(s)
    assert sid == snapshot(s)  # stable id
    assert load(sid).model_dump_json() == s.model_dump_json()
    assert step(fork(sid, {}, s.seed), actions, s.seed).model_dump_json() == step(s, actions, s.seed).model_dump_json()


def test_fork_applies_changes():
    s = new_game(7, SEAT)
    f = fork(snapshot(s), {"nations": {"ostrava": {"stats": {"food": 90}}}, "relations": {"ostrava|zarnia": 50}}, 11)
    assert f.nations["ostrava"].stats.food == 90 and f.nations["ostrava"].stats.army == s.nations["ostrava"].stats.army
    assert f.relations["ostrava|zarnia"] == 50 and f.seed == 11
    with pytest.raises(KeyError):
        fork("s_missing", {}, 7)


def _played(script: str) -> Game:
    g = Game(seed=7, use_agents=False, needle=False)
    g.start_crisis("one_berth")
    while g.state.phase == "crisis":
        s = asyncio.run(g.turn())
        for t, to, out, interrupted in SCRIPTS[script]:
            if s.crisis and t == s.crisis.tick:
                g.apply_call(to, out.model_copy(deep=True), interrupted=interrupted)
    return g


@pytest.mark.parametrize("script", list(SCRIPTS))
def test_replay_without_shift_changes_nothing(script):
    assert _played(script).replay(0) == []


def test_replay_late_offer_flips_someone():
    g = _played("honest")
    changes = g.replay(8)  # the offers arrive after Ostrava's deadline
    assert changes and all(set(c) == {"nation", "was", "now"} for c in changes)
    assert any(c["nation"] == "ostrava" for c in changes)
