"""Standalone dev server for /voice: `uvicorn voice.app:app --port 8000`.

The real game serves these routes from Om's engine app instead.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import router

app = FastAPI(title="GAMBIT voice (dev)")
app.include_router(router)
app.mount("/voice-static", StaticFiles(directory=Path(__file__).parent / "static"), name="voice-static")
