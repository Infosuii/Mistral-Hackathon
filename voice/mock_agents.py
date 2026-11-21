"""Stand-ins for Abi's phone functions until /agents lands.

The phone path is split (DECIDED 12:29): a fast model speaks, Large 4 interprets.
- speak_fast(view) -> {reply_text, emotion}: one small call on PHONE_FAST_MODEL
  (default mistral-large-2512, which Mistral marks deprecated), falling back to
  mistral-large-4 if it errors or returns bad JSON.
- interpret(view, reply_text) -> CallOutput fields: no-op stand-in (no promises,
  no belief change) until Abi's real one exists.
- fixed_reply(view): the MASTER_PLAN.md §4.6 example, no model call at all.
None of these is the real leader prompt.
"""
from __future__ import annotations

import json
import os

from .audio import EMOTIONS, _client

FAST_MODEL = os.environ.get("PHONE_FAST_MODEL", os.environ.get("VOICE_REPLY_MODEL", "mistral-large-2512"))
FALLBACK_MODEL = "mistral-large-4"

EXAMPLE_REPLY = {
    "reply_text": "Half a day is an insult. You promised us the berth.",
    "emotion": "angry",
    "promises": [{"to": "ostrava", "what": "berth", "when": "morning", "condition": None}],
    "actions": [],
    "belief_updates": {"trust_in_player": -0.1, "resolve_of_player": 0.1},
    "ends_call": False,
}


async def fixed_reply(view: dict) -> dict:
    return json.loads(json.dumps(EXAMPLE_REPLY))


def _messages(view: dict) -> list[dict]:
    system = (
        f"You are the leader of {view['nation']}, a proud fictional nation, on a tense phone call "
        "with a foreign president about the single remaining berth at Port Kessar. "
        "Answer in character in at most two short sentences. "
        f"Reply only with JSON: {{\"reply_text\": str, \"emotion\": one of {sorted(EMOTIONS)}}}."
    )
    if view.get("interrupted"):
        system += " The president just interrupted you mid-sentence; you noticed."
    return [
        {"role": "system", "content": system},
        *({"role": "user" if t["role"] == "player" else "assistant", "content": t["text"]}
          for t in (view.get("history") or [])),
        {"role": "user", "content": view["transcript"] or "(silence)"},
    ]


async def _ask(model: str, messages: list[dict]) -> dict:
    body = {"model": model, "response_format": {"type": "json_object"},
            "max_tokens": 800, "messages": messages}  # reasoning tokens count against max_tokens
    if model.startswith("mistral-large-4"):
        body["reasoning_effort"] = "low"  # lowest it accepts; none/minimal are rejected
    r = await _client().post("/chat/completions", json=body)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    if isinstance(content, list):  # reasoning models return [thinking..., text]
        content = "".join(p.get("text", "") for p in content if p.get("type") == "text")
    out = json.loads(content)
    if not isinstance(out.get("reply_text"), str) or not out["reply_text"].strip():
        raise ValueError(f"no reply_text in {content[:200]!r}")
    return {"reply_text": out["reply_text"].strip(), "emotion": out.get("emotion", "calm")}


async def speak_fast(view: dict) -> dict:
    try:
        return await _ask(FAST_MODEL, _messages(view))
    except Exception as e:
        print(f"[voice] {FAST_MODEL} failed ({e}); falling back to {FALLBACK_MODEL}")
        return await _ask(FALLBACK_MODEL, _messages(view))


async def interpret(view: dict, reply_text: str) -> dict:
    return {"promises": [], "actions": [],
            "belief_updates": {"trust_in_player": 0, "resolve_of_player": 0}, "ends_call": False}


async def quick_reply(view: dict) -> dict:
    """Single-call stand-in (reply only), used by voice.roundtrip timing."""
    return {**EXAMPLE_REPLY, "promises": [],
            "belief_updates": {"trust_in_player": 0, "resolve_of_player": 0},
            **(await speak_fast(view))}


async def wiretap_lines(a: str, b: str) -> list[dict]:
    return [
        {"speaker": a, "text": "The Valdorian promised you the berth too. Did you know that?",
         "emotion": "sarcastic"},
        {"speaker": b, "text": "Then neither of us should trust a word they say.",
         "emotion": "skeptical"},
    ]
