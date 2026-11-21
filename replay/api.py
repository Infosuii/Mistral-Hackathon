"""Expose the engine's read-only replay of the most recent crisis."""

import asyncio
import os

from fastapi import APIRouter, HTTPException

from contracts.models import ReplayRequest, ReplayResponse
from engine.game import GAME

router = APIRouter()


async def explain(change: dict, shift_ticks: int) -> str:
    timing = "earlier" if shift_ticks < 0 else "later"
    fallback = f"The player's call moved {timing}, changing what was on the table when this leader decided."
    if os.environ.get("GAMBIT_AGENTS", "").lower() == "stub":
        return fallback
    try:
        from agents import why

        reason = await asyncio.wait_for(why({**change, "shift_ticks": shift_ticks}), timeout=2)
        return reason.strip() if isinstance(reason, str) and reason.strip() else fallback
    except Exception:
        return fallback


@router.post("/replay", response_model=ReplayResponse)
async def replay(request: ReplayRequest) -> ReplayResponse:
    async with GAME.lock:
        try:
            changed = GAME.replay(request.shift_ticks)
        except LookupError as error:
            raise HTTPException(409, "Finish a crisis before replaying it.") from error

    explanations = await asyncio.gather(*(explain(change, request.shift_ticks) for change in changed))
    return ReplayResponse.model_validate({
        "shift_ticks": request.shift_ticks,
        "changed": [{**change, "why": reason} for change, reason in zip(changed, explanations)],
    })
