"""GAMBIT voice (Ashish): Voxtral speech in and out. See voice/README.md."""
import json as _json
from pathlib import Path as _Path

from .audio import speak, start_speech, transcribe

_CASTING = _json.loads((_Path(__file__).parent / "casting.json").read_text())


def audio_url_for(nation: str, text: str, emotion: str | None = None) -> str | None:
    """URL of a leader line in that leader's voice, for state.incoming_call.audio_url.

    Instant for pre-rendered lines (voice/prerendered/). Otherwise starts rendering in the
    running event loop and returns a URL that streams as it renders. None if the nation has
    no voice or the line cannot be started (no loop running)."""
    cast = _CASTING.get(nation)
    if not cast or nation.startswith("_"):
        return None
    return start_speech(text, cast["voice_id"], emotion)


__all__ = ["audio_url_for", "speak", "start_speech", "transcribe"]
