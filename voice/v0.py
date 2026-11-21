"""V0 voice tests (MASTER_PLAN.md section 6).

    python -m voice.v0 sample      # make voice/v0_out/sample.wav (a synthetic player line)
    python -m voice.v0 timing      # talk -> reply -> first audio, 5 runs, median
    python -m voice.v0 emotion     # same line angry / calm / tense, shuffled for a blind test
    python -m voice.v0 formats     # which upload formats transcription accepts
    python -m voice.v0 all

The browser's own recording format (webm/opus from MediaRecorder) is tested
by the page at /voice-static/v0.html, because only a browser can produce it.
"""
from __future__ import annotations

import asyncio
import json
import random
import statistics
import sys
from pathlib import Path

from .audio import speak_to_file, transcribe
from .roundtrip import CASTING, run

OUT = Path(__file__).parent / "v0_out"
PLAYER_LINE = "We can split the day. Ostrava docks in the morning and Zarnia at night."
EMOTION_LINE = "You promised us the berth, and now you offer half a day."


async def sample() -> Path:
    OUT.mkdir(exist_ok=True)
    src, _, _ = await speak_to_file(PLAYER_LINE, CASTING["_player_test_voice"]["voice_id"],
                                    "calm", "wav")
    dst = OUT / "sample.wav"
    dst.write_bytes(src.read_bytes())
    print(f"wrote {dst} ({dst.stat().st_size} bytes)")
    return dst


async def timing(n: int = 5) -> dict:
    path = OUT / "sample.wav"
    if not path.exists():
        await sample()
    runs = []
    for i in range(n):
        r = await run(path)
        runs.append(r)
        print(f"run {i + 1}: first audio {r['first_audio_s']}s  (stt {r['stt_s']}, "
              f"reply {r['reply_s']}, tts {r['tts_first_chunk_s']})  [{r['emotion']}] "
              f"{r['reply_text']}")
    med = {k: round(statistics.median(r[k] for r in runs), 2)
           for k in ("stt_s", "reply_s", "tts_first_chunk_s", "first_audio_s")}
    print(f"transcript: {runs[0]['transcript']}")
    print(f"median: {med}")
    return med


async def emotion() -> None:
    OUT.mkdir(exist_ok=True)
    voice = CASTING["ostrava"]["voice_id"]
    labels = ["angry", "calm", "tense"]
    random.shuffle(labels)
    key = {}
    for i, emo in enumerate(labels):
        src, _, _ = await speak_to_file(EMOTION_LINE, voice, emo, "mp3")
        dst = OUT / f"blind_{'ABC'[i]}.mp3"
        dst.write_bytes(src.read_bytes())
        key[dst.name] = emo
    (OUT / "blind_key.json").write_text(json.dumps(key, indent=1))
    # One clip per leader, same line, for casting.
    for nation, c in CASTING.items():
        if nation.startswith("_"):
            continue
        src, _, _ = await speak_to_file(EMOTION_LINE, c["voice_id"], "calm", "mp3")
        (OUT / f"cast_{nation}.mp3").write_bytes(src.read_bytes())
    print(f"wrote blind_A/B/C.mp3 (answers in blind_key.json) and cast_<nation>.mp3 in {OUT}")


async def formats() -> dict:
    """Synthesize the player line in each output format and try to transcribe it."""
    voice = CASTING["_player_test_voice"]["voice_id"]
    result = {}
    for fmt in ("wav", "mp3", "opus", "flac"):
        path, _, _ = await speak_to_file(PLAYER_LINE, voice, "calm", fmt)
        try:
            text = await transcribe(path.read_bytes())
            result[fmt] = f"ok: {text}"
        except Exception as e:
            result[fmt] = f"FAILED: {e}"
        print(f"{fmt:5} {result[fmt]}")
    return result


FAST_LINES = [
    "We can split the day. You dock in the morning.", "Stop. Listen to me before you announce anything.",
    "I promised Zarnia nothing.", "Send your tugs and there will be two berths by nightfall.",
    "If you blockade the strait, Valdoria will close its markets to you.", "Fine. The berth is yours.",
    "Why should I trust you after last month?", "Um... I need a moment.",
    "Your people are starving and you want to talk about pride?", "Goodbye, General.",
]


async def fastcheck(n: int = 20) -> None:
    """Does the fast phone model return valid structured replies? (DECIDED 12:29)"""
    import re
    import time
    from .mock_agents import FAST_MODEL, _ask, _messages
    from .audio import EMOTIONS
    nations = [k for k in CASTING if not k.startswith("_")]
    ok, times, problems = 0, [], []
    for i in range(n):
        view = {"nation": nations[i % len(nations)], "transcript": FAST_LINES[i % len(FAST_LINES)],
                "interrupted": i % 4 == 1, "history": None}
        t = time.perf_counter()
        try:
            out = await _ask(FAST_MODEL, _messages(view))
        except Exception as e:
            problems.append(f"{i}: {e}")
            continue
        times.append(time.perf_counter() - t)
        sentences = len([s for s in re.split(r"(?<=[.!?])\s+", out["reply_text"]) if s.strip()])
        if out["emotion"] not in EMOTIONS:
            problems.append(f"{i}: emotion {out['emotion']!r} not in the enum")
        elif sentences > 2:
            problems.append(f"{i}: {sentences} sentences")
        else:
            ok += 1
    print(f"{FAST_MODEL}: {ok}/{n} valid; median {statistics.median(times):.2f}s, "
          f"max {max(times):.2f}s")
    for p in problems:
        print("  ", p)


async def main(cmd: str) -> None:
    if cmd == "fastcheck":
        await fastcheck()
        return
    if cmd in ("sample", "all"):
        await sample()
    if cmd in ("formats", "all"):
        await formats()
    if cmd in ("emotion", "all"):
        await emotion()
    if cmd in ("timing", "all"):
        await timing()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "all"))
