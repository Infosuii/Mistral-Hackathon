"""The functions the engine and voice code call (MASTER_PLAN.md section 4.1).

All are async. decide() and call_reply() return valid output or raise quickly (one
retry on bad JSON, inside one deadline), so callers can fall back. headline(), why(),
historian() and wiretap() never raise: they fall back to a template line.

Personality lives in agents/personas/*.md (the design file; edit those, not this code).
"""
from __future__ import annotations

import asyncio
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
SPEAK_HEDGE_S = float(os.environ.get("GAMBIT_SPEAK_HEDGE_S", "2.5"))  # medium joins the spoken reply
# Large 4 first; the hedge model joins if Large 4 has not answered by then.
# Shorter head start for a reasoning model (Large 4 almost never answers in time).
HEDGE_AFTER_S = float(os.environ.get("GAMBIT_HEDGE_AFTER_S", "2.5" if llm.reasons(llm.DECIDE_MODEL) else "3.5"))
INTERPRET_BUDGET_S = float(os.environ.get("GAMBIT_AGENTS_INTERPRET_S", "45"))
INTERPRET_HEDGE_S = float(os.environ.get("GAMBIT_INTERPRET_HEDGE_S", "12"))
MAX_OPTIONS = 10
HESITATION_MS = 2500  # ideas.md 6b
# An option this many points below the advisers' top needs a strategic or factual reason.
DECISIVE_GAP = float(os.environ.get("GAMBIT_DECISIVE_GAP", "3"))

def _j(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def _dump(state: Any) -> dict:
    return state.model_dump(mode="json", by_alias=True) if hasattr(state, "model_dump") else dict(state)


def _who(state: dict, nation: str) -> str:
    n = state.get("nations", {}).get(nation, {})
    return f"{n.get('leader', 'the leader')} of {n.get('name', nation.title())} (nation id: {nation})"


SEAT_ADDRESS = {  # how leaders address the player on the phone, by seat
    "president": '"President"',
    "diplomat": '"Minister" (they are an envoy, not a head of state)',
    "mediator": 'plainly, without a title of state (they represent no nation)',
}

SEAT_STYLE = {  # how leaders see the player in each seat (ideas.md section 4)
    "president": "Treat them as a head of state: their promises commit {nation}.",
    "diplomat": "They are {nation}'s envoy; their president can overrule them, so their promises are worth less and you may "
                "ask whether their president agrees.",
    "mediator": "They are a neutral mediator with no army, no money and no nation behind them, only their word. Press them "
                "to carry your demands to the other side, test whether they are truly neutral, and trust them less the "
                "moment they seem to favour anyone. Their promises are about what they will broker, not what they will give.",
}


def _player(state: dict) -> str:
    """Who the player is, for the prompts: 'the president of Valdoria', 'a neutral mediator', ..."""
    seat = state.get("seat") or {}
    role, nid = seat.get("role", "president"), seat.get("nation")
    name = (state.get("nations", {}).get(nid) or {}).get("name", str(nid or "").title())
    if role == "mediator":
        return "a neutral mediator"
    return f"the {role} of {name}" if name else f"the {role}"


def _seat_style(state: dict) -> str:
    seat = state.get("seat") or {}
    nid = seat.get("nation")
    name = (state.get("nations", {}).get(nid) or {}).get("name", str(nid or "").title())
    return SEAT_STYLE.get(seat.get("role", "president"), SEAT_STYLE["president"]).format(nation=name)


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
        "player": _player(state),
        "how_to_treat_the_player": _seat_style(state),
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
            "facts": _crisis_facts(state),
        }
    return brief


