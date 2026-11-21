"""Expose the engine's read-only replay of the most recent crisis."""

import asyncio
import os

from fastapi import APIRouter, HTTPException

from contracts.models import ReplayRequest, ReplayResponse
from engine.game import GAME

router = APIRouter()


def timing_reason(change: dict, inputs: dict) -> str:
    decision_tick = inputs["original_decision_tick"]
    nation = change["nation"].title()
    for call in inputs["calls"]:
        if call["to"] != change["nation"]:
            continue
        before, after = call["original_tick"], call["shifted_tick"]
        if before < decision_tick <= after:
            return f"The call moved from tick {before} to {after}, after {nation}'s original decision."
        if after < decision_tick <= before:
            return f"The call moved from tick {before} to {after}, reaching {nation} before its original decision."
    return "Moving the calls changed which commitments were in place when this leader decided."


async def explain(change: dict, shift_ticks: int, inputs: dict) -> str:
    fallback = timing_reason(change, inputs)
    if os.environ.get("GAMBIT_AGENTS", "").lower() == "stub":
        return fallback
    try:
        from agents import why

        # The hook's own budget is eight seconds, including its fallback model.
        reason = await asyncio.wait_for(why({**change, "shift_ticks": shift_ticks, "inputs": inputs}), timeout=8.5)
        return reason.strip() if isinstance(reason, str) and reason.strip() else fallback
    except Exception:
        return fallback


@router.post("/replay", response_model=ReplayResponse)
async def replay(request: ReplayRequest) -> ReplayResponse:
    shift = request.shift_ticks
    async with GAME.lock:
        archived = GAME.last_crisis
        if archived is None:
            raise HTTPException(409, "Finish a crisis before replaying it.")
        changed = GAME.replay(shift)
        crisis = archived["start"].crisis
        calls = [
            {
                "to": to,
                "original_tick": tick,
                "shifted_tick": min(crisis.ticks_total, max(0, tick + shift)),
                "promises": [promise.model_dump(mode="json") for promise in output.promises],
                "actions": [action.type for action in output.actions],
                "interrupted": interrupted,
            }
            for tick, to, output, interrupted in archived["calls"]
        ]
        inputs = [
            {
                "original_decision_tick": archived["decisions"][change["nation"]].tick,
                "deadline_tick": crisis.deadlines.get(change["nation"]),
                "calls": calls,
            }
            for change in changed
        ]

    explanations = await asyncio.gather(*(explain(change, shift, facts) for change, facts in zip(changed, inputs)))
    return ReplayResponse.model_validate({
        "shift_ticks": shift,
        "changed": [{**change, "why": reason} for change, reason in zip(changed, explanations)],
    })
