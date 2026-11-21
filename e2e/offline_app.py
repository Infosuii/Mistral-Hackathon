"""Offline ASGI app for `scripts/demo.sh --offline` (zero network, no API key).

Mounts the real engine, voice and replay routers, switches leader turns to the
engine's advisers (GAMBIT_AGENTS=stub), uses pre-rendered Wiretap scripts, and
serves deterministic in-character phone replies backed by committed audio files
in voice/prerendered/.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ["GAMBIT_AGENTS"] = "stub"
os.environ["VOICE_WIRETAP"] = "demo"
os.environ["VOICE_MOCK"] = "fixed"
os.environ.pop("MISTRAL_API_KEY", None)

from contracts.models import CallOutput  # noqa: E402
import engine.app as eng_app  # noqa: E402
import voice.api as v_api  # noqa: E402
from voice.audio import PRERENDERED, cache_key, find_audio  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CASTING = json.loads((ROOT / "voice" / "casting.json").read_text(encoding="utf-8"))

# Ensure stub mode even if engine.game was imported before env vars were set.
eng_app.GAME._decide_fn = None


def _offline_audio_url(text: str, voice_id: str, emotion: str | None = None, fmt: str = "mp3") -> str | None:
    """Return an audio URL only when an exact recording exists for (text, voice_id, emotion).

    Uncached offline replies return None so the phone displays the written reply cleanly
    instead of playing an unrelated clip such as 'The line is breaking up'.
    """
    exact = f"{cache_key(text, voice_id, emotion, fmt)}.{fmt}"
    if find_audio(exact) is not None:
        return f"/audio/{exact}"
    return None


async def _offline_transcribe(audio: bytes, mime: str | None = None) -> str:
    return "We can offer you the berth in the morning if you hold off."


async def _offline_speak(text: str, voice_id: str, emotion: str | None = None, fmt: str = "mp3") -> str | None:
    return _offline_audio_url(text, voice_id, emotion, fmt)


def _offline_reply(view) -> tuple[str, str, CallOutput]:
    nation = view.nation
    t = (view.transcript or "").lower()
    phase = view.state.phase
    promises: list[dict] = []
    actions: list[dict] = []
    trust = 0.05
    resolve = 0.05
    emotion = "calm"
    reply = "We have noted your position, President. Keep your word."

    if phase == "strategy":
        emotion = "warm"
        reply = "Valdoria's offer is practical. We will open a trade deal on the next turn."
        give_res = "food" if nation == "kessaria" else "oil"
        actions = [{
            "type": "propose_trade",
            "by": nation,
            "target": view.state.seat.nation or "valdoria",
            "params": {"give": {give_res: 10}, "get": {"chips": 10}},
        }]
    elif "tug" in t and nation == "nordhaven":
        emotion = "assertive"
        reply = "Your timing is tight, President, but stability comes first. Nordhaven will dispatch the tugs."
        promises = [{"to": "nordhaven", "what": "send_tugs", "when": "now", "condition": None}]
        actions = [{"type": "send_tugs", "by": "nordhaven"}]
        trust = 0.1
    elif "evening" in t or "tonight" in t or "night" in t or "afternoon" in t:
        slot = "afternoon" if "afternoon" in t else "evening"
        emotion = "calm"
        reply = f"Very well—the {slot} slot is recorded. We will hold you to it."
        promises = [{"to": nation, "what": "berth", "when": slot, "condition": None}]
    elif "morning" in t:
        emotion = "tense" if view.interrupted else "assertive"
        reply = (
            "You dare cut me off—fine, put the morning berth in writing and I hold my ships."
            if view.interrupted
            else "The morning slot is acceptable. Do not cross us."
        )
        promises = [{"to": nation, "what": "berth", "when": "morning", "condition": None}]
        if view.interrupted and nation == "ostrava":
            actions = [{"type": "wait", "by": "ostrava"}]
            resolve = 0.1
            trust = -0.05
    elif "berth" in t or "dock" in t or "whole day" in t or "entire day" in t:
        emotion = "determined"
        reply = "Good. Our grain ships are moving on your word that the berth is ours all day."
        promises = [{"to": nation, "what": "berth", "when": "all_day", "condition": None}]
        resolve = 0.05

    if (view.hesitation_ms or 0) > 2500:
        resolve = round(resolve - 0.15, 3)

    out = CallOutput(
        reply_text=reply,
        emotion=emotion,
        promises=promises,
        actions=actions,
        belief_updates={"trust_in_player": trust, "resolve_of_player": resolve},
        ends_call=False,
    )
    return reply, emotion, out


async def _offline_fast(view) -> dict:
    reply, emotion, _ = _offline_reply(view)
    return {"reply_text": reply, "emotion": emotion}


async def _offline_interpret(view, reply_text: str) -> CallOutput:
    _, _, out = _offline_reply(view)
    return out


v_api._phone = lambda: (_offline_fast, _offline_interpret, True)
v_api.speak = _offline_speak
v_api.transcribe = _offline_transcribe

app = eng_app.app
