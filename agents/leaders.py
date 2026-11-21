"""The functions the engine and voice code call (MASTER_PLAN.md section 4.1).

All are async. decide() and call_reply() return valid output or raise quickly (one
retry on bad JSON, inside one deadline), so callers can fall back. headline(), why(),
historian() and wiretap() never raise: they fall back to a template line.

Personality lives in agents/personas/*.md (the design file; edit those, not this code).
"""
from __future__ import annotations

import json
import os
import random
import re
import time
from typing import Any, Optional

from contracts.models import (
    NATION_IDS, Action, CallOutput, CallView, Emotion, LeaderOutput, LeaderView, Message,
)

from . import llm
from .personas import PROUD, card, defies_when, temper

EMOTIONS: tuple[str, ...] = Emotion.__args__  # type: ignore[attr-defined]

# The engine waits 8 s (engine/game.py); finish or raise before that.
DECIDE_BUDGET_S = float(os.environ.get("GAMBIT_AGENTS_DECIDE_S", "7.5"))
CALL_BUDGET_S = float(os.environ.get("GAMBIT_AGENTS_CALL_S", "6"))
MAX_OPTIONS = 10
HESITATION_MS = 2500  # ideas.md 6b

# What each leader privately intended in earlier months, per game seed. Lets a leader
# keep a plan across turns without a contract change. Cleared when the seed changes.
_MEMORY: dict[tuple[int, str], list[tuple[int, str]]] = {}


