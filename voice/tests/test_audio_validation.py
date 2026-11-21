import asyncio

import pytest
from fastapi.testclient import TestClient

from engine.app import app
from voice import api, audio


def test_audio_errors_are_actionable(monkeypatch):
    async def rejected(*args):
        raise audio.BadAudio(422, "No decodable speech.")
    monkeypatch.setattr(api, "transcribe", rejected)
    with TestClient(app) as client:
        assert client.post("/transcribe", content=b"").status_code == 422
        assert client.post("/transcribe", content=b"broken").status_code == 422
        assert client.post("/call", json={"to": "ostrava", "audio": "!!"}).status_code == 422
        assert client.post("/api/transcribe", content=(b"x" * 1024 for _ in range(5121))).status_code == 413
        assert client.post("/api/call", json={"to": "ostrava", "audio": "A" * (7 * 1024 * 1024)}).status_code == 413

    assert audio.sniff_format(b"fLaC") == ("flac", "audio/flac")
    with pytest.raises(audio.BadAudio):
        audio.sniff_format(b"unknown")


def test_failed_synthesis_emits_an_http_error(monkeypatch):
    monkeypatch.setitem(audio.JOBS, "failed-audit.mp3", audio.Job(done=True, error="offline"))
    with TestClient(app) as client:
        assert client.get("/audio/failed-audit.mp3").status_code == 503


def test_demo_pair_without_audio_stays_local(monkeypatch):
    monkeypatch.setenv("VOICE_WIRETAP", "demo")
    async def unexpected(*args, **kwargs):
        pytest.fail("A demo Wiretap attempted a provider request")
    import agents
    monkeypatch.setattr(agents, "wiretap", unexpected)
    monkeypatch.setattr(api, "speak", unexpected)
    result = asyncio.run(api.wiretap("nordhaven", "ostrava"))
    assert [line["speaker"] for line in result["lines"]] == ["nordhaven", "ostrava"]
    assert all(line["text"] and line["audio_url"] is None for line in result["lines"])
