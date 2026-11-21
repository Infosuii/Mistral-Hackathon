"""A phone call that lands while a turn or tick is being computed must survive it,
and an interruption must cancel a pending threat at once."""

import asyncio

from contracts.models import Action, CallOutput
from engine.game import Game, advisers_choice


async def slow_decide(view):
    await asyncio.sleep(0.2)  # a leader thinking
    return advisers_choice(view.state, view.nation, view.advice, "test")


def reply(**kw):
    base = {"reply_text": "ok", "emotion": "calm", "promises": [], "actions": [],
            "belief_updates": {"trust_in_player": 0, "resolve_of_player": 0}, "ends_call": False}
    return CallOutput.model_validate({**base, **kw})


def test_call_during_strategy_turn_is_kept():
    async def run():
        g = Game(seed=7, decide=slow_decide, needle=False)
        turn = asyncio.create_task(g.turn())
        await asyncio.sleep(0.05)  # the turn is now waiting on the leaders
        cid = g.begin_call("ostrava")
        g.apply_call("ostrava", reply(belief_updates={"trust_in_player": 0.2, "resolve_of_player": 0}), call_id=cid)
        landed = g.state.nations["ostrava"].beliefs.trust_in_player
        await turn
        return landed, g
    landed, g = asyncio.run(run())
    assert g.state.nations["ostrava"].beliefs.trust_in_player == landed
    assert g.state.last_call is not None and g.state.last_call.pending is False
    assert g.state.turn == 1


def test_promise_during_crisis_tick_is_kept():
    async def run():
        g = Game(seed=7, decide=slow_decide, needle=False)
        g.start_crisis("one_berth")
        for _ in range(5):
            await g.turn()
        tick = asyncio.create_task(g.turn())  # tick 6 waits on Nordhaven's leader
        await asyncio.sleep(0.05)
        cid = g.begin_call("ostrava")
        g.apply_call("ostrava", reply(promises=[{"to": "ostrava", "what": "berth", "when": "morning",
                                                 "condition": None}]), call_id=cid)
        await tick
        return g
    g = asyncio.run(run())
    assert g.state.crisis.tick == 6
    assert [p.to for p in g.state.crisis.promises] == ["ostrava"]
    assert g.state.last_call.pending is False


def test_interrupt_cancels_the_threat_before_the_reply_is_worked_out():
    async def run():
        g = Game(seed=7, decide=slow_decide, needle=False)
        g.start_crisis("one_berth")
        g.pending_announce = Action(type="announce", by="ostrava", params={"action": "blockade"})
        assert g.interrupt("zarnia") is False  # the wrong leader: nothing is cancelled
        assert g.interrupt("ostrava") is True
        await g.turn()
        return g
    g = asyncio.run(run())
    assert g.state.crisis.public_commitments == []
