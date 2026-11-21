"""Stand-ins for Abi's agents.call_reply() until /agents lands.

fixed_reply() returns the example from MASTER_PLAN.md section 4.6.
quick_reply() makes one small mistral-large-4 call so V0 can time the full
talk -> reply -> audio path. It is not the real leader prompt.
"""
from __future__ import annotations

import json
import os

from .audio import EMOTIONS, _client

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


async def quick_reply(view: dict) -> dict:
    system = (
        f"You are the leader of {view['nation']}, a proud fictional nation, on a tense phone call "
        "with a foreign president about the single remaining berth at Port Kessar. "
        "Answer in character in at most two short sentences. "
        f"Reply only with JSON: {{\"reply_text\": str, \"emotion\": one of {sorted(EMOTIONS)}}}."
    )
    if view.get("interrupted"):
        system += " The president just interrupted you mid-sentence; you noticed."
    model = os.environ.get("VOICE_REPLY_MODEL", "mistral-large-4")
    body = {
        "model": model,
        "response_format": {"type": "json_object"},
        "max_tokens": 800,  # reasoning tokens count against this
        "messages": [
            {"role": "system", "content": system},
            *({"role": "user" if t["role"] == "player" else "assistant", "content": t["text"]}
              for t in (view.get("history") or [])),
            {"role": "user", "content": view["transcript"] or "(silence)"},
        ],
    }
    if model.startswith("mistral-large-4"):
        body["reasoning_effort"] = "low"  # lowest it accepts; none/minimal are rejected
    r = await _client().post("/chat/completions", json=body)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    if isinstance(content, list):  # reasoning models return [thinking..., text]
        content = "".join(p.get("text", "") for p in content if p.get("type") == "text")
    out = json.loads(content)
    return {**EXAMPLE_REPLY, "promises": [],
            "belief_updates": {"trust_in_player": 0, "resolve_of_player": 0},
            "reply_text": out.get("reply_text", ""), "emotion": out.get("emotion", "calm")}


async def wiretap_lines(a: str, b: str) -> list[dict]:
    return [
        {"speaker": a, "text": "The Valdorian promised you the berth too. Did you know that?",
         "emotion": "sarcastic"},
        {"speaker": b, "text": "Then neither of us should trust a word they say.",
         "emotion": "skeptical"},
    ]
