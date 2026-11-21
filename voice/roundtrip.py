"""Talk -> reply -> first audio, timed.

    python -m voice.roundtrip sample.wav [--to ostrava] [--fixed] [--no-play]

Prints the transcript, the leader's reply, and seconds from "player stopped
talking" to the first audio chunk (target under 3). Uses the quick stand-in
leader call unless agents.call_reply exists; --fixed skips the model.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import mock_agents
from .audio import CACHE, cache_key, stream_speech, transcribe

CASTING = json.loads((Path(__file__).parent / "casting.json").read_text())


async def run(path: Path, to: str = "ostrava", fixed: bool = False) -> dict:
    audio = path.read_bytes()
    t0 = time.perf_counter()
    transcript = await transcribe(audio)
    t_stt = time.perf_counter()

    view = {"to": to, "transcript": transcript, "interrupted": False, "hesitation_ms": None}
    try:
        from agents import call_reply  # type: ignore
    except ImportError:
        call_reply = mock_agents.fixed_reply if fixed else mock_agents.quick_reply
    out = await call_reply(view)
    t_llm = time.perf_counter()

    voice = CASTING[to]["voice_id"]
    chunks, t_first = [], None
    async for chunk in stream_speech(out["reply_text"], voice, out.get("emotion")):
        if t_first is None:
            t_first = time.perf_counter()
        chunks.append(chunk)
    t_done = time.perf_counter()

    CACHE.mkdir(exist_ok=True)
    reply_path = CACHE / f"{cache_key(out['reply_text'], voice, out.get('emotion'))}.mp3"
    reply_path.write_bytes(b"".join(chunks))
    return {
        "transcript": transcript,
        "reply_text": out["reply_text"],
        "emotion": out.get("emotion"),
        "stt_s": round(t_stt - t0, 2),
        "reply_s": round(t_llm - t_stt, 2),
        "tts_first_chunk_s": round(t_first - t_llm, 2),
        "first_audio_s": round(t_first - t0, 2),
        "full_audio_s": round(t_done - t0, 2),
        "reply_file": str(reply_path),
    }


def play(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # default player
    elif sys.platform == "darwin":
        subprocess.Popen(["afplay", path])
    else:
        subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path])


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("audio", type=Path)
    p.add_argument("--to", default="ostrava")
    p.add_argument("--fixed", action="store_true", help="skip the model; use the 4.6 example")
    p.add_argument("--no-play", action="store_true")
    a = p.parse_args()
    r = asyncio.run(run(a.audio, a.to, a.fixed))
    print(f"transcript : {r['transcript']}")
    print(f"reply      : [{r['emotion']}] {r['reply_text']}")
    print(f"timings    : stt {r['stt_s']}s + reply {r['reply_s']}s + tts first chunk "
          f"{r['tts_first_chunk_s']}s")
    print(f"seconds to first audio: {r['first_audio_s']}  (full audio {r['full_audio_s']}s)")
    if not a.no_play:
        play(r["reply_file"])


if __name__ == "__main__":
    main()