def _crisis_facts(state: dict) -> list[str]:
    """Plain facts that change the calculus, stated outright (Reviewer's REQUEST): whether a
    second berth exists, and what the port's owner decided."""
    c = state.get("crisis") or {}
    try:
        from engine.crisis import crisis_file  # type: ignore
        rules = crisis_file(c["id"]).rules
    except Exception:  # noqa: BLE001
        return []
    facts = []
    dec = c.get("decisions") or {}
    tugs = rules.get("second_berth_requires")
    if tugs:
        d = dec.get(tugs["nation"]) or {}
        who = (state.get("nations", {}).get(tugs["nation"]) or {}).get("name", tugs["nation"].title())
        if d.get("action") == tugs["action"] and d.get("tick", 99) <= tugs["by_tick"]:
            facts.append(f"A SECOND BERTH IS OPEN: {who} sent the tugs. Both grain ships can dock; nobody has to wait or fight for the berth.")
        elif c.get("tick", 0) > tugs["by_tick"] or d:
            facts.append(f"There is only one berth: {who} did not send the tugs in time.")
        else:
            facts.append(f"Only one berth for now; {who} can open a second by sending tugs before hour {tugs['by_tick']}.")
    k = (dec.get("kessaria") or {}).get("action")
    if k:
        facts.append(f"Kessaria, which owns the port, decided: {k.replace('_', ' ')}.")
    return facts


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
Your advisers' scores already include your pride, your public commitments and the cost of backing down in public: do not count those twice.
An option marked FAR BELOW is one your advisers strongly advise against. Take it only for a reason tied to your private strategy or a concrete fact in the situation, and name that reason; pride, honour or looking strong are never enough on their own. Read the crisis facts first: they can make an option safe or pointless.
If you have a private strategy, pursue it: pick the option that advances it unless events have overtaken it, and let your private intent say how this move serves it.
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
    strategy = _private_strategy(view)
    if isinstance(view, dict) and "private_strategy" not in LeaderView.model_fields:
        view = {k: x for k, x in view.items() if k != "private_strategy"}
    v = view if isinstance(view, LeaderView) else LeaderView.model_validate(view)
    state = _dump(v.state)
    options = [a.action.model_dump(mode="json") for a in v.advice[:MAX_OPTIONS]]
    if not options:
        options = [{"type": "wait", "by": v.nation, "target": None, "params": {}}]
    top = v.advice[0].score if v.advice else 0.0
    user = {
        "situation": _brief(state, v.nation),
        "your_private_strategy": strategy,
        "private_messages_received": [f"{m.from_}: {m.text}" for m in v.messages_received][-6:],
        "your_earlier_private_intents": v.earlier_private_intents,
        "options_ranked_by_your_advisers": [
            f"{i}. {_label(o)} (adviser score {a.score:+.1f}"
            + (f", {top - a.score:.1f} below the advisers' choice: FAR BELOW" if top - a.score > DECISIVE_GAP else "") + ")"
            for i, (o, a) in enumerate(zip(options, v.advice))
        ] or ["0. wait"],
    }
    close = [i for i, a in enumerate(v.advice[:len(options)]) if i > 0 and top - a.score <= DECISIVE_GAP]
    if close and random.random() < temper(v.nation):
        user["your_instinct_this_month"] = (
            f"You distrust your advisers' first choice. You defy advice when {defies_when(v.nation)} "
            f"Look for a reason in the situation and consider option {' or '.join(map(str, close))} instead.")
    msgs = [{"role": "system", "content": card(v.nation) + "\n\n" + DECIDE_RULES.format(who=_who(state, v.nation))},
            {"role": "user", "content": _j(user)}]
    scores = [a.score for a in v.advice[:len(options)]]
    out = await llm.hedged(lambda m: llm.chat_json(
        msgs, lambda d: _parse_decide(d, options, scores, v.nation),
        deadline=deadline, model=m, max_tokens=500, temperature=0.9),
        primary=llm.DECIDE_MODEL, backup=llm.DECIDE_BACKUP if llm.DECIDE_MODEL == llm.HEDGE_MODEL else None,
        after=HEDGE_AFTER_S)
    out = await _reconsider(out, msgs, options, scores, state, v.nation, deadline)
    return out


async def _reconsider(out: LeaderOutput, msgs: list[dict], options: list[dict], scores: list[float],
                      state: dict, nation: str, deadline: float) -> LeaderOutput:
    """If the leader took an option FAR BELOW the advisers' choice, the chief of staff objects
    once with the facts and the leader may choose again (Reviewer's REQUEST). Keeps the first
    answer if time is short or the second call fails."""
    pick = out.actions[0].type if out.actions else "wait"
    idx = next((i for i, o in enumerate(options) if o["type"] == pick
                and (not out.actions or o.get("target") == out.actions[0].target)), None)
    if idx is None or not scores or scores[0] - scores[idx] <= DECISIVE_GAP or deadline - time.perf_counter() < 2.0:
        return out
    facts = " ".join(_crisis_facts(state)) if state.get("crisis") else ""
    objection = (
        f"Your chief of staff objects before the order goes out: \"{_label(options[idx])}\" is "
        f"{scores[0] - scores[idx]:.1f} points below your advisers' choice, \"{_label(options[0])}\", and their scores "
        f"already include the cost of backing down in public. {facts} "
        "Keep your order only if your private strategy truly requires it and say exactly how; otherwise choose again. "
        "Reply with the same JSON object.")
    again = msgs + [{"role": "assistant", "content": _j({"choice": idx, "public_statement": out.public_statement,
                                                          "private_intent": out.private_intent, "reason": out.reason})},
                    {"role": "user", "content": objection}]
    try:
        return await llm.chat_json(again, lambda d: _parse_decide(d, options, scores, nation), deadline=deadline,
                                   model=llm.HEDGE_MODEL, max_tokens=500, temperature=0.7)
    except llm.LLMError:
        return out


