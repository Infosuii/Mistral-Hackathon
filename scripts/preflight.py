#!/usr/bin/env python3
"""Preflight for the demo laptop: can this machine reach every Mistral service the game uses?

    python scripts/preflight.py          # about 10 seconds, a handful of tiny requests

Checks the key, each chat model the game calls, speech generation and transcription, and
prints one line per check with the time it took and, on failure, the HTTP status and reason
(401 = bad key, 429 = rate limit: someone else is using the shared key). Exits 1 if any
check fails. Run it before the playtest, the recording and judging.
"""
from __future__ import annotations

import base64
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass
import httpx

API = "https://api.mistral.ai/v1"
CHAT_MODELS = [
    ("spoken replies", os.environ.get("GAMBIT_FAST_MODEL", "mistral-large-2512")),
    ("reply fallback and monthly decisions", os.environ.get("GAMBIT_FAST_FALLBACK", "mistral-medium-latest")),
    ("Le Chonk: promises, strategy, verdict", "mistral-large-4"),
]


def line(ok: bool, name: str, seconds: float, detail: str = "") -> bool:
    print(f"{'ok  ' if ok else 'FAIL'}  {seconds:5.1f}s  {name}" + (f"  — {detail}" if detail else ""))
    return ok


def explain(r: httpx.Response) -> str:
    hint = {401: "the key is wrong or revoked", 403: "this key may not use this model",
            429: "rate limited: another machine or agent is using the same key"}.get(r.status_code, "")
    return f"HTTP {r.status_code} {hint or r.text[:120]}".strip()


def main() -> int:
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        print("FAIL  no MISTRAL_API_KEY. Put it in .env at the repo root. Without it every leader "
              "answers with the setup-problem line and nothing works.")
        return 1
    print(f"key   found, ends in ...{key[-4:]}")
    ok = True
    with httpx.Client(headers={"Authorization": f"Bearer {key}"}, timeout=40) as c:
        for what, model in CHAT_MODELS:
            t = time.perf_counter()
            try:
                r = c.post(f"{API}/chat/completions", json={"model": model, "max_tokens": 8,
                           "messages": [{"role": "user", "content": "Reply with the one word: ready"}]})
                ok &= line(r.status_code == 200, f"{model} ({what})", time.perf_counter() - t,
                           "" if r.status_code == 200 else explain(r))
            except Exception as e:
                ok &= line(False, f"{model} ({what})", time.perf_counter() - t, f"{type(e).__name__}: {e}")
        audio = b""
        t = time.perf_counter()
        try:
            r = c.post(f"{API}/audio/speech", json={"model": "voxtral-mini-tts-3-0", "voice_id": "gb_jane_neutral",
                       "input": "The berth is yours for the morning.", "response_format": "mp3"})
            if r.status_code == 200:
                audio = base64.b64decode(r.json()["audio_data"])
            ok &= line(r.status_code == 200 and len(audio) > 1000, "Voxtral speech (leaders' voices)",
                       time.perf_counter() - t, "" if r.status_code == 200 else explain(r))
        except Exception as e:
            ok &= line(False, "Voxtral speech (leaders' voices)", time.perf_counter() - t, f"{type(e).__name__}: {e}")
        if audio:
            t = time.perf_counter()
            try:
                r = c.post(f"{API}/audio/transcriptions", data={"model": "voxtral-mini-transcribe-3"},
                           files={"file": ("check.mp3", audio, "audio/mpeg")})
                text = r.json().get("text", "") if r.status_code == 200 else ""
                ok &= line(r.status_code == 200 and "berth" in text.lower(), "Voxtral transcription (your voice)",
                           time.perf_counter() - t, f'heard "{text.strip()[:50]}"' if r.status_code == 200 else explain(r))
            except Exception as e:
                ok &= line(False, "Voxtral transcription (your voice)", time.perf_counter() - t, f"{type(e).__name__}: {e}")
    print("\nAll clear: this machine can run the live game." if ok else
          "\nNot ready: fix the FAIL lines above before anyone picks up the microphone.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
