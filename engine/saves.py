"""Versioned local save slots for the single-session server."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError

from contracts.models import Action, Advice, CallOutput, CrisisPromise, Decision, LeaderDetail, ReceivedMessage, State
from engine.game import Game, allowed_crises, available_crises, available_roles
from engine.snapshots import snapshot


class SaveInfo(BaseModel):
    id: UUID
    name: str
    seed: int
    nation: str | None
    turn: int
    saved_at: datetime


class CrisisArchive(BaseModel):
    start: State
    calls: list[tuple[int, str, CallOutput, bool]]
    decisions: dict[str, Decision]
    advice: dict[str, list[Advice]]
    own: dict[str, Decision]
    announces: list[tuple[int, Action]]


class Checkpoint(BaseModel):
    version: int = Field(default=1, ge=1, le=1)
    info: SaveInfo
    state: State
    start_state: State
    session_log: list[dict]
    dispatch_log: list[dict] = Field(default_factory=list)
    leaders: dict[str, LeaderDetail]
    inbox: dict[str, list[ReceivedMessage]]
    queued: list[Action]
    player_action: Action | None
    promises: list[CrisisPromise]
    pending_announce: Action | None
    crisis_log: list[State]
    crisis_advice: dict[str, list[Advice]]
    crisis_own: dict[str, Decision]
    crisis_announces: list[tuple[int, Action]]
    crisis_calls: list[tuple[int, str, CallOutput, bool]]
    last_crisis: CrisisArchive | None
    months_in_power: int
    peace_months: int
    promises_kept: int
    promises_broken: int
    peaceful_crises: int
    original_leader: str
    strategies: dict[str, dict[str, str]]


class SaveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


def directory() -> Path:
    return Path(os.environ.get("GAMBIT_SAVE_DIR", Path(__file__).resolve().parent.parent / ".gambit-saves"))


def create(game: Game, name: str) -> SaveInfo:
    if game.state.last_call and game.state.last_call.pending:
        raise ValueError("wait for the current call to finish")
    name = name.strip()
    if not name:
        raise ValueError("a save needs a name")
    info = SaveInfo(
        id=uuid4(), name=name, seed=game.state.seed, nation=game.state.seat.nation,
        turn=game.state.turn, saved_at=datetime.now(timezone.utc),
    )
    fields = {field: getattr(game, field) for field in Checkpoint.model_fields if field not in {"version", "info"}}
    record = Checkpoint(info=info, **fields)
    folder = directory()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{info.id}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(record.model_dump_json(by_alias=True), encoding="utf-8")
    temporary.replace(path)
    return info


def list_slots() -> list[SaveInfo]:
    slots = []
    for path in directory().glob("*.json"):
        try:
            record = Checkpoint.model_validate_json(path.read_bytes())
        except (OSError, ValidationError):
            continue
        slots.append(record.info)
    return sorted(slots, key=lambda slot: slot.saved_at, reverse=True)


def restore(game: Game, slot: UUID) -> State:
    try:
        record = Checkpoint.model_validate_json((directory() / f"{slot}.json").read_bytes())
    except FileNotFoundError as e:
        raise LookupError("save not found") from e
    if record.state.seat.role not in (available_roles() or ["president"]):
        raise ValueError("the saved role is disabled in this server")
    if record.state.crisis and record.state.crisis.id not in allowed_crises():
        raise ValueError("the saved crisis is disabled in this server")
    game.epoch += 1
    game.call_count = 0
    game.latest_call_id = None
    for field in Checkpoint.model_fields:
        if field not in {"version", "info", "last_crisis"}:
            setattr(game, field, getattr(record, field))
    game.last_crisis = None
    if record.last_crisis:
        archive = record.last_crisis
        game.last_crisis = {field: getattr(archive, field) for field in CrisisArchive.model_fields}
        game.last_crisis["snapshot_id"] = snapshot(archive.start)
    game.state = game.state.model_copy(update={
        "available_roles": available_roles(),
        "available_crises": available_crises(),
    })
    return game.state
