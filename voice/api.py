"""Voice endpoints: POST /call, GET /wiretap, GET /audio/<file>, POST /transcribe.

Om's engine app mounts these with `app.include_router(voice.api.router)`.
For working alone, `uvicorn voice.app:app --port 8000` serves them by themselves.

Set VOICE_MOCK=fixed (default) or VOICE_MOCK=llm to choose the stand-in for
agents.call_reply() while /agents is not on main.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from contracts.models import CallOutput, CallRequest, CallView

from . import mock_agents
from .audio import CACHE, EMOTIONS, JOBS, speak, transcribe

router = APIRouter()
CASTING = json.loads((Path(__file__).parent / "casting.json").read_text())


def voice_for(nation: str) -> str:
    if nation not in CASTING or nation.startswith("_"):
        raise HTTPException(404, f"no voice cast for nation {nation!r}")
    return CASTING[nation]["voice_id"]


def _agents():
    """(call_reply, is_real): Abi's function when it exists, else a stand-in."""
    try:
        import agents  # type: ignore
        return getattr(agents, "call_reply"), True
    except (ImportError, AttributeError):
        return (mock_agents.quick_reply if os.environ.get("VOICE_MOCK") == "llm"
                else mock_agents.fixed_reply), False


EXAMPLE_STATE = Path(__file__).resolve().parent.parent / "contracts" / "examples" / "state.json"


def _game():
    """Om's live game (engine/game.py), or None when /voice runs on its own."""
    try:
        from engine.game import GAME  # type: ignore
        return GAME
    except ImportError:
        return None


def _current_state() -> dict:
    game = _game()
    if game is not None:
        return game.state.model_dump(mode="json", by_alias=True)
    return json.loads(EXAMPLE_STATE.read_text())


def _apply_to_engine(req: CallRequest, out: CallOutput) -> None:
    """Belief updates and promises take effect at once; actions on the next turn."""
    game = _game()
    if game is not None:
        game.apply_call(req.to, out, interrupted=req.interrupted, hesitation_ms=req.hesitation_ms)


# One running conversation per nation (CallView.history, decided 12:14). A call ends when
# the leader sets ends_call, or after CALL_IDLE_S of silence.
CALL_IDLE_S = 180
_calls: dict[str, dict] = {}


def _history(nation: str, state: dict) -> list[dict]:
    call = _calls.get(nation)
    if call is None or time.time() - call["at"] > CALL_IDLE_S:
        call = _calls[nation] = {"at": time.time(), "turns": []}
        ring = state.get("incoming_call") or {}
        if ring.get("from") == nation and ring.get("opening_line"):
            call["turns"].append({"role": "leader", "text": ring["opening_line"]})
    return call["turns"]


FALLBACK_REPLY = {
    "reply_text": "The line is breaking up. Say that again.",
    "emotion": "tense", "promises": [], "actions": [],
    "belief_updates": {"trust_in_player": 0, "resolve_of_player": 0}, "ends_call": False,
}


@router.post("/call")
async def call(req: CallRequest):
    voice_id = voice_for(req.to)
    t0 = time.perf_counter()
    if req.text is not None:
        transcript = req.text.strip()
    elif req.audio:
        try:
            transcript = await transcribe(base64.b64decode(req.audio))
        except Exception as e:
            raise HTTPException(502, f"transcription failed: {e}")
    else:
        raise HTTPException(422, "send audio or text")
    t_stt = time.perf_counter()

    state = _current_state()
    history = _history(req.to, state)
    view = {"nation": req.to, "transcript": transcript, "interrupted": req.interrupted,
            "hesitation_ms": req.hesitation_ms, "state": state,
            "history": list(history) or None}
    try:
        call_reply, real = _agents()
        raw = await call_reply(CallView.model_validate(view) if real else view)
        if hasattr(raw, "model_dump"):
            raw = raw.model_dump(mode="json")
        if raw.get("emotion") not in EMOTIONS:  # an off-list tag is ignored by Voxtral anyway
            raw["emotion"] = "calm"
        result = CallOutput.model_validate(raw)
    except Exception as e:  # never leave the player in silence
        print(f"[voice] call_reply failed, using fallback line: {e}")
        result = CallOutput.model_validate(FALLBACK_REPLY)
    out = result.model_dump(mode="json")
    t_llm = time.perf_counter()

    history += [{"role": "player", "text": transcript}, {"role": "leader", "text": out["reply_text"]}]
    _calls[req.to]["at"] = time.time()
    if out.get("ends_call"):
        _calls.pop(req.to, None)

    _apply_to_engine(req, result)
    url = await speak(out["reply_text"], voice_id, out["emotion"])
    print(f"[voice] /call {req.to}: stt {t_stt - t0:.2f}s, reply {t_llm - t_stt:.2f}s")
    return {
        "transcript": transcript,
        "reply_text": out["reply_text"],
        "reply_audio_url": url,
        "emotion": out["emotion"],
        "promises": out.get("promises", []),
        "actions": out.get("actions", []),
    }


@router.get("/wiretap")
async def wiretap(a: str, b: str):
    try:
        import agents  # type: ignore
        lines = await agents.wiretap(a, b)
    except (ImportError, AttributeError):
        lines = await mock_agents.wiretap_lines(a, b)
    out = []
    for line in lines:
        url = await speak(line["text"], voice_for(line["speaker"]), line.get("emotion"))
        out.append({"speaker": line["speaker"], "text": line["text"], "audio_url": url})
    return {"lines": out}


@router.post("/transcribe")
async def transcribe_raw(request: Request):
    """Raw audio body in, {"text"} out. Used by the talk button's live transcript and V0."""
    body = await request.body()
    if not body:
        raise HTTPException(422, "empty body")
    t0 = time.perf_counter()
    try:
        text = await transcribe(body, request.headers.get("content-type"))
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"text": text, "seconds": round(time.perf_counter() - t0, 2), "bytes": len(body)}


@router.get("/voice/talk-button.js")
async def talk_button_js():
    return FileResponse(Path(__file__).parent / "talk-button.js", media_type="text/javascript")


MEDIA = {"mp3": "audio/mpeg", "wav": "audio/wav", "opus": "audio/ogg", "flac": "audio/flac"}


@router.get("/audio/{name}")
async def audio(name: str):
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "bad name")
    media = MEDIA.get(name.rsplit(".", 1)[-1], "application/octet-stream")
    path = CACHE / name
    if path.exists():
        return FileResponse(path, media_type=media)
    job = JOBS.get(name)
    if job is None:
        raise HTTPException(404, "unknown audio")

    async def chunks():
        i = 0
        while True:
            async with job.cond:
                await job.cond.wait_for(lambda: len(job.chunks) > i or job.done)
                new = job.chunks[i:]
                finished = job.done
            for c in new:
                yield c
            i += len(new)
            if finished and i >= len(job.chunks):
                return

    return StreamingResponse(chunks(), media_type=media)
