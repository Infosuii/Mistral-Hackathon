"""Run with: python -m pytest engine/tests -q"""

from __future__ import annotations

import subprocess
import sys

from contracts.models import NATION_IDS, Action, Seat, State
from engine.core import advise, is_legal, legal_actions, new_game, step

SEAT = Seat(role="president", nation="valdoria")


def play(seed: int, turns: int = 20) -> list[State]:
    states = [new_game(seed, SEAT)]
    for _ in range(turns):
        s = states[-1]
        states.append(step(s, [advise(s, n)[0].action for n in NATION_IDS], seed))
    return states


def test_same_seed_same_world():
    a = [s.model_dump_json() for s in play(7)]
    b = [s.model_dump_json() for s in play(7)]
    assert a == b


def test_different_seed_different_world():
    assert play(7)[-1].model_dump_json() != play(8)[-1].model_dump_json()


def test_step_is_pure():
    s = play(7, 3)[-1]
    before = s.model_dump_json()
    actions = [advise(s, n)[0].action for n in NATION_IDS]
    first = step(s, actions, 7)
    assert s.model_dump_json() == before  # input untouched
    assert step(s, actions, 7).model_dump_json() == first.model_dump_json()


def test_every_state_matches_the_contract():
    for s in play(7) + play(3):
        State.model_validate(s.model_dump(mode="json", by_alias=True))
        assert sum(n.stats.territory for n in s.nations.values()) == len(s.provinces)


def test_advise_is_ranked_and_legal():
    s = play(7, 5)[-1]
    for n in NATION_IDS:
        ranked = advise(s, n)
        assert ranked, n
        assert [a.score for a in ranked] == sorted((a.score for a in ranked), reverse=True)
        assert any(a.action.type == "wait" for a in ranked)
        assert all(is_legal(s, a.action) and a.action.by == n for a in ranked)
        assert len(ranked) == len(legal_actions(s, n))


def test_illegal_action_is_ignored():
    s = new_game(7, SEAT)
    bogus = Action(type="declare_war", by="valdoria", target="valdoria")
    assert not is_legal(s, bogus)
    assert step(s, [bogus], 7).model_dump_json() == step(s, [], 7).model_dump_json()


def test_headless_run_is_byte_identical():
    cmd = [sys.executable, "-m", "engine.run", "--seed", "7", "--turns", "20"]
    out1 = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    out2 = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    assert out1 == out2 and out1.count("== month") == 20
