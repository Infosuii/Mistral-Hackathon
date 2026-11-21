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
    _, now = rerun_crisis(start, [], {"ostrava": Decision(action="dock", tick=8)}, cached_advice, 7)
    assert now["ostrava"] == "dock"
    # When the advisers' top itself changes, the leader follows the new advice.
    cached_advice["ostrava"][0] = Advice(action=Action(type="wait", by="ostrava"), score=9.0)
    _, now = rerun_crisis(start, [], {"ostrava": Decision(action="dock", tick=8)}, cached_advice, 7)
    assert now["ostrava"] == "blockade"


def _call(to, what="berth", when="all_day"):
    from contracts.models import CallOutput
    return CallOutput(reply_text="...", emotion="calm", belief_updates={"trust_in_player": 0, "resolve_of_player": 0},
                      promises=[{"to": to, "what": what, "when": when}])


def _run(calls):
    async def go():
        g = Game(seed=7, use_agents=False, needle=False)
        g.start_crisis("one_berth")
        while g.state.phase == "crisis":
            s = await g.turn()
            for t, to in calls:
                if s.crisis and s.crisis.tick == t:
                    g.apply_call(to, _call(to))
        return g
    return asyncio.run(go())


def test_clash_after_compare_notes_is_caught_when_made():
    g = _run([(1, "ostrava"), (6, "zarnia")])  # the second promise comes after tick 5
    caught = [n.text for n in g.state.news if "promised the berth to both" in n.text]
    assert len(caught) == 1
    assert g.state.nations["ostrava"].beliefs.trust_in_player < 0.5


def test_caught_once_not_twice_and_no_noise_without_clash():
    g = _run([(1, "ostrava"), (3, "zarnia"), (6, "zarnia")])  # caught at tick 5; Ostrava's promise is already void
    assert len([n for n in g.state.news if "promised the berth to both" in n.text]) == 1
    g = _run([(1, "ostrava"), (6, "ostrava")])
    assert not any("compare notes" in n.text and "both" in n.text for n in g.state.news)
    assert sum("story holds" in n.text for n in g.state.news) == 1  # only the scripted tick-5 line


def _mk(promises=(), actions=(), resolve=0.0):
    from contracts.models import CallOutput
    return CallOutput(reply_text="ok", emotion="calm", promises=list(promises), actions=list(actions),
                      belief_updates={"trust_in_player": 0.0, "resolve_of_player": resolve})


def _played_calls(calls):
    async def go():
        g = Game(seed=7, use_agents=False, needle=False)
        g.start_crisis("one_berth")
        while g.state.phase == "crisis":
            s = await g.turn()
            if not s.crisis:
                break
            for t, to, out, intr in calls:
                if t == s.crisis.tick:
                    g.apply_call(to, out.model_copy(deep=True), interrupted=intr)
        return g
    return asyncio.run(go())


NEON_INTERRUPT_WAIT = [  # Neon's repro on #27 (13:38)
    (1, "ostrava", _mk([{"to": "ostrava", "what": "berth", "when": "all_day"}]), False),
    (3, "zarnia", _mk([{"to": "zarnia", "what": "berth", "when": "all_day"}]), False),
    (7, "ostrava", _mk([{"to": "ostrava", "what": "berth", "when": "morning"}], [{"type": "wait", "by": "ostrava"}], 0.1), True),
]


def test_late_deal_and_late_interruption_flip_ostrava():
    g = _played_calls(NEON_INTERRUPT_WAIT)
    assert g.last_crisis["decisions"]["ostrava"].action == "wait"
    assert g.replay(0) == []
    for shift in (1, 2, 3, 4):  # the call lands after Ostrava's tick-8 deadline
        flips = {c["nation"]: (c["was"], c["now"]) for c in g.replay(shift)}
        assert flips.get("ostrava") == ("wait", "blockade"), (shift, flips)


def test_shifted_interruption_lets_the_threat_go_public():
    from engine.crisis import rerun_crisis
    g = _played_calls(NEON_INTERRUPT_WAIT)
    lc = g.last_crisis
    late = [(t + 1 if t == 7 else t, to, out, intr) for t, to, out, intr in lc["calls"]]
    final, _ = rerun_crisis(lc["start"], late, lc["own"], lc["advice"], 7)
    assert any(e.type == "public_commitment" and e.nation == "ostrava" for e in final.events)
    on_time, _ = rerun_crisis(lc["start"], lc["calls"], lc["own"], lc["advice"], 7)
    assert not any(e.type == "public_commitment" for e in on_time.events)


