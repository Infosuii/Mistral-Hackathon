"""POST /call through the engine app, with fake agents and no network.

    python -m pytest voice/tests -q
"""
import os
import sys
import time
import types

import pytest

os.environ["GAMBIT_AGENTS"] = "stub"

from fastapi.testclient import TestClient  # noqa: E402

import voice.api as api  # noqa: E402
from engine.app import app  # noqa: E402

START = {"seed": 7, "seat": {"role": "president", "nation": "valdoria"}}
CALL = {"to": "ostrava", "text": "You can have the morning.", "interrupted": False, "hesitation_ms": 800}


@pytest.fixture
def client(monkeypatch):
    async def fake_speak(text, voice_id, emotion=None, fmt="mp3"):
        return f"/audio/{voice_id}.mp3"
    monkeypatch.setattr(api, "speak", fake_speak)
    api._calls.clear()
    with TestClient(app) as c:
        c.post("/start", json=START)
        yield c
    sys.modules.pop("agents", None)


def fake_agents(**fns):
    mod = types.ModuleType("agents")
    for k, v in fns.items():
        setattr(mod, k, v)
    sys.modules["agents"] = mod


def trust(c):
    return c.get("/state").json()["nations"]["ostrava"]["beliefs"]["trust_in_player"]


def test_split_path_speaks_first_and_applies_later(client):
    seen = {}

    async def speak_fast(view):
        seen["view"] = view
        return {"reply_text": "Half a day is an insult.", "emotion": "angry"}

    async def interpret(view, reply_text):
        seen["reply_text"] = reply_text
        return {"promises": [{"to": "ostrava", "what": "berth", "when": "morning", "condition": None}],
                "actions": [], "belief_updates": {"trust_in_player": -0.2, "resolve_of_player": 0.1},
                "ends_call": False}

    fake_agents(speak_fast=speak_fast, interpret=interpret)
    before = trust(client)
    r = client.post("/api/call", json=CALL).json()
    assert r["reply_text"] == "Half a day is an insult." and r["emotion"] == "angry"
    assert r["reply_audio_url"].endswith(".mp3")
    assert r["promises"] == []  # they arrive through /state once Large 4 is done
    assert seen["view"].nation == "ostrava" and seen["view"].hesitation_ms == 800
    for _ in range(50):
        if trust(client) != before:
            break
        time.sleep(0.05)
    assert trust(client) == pytest.approx(before - 0.2)
    assert seen["reply_text"] == "Half a day is an insult."

    # second turn carries the history of the first
    client.post("/api/call", json={**CALL, "text": "Then what do you want?"})
    assert [t.text for t in seen["view"].history] == ["You can have the morning.", "Half a day is an insult."]


def test_pending_call_fills_last_call(client):
    from engine.game import GAME
    if not hasattr(GAME, "begin_call"):
        pytest.skip("engine has no begin_call yet (PR #45)")

    async def speak_fast(view):
        return {"reply_text": "Half a day is an insult.", "emotion": "angry"}

    async def interpret(view, reply_text):
        return {"promises": [{"to": "ostrava", "what": "berth", "when": "morning", "condition": None}],
                "actions": [], "belief_updates": {"trust_in_player": -0.1, "resolve_of_player": 0},
                "ends_call": False}

    fake_agents(speak_fast=speak_fast, interpret=interpret)
    r = client.post("/api/call", json=CALL).json()
    assert r["pending"] is True and r["call_id"]
    for _ in range(50):
        last = client.get("/state").json().get("last_call") or {}
        if last.get("call_id") == r["call_id"] and last.get("pending") is False:
            break
        time.sleep(0.05)
    assert last["call_id"] == r["call_id"] and last["pending"] is False
    assert last["promises"][0]["what"] == "berth"


def test_failing_reply_still_speaks_and_records_promises(client):
    seen = {}

    async def speak_fast(view):
        raise RuntimeError("model down")

    async def interpret(view, reply_text):
        seen["reply_text"] = reply_text
        return {"promises": [], "actions": [],
                "belief_updates": {"trust_in_player": -0.3, "resolve_of_player": 0}, "ends_call": False}

    fake_agents(speak_fast=speak_fast, interpret=interpret)
    before = trust(client)
    r = client.post("/api/call", json=CALL)
    assert r.status_code == 200
    assert r.json()["reply_text"] == api.FALLBACK_REPLY["reply_text"]
    for _ in range(50):  # what the player said still counts
        if trust(client) != before:
            break
        time.sleep(0.05)
    assert trust(client) == pytest.approx(before - 0.3)
    assert seen["reply_text"] == api.FALLBACK_REPLY["reply_text"]


def test_single_call_reply_is_applied_at_once(client):
    async def call_reply(view):
        return {"reply_text": "Agreed.", "emotion": "warm", "promises": [], "actions": [],
                "belief_updates": {"trust_in_player": 0.1, "resolve_of_player": 0}, "ends_call": True}

    fake_agents(call_reply=call_reply)
    before = trust(client)
    r = client.post("/api/call", json=CALL).json()
    assert r["reply_text"] == "Agreed."
    assert trust(client) == pytest.approx(before + 0.1)
    assert "ostrava" not in api._calls  # ends_call closes the conversation


def test_demo_lines_play_with_network_off(monkeypatch):
    import asyncio

    import voice
    import voice.audio as audio
    from voice.prerender import demo_lines, render

    async def no_network(*a, **k):
        raise AssertionError("network used")
        yield  # pragma: no cover

    monkeypatch.setattr(audio, "stream_speech", no_network)
    monkeypatch.setenv("VOICE_WIRETAP", "demo")
    assert asyncio.run(render(check_only=True)) == 0  # every demo line is committed

    with TestClient(app) as c:
        tap = c.get("/api/wiretap", params={"a": "zarnia", "b": "ostrava"}).json()["lines"]
        assert len(tap) == 3
        urls = [line["audio_url"] for line in tap]
        _, nation, text, emotion = next(x for x in demo_lines() if x[0].startswith("one_berth tick 1"))
        urls.append(voice.audio_url_for(nation, text, emotion))
        for url in urls:
            r = c.get("/api" + url)
            assert r.status_code == 200 and r.content[:3] == b"ID3", url


def test_unknown_nation_is_404(client):
    assert client.post("/api/call", json={**CALL, "to": "atlantis"}).status_code in (404, 422)


def test_mediator_gets_no_wiretap(client, monkeypatch):
    from contracts.models import Seat
    from engine.game import GAME

    async def no_audio(*a, **k):
        raise AssertionError("audio generated for a mediator")
    monkeypatch.setattr(api, "speak", no_audio)
    monkeypatch.setattr(GAME.state, "seat", Seat(role="mediator", nation=None))
    assert client.get("/api/wiretap", params={"a": "zarnia", "b": "ostrava"}).status_code == 403


def test_a_keyless_live_server_says_so_instead_of_faking_a_bad_line(client, monkeypatch):
    """Real agents but no MISTRAL_API_KEY: the reply names the setup problem, with no audio."""
    async def speak_fast(view):
        raise RuntimeError("MISTRAL_API_KEY is not set")

    async def interpret(view, reply_text):
        raise RuntimeError("MISTRAL_API_KEY is not set")

    fake_agents(speak_fast=speak_fast, interpret=interpret)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    r = client.post("/call", json=CALL).json()
    assert "MISTRAL_API_KEY" in r["reply_text"] and "breaking up" not in r["reply_text"]
    assert r["reply_audio_url"] is None and r["promises"] == []
