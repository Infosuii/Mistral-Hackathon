"""What a phone call does to the world. Pure: returns a new State.

Used by GAME.apply_call (live) and by rerun_crisis (replay), so both agree."""

from __future__ import annotations

from contracts.models import CallOutput, CrisisPromise, State, relation_key
from engine.core import weights


WHEN_WORDS = [  # checked in order; the first match wins
    ("all_day", ("all day", "whole day", "full day", "entire day", "24 hours", "all_day")),
    ("morning", ("morning", "dawn", "first light")),
    ("afternoon", ("afternoon", "noon", "midday")),
    ("evening", ("evening", "night", "tonight", "dusk")),
]


def normalise_promise(state: State, to: str, what: str, when: str) -> tuple[str, str]:
    """Map a free-text promise onto the crisis's words, so the engine can count it.

    `what` becomes "berth" or one of the recipient's crisis actions when the text names
    one ("berth for full day" -> "berth"); `when` becomes all_day / morning / afternoon /
    evening when the text says so ("night" -> "evening"). Anything else is kept as is."""
    if state.crisis is None:
        return what, when
    from engine.crisis import crisis_file
    cf = crisis_file(state.crisis.id)
    vocab = set(cf.actions.get(to, [])) | ({"berth"} if "berth" in str(cf.rules) else set())
    text = f"{what} {when}".lower().replace("_", " ")
    if what not in vocab:
        hits = [v for v in vocab if v.replace("_", " ") in text]
        if hits:
            what = max(hits, key=len)
    for word, phrases in WHEN_WORDS:
        if any(ph in text for ph in phrases):
            return what, word
    return what, when


def apply_call_effects(state: State, to: str, out: CallOutput, interrupted: bool,
                       ledger_start: int = 0) -> tuple[State, list[CrisisPromise]]:
    """Belief updates (clamped 0-1), relations -5 when a proud leader is interrupted,
    and the call's promises. In a crisis the promises go into state.crisis.promises;
    otherwise they are returned for the caller to keep. Actions are not applied here:
    the caller queues out.actions for the next turn or tick."""
    s = state.model_copy(deep=True)
    b = s.nations[to].beliefs
    if b is not None:
        b.trust_in_player = round(min(1.0, max(0.0, b.trust_in_player + out.belief_updates.trust_in_player)), 3)
        b.resolve_of_player = round(min(1.0, max(0.0, b.resolve_of_player + out.belief_updates.resolve_of_player)), 3)
    seat = s.seat.nation
    call = weights()["call"]
    if interrupted and to in call["proud"] and to != seat:
        k = relation_key(seat, to)
        s.relations[k] = max(-100, s.relations.get(k, 0) + call["interrupt_relation_proud"])
    tick = s.crisis.tick if s.crisis else s.turn
    ledger = s.crisis.promises if s.crisis else []
    base = len(ledger) if s.crisis else ledger_start
    new = []
    for i, p in enumerate(out.promises):
        what, when = normalise_promise(s, p.to, p.what, p.when)
        new.append(CrisisPromise(id=f"p{base + i + 1}", tick=tick, by="player", to=p.to, what=what,
                                 when=when, condition=p.condition))
    ledger += new
    if s.incoming_call and s.incoming_call.from_ == to:
        s.incoming_call = None  # answered
    return s, ([] if s.crisis else new)
