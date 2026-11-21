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

from contracts.models import NATION_IDS, LeaderDetail, StartRequest, State
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


@router.get("/leaders/{nation}", response_model=LeaderDetail)
async def leader(nation: str) -> LeaderDetail:
    if nation not in NATION_IDS:
        raise HTTPException(404, f"unknown nation {nation!r}")
    return GAME.leader(nation)


app = FastAPI(title="GAMBIT")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

routers = [router]
for module in ("voice.api", "replay.api"):
    try:
        routers.append(importlib.import_module(module).router)
        log.info("mounted %s", module)
    except ModuleNotFoundError as e:
        if e.name and module.startswith(e.name):
            continue  # that folder has no routes yet
        log.exception("could not mount %s", module)
    except Exception:
        log.exception("could not mount %s", module)

for r in routers:
    app.include_router(r)
    app.include_router(r, prefix="/api")
