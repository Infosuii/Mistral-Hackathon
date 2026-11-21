"""In a crisis a leader may defy its advisers only within rules.max_defiance."""

import asyncio

import agents
import engine.game as game_mod
from contracts.models import Action, CallOutput, LeaderOutput, ReplayRequest, Seat
from engine.core import advise
from engine.game import Game
from replay import api as replay_api


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


# --- escalations: no war against the cabinet -----------------------------------------


def half_day(to: str, resolve: float = 0.0) -> CallOutput:
    return CallOutput.model_validate({
        "reply_text": "ok", "emotion": "calm", "actions": [], "ends_call": False,
        "promises": [{"to": to, "what": "berth", "when": "morning", "condition": None}],
        "belief_updates": {"trust_in_player": 0, "resolve_of_player": resolve}})


async def play_to_the_end(interrupt: bool) -> Game:
    """The player is caught double-promising; Ostrava rings at tick 7 to announce a blockade.
    The leader always wants the blockade. Does interrupting him with a half-day offer matter?"""
    g = await to_ostravas_deadline(always("blockade"), tugs=False)
    assert g.pending_announce is not None and g.pending_announce.by == "ostrava"
    if interrupt:
        g.interrupt("ostrava")
        g.apply_call("ostrava", half_day("ostrava"), interrupted=True)
    while g.state.crisis is not None:
        await g.turn()
    return g


def test_interrupting_with_an_offer_stops_the_blockade():
    g = asyncio.run(play_to_the_end(interrupt=True))
    assert g.last_crisis["decisions"]["ostrava"].action == "dock"
    assert "overruled by the cabinet" in g.leaders["ostrava"].reason


def test_without_the_interruption_he_blockades():
    g = asyncio.run(play_to_the_end(interrupt=False))
    assert g.last_crisis["decisions"]["ostrava"].action == "blockade"


def test_replay_shows_what_waiting_would_have_cost():
    g = asyncio.run(play_to_the_end(interrupt=True))
    assert g.replay(0) == []  # same timing, same outcome
    late = {c["nation"]: (c["was"], c["now"]) for c in g.replay(5)}  # the interruption arrives after his deadline
    assert late.get("ostrava") == ("dock", "blockade")


# --- the tugs: a paid request is dependable, and its timing shows in the replay ----------


def paid_tug_request() -> CallOutput:
    return CallOutput.model_validate({
        "reply_text": "I will see what is free.", "emotion": "calm", "actions": [], "ends_call": False,
        "promises": [{"to": "nordhaven", "what": "send_tugs", "when": "all_day", "condition": None}],
        "belief_updates": {"trust_in_player": 0, "resolve_of_player": 0}})


async def one_berth_with_tug_call(ask_at_tick: int | None, seat: Seat | None = None) -> Game:
    """Nordhaven's leader always prefers to stay out. The player may ask for tugs, and pay."""
    g = Game(seed=7, seat=seat, decide=always("stay_out"), needle=False)
    g.start_crisis("one_berth")
    while g.state.crisis is not None:
        if ask_at_tick is not None and g.state.crisis.tick == ask_at_tick:
            g.apply_call("nordhaven", paid_tug_request())
            ask_at_tick = None
        await g.turn()
    return g


def test_a_paid_request_gets_the_tugs_even_from_a_reluctant_leader():
    g = asyncio.run(one_berth_with_tug_call(ask_at_tick=2))
    assert g.last_crisis["decisions"]["nordhaven"].action == "send_tugs"


def test_without_a_request_nordhaven_stays_out():
    g = asyncio.run(one_berth_with_tug_call(ask_at_tick=None))
    assert g.last_crisis["decisions"]["nordhaven"].action == "stay_out"


def test_replay_shows_the_tug_call_arriving_too_late():
    g = asyncio.run(one_berth_with_tug_call(ask_at_tick=2))
    assert g.replay(0) == []
    late = {c["nation"]: (c["was"], c["now"]) for c in g.replay(5)}  # tick 7, after his tick-6 deadline
    assert late.get("nordhaven") == ("send_tugs", "stay_out")


def test_mediator_replay_explains_the_archived_call_timing(monkeypatch):
    monkeypatch.setattr(game_mod, "MEDIATOR", True)
    monkeypatch.setenv("GAMBIT_AGENTS", "live")
    game = asyncio.run(one_berth_with_tug_call(2, Seat(role="mediator", nation=None)))
    monkeypatch.setattr(replay_api, "GAME", game)
    explained = []

    async def model_reason(change):
        explained.append(change)
        return "An oil deal arrived too late."

    monkeypatch.setattr(agents, "why", model_reason)
    response = asyncio.run(replay_api.replay(ReplayRequest(shift_ticks=5)))
    nordhaven = next(change for change in response.changed if change.nation == "nordhaven")
    assert (nordhaven.was, nordhaven.now) == ("send_tugs", "stay_out")
    assert nordhaven.why == "The call moved from tick 2 to 7, after Nordhaven's original decision."
    assert explained == []

    unchanged = asyncio.run(replay_api.replay(ReplayRequest(shift_ticks=0)))
    assert unchanged.changed == []
