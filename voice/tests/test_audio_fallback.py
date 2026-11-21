"""A reply the TTS refuses (e.g. a 403 guardrail block) plays the leader's pre-rendered
"line is breaking up" clip instead of silence. No network.

    python -m pytest voice/tests -q
"""
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import voice.audio as audio
from voice.api import router

CASTING = json.loads((Path(audio.__file__).parent / "casting.json").read_text())


def test_blocked_synthesis_plays_the_fallback_line(monkeypatch):
    async def blocked(text, voice_id, emotion=None, fmt="mp3"):
        raise RuntimeError("speak failed 403: Request blocked by guardrail policy")
        yield b""  # an async generator, like stream_speech

    monkeypatch.setattr(audio, "stream_speech", blocked)
    voice_id = CASTING["ostrava"]["voice_id"]
    expected = audio.find_audio(
        f"{audio.cache_key(audio.FALLBACK_LINE[0], voice_id, audio.FALLBACK_LINE[1])}.mp3")
    assert expected is not None, "run python -m voice.prerender"

    app = FastAPI()
    app.include_router(router)

    @app.post("/say")
    async def say():
        return {"url": await audio.speak("A line the guardrail refuses.", voice_id, "angry")}

    with TestClient(app) as c:
        url = c.post("/say").json()["url"]
        r = c.get(url)
    assert r.status_code == 200 and r.content == expected.read_bytes()