# --- the phone: speak_fast + interpret (DECIDED 12:29), and the one-call call_reply ---

CALL_VOICE = """You are {who}, on a live phone call with the player, {player}. Stay in character.
Answer in at most TWO short spoken sentences. Plain speech: no stage directions, no lists, no emoji.
Talk to them, not at them: answer what they actually said. Address them {address}.
Vary how you open each reply: do not start with the form of address or a stock phrase more than once in a call, and never begin with any opening listed in avoid_openings.
Never read statistics aloud, and never invent facts: mention only events, places, numbers and times that are in the situation or the call so far (no made-up weather, distances, travel times, quantities or deadlines). If a detail is not there, say you will check, or ask them.
Pick one emotion for your voice from: {emotions}."""

SPEAK_JSON = """Reply with ONLY this JSON object: {"reply_text": str, "emotion": str}"""

JUDGE_RULES = """"promises": what the PLAYER committed to YOU in what they just said, as {"what": short noun phrase, "when": short or "now", "condition": short or null}. Only record real commitments to you; usually none. A promise is something the player says THEY will do or give. A request or demand the player makes of YOU ("hold your ships", "stand down", "wait") is not a promise by the player: record nothing for it unless they offer something in return.{vocab}
"action": the number of an option you agree to take right now, or null (usually null; only if you were persuaded).
"trust_delta" in -0.3..0.3: how much more or less you trust the player after this. A contradiction of an earlier promise, or a promise you know they made to a rival, is strongly negative.
"resolve_delta" in -0.2..0.2: how firm the player sounded (a credible threat or clear red line is positive; pleading or vagueness is negative).
"ends_call": true only if you hang up or the conversation is clearly over."""

CALL_JSON = """Reply with ONLY this JSON object: {"reply_text": str, "emotion": str, "promises": [], "action": int or null, "trust_delta": number, "resolve_delta": number, "ends_call": bool}"""

INTERPRET_JSON = """You already answered the player out loud with: "{reply}"
Now, as this leader, judge what happened on this line. Reply with ONLY this JSON object: {{"promises": [], "action": int or null, "trust_delta": number, "resolve_delta": number, "ends_call": bool}}"""


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


def _call_view(view: CallView | dict) -> CallView:
    return view if isinstance(view, CallView) else CallView.model_validate(view)


def _judge_rules(state: dict, nation: str) -> str:
    vocab = _crisis_vocab(state, nation)
    extra = ("" if vocab is None else
             f'\nIn this crisis "what" must be one of {vocab} (the berth itself, or a crisis action), and for the berth '
             f'"when" must be one of {list(SLOTS)} (all_day if no time was given). "condition" is null unless the player '
             "made it conditional. If the player asks you to take one of your own moves and offers something for it, "
             "record a promise with \"what\" set to that move, even if you have not agreed yet. If they only ask or demand "
             "that move and offer nothing for it, record no promise.")
    return JUDGE_RULES.replace("{vocab}", extra)


def _opening_words(text: str) -> str:
    words = text.strip().split()
    if not words:
        return ""
    return " ".join(words[:2]).rstrip(",.;:!?—-")


def _avoid_openings(v: CallView) -> list[str]:
    """Return the last two opening phrases this leader used in CallView.history (#28)."""
    if not v.history:
        return []
    seen: list[str] = []
    leader_lines = [t.text for t in v.history if t.role == "leader" and t.text.strip()]
    for line in leader_lines[-2:]:
        op = _opening_words(line)
        if op and op not in seen:
            seen.append(op)
    return seen