def _j(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def _dump(state: Any) -> dict:
    return state.model_dump(mode="json", by_alias=True) if hasattr(state, "model_dump") else dict(state)


def _who(state: dict, nation: str) -> str:
    n = state.get("nations", {}).get(nation, {})
    return f"{n.get('leader', 'the leader')} of {n.get('name', nation.title())} (nation id: {nation})"


def _brief(state: dict, nation: str) -> dict:
    """What a leader knows: public numbers, own beliefs, own relations, news, and in a
    crisis only the promises made to it and the public commitments."""
    nations = {}
    for nid, n in state.get("nations", {}).items():
        st = n.get("stats") or {}
        nations[nid] = {"leader": n.get("leader"), "system": n.get("system"),
                        "stats": {k: st.get(k) for k in ("gdp", "food", "oil", "chips", "army", "stability", "approval")},
                        "status": n.get("status", []), "says": n.get("public_statement", "")}
    me = state.get("nations", {}).get(nation, {})
    seat = state.get("seat") or {}
    brief: dict[str, Any] = {
        "you": nation, "month": state.get("turn"), "phase": state.get("phase"),
        "player": f"{seat.get('role', 'president')} of {seat.get('nation')}",
        "your_beliefs_about_player": me.get("beliefs"),
        "nations": nations,
        "your_relations": {k: v for k, v in state.get("relations", {}).items() if nation in k.split("|")},
        "links": [f"{l['type']}: {l['a']}-{l['b']}" for l in state.get("links", [])],
        "news": [n.get("text") for n in state.get("news", [])[-6:]],
    }
    c = state.get("crisis")
    if c:
        brief["crisis"] = {
            "id": c.get("id"), "hour": c.get("tick"), "of": c.get("ticks_total"),
            "your_deadline": (c.get("deadlines") or {}).get(nation),
            "promises_to_you": [p for p in c.get("promises", []) if p.get("to") == nation],
            "public_commitments": c.get("public_commitments", []),
            "already_decided": {k: v.get("action") for k, v in (c.get("decisions") or {}).items()},
        }
    return brief


def _label(a: dict) -> str:
    p = a.get("params") or {}
    t = a.get("type", "")
    tgt = a.get("target")
    if t == "propose_trade" and p:
        give = ", ".join(f"{v} {k}" for k, v in (p.get("give") or {}).items()) if isinstance(p.get("give"), dict) else p.get("give")
        get = ", ".join(f"{v} {k}" for k, v in (p.get("get") or {}).items()) if isinstance(p.get("get"), dict) else p.get("get")
        return f"propose trade with {tgt}: give {give}, get {get}"
    if t == "set_tariff":
        return f"tariff {p.get('pct', '?')}% on {tgt}"
    s = t.replace("_", " ")
    return f"{s} {tgt}" if tgt else s


# --- decide ------------------------------------------------------------------

DECIDE_RULES = """GAMBIT is a strategy game of five fictional nations. You are {who}. Stay in character.
It is your move. Your advisers have scored every option, best first. You may follow them or take any other option. Real leaders sometimes overrule their advisers out of pride, fear, ambition or a grudge, and your persona says when you do; when you do, say why in "reason", in your own voice.
Your public statement is what the world hears. Your private intent is what you really plan. They often differ: bluff, flatter or threaten in public if it serves your plan.
Messages are private notes to other leaders (they never reach the player directly): use them to bargain, threaten or scheme. Send zero to two.
Reply with ONLY this JSON object:
{{"choice": int (number of the option you take), "public_statement": str (one or two sentences, in your voice), "private_intent": str (one sentence), "reason": str (one short sentence), "messages": [{{"to": nation id, "text": str}}]}}"""


def _parse_decide(data: dict, options: list[dict], scores: list[float], nation: str) -> LeaderOutput:
    choice = data.get("choice")
    if isinstance(choice, str) and choice.strip().lstrip("-").isdigit():
        choice = int(choice.strip())
    if not isinstance(choice, int) or not 0 <= choice < len(options):
        raise ValueError(f'"choice" must be an option number from 0 to {len(options) - 1}')
    for k in ("public_statement", "private_intent", "reason"):
        if not str(data.get(k) or "").strip():
            raise ValueError(f'"{k}" must be a non-empty string')
    act = dict(options[choice], by=nation)
    msgs = []
    for m in data.get("messages") or []:
        if isinstance(m, dict) and m.get("to") in NATION_IDS and m.get("to") != nation and str(m.get("text") or "").strip():
            msgs.append(Message(to=m["to"], text=str(m["text"]).strip()))
    return LeaderOutput(
        public_statement=str(data["public_statement"]).strip(),
        private_intent=str(data["private_intent"]).strip(),
        actions=[] if act["type"] == "wait" else [Action.model_validate(act)],
        # A pick that ties the top score is the advisers' advice too (wait and a trade can both be 0).
        followed_advice=choice == 0 or (bool(scores) and scores[choice] >= scores[0] - 0.05),
        reason=str(data["reason"]).strip(),
        messages=msgs[:2],
    )


async def decide(view: LeaderView | dict) -> LeaderOutput:
    """One leader's move. Raises llm.LLMError within DECIDE_BUDGET_S on failure."""
    deadline = time.perf_counter() + DECIDE_BUDGET_S
    v = view if isinstance(view, LeaderView) else LeaderView.model_validate(view)
    state = _dump(v.state)
    options = [a.action.model_dump(mode="json") for a in v.advice[:MAX_OPTIONS]]
    if not options:
        options = [{"type": "wait", "by": v.nation, "target": None, "params": {}}]
    key = (int(state.get("seed", 0)), v.nation)
    if key not in _MEMORY:
        for k in [k for k in _MEMORY if k[0] != key[0]]:
            del _MEMORY[k]
    past = [f"month {t}: {i}" for t, i in _MEMORY.get(key, []) if t < (state.get("turn") or 0)][-3:]
    user = {
        "situation": _brief(state, v.nation),
        "private_messages_received": [f"{m.from_}: {m.text}" for m in v.messages_received][-6:],
        "your_earlier_private_intents": past,
        "options_ranked_by_your_advisers": [
            f"{i}. {_label(o)} (adviser score {a.score:+.1f})" for i, (o, a) in enumerate(zip(options, v.advice))
        ] or ["0. wait"],
    }
    if len(options) > 1 and random.random() < temper(v.nation):
        user["your_instinct_this_month"] = (
            f"You distrust your advisers' first choice. You defy advice when {defies_when(v.nation)} "
            "Look for a reason in the situation and take a different option, unless it would be suicidal.")
    out = await llm.chat_json(
        [{"role": "system", "content": card(v.nation) + "\n\n" + DECIDE_RULES.format(who=_who(state, v.nation))},
         {"role": "user", "content": _j(user)}],
        lambda d: _parse_decide(d, options, [a.score for a in v.advice[:len(options)]], v.nation),
        deadline=deadline, max_tokens=500, temperature=0.9)
    _MEMORY.setdefault(key, []).append((state.get("turn") or 0, out.private_intent))
    return out


# --- call_reply --------------------------------------------------------------

CALL_RULES = """You are {who}, on a live phone call with the player, the {player}. Stay in character.
Answer in at most TWO short spoken sentences. Plain speech: no stage directions, no lists, no emoji.
Pick one emotion for your voice from: {emotions}.
"promises": what the PLAYER committed to in what they just said, as {{"to": nation id the promise is made to, "what": short noun phrase, "when": short or "now", "condition": short or null}}. Only record real commitments; usually none.
"action": the number of an option you agree to take right now, or null (usually null; only if you were persuaded).
"trust_delta" in -0.3..0.3: how much more or less you trust the player after this. A contradiction of an earlier promise, or a promise you know they made to a rival, is strongly negative.
"resolve_delta" in -0.2..0.2: how firm the player sounded (a credible threat or clear red line is positive; pleading or vagueness is negative).
"ends_call": true only if you hang up or the conversation is clearly over.
Reply with ONLY this JSON object: {{"reply_text": str, "emotion": str, "promises": [], "action": int or null, "trust_delta": number, "resolve_delta": number, "ends_call": bool}}"""


def _two_sentences(text: str) -> str:
    text = re.sub(r"\s+", " ", re.sub(r"\*[^*]*\*|\([^)]*\)|\[[^\]]*\]", "", text)).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:2]).strip()


