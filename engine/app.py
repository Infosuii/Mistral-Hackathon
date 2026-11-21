"""The one backend process.

    uvicorn engine.app:app --reload --port 8000

Every route is served both at the root (/state) and under /api (/api/state), so the
page works whether or not its dev proxy strips the prefix. Other folders add their
routes by exposing a FastAPI `router` in voice/api.py or replay/api.py; this app
includes them when they exist.
"""

from __future__ import annotations

import importlib
import logging
import sys
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import asyncio

from contracts.models import (
    Action, BuildRequest, CallResult, Event, PlayerActions, NATION_IDS, CrisisStartRequest, FuturesRequest, FuturesResponse, LeaderDetail, StartRequest, State,
)
from engine import saves
from engine.core import cancel_project, queue_project
from engine.futures import futures
from engine.snapshots import clear_snapshots, load
from engine.game import GAME, allowed_crises, public_leader, public_view
import engine.game as _game_mod

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gambit.engine")

router = APIRouter()


@router.post("/start", response_model=State)
async def start(req: StartRequest) -> State:
    async with GAME.lock:
        try:
            state = GAME.reset(req.seed, req.seat)
            clear_snapshots()
            return public_view(state)
        except ValueError as e:  # a seat that is not enabled (GAMBIT_MEDIATOR)
            raise HTTPException(400, str(e))


@router.get("/state", response_model=State)
async def get_state() -> State:
    return public_view(GAME.state)


@router.post("/construction", response_model=State)
async def construction(project: BuildRequest) -> State:
    async with GAME.lock:
        try:
            GAME.state = queue_project(GAME.state, project)
        except ValueError as e:
            raise HTTPException(409, str(e)) from e
        return public_view(GAME.state)


@router.post("/construction/cancel", response_model=State)
async def construction_cancel(project: BuildRequest) -> State:
    async with GAME.lock:
        try:
            GAME.state = cancel_project(GAME.state, project)
        except ValueError as e:
            raise HTTPException(409, str(e)) from e
        return public_view(GAME.state)


@router.get("/saves", response_model=list[saves.SaveInfo])
async def list_saves() -> list[saves.SaveInfo]:
    return saves.list_slots()


@router.post("/saves", response_model=saves.SaveInfo, status_code=201)
async def create_save(req: saves.SaveRequest) -> saves.SaveInfo:
    async with GAME.lock:
        try:
            return saves.create(GAME, req.name)
        except ValueError as e:
            raise HTTPException(409, str(e)) from e


@router.post("/saves/{slot}/load", response_model=State)
async def load_save(slot: UUID) -> State:
    async with GAME.lock:
        try:
            return public_view(saves.restore(GAME, slot))
        except LookupError as e:
            raise HTTPException(404, str(e)) from e
        except ValueError as e:
            raise HTTPException(409, str(e)) from e


@router.get("/news", response_model=list[Event])
async def news() -> list[Event]:
    return [Event.model_validate(entry) for entry in GAME.session_log if entry["type"] == "news"]


@router.get("/history", response_model=list[Event])
async def history() -> list[Event]:
    return [Event.model_validate(entry) for entry in GAME.session_log
            if entry["type"] != "news"]


@router.get("/dispatches", response_model=list[Event])
async def dispatches() -> list[Event]:
    if GAME.state.seat.role == "mediator":
        raise HTTPException(403, "a mediator has access to public positions")
    return [Event.model_validate(entry) for entry in GAME.dispatch_log]


@router.post("/turn", response_model=State)
async def turn() -> State:
    return public_view(await GAME.turn())


@router.post("/crisis/start", response_model=State)
async def crisis_start(req: CrisisStartRequest) -> State:
    if req.id not in allowed_crises():
        raise HTTPException(404, f"unknown crisis {req.id!r}; have {allowed_crises()}")
    async with GAME.lock:
        if GAME.state.phase != "strategy":
            raise HTTPException(409, f"cannot start a crisis during phase {GAME.state.phase!r}")
        return public_view(GAME.start_crisis(req.id))


