"""In a crisis a leader may defy its advisers only within rules.max_defiance."""

import asyncio

from contracts.models import Action, CallOutput, LeaderOutput
from engine.core import advise
from engine.game import Game


def always(action: str):
    async def decide(view):
        return LeaderOutput(public_statement="We stand firm.", private_intent="Show strength.",
                            actions=[Action(type=action, by=view.nation)], followed_advice=False,
                            reason="The generals expect steel.")
    return decide


def promise(to: str) -> CallOutput:
    return CallOutput.model_validate({
        "reply_text": "ok", "emotion": "calm", "actions": [], "ends_call": False,
        "promises": [{"to": to, "what": "berth", "when": "all_day", "condition": None}],
        "belief_updates": {"trust_in_player": 0, "resolve_of_player": 0}})


async def to_ostravas_deadline(decide, tugs: bool) -> Game:
    g = Game(seed=7, decide=decide, needle=False)
    g.start_crisis("one_berth")
    await g.turn()
    g.apply_call("ostrava", promise("ostrava"))
    g.apply_call("zarnia", promise("zarnia"))
    for _ in range(4):
        await g.turn()  # tick 5: the double promise is caught
    if tugs:
        g.queued.append(Action(type="send_tugs", by="nordhaven"))  # a second berth, in time
    await g.turn()
    await g.turn()  # tick 7
    return g


def test_cabinet_overrules_a_blockade_when_docking_is_far_better():
    async def run():
        g = await to_ostravas_deadline(always("blockade"), tugs=True)
        adv = advise(g.state, "ostrava")
        assert adv[0].action.type == "dock" and adv[0].score - dict((a.action.type, a.score) for a in adv)["blockade"] > 4
        return await g._one_leader("ostrava", adv)
    out, chosen = asyncio.run(run())
    assert [a.type for a in chosen] == ["dock"]
    assert "overruled by the cabinet" in out.reason


def test_leader_may_still_defy_when_the_options_are_close():
    async def run():
        g = await to_ostravas_deadline(always("blockade"), tugs=False)
        adv = advise(g.state, "ostrava")
        scores = {a.action.type: a.score for a in adv}
        assert adv[0].score - scores["blockade"] <= 4  # no second berth: a real judgement call
        return await g._one_leader("ostrava", adv)
    out, chosen = asyncio.run(run())
    assert [a.type for a in chosen] == ["blockade"]
    assert "overruled" not in out.reason


def test_nordhaven_may_send_tugs_against_advice():
    async def run():
        g = Game(seed=7, decide=always("send_tugs"), needle=False)
        g.start_crisis("one_berth")
        for _ in range(5):
            await g.turn()
        adv = advise(g.state, "nordhaven")
        return await g._one_leader("nordhaven", adv)
    out, chosen = asyncio.run(run())
    assert [a.type for a in chosen] == ["send_tugs"]
