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
from pydantic import BaseModel

from . import mock_agents
from .audio import CACHE, EMOTIONS, JOBS, speak, transcribe

router = APIRouter()
CASTING = json.loads((Path(__file__).parent / "casting.json").read_text())


def voice_for(nation: str) -> str:
    if nation not in CASTING or nation.startswith("_"):
        raise HTTPException(404, f"no voice cast for nation {nation!r}")
    return CASTING[nation]["voice_id"]


def _agents():
    """Use Abi's real functions when they exist, else the stand-ins."""
    try:
        import agents  # type: ignore
        call_reply = getattr(agents, "call_reply")
    except (ImportError, AttributeError):
        call_reply = (mock_agents.quick_reply if os.environ.get("VOICE_MOCK") == "llm"
                      else mock_agents.fixed_reply)
    return call_reply


def _apply_to_engine(to: str, out: dict) -> None:
    """Hand promises, actions and belief updates to the engine once it offers a hook."""
    try:
        import engine  # type: ignore
        apply_call = getattr(engine, "apply_call")
    except (ImportError, AttributeError):
        return
    apply_call(to, out)


class CallRequest(BaseModel):
    to: str
    audio: str | None = None     # base64 of whatever the browser recorded
    text: str | None = None      # typed fallback
    interrupted: bool = False
    hesitation_ms: int | None = None


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

    view = {"to": req.to, "transcript": transcript, "interrupted": req.interrupted,
            "hesitation_ms": req.hesitation_ms}
    out = await _agents()(view)
    if out.get("emotion") not in EMOTIONS:
        out["emotion"] = "calm"
    t_llm = time.perf_counter()

    _apply_to_engine(req.to, out)
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