def _player_actions_enabled() -> None:
    if not _game_mod.PLAYER_ACTIONS:
        raise HTTPException(404, "player actions are off (GAMBIT_PLAYER_ACTIONS)")


@router.get("/actions", response_model=PlayerActions)
async def get_actions() -> PlayerActions:
    """The one-sided moves the player's nation may make now, and the one queued. With
    GAMBIT_PLAYER_ACTIONS off it lists nothing (200, not 404), so the page's console stays
    clean (Neon, #27 14:28); POST /action is still refused."""
    if not _game_mod.PLAYER_ACTIONS:
        return PlayerActions(actions=[], queued=None)
    return PlayerActions(actions=GAME.player_options(), queued=GAME.player_action)


@router.post("/action", response_model=PlayerActions)
async def post_action(action: Action) -> PlayerActions:
    """Queue one move (set_tariff, declare_war, make_peace) for the player's nation for the
    next month (DECIDED 13:49). Trade and alliances stay phone calls."""
    _player_actions_enabled()
    async with GAME.lock:
        try:
            GAME.queue_player_action(action)
        except ValueError as e:
            raise HTTPException(409 if "phase" in str(e) else 400, str(e))
        return PlayerActions(actions=GAME.player_options(), queued=GAME.player_action)


@router.post("/end", response_model=State)
async def end() -> State:
    """End the session now (the end screen's trigger). state.ending.verdict follows."""
    async with GAME.lock:
        if GAME.state.phase == "ended":
            raise HTTPException(409, "the session has already ended")
        return public_view(GAME.end("ended"))


@router.post("/futures", response_model=FuturesResponse)
async def post_futures(req: FuturesRequest) -> FuturesResponse:
    """War odds six months ahead: the snapshot (before) against the current state (after).
    The needle also updates by itself after every call that changes something: see
    state.last_futures."""
    try:
        before = load(req.snapshot_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    epoch = GAME.epoch
    GAME.needle_seq += 1
    seq = GAME.needle_seq
    result = await asyncio.to_thread(futures, before, GAME.state, list(GAME.queued))
    if epoch != GAME.epoch:
        raise HTTPException(409, "The game restarted during the forecast.")
    result = result.model_copy(update={"caption": (
        f"Six-month war odds from the saved snapshot to now: "
        f"{result.before.war_p:.0%} → {result.after.war_p:.0%}."
    )})
    if seq == GAME.needle_seq:
        GAME.state = GAME.state.model_copy(update={"last_futures": result})
    return result


@router.get("/calls/{call_id}", response_model=CallResult)
async def call_result(call_id: str) -> CallResult:
    result = GAME.call_results.get(call_id)
    if result is None:
        raise HTTPException(404, "No such call in the current session.")
    return result


@router.get("/leaders/{nation}", response_model=LeaderDetail)
async def leader(nation: str) -> LeaderDetail:
    if nation not in NATION_IDS:
        raise HTTPException(404, f"unknown nation {nation!r}")
    return public_leader(GAME.state, GAME.leader(nation))


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        agents_client = sys.modules.get("agents.llm")
        if agents_client is not None:
            await agents_client.close_client()


app = FastAPI(title="GAMBIT", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

routers = [router]
MOUNT_ERRORS: dict[str, str] = {}  # scripts/smoke.sh fails if this is not empty
for module in ("voice.api", "replay.api", "war.api"):
    try:
        routers.append(importlib.import_module(module).router)
        log.info("mounted %s", module)
    except ModuleNotFoundError as e:
        if e.name and module.startswith(e.name):
            continue  # that folder has no routes yet
        MOUNT_ERRORS[module] = f"{type(e).__name__}: {e}"
        log.exception("could not mount %s", module)
    except Exception as e:
        MOUNT_ERRORS[module] = f"{type(e).__name__}: {e}"
        log.exception("could not mount %s", module)

for r in routers:
    app.include_router(r)
    app.include_router(r, prefix="/api")
