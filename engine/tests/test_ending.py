"""End of session (W7). Run with: python -m pytest engine/tests -q"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from engine.app import app
from engine.game import GAME, Game


def test_end_endpoint_scores_and_plain_verdict():
    GAME._decide_fn = None
    c = TestClient(app)
    c.post("/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}})
    for _ in range(3):
        c.post("/turn")
    r = c.post("/end").json()
    assert r["phase"] == "ended" and r["ending"]["reason"] == "ended"
    assert r["ending"]["score"]["months_in_power"] == 3 and r["ending"]["verdict"]
    assert c.post("/end").status_code == 409
    assert c.post("/turn").json()["turn"] == 3  # nothing moves after the end
    assert c.post("/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}}).json()["ending"] is None


def test_session_ends_at_the_month_limit():
    g = Game(seed=7, use_agents=False, needle=False)
    for _ in range(40):
        asyncio.run(g.turn())
    assert g.state.phase == "ended" and g.state.ending.reason == "time" and g.state.turn == 36


def test_three_year_term_has_a_review_each_year_but_the_last():
    g = Game(seed=7, use_agents=False, needle=False)
    for _ in range(40):
        asyncio.run(g.turn())
    reviews = [e for e in g.session_log if e["type"] == "year_review"]
    if g.state.ending.reason == "time":  # an ousted leader stops early and sees fewer reviews
        assert [(e["turn"], e["year"], e["years"]) for e in reviews] == [(12, 1, 3), (24, 2, 3)]
    assert all(e["nation"] == "valdoria" and "approval" in e for e in reviews)
    news = [n["text"] for n in g.session_log if n["type"] == "news" and n["text"].startswith("Year ")]
    assert len(news) == len(reviews)


def test_voted_out_ends_the_session():
    g = Game(seed=7, use_agents=False, needle=False)
    for _ in range(11):
        asyncio.run(g.turn())
    g.state.nations["valdoria"].stats.approval = 10  # month 12 is the yearly election
    asyncio.run(g.turn())
    assert g.state.phase == "ended" and g.state.ending.reason == "voted_out"
    assert g.state.ending.score.months_in_power == 11


def test_crisis_promises_count_in_the_score():
    from engine.run_crisis import play
    async def go():
        from engine.run_crisis import SCRIPTS
        g = Game(seed=7, use_agents=False, needle=False)
        g.start_crisis("one_berth")
        while g.state.phase == "crisis":
            s = await g.turn()
            for t, to, out, intr in SCRIPTS["honest"]:
                if s.crisis and t == s.crisis.tick:
                    g.apply_call(to, out.model_copy(deep=True), interrupted=intr)
        return g.end().ending.score
    sc = asyncio.run(go())
    assert sc.promises_kept == 2 and sc.promises_broken == 0


def test_historian_writes_the_verdict_in_the_background():
    async def historian(log):
        assert any(e.get("type") == "session_end" for e in log)
        return "A steady hand."

    async def go():
        g = Game(seed=7, use_agents=False, needle=False)
        g._decide_fn = object()  # pretend the leaders are live
        import engine.game as gm
        gm._load_historian, old = (lambda: historian), gm._load_historian
        try:
            s = g.end()
            assert s.ending.verdict is None  # pending
            await g._historian_task
        finally:
            gm._load_historian = old
        return g.state.ending.verdict
    assert asyncio.run(go()) == "A steady hand."