def _call_context(v: CallView) -> tuple[str, dict, list[dict]]:
    """(system prompt head, user payload, legal options) shared by every phone function."""
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
    avoid = _avoid_openings(v)
    user = {
        "situation": _brief(state, v.nation),
        "call_so_far": [f"{t.role}: {t.text}" for t in (v.history or [])][-8:],
        "player_just_said": v.transcript,
        "how_they_said_it": cues or ["normally"],
        "options_you_could_agree_to_now": [f"{i}. {_label(o)}" for i, o in enumerate(options)],
    }
    if avoid:
        user["avoid_openings"] = avoid
    system = card(v.nation) + "\n\n" + CALL_VOICE.format(
        who=_who(state, v.nation), player=_player(state),
        address=SEAT_ADDRESS.get((state.get("seat") or {}).get("role", "president"), SEAT_ADDRESS["president"]),
        emotions=", ".join(EMOTIONS))
    return system, user, options


def _parse_voice(data: dict, v: CallView) -> dict:
    reply = _two_sentences(str(data.get("reply_text") or ""))
    if not reply:
        raise ValueError('"reply_text" must be one or two spoken sentences')
    emotion = data.get("emotion") if data.get("emotion") in EMOTIONS else ("tense" if v.nation in PROUD else "calm")
    return {"reply_text": reply, "emotion": emotion}


SLOTS = ("morning", "afternoon", "evening", "all_day")  # engine/crisis.py compatible_when
_SLOT_WORDS = [("all_day", r"all[ _-]?day|whole day|full day|entire day|24 ?h|all 24|day and night|whole time"),
               ("morning", r"morning|dawn|sunrise|first light|first half|a\.?m\b"),
               ("afternoon", r"afternoon|midday|noon|second half|p\.?m\b"),
               ("evening", r"evening|night|dusk|nightfall|sunset|tonight")]


def _crisis_vocab(state: dict, nation: str) -> Optional[list[str]]:
    """In a crisis, the promise subjects the engine understands: "berth" and this leader's
    own crisis action ids (engine/crisis.py matches promise.what exactly against
    actions[promise.to]). None outside a crisis."""
    c = state.get("crisis")
    if not c:
        return None
    try:
        from engine.crisis import crisis_file  # type: ignore
        cf = crisis_file(c["id"])
        ids = list(cf.actions.get(nation, []))
        needs = cf.rules.get("needs_berth", [])
    except Exception:  # noqa: BLE001
        ids, needs = [], []
    # Only nations that need the berth can be promised it (a "second berth" asked of
    # Nordhaven is the tugs, not a berth for Nordhaven).
    return (["berth"] if nation in needs else []) + ids


def _norm_what(what: str, vocab: list[str]) -> Optional[str]:
    w = what.strip().lower()
    key = re.sub(r"[^a-z]+", "_", w).strip("_")
    if "berth" in vocab and re.search(r"berth|dock|port|slot|mooring|harbou?r|unload", w):
        return "berth"  # first: "dock at dawn" and "assign_berth_x" mean the berth itself
    if key in vocab:
        return key
    for a in sorted(vocab, key=len, reverse=True):  # "send the tugs" -> send_tugs
        if a != "berth" and all(part in key for part in a.split("_")):
            return a
    return None


def _norm_when(when: str, what: str) -> str:
    text = f"{when} {what}".lower()
    for slot, pat in _SLOT_WORDS:
        if re.search(pat, text):
            return slot
    return "all_day"  # "the berth is yours" with no time: the whole day


# Words that name a crisis move a player might ask a leader for (Reviewer's REQUEST: the tugs
# request must always register). Moves a player would not ask for (blockade, close_port...)
# are left to the model.
ASKABLE = {
    "send_tugs": r"\btugs?\b|\btow(ing|s)?\b|second berth",
    "wait": r"\bwait\b|hold (off|back)|stand (down|by)",
    "split_day": r"split (the )?day|share the berth|half (a )?day each",
}
OFFER = re.compile(r"\b(pay|pays|paying|paid|cover|covers|in return|in exchange|offer|give you|guarantee|compensat\w*|"
                   r"reward|cost of|we will|i will|i'll|we'll|you'll get|you will get)\b", re.I)


def _requested_moves(transcript: str, nation: str, state: dict) -> list[str]:
    """Crisis moves of `nation` that the player asked for while offering something."""
    c = state.get("crisis")
    if not c or not OFFER.search(transcript or ""):
        return []
    try:
        from engine.crisis import crisis_file  # type: ignore
        own = crisis_file(c["id"]).actions.get(nation, [])
    except Exception:  # noqa: BLE001
        return []
    return [a for a in own if a in ASKABLE and re.search(ASKABLE[a], transcript, re.I)]