def _legal(state: Any, nation: str) -> list[dict]:
    """The engine's ranked legal actions, if the engine is importable."""
    try:
        from engine.core import advise  # type: ignore
        return [a.action.model_dump(mode="json") for a in advise(state, nation)][:MAX_OPTIONS]
    except Exception:  # noqa: BLE001
        return []


def _clamp(x: Any, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return 0.0


def _parse_call(data: dict, v: CallView, options: list[dict]) -> CallOutput:
    reply = _two_sentences(str(data.get("reply_text") or ""))
    if not reply:
        raise ValueError('"reply_text" must be one or two spoken sentences')
    proud = v.nation in PROUD
    emotion = data.get("emotion") if data.get("emotion") in EMOTIONS else ("tense" if proud else "calm")
    promises = []
    for p in data.get("promises") or []:
        if not isinstance(p, dict) or not str(p.get("what") or "").strip():
            continue
        promises.append({"to": p.get("to") if p.get("to") in NATION_IDS else v.nation,
                         "what": str(p["what"]).strip(), "when": str(p.get("when") or "now").strip(),
                         "condition": (str(p["condition"]).strip() or None) if p.get("condition") else None})
    actions = []
    a = data.get("action")
    if isinstance(a, int) and 0 <= a < len(options) and options[a]["type"] != "wait":
        actions.append(dict(options[a], by=v.nation))
    # ideas.md 6b: trust from what was said; resolve from how it was said.
    trust = _clamp(data.get("trust_delta"), -0.3, 0.3)
    resolve = _clamp(data.get("resolve_delta"), -0.2, 0.2)
    if v.interrupted:
        resolve += 0.10
        if proud:
            trust -= 0.05  # an insult; the engine also cuts relations by 5
    if (v.hesitation_ms or 0) > HESITATION_MS:
        resolve -= 0.15
    return CallOutput.model_validate({
        "reply_text": reply, "emotion": emotion, "promises": promises, "actions": actions,
        "belief_updates": {"trust_in_player": round(_clamp(trust, -1, 1), 3),
                           "resolve_of_player": round(_clamp(resolve, -1, 1), 3)},
        "ends_call": bool(data.get("ends_call", False)),
    })


async def call_reply(view: CallView | dict) -> CallOutput:
    """The called leader's spoken answer. Raises llm.LLMError within CALL_BUDGET_S."""
    deadline = time.perf_counter() + CALL_BUDGET_S
    v = view if isinstance(view, CallView) else CallView.model_validate(view)
    state = _dump(v.state)
    proud = v.nation in PROUD
    cues = []
    if v.interrupted:
        cues.append("The player cut you off mid-sentence." +
                    (" You take that as an insult, but note they sound determined." if proud else ""))
    if (v.hesitation_ms or 0) > HESITATION_MS:
        cues.append(f"The player hesitated {v.hesitation_ms / 1000:.1f} seconds before answering." +
                    (" You read that as weakness and push harder." if proud else " They seem unsure."))
    options = _legal(v.state, v.nation)
    seat = state.get("seat") or {}
    user = {
        "situation": _brief(state, v.nation),
        "call_so_far": [f"{t.role}: {t.text}" for t in (v.history or [])][-8:],
        "player_just_said": v.transcript,
        "how_they_said_it": cues or ["normally"],
        "options_you_could_agree_to_now": [f"{i}. {_label(o)}" for i, o in enumerate(options)],
    }
    system = card(v.nation) + "\n\n" + CALL_RULES.format(
        who=_who(state, v.nation), player=f"{seat.get('role', 'president')} of {seat.get('nation', 'another nation')}",
        emotions=", ".join(EMOTIONS))
    return await llm.chat_json(
        [{"role": "system", "content": system}, {"role": "user", "content": _j(user)}],
        lambda d: _parse_call(d, v, options),
        deadline=deadline, model=llm.CALL_MODEL, max_tokens=300, temperature=0.8)


# --- headline, why, historian, wiretap (never raise) -------------------------

async def _one_field(system: str, user: str, field: str, timeout: float, max_tokens: int = 200) -> str:
    raw = await llm.chat([{"role": "system", "content": system + f' Reply as JSON {{"{field}": str}}.'},
                          {"role": "user", "content": user}],
                         timeout=timeout, max_tokens=max_tokens, temperature=0.8)
    out = str(llm.loads(raw)[field]).strip().strip('"')
    if not out:
        raise ValueError("empty")
    return out


async def headline(event: dict) -> str:
    """One newspaper headline for an engine event."""
    try:
        return await _one_field(
            "Write one punchy newspaper headline (at most 10 words, no quotes) for this event in a fictional "
            "world of five nations: Valdoria, Ostrava, Kessaria, Nordhaven, Zarnia.", _j(event), "headline", 8.0, 80)
    except Exception:  # noqa: BLE001
        return f"{str(event.get('type', 'event')).replace('_', ' ').title()} in {str(event.get('nation') or 'the region').title()}"


async def why(change: dict) -> str:
    """One line for the replay panel. change = {nation, was, now, inputs?}."""
    n = str(change.get("nation", ""))
    fallback = f"{n.title()} switched from {change.get('was')} to {change.get('now')}."
    try:
        return await _one_field(
            "In one sentence of at most 18 words, say why this leader changed their crisis decision when the "
            "player's offer arrived at a different time. Use the inputs given; be concrete; name the leader's motive.",
            card(n) + "\n\n" + _j(change), "why", 8.0, 120)
    except Exception:  # noqa: BLE001
        return fallback


async def historian(log: list[dict]) -> str:
    """One paragraph judging the player's session, for the end screen."""
    try:
        return await _one_field(
            "You are a historian writing, years later, one paragraph (80-120 words) judging the player's time "
            "as a leader in this fictional world. Name the turning point and one leader who was deceived or "
            "betrayed, if any. Wry and specific; no bullet points.",
            _j(log[-60:]), "verdict", 20.0, 400)
    except Exception:  # noqa: BLE001
        return ("History records a short and turbulent tenure, the details of which "
                "the archives have not yet released.")


WIRETAP_RULES = """Write a short intercepted private phone call between two leaders in GAMBIT, a game of five fictional nations, about the player ({player}).
Speaker A: {a_who}. Persona:
{a_card}

Speaker B: {b_who}. Persona:
{b_card}

Four lines, alternating A, B, A, B, each at most two short spoken sentences, each in that leader's own voice. They do not know they are overheard, so they say what they really think: what the player promised each of them, whether to trust the player, and what they will do. Use only facts in the situation and their private messages.
Each line gets one emotion from: {emotions}.
Reply with ONLY JSON: {{"lines": [{{"speaker": "A" or "B", "text": str, "emotion": str}}]}}"""


def _game_context() -> tuple[Optional[dict], dict[str, str]]:
    """The live state and each leader's last private intent, if the engine is running."""
    try:
        from engine.game import GAME  # type: ignore
        intents = {n: d.private_intent for n, d in GAME.leaders.items() if d.private_intent}
        return _dump(GAME.state), intents
    except Exception:  # noqa: BLE001
        return None, {}


async def wiretap(a: str, b: str, state: Any = None, messages: Optional[list[dict]] = None) -> list[dict]:
    """Two leaders discuss the player. Returns [{speaker, text, emotion}], 4 lines.
    state defaults to the live game; messages are their private notes [{from, to, text}]."""
    live, intents = _game_context()
    st = _dump(state) if state is not None else (live or {})
    seat = st.get("seat") or {}
    fallback = [
        {"speaker": a, "text": "The Valdorians promise everyone everything. Did they promise you the same?", "emotion": "skeptical"},
        {"speaker": b, "text": "Word for word. Then neither of us should trust a thing they say.", "emotion": "sarcastic"},
    ]
    if a not in NATION_IDS or b not in NATION_IDS or a == b:
        return fallback
    try:
        situation = _brief(st, a) if st else {}
        promises = [p for p in ((st.get("crisis") or {}).get("promises") or []) if p.get("to") in (a, b)]
        ctx = {"situation": situation, "promises_the_player_made_to_them": promises,
               "their_private_messages": [m for m in (messages or []) if {m.get("from"), m.get("to")} <= {a, b}],
               "their_private_intents": {k: v for k, v in intents.items() if k in (a, b)}}
        system = WIRETAP_RULES.format(
            player=f"{seat.get('role', 'president')} of {seat.get('nation', 'valdoria')}",
            a_who=_who(st, a), b_who=_who(st, b), a_card=card(a), b_card=card(b), emotions=", ".join(EMOTIONS))
        raw = await llm.chat([{"role": "system", "content": system}, {"role": "user", "content": _j(ctx)}],
                             timeout=10.0, max_tokens=500, temperature=0.9)
        lines = []
        for ln in llm.loads(raw).get("lines") or []:
            who = {"A": a, "B": b}.get(str(ln.get("speaker")).strip().upper(), ln.get("speaker"))
            text = _two_sentences(str(ln.get("text") or ""))
            if who in (a, b) and text:
                emo = ln.get("emotion") if ln.get("emotion") in EMOTIONS else "tense"
                lines.append({"speaker": who, "text": text, "emotion": emo})
        return lines[:4] if len(lines) >= 2 else fallback
    except Exception:  # noqa: BLE001
        return fallback
