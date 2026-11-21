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


def _load_env(path: Path) -> None:
    """Read KEY=VALUE lines from the repo's .env without overriding real env vars.
    Kept dependency-free so a plain `pip install -r requirements.txt` can mount /voice."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


_load_env(Path(__file__).resolve().parent.parent / ".env")

API = "https://api.mistral.ai/v1"
STT_MODEL = "voxtral-mini-transcribe-3"
TTS_MODEL = "voxtral-mini-tts-3-0"
CACHE = Path(os.environ.get("GAMBIT_VOICE_CACHE") or Path(__file__).resolve().parent / "cache")  # gitignored, per machine
PRERENDERED = Path(__file__).resolve().parent / "prerendered"  # committed demo lines (V3)
AUDIO_BASE = os.environ.get("VOICE_AUDIO_BASE", "/audio")

# Said when a reply cannot be produced or spoken. Pre-rendered for every cast voice (voice/prerender.py).
FALLBACK_LINE = ("The line is breaking up. Say that again.", "tense")

# MASTER_PLAN.md section 4.6. Anything else is silently ignored by Voxtral.
EMOTIONS = {
    "angry", "anxious", "assertive", "calm", "confident", "critical", "determined",
    "disappointed", "frustrated", "proud", "sarcastic", "skeptical", "tense",
    "urgent", "warm",
}

# Proper nouns the player will say; biases transcription towards them.
BIAS_TERMS = ["Ostrava", "Zarnia", "Nordhaven", "Kessaria", "Valdoria", "Port Kessar",
              "Dravic", "Lindqvist", "Oryn", "Isolde", "Varga",  # leaders' names (noise test)
              "berth", "blockade", "tugs"]

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

class BadAudio(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def sniff_format(audio: bytes) -> tuple[str, str]:
    """Guess (extension, mime) from the first bytes. The browser usually sends webm/opus."""
    head = audio[:12]
    if head[:4] == b"fLaC":
        return "flac", "audio/flac"
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
    raise BadAudio(415, "Unsupported recording format.")


class VoiceRateLimited(RuntimeError):
    def __init__(self, retry_after: int):
        super().__init__("speech quota is busy")
        self.retry_after = retry_after


_audio_cooldowns: dict[str, float] = {}


def _check_quota(kind: str) -> None:
    remaining = _audio_cooldowns.get(kind, 0) - time.monotonic()
    if remaining > 0:
        raise VoiceRateLimited(max(1, int(remaining + 0.999)))


def _record_quota(kind: str, header: str | None) -> None:
    try:
        seconds = max(1, int(header or "2"))
    except ValueError:
        seconds = 2
    _audio_cooldowns[kind] = time.monotonic() + seconds
    raise VoiceRateLimited(seconds)


async def transcribe(audio: bytes, mime: str | None = None) -> str:
    _check_quota("stt")
    ext, sniffed = sniff_format(audio)
    files = {"file": (f"speech.{ext}", audio, sniffed)}
    data = {"model": STT_MODEL, "language": "en", "context_bias": BIAS_TERMS}
    r = await _client().post("/audio/transcriptions", data=data, files=files)
    if r.status_code == 429:
        _record_quota("stt", r.headers.get("retry-after"))
    if r.status_code in (400, 415, 422):
        raise BadAudio(422, "Could not transcribe this recording.")
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
    _check_quota("tts")
    body = {
        "model": TTS_MODEL,
        "input": tagged(text, emotion),
        "voice_id": voice_id,
        "response_format": fmt,
        "stream": True,
    }
    async with _client().stream("POST", "/audio/speech", json=body) as r:
        if r.status_code == 429:
            _record_quota("tts", r.headers.get("retry-after"))
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
    tmp = CACHE / f"{name}.part"
    try:
        async for chunk in stream_speech(text, voice_id, emotion, fmt):
            async with job.cond:
                if job.first_chunk_s is None:
                    job.first_chunk_s = time.perf_counter() - job.started
                job.chunks.append(chunk)
                job.cond.notify_all()
        CACHE.mkdir(exist_ok=True)
        if not job.chunks:
            raise RuntimeError("Speech service returned no audio.")
        tmp.write_bytes(b"".join(job.chunks))
        tmp.replace(CACHE / name)
    except Exception as e:  # surfaced to the audio request and the log
        job.error = str(e)
        print(f"[voice] synthesis failed for {name}: {e}")
        fallback = find_audio(f"{cache_key(FALLBACK_LINE[0], voice_id, FALLBACK_LINE[1], fmt)}.{fmt}")
        if not isinstance(e, VoiceRateLimited) and fallback is not None and not job.chunks:  # e.g. a 403 guardrail block: never leave the call silent
            async with job.cond:
                job.chunks.append(fallback.read_bytes())
                job.cond.notify_all()
            print(f"[voice] played the pre-rendered fallback line instead of {name}")
    finally:
        async with job.cond:
            job.done = True
            job.cond.notify_all()
        tmp.unlink(missing_ok=True)
        if job.error is None:
            JOBS.pop(name, None)
        else:
            # Keep the failure or fallback long enough for the URL in the reply to be read.
            def expire():
                if JOBS.get(name) is job:
                    JOBS.pop(name)
            asyncio.get_running_loop().call_later(60, expire)


def find_audio(name: str) -> Path | None:
    """A finished file: the committed demo renders first, then the local cache."""
    for folder in (PRERENDERED, CACHE):
        if (folder / name).exists():
            return folder / name
    return None


def start_speech(text: str, voice_id: str, emotion: str | None = None,
                 fmt: str = "mp3") -> str | None:
    """Sync version of speak() for code already inside the event loop (the engine's turn).
    Returns the URL, or None if the line is not rendered and no loop is running."""
    name = f"{cache_key(text, voice_id, emotion, fmt)}.{fmt}"
    if find_audio(name) is None and not os.environ.get("MISTRAL_API_KEY") and os.environ.get("VOICE_MOCK") == "fixed":
        return None
    if find_audio(name) is None and (name not in JOBS or JOBS[name].error):
        if _audio_cooldowns.get("tts", 0) > time.monotonic():
            return None
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return None
        JOBS[name] = Job()
        task = asyncio.create_task(_run(name, text, voice_id, emotion, fmt))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    return f"{AUDIO_BASE}/{name}"


_tasks: set[asyncio.Task] = set()


async def speak(text: str, voice_id: str, emotion: str | None = None, fmt: str = "mp3") -> str | None:
    """Start (or reuse) synthesis and return the URL the page can play right away."""
    return start_speech(text, voice_id, emotion, fmt)


async def speak_to_file(text: str, voice_id: str, emotion: str | None = None,
                        fmt: str = "mp3") -> tuple[Path, float, float]:
    """Synthesize fully and wait. Returns (path, seconds to first chunk, total seconds).
    For scripts and pre-rendering; the server uses speak()."""
    name = f"{cache_key(text, voice_id, emotion, fmt)}.{fmt}"
    path = find_audio(name) or CACHE / name
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