def _parse_promises(data: dict, v: CallView, state: dict) -> list[dict]:
    """Only promises made to the leader on the line count: the other leaders did not hear
    them. In a crisis, what/when are mapped onto the engine's vocabulary or dropped."""
    vocab = _crisis_vocab(state, v.nation)
    # "Hold your ships" is a demand, not a player promise: a promise whose subject is one of
    # this leader's own moves only counts when the player offered something for it on this call.
    player_said = " ".join([v.transcript or ""] + [t.text for t in (v.history or []) if t.role == "player"])
    offered = bool(OFFER.search(player_said))
    out = []
    for p in data.get("promises") or []:
        if not isinstance(p, dict) or not str(p.get("what") or "").strip():
            continue
        if p.get("to") not in (None, "", v.nation):
            continue
        what, when = str(p["what"]).strip(), str(p.get("when") or "").strip()
        if vocab is not None:
            norm = _norm_what(what, vocab)
            if norm is None or (norm != "berth" and not offered):
                continue
            when =_norm_when(when, what) if norm == "berth" else (when if when in SLOTS else "now")
            what = norm
        cond = p.get("condition")
        cond = str(cond).strip() if cond and str(cond).strip().lower() not in ("none", "null", "no") else None
        out.append({"to": v.nation, "what": what, "when": when or "now", "condition": cond})
    # A request for one of this leader's own moves, with something offered for it, is always
    # recorded, even if the model missed it or the reply was non-committal.
    for move in _requested_moves(v.transcript, v.nation, state):
        if not any(p["what"] == move for p in out):
            slot = _norm_when("", v.transcript)
            out.append({"to": v.nation, "what": move, "when": slot if slot != "all_day" or "day" in v.transcript.lower() else "now",
                        "condition": None})
    return out


def _parse_judgement(data: dict, v: CallView, options: list[dict], state: Optional[dict] = None) -> dict:
    promises = _parse_promises(data, v, state if state is not None else _dump(v.state))
    actions = []
    a = data.get("action")
    if isinstance(a, int) and 0 <= a < len(options) and options[a]["type"] != "wait":
        actions.append(dict(options[a], by=v.nation))
    # ideas.md 6b: trust from what was said; resolve from how it was said.
    trust = _clamp(data.get("trust_delta"), -0.3, 0.3)
    resolve = _clamp(data.get("resolve_delta"), -0.2, 0.2)
    if v.interrupted:
        resolve += 0.10
        if v.nation in PROUD:
            trust -= 0.05  # an insult; the engine also cuts relations by 5
    if (v.hesitation_ms or 0) > HESITATION_MS:
        resolve -= 0.15
    return {"promises": promises, "actions": actions,
            "belief_updates": {"trust_in_player": round(_clamp(trust, -1, 1), 3),
                               "resolve_of_player": round(_clamp(resolve, -1, 1), 3)},
            "ends_call": bool(data.get("ends_call", False))}


async def speak_fast(view: CallView | dict) -> dict:
    """The spoken reply only: {reply_text, emotion}, about 1 s on the fast model. If it has
    not answered within SPEAK_HEDGE_S (or fails sooner), llm.FAST_FALLBACK (medium) races it;
    the first valid reply wins. One hard deadline of CALL_BUDGET_S for both, so the caller's
    fallback line plays within it. Raises llm.LLMError on failure."""
    v = _call_view(view)
    system, user, _ = _call_context(v)
    msgs = [{"role": "system", "content": system + "\n" + SPEAK_JSON}, {"role": "user", "content": _j(user)}]
    deadline = time.perf_counter() + CALL_BUDGET_S
    return await llm.hedged(lambda m: llm.chat_json(msgs, lambda d: _parse_voice(d, v), model=m, deadline=deadline,
                                                    max_tokens=150, temperature=0.8),
                            primary=llm.FAST_MODEL, backup=llm.FAST_FALLBACK, after=SPEAK_HEDGE_S)


