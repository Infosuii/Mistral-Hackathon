"""Standalone dev server for /voice: `uvicorn voice.app:app --port 8000`.

The real game serves these routes from Om's engine app instead.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import CASTING, router
from .audio import AUDIO_BASE, speak_to_file

app = FastAPI(title="GAMBIT voice (dev)")

BLIND_LINE = "You promised us the berth, and now you offer half a day."


@app.get("/dev/blind-set")
async def blind_set():
    """Clips for the blind emotion test at /voice-static/blind.html: same line, three tags."""
    clips = []
    for nation in ("ostrava", "kessaria"):
        cast = CASTING[nation]
        for emotion in ("angry", "calm", "tense"):
            path, _, _ = await speak_to_file(BLIND_LINE, cast["voice_id"], emotion)
            clips.append({"voice": f"{cast['name']} ({nation})", "emotion": emotion,
                          "url": f"{AUDIO_BASE}/{path.name}"})
    return {"line": BLIND_LINE, "clips": clips}
app.include_router(router)
app.include_router(router, prefix="/api")  # same as engine/app.py
app.mount("/voice-static", StaticFiles(directory=Path(__file__).parent / "static"), name="voice-static")
