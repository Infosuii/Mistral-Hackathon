import asyncio
from threading import Event

import pytest
from fastapi import HTTPException

from contracts.models import Action, CallRequest, FuturesRequest, FuturesResponse, Seat, StartRequest
from engine import app
from engine.game import Game
from engine.snapshots import snapshot
from voice import api


@pytest.mark.parametrize("split", [False, True])
def test_restart_during_spoken_reply(split, monkeypatch):
    async def run():
        game = Game(needle=False, use_agents=False)
        monkeypatch.setattr(api, "_game", lambda: game)
        entered, release = asyncio.Event(), asyncio.Event()

        async def reply(view):
            entered.set()
            await release.wait()
            return {"reply_text": "Agreed.", "emotion": "calm"}

        monkeypatch.setattr(api, "_phone", lambda: (reply, reply if split else None, False))
        call = asyncio.create_task(api.call(CallRequest(to="ostrava", text="An old offer.")))
        await entered.wait()
        game.reset(7)
        release.set()
        with pytest.raises(HTTPException) as exc:
            await call
        assert exc.value.status_code == 409
        assert game.state.last_call is None and not game.queued
        assert api._history("ostrava", game.state.model_dump(), game.epoch) == []
        game.end()
        with pytest.raises(HTTPException) as ended:
            await api.call(CallRequest(to="ostrava", text="Too late."))
        assert ended.value.status_code == 409

    asyncio.run(run())


def test_restart_during_explicit_forecast(monkeypatch):
    async def run():
        g = Game(needle=False, use_agents=False)
        monkeypatch.setattr(app, "GAME", g)
        entered, release = Event(), Event()

        def forecast(*args):
            entered.set()
            assert release.wait(5)
            return FuturesResponse(before={"war_p": .1}, after={"war_p": .2}, caption="Old game")

        monkeypatch.setattr(app, "futures", forecast)
        sid = snapshot(g.state)
        task = asyncio.create_task(app.post_futures(FuturesRequest(snapshot_id=sid)))
        assert await asyncio.to_thread(entered.wait, 5)
        try:
            await app.start(StartRequest(seed=42, seat=Seat(role="president", nation="valdoria")))
        finally:
            release.set()
        with pytest.raises(HTTPException) as exc:
            await task
        assert exc.value.status_code == 409 and g.state.last_futures is None
        with pytest.raises(HTTPException) as missing:
            await app.post_futures(FuturesRequest(snapshot_id=sid))
        assert missing.value.status_code == 404

    asyncio.run(run())


def test_monthly_deal_waits_through_crisis():
    async def run():
        g = Game(needle=False, use_agents=False)
        action = Action(type="set_tariff", by="kessaria", target="valdoria", params={"pct": 10})
        g.queued.append(action)
        g.start_crisis("one_berth")
        assert not g.queued
        while g.state.crisis:
            await g.turn()
        assert g.queued == [action]
        await g.turn()
        assert not g.queued
        assert any(e.type == "tariff" and e.nation == "kessaria" and e.target == "valdoria"
                   for e in g.state.events)

    asyncio.run(run())