async def interpret(view: CallView | dict, reply_text: str) -> CallOutput:
    """What the call changed, on Large 4, run in the background after speak_fast():
    promises, agreed actions, belief_updates, ends_call (reply_text is the line spoken;
    emotion is a placeholder the caller overrides). Raises llm.LLMError on failure."""
    v = _call_view(view)
    system, user, options = _call_context(v)
    msgs = [{"role": "system", "content": system + "\n" + _judge_rules(_dump(v.state), v.nation) + "\n" + INTERPRET_JSON.format(reply=reply_text)},
            {"role": "user", "content": _j(user)}]
    deadline = time.perf_counter() + INTERPRET_BUDGET_S
    judged = await llm.hedged(lambda m: llm.chat_json(
        msgs, lambda d: _parse_judgement(d, v, options), deadline=deadline, model=m,
        max_tokens=300, temperature=0.3), after=INTERPRET_HEDGE_S)
    return CallOutput.model_validate({"reply_text": reply_text or "...", "emotion": "calm", **judged})


async def call_reply(view: CallView | dict) -> CallOutput:
    """Spoken reply and its effects in one fast call (used when the split path is off).
    Raises llm.LLMError within CALL_BUDGET_S."""
    v = _call_view(view)
    system, user, options = _call_context(v)
    msgs = [{"role": "system", "content": system + "\n" + _judge_rules(_dump(v.state), v.nation) + "\n" + CALL_JSON},
            {"role": "user", "content": _j(user)}]
    return await llm.chat_json(
        msgs, lambda d: CallOutput.model_validate({**_parse_voice(d, v), **_parse_judgement(d, v, options)}),
        deadline=time.perf_counter() + CALL_BUDGET_S, model=llm.CALL_MODEL, max_tokens=300, temperature=0.8)


# --- strategy: Large 4 writes each leader's private plan (DECIDED 13:06) --------

STRATEGY_RULES = """GAMBIT is a strategy game of five fictional nations. You are {who}. Stay in character.
{when} Write your PRIVATE strategy, which you will follow in every later decision and phone call. Nobody else sees it.
In two to four sentences: your goal, who you will court and who you will squeeze, your red line, what you will say in public to hide it, and what would make you abandon the plan. Be concrete: name nations and moves available in this game.
Reply with ONLY this JSON object: {{"strategy": str}}"""

STRATEGY_BUDGET_S = float(os.environ.get("GAMBIT_AGENTS_STRATEGY_S", "90"))
# Large 4 usually answers in 20-35 s; past that, medium races it so a crisis plan lands early.
STRATEGY_HEDGE_S = float(os.environ.get("GAMBIT_STRATEGY_HEDGE_S", "30"))


def strategy_enabled() -> bool:
    """GAMBIT_PRIVATE_STRATEGY (DECIDED 13:07): off unless set to 1/true/on."""
    return os.environ.get("GAMBIT_PRIVATE_STRATEGY", "").strip().lower() in ("1", "true", "on", "yes")


def _private_strategy(view: Any) -> Optional[str]:
    """LeaderView.private_strategy, which the engine stores per session (it is the only
    source: agents keeps no copy, so a reset never reuses an old game's plan). Ignored
    while GAMBIT_PRIVATE_STRATEGY is off."""
    if not strategy_enabled():
        return None
    given = view.get("private_strategy") if isinstance(view, dict) else getattr(view, "private_strategy", None)
    return given.strip() if isinstance(given, str) and given.strip() else None


async def strategize(state: Any, nation: str) -> str:
    """One leader's private strategy for the game (strategy phase) or for the current crisis,
    on Large 4 (medium joins after STRATEGY_HEDGE_S, 30 s). The engine stores the result for this
    session and passes it back as LeaderView.private_strategy. Run it in the background at
    game start and when a crisis starts. Never raises: falls back to the persona card's
    private agenda."""
    st = _dump(state)
    c = st.get("crisis")
    if c:
        try:
            from engine.crisis import crisis_file  # type: ignore
            cf = crisis_file(c["id"])
            when = (f"A crisis has begun: {cf.title}. {cf.intro_news} It lasts {cf.ticks_total} hours; you must commit by "
                    f"hour {cf.deadlines.get(nation)}. Your possible moves: {cf.actions.get(nation, [])}.")
        except Exception:  # noqa: BLE001
            when = f"A crisis has begun: {c.get('id')}. You must commit by hour {(c.get('deadlines') or {}).get(nation)}."
    else:
        when = ("The game is starting: it runs for a year, month by month. Each month you may trade, set tariffs, "
                "propose alliances, declare war or make peace.")
    msgs = [{"role": "system", "content": card(nation) + "\n\n" + STRATEGY_RULES.format(who=_who(st, nation), when=when)},
            {"role": "user", "content": _j({"situation": _brief(st, nation)})}]

    def parse(d: Any) -> str:
        out = str(d["strategy"]).strip()
        if len(out.split()) < 8:
            raise ValueError('"strategy" must be two to four sentences')
        return out
    try:
        deadline = time.perf_counter() + STRATEGY_BUDGET_S
        out = await llm.hedged(lambda m: llm.chat_json(msgs, parse, deadline=deadline, model=m,
                                                       max_tokens=400, temperature=0.9),
                               after=STRATEGY_HEDGE_S)
    except Exception:  # noqa: BLE001
        agenda = next((ln.split(":", 1)[-1].strip(" *") for ln in card(nation).splitlines()
                       if "private agenda" in ln.lower()), "")
        out = agenda or "Protect the regime, give nothing away for free, and wait for others to overreach."
    return out


