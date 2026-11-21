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
    "set_tariff", "propose_trade", "propose_alliance", "leave_alliance", "declare_war", "make_peace",
    "deploy_fleet", "recall_fleet"
]
STRATEGY_ACTION_TYPES: tuple[str, ...] = (
    "set_tariff", "propose_trade", "propose_alliance", "leave_alliance", "declare_war", "make_peace",
    "deploy_fleet", "recall_fleet"
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
    # A mediator has no home nation (DECIDED 13:09): nation is null for mediator only.
    nation: Optional[NationId] = None

    @model_validator(mode="after")
    def _nation_matches_role(self) -> "Seat":
        if self.role == "mediator" and self.nation is not None:
            raise ValueError("a mediator has no nation: send nation null")
        if self.role != "mediator" and self.nation is None:
            raise ValueError(f"a {self.role} needs a nation")
        return self


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


# --- 4.6 Call, slow half (decided by Tamim 12:29) ----------------------------


class CallResult(Model):
    """What Mistral Large 4 made of a call. Arrives after the spoken reply: /call
    answers with pending=true, then state.last_call carries this once it is ready."""

    call_id: str
    to: NationId
    pending: bool
    promises: list["CallPromise"] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    ends_call: bool = False


# --- End of session (W7; proposed 12:44, Tamim to confirm) -------------------


class Score(Model):
    months_in_power: int
    peace_months: int
    gdp_change: float
    stability_change: float
    promises_kept: int
    promises_broken: int
    # Mediator seat only (DECIDED 13:09): crises resolved without war, mean trust of all five leaders.
    peaceful_crises: Optional[int] = None
    average_trust: Optional[float] = Field(default=None, ge=0, le=1)


class Ending(Model):
    """Set when phase becomes "ended". verdict is null until the historian has written it."""

    reason: Literal["ended", "voted_out", "coup", "time"]
    score: Score
    verdict: Optional[str] = None


class CrisisOption(Model):
    """One entry of state.available_crises (DECIDED 13:12)."""

    id: str
    title: str


# --- 4.2 State (continued) ---------------------------------------------------


BuildingKind = Literal["army_base", "arms_factory", "airfield", "factory", "farm", "chip_works", "freight_yard"]


class BuildRequest(Model):
    province: str
    kind: BuildingKind


class Building(BuildRequest):
    built_turn: int = Field(ge=0)


class Fleet(Model):
    target: NationId
    arrival_turn: int = Field(ge=0)
    returning: bool = False


class State(Model):
    turn: int = Field(ge=0)
    phase: Phase
    seed: int
    seat: Seat
    nations: dict[NationId, Nation]
    relations: dict[str, int]
    links: list[Link] = Field(default_factory=list)
    provinces: dict[str, NationId] = Field(default_factory=dict)
    fleets: dict[NationId, Fleet] = Field(default_factory=dict)
    buildings: list[Building] = Field(default_factory=list)
    construction: Optional[BuildRequest] = None  # legacy single slot, read from older saves only
    construction_queue: list[BuildRequest] = Field(default_factory=list)  # paid when queued, opens next month
    unrest: dict[str, int] = Field(default_factory=dict)  # captured province -> months of unrest left
    disrupted: list[str] = Field(default_factory=list)  # provinces producing at reduced output this month
    rail_services: list[str] = Field(default_factory=list)
    rail_income: dict[NationId, dict[str, float]] = Field(default_factory=dict)
    road_services: list[str] = Field(default_factory=list)  # road ids carrying haulage this month
    road_income: dict[NationId, dict[str, float]] = Field(default_factory=dict)
    air_services: list[str] = Field(default_factory=list)  # "pA|pB" airfield pairs with scheduled flights
    air_income: dict[NationId, dict[str, float]] = Field(default_factory=dict)
    news: list[NewsItem] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    incoming_call: Optional[IncomingCall] = None
    crisis: Optional[Crisis] = None
    last_futures: Optional[FuturesResponse] = None
    last_call: Optional[CallResult] = None  # the latest call's promises and actions
    ending: Optional[Ending] = None  # set when phase is "ended"
    available_roles: Optional[list[Role]] = None  # seats /start accepts; missing means president only
    available_crises: Optional[list[CrisisOption]] = None  # crises /crisis/start accepts; missing means One Berth only

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
    earlier_private_intents: list[str] = Field(default_factory=list)
    # The leader's own plan for the game or the current crisis (DECIDED 13:07), when written.
    private_strategy: Optional[str] = None


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


class CallTurn(Model):
    role: Literal["player", "leader"]
    text: str


class CallView(Model):
    """Input to agents.call_reply (confirmed by Tamim, 12:14)."""

    nation: NationId
    transcript: str
    interrupted: bool
    hesitation_ms: Optional[int] = None
    state: State
    # Earlier turns of this call, oldest first, so the leader remembers them. /call keeps it.
    history: Optional[list[CallTurn]] = None


class CallResponse(Model):
    transcript: str
    reply_text: str
    reply_audio_url: Optional[str]
    emotion: Emotion
    promises: list[CallPromise]
    actions: list[Action]
    # Split replies (12:29): with pending=true, promises and actions are empty here and
    # arrive in state.last_call (same call_id) once Large 4 has interpreted the call.
    call_id: Optional[str] = None
    pending: bool = False


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


class PlayerActions(Model):
    """GET /actions and POST /action (DECIDED 13:49, behind GAMBIT_PLAYER_ACTIONS): the
    one-sided moves the player's own nation may make now, and the one queued for next turn.
    Trade and alliances stay phone calls."""

    actions: list[Action]
    queued: Optional[Action] = None


class LeaderDetail(Model):
    """GET /leaders/{id}. The only place private_intent is exposed."""

    public_statement: str
    private_intent: str
    advice: list[Advice]
    chosen: list[Action]
    reason: str
    persona: str
    private_strategy: Optional[str] = None  # DECIDED 13:07; null until written


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


CallResult.model_rebuild()
State.model_rebuild()
