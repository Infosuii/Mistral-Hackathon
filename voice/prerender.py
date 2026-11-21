"""V3: render the demo's fixed lines ahead of time so they play instantly, even offline.

    python -m voice.prerender           # render anything missing into voice/prerendered/
    python -m voice.prerender --check   # exit 1 if a line is missing (no network calls)

Covers every scripted incoming_call in data/crises/*.json and the drafts in voice/crises/*.json, the Wiretap scripts in
voice/demo_lines.json, and the "line is breaking up" fallback for every leader.
The files are committed, so every laptop has them without an API key.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from .audio import PRERENDERED, cache_key, find_audio, stream_speech

ROOT = Path(__file__).resolve().parent.parent
CASTING = json.loads((Path(__file__).parent / "casting.json").read_text())
FALLBACK_LINE = ("The line is breaking up. Say that again.", "tense")  # matches voice/api.py


def demo_lines() -> list[tuple[str, str, str, str]]:
    """(label, nation, text, emotion) for every fixed line in the demo."""
    out = []
    drafts = sorted((Path(__file__).parent / "crises").glob("*.json"))  # V4 files before they move to data/crises
    for f in sorted((ROOT / "data" / "crises").glob("*.json")) + drafts:
        crisis = json.loads(f.read_text(encoding="utf-8"))
        for e in crisis.get("scripted", []):
            if e.get("type") == "incoming_call" and e.get("opening_line"):
                out.append((f"{crisis['id']} tick {e['tick']}", e["from"], e["opening_line"], e.get("emotion")))
    wiretap = json.loads((Path(__file__).parent / "demo_lines.json").read_text(encoding="utf-8"))["wiretap"]
    for pair, lines in wiretap.items():
        for i, line in enumerate(lines):
            out.append((f"wiretap {pair} #{i + 1}", line["speaker"], line["text"], line.get("emotion")))
    for nation in CASTING:
        if not nation.startswith("_"):
            out.append((f"fallback {nation}", nation, *FALLBACK_LINE))
    return out


def file_name(nation: str, text: str, emotion: str | None) -> str:
    return f"{cache_key(text, CASTING[nation]['voice_id'], emotion)}.mp3"


async def render(check_only: bool) -> int:
    PRERENDERED.mkdir(exist_ok=True)
    missing = 0
    for label, nation, text, emotion in demo_lines():
        name = file_name(nation, text, emotion)
        if (PRERENDERED / name).exists():
            print(f"ok      {label}")
            continue
        if check_only:
            missing += 1
            print(f"MISSING {label}: {text}")
            continue
        cached = find_audio(name)
        if cached is not None:
            data = cached.read_bytes()
        else:
            data = b"".join([c async for c in stream_speech(text, CASTING[nation]["voice_id"], emotion)])
        (PRERENDERED / name).write_bytes(data)
        print(f"render  {label} ({len(data) // 1024} KB)")
    return missing


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(render("--check" in sys.argv)) else 0)
