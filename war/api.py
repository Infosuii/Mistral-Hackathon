"""War endpoints (mounted by engine/app.py like voice and replay). On by default (DECIDED
16:36: war ships on); GAMBIT_WAR=0 turns them off, and then the page hides the War Room.

GET  /war                      garrisons, marching armies, wars and scores, battle log
POST /war/declare  {target}
POST /war/attack   {province, share?, advance?}
POST /war/recruit  {troops}
POST /war/reinforce {target}   march spare troops to the front facing target
POST /war/peace    {target, kind: white|pay|demand|pact, amount?}
"""
from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from engine.game import GAME

from .sim import WarRoom

router = APIRouter()
_room: Optional[WarRoom] = None
_epoch: Optional[int] = None


def enabled() -> bool:
    return os.environ.get("GAMBIT_WAR", "1").strip().lower() not in ("0", "false", "off", "no")


def room() -> WarRoom:
    """The war room for the current game; a new game (new epoch) gets a fresh one."""
    global _room, _epoch
    if not enabled():
        raise HTTPException(404, "war is off (GAMBIT_WAR=0)")
    if _room is None or _epoch != GAME.epoch:
        _room, _epoch = WarRoom(GAME.state, seed=GAME.state.seed), GAME.epoch
    return _room


def player() -> str:
    seat = GAME.state.seat
    if seat.role == "mediator" or not seat.nation:
        raise HTTPException(409, "a mediator has no army")
    if GAME.state.phase == "ended":
        raise HTTPException(409, "the session has ended")
    return seat.nation


class Declare(BaseModel):
    target: str


class Attack(BaseModel):
    province: str
    share: float = 0.7
    advance: bool = True


class Recruit(BaseModel):
    troops: float = 1000


class Reinforce(BaseModel):
    target: str


class Peace(BaseModel):
    target: str
    kind: str = "white"
    amount: float = 0


async def _do(fn) -> dict[str, Any]:
    async with GAME.lock:
        r = room()
        r.advance(GAME.state)
        try:
            extra = fn(r)
        except ValueError as e:
            raise HTTPException(422, str(e))
        r.advance(GAME.state)
        return {**r.view(GAME.state), **(extra or {})}


@router.get("/war")
async def get_war() -> dict[str, Any]:
    return await _do(lambda r: None)


@router.post("/war/declare")
async def declare(req: Declare) -> dict[str, Any]:
    me = player()
    return await _do(lambda r: {"message": r.declare(GAME.state, me, req.target)})


@router.post("/war/attack")
async def attack(req: Attack) -> dict[str, Any]:
    me = player()
    return await _do(lambda r: {"army": r.attack(GAME.state, me, req.province, req.share, req.advance).id})


@router.post("/war/recruit")
async def recruit(req: Recruit) -> dict[str, Any]:
    me = player()
    return await _do(lambda r: {"cost": r.recruit(GAME.state, me, req.troops)})


@router.post("/war/reinforce")
async def reinforce(req: Reinforce) -> dict[str, Any]:
    me = player()
    return await _do(lambda r: {"message": f"{r.reinforce(GAME.state, me, req.target):,.0f} troops march to the front"})


@router.post("/war/peace")
async def peace(req: Peace) -> dict[str, Any]:
    me = player()
    return await _do(lambda r: r.peace(GAME.state, me, req.target, req.kind, req.amount))
