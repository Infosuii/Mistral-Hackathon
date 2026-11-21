"""GAMBIT contracts: the shapes in MASTER_PLAN.md section 4.

Field names match the plan exactly. Change a shape only through the board (Tamim
approves, Om updates this file and the examples, then posts CHANGED).

Models reject unknown fields, so a typo in a field name fails loudly instead of
being dropped. Event and ScriptedEvent are the exceptions: their extra fields
depend on the event type.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --- shared vocabulary -------------------------------------------------------

NationId = Literal["valdoria", "ostrava", "kessaria", "nordhaven", "zarnia"]
NATION_IDS: tuple[str, ...] = ("valdoria", "ostrava", "kessaria", "nordhaven", "zarnia")

Phase = Literal["strategy", "crisis", "ended"]
Role = Literal["president", "diplomat", "mediator"]
System = Literal["democracy", "junta", "monarchy", "technocracy", "one_party"]
LinkType = Literal["trade", "alliance", "war"]

# Section 4.4. Crisis action types come from the crisis file, so Action.type is a str.
StrategyActionType = Literal[
    "set_tariff", "propose_trade", "propose_alliance", "declare_war", "make_peace"
]
STRATEGY_ACTION_TYPES: tuple[str, ...] = (
    "set_tariff", "propose_trade", "propose_alliance", "declare_war", "make_peace"
)

# Section 4.6. Real Voxtral tags; anything else is silently ignored by the voice model.
Emotion = Literal[
    "angry", "anxious", "assertive", "calm", "confident", "critical", "determined",
    "disappointed", "frustrated", "proud", "sarcastic", "skeptical", "tense",
    "urgent", "warm",
]


def relation_key(a: str, b: str) -> str:
    """Relation keys are the two nation ids sorted and joined with '|'."""
    return "|".join(sorted((a, b)))


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --- 4.4 Action --------------------------------------------------------------


class Action(Model):
    type: str
    by: NationId
    target: Optional[NationId] = None
    params: dict[str, Any] = Field(default_factory=dict)


class Advice(Model):
    """One entry of advise(state, nation): ranked, best first."""

    action: Action
    score: float


# --- 4.2 State ---------------------------------------------------------------


class Seat(Model):
    role: Role
    nation: NationId


class Stats(Model):
    gdp: float
    oil: float
    food: float
    chips: float
    army: float
    stability: float = Field(ge=0, le=100)
    approval: float = Field(ge=0, le=100)
    territory: int = Field(ge=0)


class Beliefs(Model):
    trust_in_player: float = Field(ge=0, le=1)
    resolve_of_player: float = Field(ge=0, le=1)


class Nation(Model):
    name: str
    system: System
    leader: str
    voice_id: str
    stats: Stats
    # The seated player's own nation has no beliefs about the player: null there.
    beliefs: Optional[Beliefs] = None
    public_statement: str = ""
    status: list[str] = Field(default_factory=list)


class Link(Model):
    type: LinkType
    a: NationId
    b: NationId


class NewsItem(Model):
    turn: int
    text: str


class Event(BaseModel):
    """Extra fields depend on the event type, so they are allowed here."""

    model_config = ConfigDict(extra="allow")

    turn: int
    type: str
    nation: Optional[NationId] = None


class IncomingCall(Model):
    """Not specified in section 4; proposed shape, mirrors a scripted incoming_call."""

    from_: NationId = Field(alias="from")
    emotion: Emotion
    opening_line: str
    audio_url: Optional[str] = None


# --- 4.3 Crisis --------------------------------------------------------------


class CrisisPromise(Model):
    id: str
    tick: int
    by: str  # "player" or a nation id
    to: NationId
    what: str
    when: str
    condition: Optional[str] = None
    kept: Optional[bool] = None


class PublicCommitment(Model):
    nation: NationId
    action: str
    tick: int


class Decision(Model):
    action: str
    tick: int


class Crisis(Model):
    id: str
    tick: int = Field(ge=0)
    ticks_total: int = Field(gt=0)
    deadlines: dict[NationId, int]
    promises: list[CrisisPromise] = Field(default_factory=list)
    public_commitments: list[PublicCommitment] = Field(default_factory=list)
    decisions: dict[NationId, Decision] = Field(default_factory=dict)


# --- 4.7 /futures (also state.last_futures) ----------------------------------


class WarOdds(Model):
    war_p: float = Field(ge=0, le=1)


class FuturesRequest(Model):
    snapshot_id: str


class FuturesResponse(Model):
    before: WarOdds
    after: WarOdds
    caption: str


# --- 4.2 State (continued) ---------------------------------------------------


class State(Model):
    turn: int = Field(ge=0)
    phase: Phase
    seed: int
    seat: Seat
    nations: dict[NationId, Nation]
    relations: dict[str, int]
    links: list[Link] = Field(default_factory=list)
    provinces: dict[str, NationId] = Field(default_factory=dict)
    news: list[NewsItem] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    incoming_call: Optional[IncomingCall] = None
    crisis: Optional[Crisis] = None
    last_futures: Optional[FuturesResponse] = None

    @field_validator("relations")
    @classmethod
    def _relation_keys(cls, v: dict[str, int]) -> dict[str, int]:
        for key, score in v.items():
            parts = key.split("|")
            if len(parts) != 2 or any(p not in NATION_IDS for p in parts) or parts[0] == parts[1]:
                raise ValueError(f"relation key {key!r} must be two nation ids joined by '|'")
            if key != relation_key(*parts):
                raise ValueError(f"relation key {key!r} must be sorted: {relation_key(*parts)!r}")
            if not -100 <= score <= 100:
                raise ValueError(f"relation {key!r} = {score} is outside -100..100")
        return v

    @model_validator(mode="after")
    def _consistent(self) -> "State":
        if (self.phase == "crisis") != (self.crisis is not None):
            raise ValueError("crisis must be set exactly when phase is 'crisis'")
        if self.provinces:
            for nid, nation in self.nations.items():
                owned = sum(1 for owner in self.provinces.values() if owner == nid)
                if nation.stats.territory != owned:
                    raise ValueError(
                        f"{nid}.stats.territory is {nation.stats.territory} "
                        f"but it owns {owned} provinces"
                    )
        return self


# --- 4.5 Leader output (agents.decide) ---------------------------------------


class Message(Model):
    to: NationId
    text: str


class LeaderOutput(Model):
    public_statement: str
    private_intent: str
    actions: list[Action]
    followed_advice: bool
    reason: str
    messages: list[Message] = Field(default_factory=list)


class ReceivedMessage(Model):
    """A Message as delivered to its recipient (proposed; see LeaderView)."""

    from_: NationId = Field(alias="from")
    text: str


class LeaderView(Model):
    """Input to agents.decide. Not specified in section 4; proposed minimal shape."""

    nation: NationId
    state: State
    advice: list[Advice]
    messages_received: list[ReceivedMessage] = Field(default_factory=list)


# --- 4.6 Call ----------------------------------------------------------------


class CallRequest(Model):
    to: NationId
    audio: Optional[str] = None  # base64
    text: Optional[str] = None  # typed fallback
    interrupted: bool = False
    hesitation_ms: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _audio_or_text(self) -> "CallRequest":
        if (self.audio is None) == (self.text is None):
            raise ValueError("send exactly one of 'audio' or 'text'")
        return self


class CallPromise(Model):
    to: NationId
    what: str
    when: str
    condition: Optional[str] = None


class BeliefUpdates(Model):
    """Deltas, applied by the engine and clamped to 0..1."""

    trust_in_player: float = Field(ge=-1, le=1)
    resolve_of_player: float = Field(ge=-1, le=1)


class CallOutput(Model):
    """agents.call_reply return value."""

    reply_text: str
    emotion: Emotion
    promises: list[CallPromise] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    belief_updates: BeliefUpdates
    ends_call: bool = False


class CallView(Model):
    """Input to agents.call_reply. Not specified in section 4; proposed minimal shape."""

    nation: NationId
    transcript: str
    interrupted: bool
    hesitation_ms: Optional[int] = None
    state: State


class CallResponse(Model):
    transcript: str
    reply_text: str
    reply_audio_url: Optional[str]
    emotion: Emotion
    promises: list[CallPromise]
    actions: list[Action]


# --- 4.7 The other endpoints -------------------------------------------------


class StartRequest(Model):
    seed: int
    seat: Seat


class CrisisStartRequest(Model):
    id: str


class ReplayRequest(Model):
    shift_ticks: int


class ReplayChange(Model):
    nation: NationId
    was: str
    now: str
    why: str


class ReplayResponse(Model):
    shift_ticks: int
    changed: list[ReplayChange]


class WiretapLine(Model):
    speaker: NationId
    text: str
    audio_url: Optional[str]


class WiretapResponse(Model):
    lines: list[WiretapLine]


class LeaderDetail(Model):
    """GET /leaders/{id}. The only place private_intent is exposed."""

    public_statement: str
    private_intent: str
    advice: list[Advice]
    chosen: list[Action]
    reason: str
    persona: str


# --- 4.8 Crisis file ---------------------------------------------------------


class ScriptedEvent(BaseModel):
    """Extra fields depend on the type (incoming_call, compare_notes, forecast, ...)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    tick: int
    type: str
    from_: Optional[NationId] = Field(default=None, alias="from")
    emotion: Optional[Emotion] = None
    opening_line: Optional[str] = None
    between: Optional[list[NationId]] = None
    text: Optional[str] = None


class CrisisFile(Model):
    id: str
    title: str
    ticks_total: int = Field(gt=0)
    intro_news: str
    deadlines: dict[NationId, int]
    actions: dict[NationId, list[str]]
    rules: dict[str, Any] = Field(default_factory=dict)
    scripted: list[ScriptedEvent] = Field(default_factory=list)
