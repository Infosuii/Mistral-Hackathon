"""Thin async wrappers over the Voxtral endpoints: transcribe() and speak().

speak() returns a URL straight away and synthesis streams in the background, so
the page can start playing the first chunk while the rest is still arriving.
Finished audio is cached on disk by (text, voice, emotion, format).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API = "https://api.mistral.ai/v1"
STT_MODEL = "voxtral-mini-transcribe-3"
TTS_MODEL = "voxtral-mini-tts-3-0"
CACHE = Path(__file__).resolve().parent / "cache"
AUDIO_BASE = os.environ.get("VOICE_AUDIO_BASE", "/audio")

# MASTER_PLAN.md section 4.6. Anything else is silently ignored by Voxtral.
EMOTIONS = {
    "angry", "anxious", "assertive", "calm", "confident", "critical", "determined",
    "disappointed", "frustrated", "proud", "sarcastic", "skeptical", "tense",
    "urgent", "warm",
}

# Proper nouns the player will say; biases transcription towards them.
BIAS_TERMS = ["Ostrava", "Zarnia", "Nordhaven", "Kessaria", "Valdoria", "Port Kessar",
              "Dravic", "berth", "blockade", "tugs"]

_clients: dict[int, httpx.AsyncClient] = {}


def _client() -> httpx.AsyncClient:
    """One keep-alive client per event loop, so repeated calls skip the TLS handshake."""
    loop = id(asyncio.get_running_loop())
    if loop not in _clients:
        key = os.environ.get("MISTRAL_API_KEY")
        if not key:
            raise RuntimeError("MISTRAL_API_KEY is not set (put it in .env)")
        _clients[loop] = httpx.AsyncClient(
            base_url=API,
            headers={"Authorization": f"Bearer {key}"},
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
    return _clients[loop]


# ---------------------------------------------------------------- speech to text

def sniff_format(audio: bytes) -> tuple[str, str]:
    """Guess (extension, mime) from the first bytes. The browser usually sends webm/opus."""
    head = audio[:12]
    if head[:4] == b"RIFF":
        return "wav", "audio/wav"
    if head[:4] == b"\x1aE\xdf\xa3":
        return "webm", "audio/webm"
    if head[:4] == b"OggS":
        return "ogg", "audio/ogg"
    if head[4:8] == b"ftyp":
        return "m4a", "audio/mp4"
    if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3", "audio/mpeg"
    return "webm", "audio/webm"


async def transcribe(audio: bytes, mime: str | None = None) -> str:
    ext, sniffed = sniff_format(audio)
    files = {"file": (f"speech.{ext}", audio, mime or sniffed)}
    data = {"model": STT_MODEL, "language": "en", "context_bias": BIAS_TERMS}
    r = await _client().post("/audio/transcriptions", data=data, files=files)
    if r.status_code != 200:
        raise RuntimeError(f"transcribe failed {r.status_code}: {r.text[:300]}")
    return r.json().get("text", "").strip()


# ---------------------------------------------------------------- text to speech

def tagged(text: str, emotion: str | None) -> str:
    if emotion in EMOTIONS:
        return f"[emotion={emotion}]{text}"
    return text


def cache_key(text: str, voice_id: str, emotion: str | None, fmt: str = "mp3") -> str:
    raw = json.dumps([text, voice_id, emotion or "", fmt])
    return hashlib.sha1(raw.encode()).hexdigest()[:20]


async def stream_speech(text: str, voice_id: str, emotion: str | None, fmt: str = "mp3"):
    """Yield audio bytes as Voxtral produces them."""
    body = {
        "model": TTS_MODEL,
        "input": tagged(text, emotion),
        "voice_id": voice_id,
        "response_format": fmt,
        "stream": True,
    }
    async with _client().stream("POST", "/audio/speech", json=body) as r:
        if r.status_code != 200:
            raise RuntimeError(
                f"speak failed {r.status_code}: {(await r.aread())[:300]!r}"
            )
        async for line in r.aiter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:])
            if event.get("type") == "speech.audio.delta":
                yield base64.b64decode(event["audio_data"])
            elif event.get("type") == "speech.audio.done":
                return


@dataclass
class Job:
    """An in-flight synthesis. GET /audio/<name> replays chunks while it runs."""
    chunks: list[bytes] = field(default_factory=list)
    done: bool = False
    error: str | None = None
    started: float = field(default_factory=time.perf_counter)
    first_chunk_s: float | None = None
    cond: asyncio.Condition = field(default_factory=asyncio.Condition)


JOBS: dict[str, Job] = {}


async def _run(name: str, text: str, voice_id: str, emotion: str | None, fmt: str):
    job = JOBS[name]
    try:
        async for chunk in stream_speech(text, voice_id, emotion, fmt):
            async with job.cond:
                if job.first_chunk_s is None:
                    job.first_chunk_s = time.perf_counter() - job.started
                job.chunks.append(chunk)
                job.cond.notify_all()
        CACHE.mkdir(exist_ok=True)
        tmp = CACHE / f"{name}.part"
        tmp.write_bytes(b"".join(job.chunks))
        tmp.replace(CACHE / name)
    except Exception as e:  # surfaced to the audio request and the log
        job.error = str(e)
        print(f"[voice] synthesis failed for {name}: {e}")
    finally:
        async with job.cond:
            job.done = True
            job.cond.notify_all()
        if job.error is None:  # the cached file serves from now on; readers keep their ref
            JOBS.pop(name, None)


async def speak(text: str, voice_id: str, emotion: str | None = None, fmt: str = "mp3") -> str:
    """Start (or reuse) synthesis and return the URL the page can play right away."""
    name = f"{cache_key(text, voice_id, emotion, fmt)}.{fmt}"
    if not (CACHE / name).exists() and (name not in JOBS or JOBS[name].error):
        JOBS[name] = Job()
        asyncio.create_task(_run(name, text, voice_id, emotion, fmt))
    return f"{AUDIO_BASE}/{name}"


async def speak_to_file(text: str, voice_id: str, emotion: str | None = None,
                        fmt: str = "mp3") -> tuple[Path, float, float]:
    """Synthesize fully and wait. Returns (path, seconds to first chunk, total seconds).
    For scripts and pre-rendering; the server uses speak()."""
    name = f"{cache_key(text, voice_id, emotion, fmt)}.{fmt}"
    path = CACHE / name
    if path.exists():
        return path, 0.0, 0.0
    t0 = time.perf_counter()
    first = None
    chunks = []
    async for chunk in stream_speech(text, voice_id, emotion, fmt):
        if first is None:
            first = time.perf_counter() - t0
        chunks.append(chunk)
    CACHE.mkdir(exist_ok=True)
    path.write_bytes(b"".join(chunks))
    return path, first or 0.0, time.perf_counter() - t0