async def strategize_all(state: Any) -> dict[str, str]:
    """strategize() for every AI nation (all but the player's seat), in parallel."""
    st = _dump(state)
    seat = (st.get("seat") or {}).get("nation")
    ai = [n for n in NATION_IDS if n != seat]  # a mediator has nation null: all five
    outs = await asyncio.gather(*(strategize(st, n) for n in ai))
    return dict(zip(ai, outs))


# --- headline, why, historian, wiretap (never raise) -------------------------

async def _one_field(system: str, user: str, field: str, timeout: float, max_tokens: int = 200) -> str:
    """Large 4 for one string field, hedged after 40% of the timeout."""
    msgs = [{"role": "system", "content": system + f' Reply as JSON {{"{field}": str}}.'},
            {"role": "user", "content": user}]

    def parse(d: Any) -> str:
        out = str(d[field]).strip().strip('"')
        if not out:
            raise ValueError(f'"{field}" is empty')
        return out
    deadline = time.perf_counter() + timeout
    out = await llm.hedged(lambda m: llm.chat_json(msgs, parse, deadline=deadline, model=m,
                                                   max_tokens=max_tokens, temperature=0.8), after=timeout * 0.4)
    return out


async def headline(event: dict) -> str:
    """One newspaper headline for an engine event."""
    try:
        return await _one_field(
            "Write one punchy newspaper headline (at most 10 words, no quotes) for this event in a fictional "
            "world of five nations: Valdoria, Ostrava, Kessaria, Nordhaven, Zarnia.", _j(event), "headline", 8.0, 80)
    except Exception:  # noqa: BLE001
        return f"{str(event.get('type', 'event')).replace('_', ' ').title()} in {str(event.get('nation') or 'the region').title()}"


def _promise_text(p: dict) -> str:
    when = p.get("when") or "now"
    cond = f", on condition: {p['condition']}" if p.get("condition") else ""
    return f"{p.get('what')} ({when}{cond})"


def _why_facts(change: dict) -> list[str]:
    """The replay inputs as plain sentences, so the model can only cite what the calls contained."""
    n = str(change.get("nation", ""))
    inputs = change.get("inputs") or {}
    facts = [f"{n.title()} first chose {change.get('was')}; with the calls moved it chose {change.get('now')}."]
    if inputs.get("original_decision_tick") is not None:
        facts.append(f"{n.title()} originally decided at tick {inputs['original_decision_tick']}"
                     + (f" (deadline tick {inputs['deadline_tick']})." if inputs.get("deadline_tick") is not None else "."))
    for c in inputs.get("calls") or []:
        to = str(c.get("to", "")).title()
        line = f"The player's call to {to} moved from tick {c.get('original_tick')} to tick {c.get('shifted_tick')}."
        promises = [_promise_text(p) for p in c.get("promises") or []]
        line += (" In it the player promised " + to + ": " + "; ".join(promises) + "." if promises
                 else " The player made no promise in it.")
        if c.get("actions"):
            line += f" {to} agreed on the call to: {', '.join(map(str, c['actions']))}."
        facts.append(line)
    if not inputs.get("calls"):
        facts.append("No player calls are on record for this crisis.")
    return facts


WHY_RULES = ("In one sentence of at most 18 words, say why this leader changed their crisis decision when the "
             "player's calls arrived at a different time. Use ONLY the facts listed: mention no offer, deal, good, "
             "fund or event that is not in them, and name a promise only by what the facts say was promised. "
             "The persona below is for the leader's motive and voice only, not a source of facts.")


