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

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import asyncio

from contracts.models import (
    NATION_IDS, CrisisStartRequest, FuturesRequest, FuturesResponse, LeaderDetail, StartRequest, State,
)
from engine.futures import futures
from engine.snapshots import load
from engine.crisis import available
from engine.game import GAME

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gambit.engine")

router = APIRouter()


@router.post("/start", response_model=State)
async def start(req: StartRequest) -> State:
    async with GAME.lock:
        return GAME.reset(req.seed, req.seat)


@router.get("/state", response_model=State)
async def get_state() -> State:
    return GAME.state


@router.post("/turn", response_model=State)
async def turn() -> State:
    return await GAME.turn()


@router.post("/crisis/start", response_model=State)
async def crisis_start(req: CrisisStartRequest) -> State:
    if req.id not in available():
        raise HTTPException(404, f"unknown crisis {req.id!r}; have {available()}")
    async with GAME.lock:
        if GAME.state.phase != "strategy":
            raise HTTPException(409, f"cannot start a crisis during phase {GAME.state.phase!r}")
        return GAME.start_crisis(req.id)


@router.post("/end", response_model=State)
async def end() -> State:
    """End the session now (the end screen's trigger). state.ending.verdict follows."""
    async with GAME.lock:
        if GAME.state.phase == "ended":
            raise HTTPException(409, "the session has already ended")
        return GAME.end("ended")


@router.post("/futures", response_model=FuturesResponse)
async def post_futures(req: FuturesRequest) -> FuturesResponse:
    """War odds six months ahead: the snapshot (before) against the current state (after).
    The needle also updates by itself after every call that changes something: see
    state.last_futures."""
    try:
        before = load(req.snapshot_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    result = await asyncio.to_thread(futures, before, GAME.state, list(GAME.queued))
    GAME.state = GAME.state.model_copy(update={"last_futures": result})
    return result


@router.get("/leaders/{nation}", response_model=LeaderDetail)
async def leader(nation: str) -> LeaderDetail:
    if nation not in NATION_IDS:
        raise HTTPException(404, f"unknown nation {nation!r}")
    return GAME.leader(nation)


app = FastAPI(title="GAMBIT")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

routers = [router]
MOUNT_ERRORS: dict[str, str] = {}  # scripts/smoke.sh fails if this is not empty
for module in ("voice.api", "replay.api"):
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