def _neon_1348(interrupt: bool) -> Game:
    """Neon's repro on #27 (13:48): caught double promise, then a tick-7 morning offer."""
    return _played_calls([
        (1, "ostrava", _mk([{"to": "ostrava", "what": "berth", "when": "all_day"}]), False),
        (3, "zarnia", _mk([{"to": "zarnia", "what": "berth", "when": "all_day"}]), False),
        (7, "ostrava", _mk([{"to": "ostrava", "what": "berth", "when": "morning"}], resolve=0.1), interrupt),
    ])


def test_interrupt_plus_half_day_beats_the_blockade_and_replay_flips_it():
    g = _neon_1348(interrupt=True)
    assert g.last_crisis["decisions"]["ostrava"].action in ("dock", "wait")
    assert g.replay(0) == []
    flip = {c["nation"]: c["now"] for c in g.replay(3)}
    assert flip.get("ostrava") == "blockade"


def test_without_the_interrupt_the_public_blockade_holds():
    g = _neon_1348(interrupt=False)
    assert g.last_crisis["decisions"]["ostrava"].action == "blockade"  # the back-down cost counts at the deadline


def test_a_leader_who_has_decided_does_not_ring_to_threaten():
    deal = _mk(actions=[{"type": "dock", "by": "ostrava"}])
    async def go():
        g = Game(seed=7, use_agents=False, needle=False)
        g.start_crisis("one_berth")
        rang = []
        while g.state.phase == "crisis":
            s = await g.turn()
            if s.crisis and s.incoming_call:
                rang.append((s.crisis.tick, s.incoming_call.from_))
            if s.crisis and s.crisis.tick == 1:
                g.apply_call("ostrava", deal)  # Ostrava agrees to dock; decided at tick 2
        return g, rang
    g, rang = asyncio.run(go())
    assert (1, "ostrava") in rang and not any(t == 7 for t, _ in rang)
    assert g.last_crisis["decisions"]["ostrava"].action == "dock"
    assert not any(e.type == "public_commitment" for e in g.state.events)


def test_betrayal_reopens_early_deal_so_tick7_blockade_still_rings():
    """Repro for the 16:11 live demo failure (#67): if Ostrava agreed to dock at tick 1
    on the player's berth promise and compare-notes catches a double promise at tick 5,
    Ostrava's early pre-deadline deal must reopen so the tick-7 blockade call still rings."""
    async def go(interrupt: bool):
        g = Game(seed=7, use_agents=False, needle=False)
        g.start_crisis("one_berth")
        tick7_ring = None
        tick7_threat = False
        while g.state.phase == "crisis":
            s = await g.turn()
            if not s.crisis:
                break
            t = s.crisis.tick
            if t == 1:
                g.apply_call("ostrava", _mk(
                    [{"to": "ostrava", "what": "berth", "when": "all_day"}],
                    [{"type": "dock", "by": "ostrava"}],
                ))
            elif t == 3:
                g.apply_call("zarnia", _mk([{"to": "zarnia", "what": "berth", "when": "all_day"}]))
            elif t == 7:
                tick7_ring = s.incoming_call
                tick7_threat = g.pending_announce is not None
                g.apply_call(
                    "ostrava",
                    _mk([{"to": "ostrava", "what": "berth", "when": "morning"}], resolve=0.1),
                    interrupted=interrupt,
                )
        return g, tick7_ring, tick7_threat

    g_int, ring_int, threat_int = asyncio.run(go(interrupt=True))
    assert ring_int is not None and ring_int.from_ == "ostrava" and "same berth" in ring_int.opening_line
    assert threat_int is True
    assert g_int.last_crisis["decisions"]["ostrava"].action in ("dock", "wait")
    assert g_int.last_crisis["decisions"]["ostrava"].tick == 8
    assert g_int.replay(0) == []
    assert {c["nation"]: c["now"] for c in g_int.replay(3)}.get("ostrava") == "blockade"

    g_no, ring_no, threat_no = asyncio.run(go(interrupt=False))
    assert ring_no is not None and ring_no.from_ == "ostrava" and threat_no is True
    assert g_no.last_crisis["decisions"]["ostrava"].action == "blockade"