async def why(change: dict) -> str:
    """One line for the replay panel. change = {nation, was, now, shift_ticks?, inputs?}."""
    n = str(change.get("nation", ""))
    fallback = f"{n.title()} switched from {change.get('was')} to {change.get('now')}."
    try:
        return await _one_field(
            WHY_RULES + "\n\nPersona:\n" + card(n),
            _j({"facts": _why_facts(change), "change": change}), "why", 8.0, 120)
    except Exception:  # noqa: BLE001
        return fallback


def _historian_context(log: list[dict], state: Optional[dict]) -> tuple[str, dict]:
    """(who-did-what rule, payload) for the historian. Each logged entry with a `by` gets an
    `actor` label so a nation's AI decision is never read as the player's."""
    seat = (state or {}).get("seat") or {}
    role, nid = seat.get("role", "president"), seat.get("nation")
    mediator = role == "mediator"
    if not mediator and not nid:  # seat unknown (no live game): say nothing rather than guess
        rule, player = "", "the player"
    elif mediator:
        rule = ("The player was an independent mediator. They controlled NO nation: all five nations, including "
                "Valdoria, were run by AI leaders, and every nation's action, offer, acceptance or rejection was that "
                "nation's own choice. Credit or blame the player only for their own phone calls and promises "
                "(entries whose actor is the player). Never call the player a leader of any nation.")
        player = "an independent mediator"
    else:
        name = ((state or {}).get("nations", {}).get(nid) or {}).get("name", nid.title())
        rule = (f"The player was the {role} of {name}: {name}'s actions were the player's. The other four nations "
                "were run by AI leaders, and their actions were their own, not the player's.")
        player = f"the {role} of {name}"

    def actor(by: Any) -> Optional[str]:
        if by == "player" or (not mediator and nid and by == nid):
            return "the player"
        return f"{by} (AI leader, not the player)" if by in NATION_IDS else None

    entries = []
    for e in log[-60:]:
        e = dict(e) if isinstance(e, dict) else {"entry": e}
        a = actor(e.get("by"))
        if a:
            e["actor"] = a
        entries.append(e)
    return rule, {"the_player": player, "who_did_what": rule, "log": entries}


async def historian(log: list[dict], state: Any = None) -> str:
    """One paragraph judging the player's session, for the end screen. state (for the seat)
    defaults to the live game."""
    try:
        st = _dump(state) if state is not None else (_game_context()[0] or {})
        rule, payload = _historian_context(log, st)
        return await _one_field(
            "You are a historian writing, years later, one paragraph (80-120 words) judging the player's time "
            "in this fictional world. " + (rule + " " if rule else "") + "Name the turning point and one leader who was deceived or "
            "betrayed, if any. Wry and specific; no bullet points.",
            _j(payload), "verdict", 40.0, 600)
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
    if state is None:
        live, intents = _game_context()
        st = live or {}
    else:
        st, intents = _dump(state), {}
    fallback = [
        {"speaker": a, "text": f"What do you make of {_player(st)}?", "emotion": "skeptical"},
        {"speaker": b, "text": "I want to hear the terms first.", "emotion": "calm"},
        {"speaker": a, "text": "Then let us compare notes afterwards.", "emotion": "tense"},
        {"speaker": b, "text": "Agreed. I will keep this channel open.", "emotion": "calm"},
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
            player=_player(st) if st else "the president of Valdoria",
            a_who=_who(st, a), b_who=_who(st, b), a_card=card(a), b_card=card(b), emotions=", ".join(EMOTIONS))
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": _j(ctx)}]
        deadline = time.perf_counter() + 12.0
        data = await llm.hedged(lambda m: llm.chat_json(msgs, lambda d: d if isinstance(d.get("lines"), list) else {}[0],
                                                        deadline=deadline, model=m, max_tokens=500, temperature=0.9),
                                after=4.0)
        lines = []
        for ln in data.get("lines") or []:
            who = {"A": a, "B": b}.get(str(ln.get("speaker")).strip().upper(), ln.get("speaker"))
            text = _two_sentences(str(ln.get("text") or ""))
            if who in (a, b) and text:
                emo = ln.get("emotion") if ln.get("emotion") in EMOTIONS else "tense"
                lines.append({"speaker": who, "text": text, "emotion": emo})
        return lines[:4] if len(lines) >= 2 else fallback
    except Exception:  # noqa: BLE001
        return fallback
