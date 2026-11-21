# /voice — Voxtral speech in and out (Ashish)

Issue #29 · tasks V0–V4, D1–D3 in MASTER_PLAN.md · casting in `CASTING.md`.

## Run it alone

```
pip install fastapi "uvicorn[standard]" httpx python-multipart python-dotenv
uvicorn voice.app:app --port 8000          # MISTRAL_API_KEY in .env at the repo root
curl -X POST localhost:8000/call -H "Content-Type: application/json" \
     -d '{"to":"ostrava","text":"We can split the day."}'
python -m voice.roundtrip voice/v0_out/sample.wav    # make the sample with: python -m voice.v0 sample
```

## In the game

`engine/app.py` mounts `voice.api.router` automatically, at the root and under `/api`:
`uvicorn engine.app:app --reload --port 8000`.

`/call` builds a `CallView` from `GAME.state` plus this call's `history` (kept per nation
until `ends_call` or 3 idle minutes; seeded with `state.incoming_call.opening_line`). It calls
`agents.call_reply` when it exists and a stand-in otherwise, validates the result as
`CallOutput`, then runs `GAME.apply_call(...)` so trust, resolve, promises and the
interruption penalty land in the state. If the leader call fails, the player hears a short
"line is breaking up" line instead of silence.

## Python API (MASTER_PLAN.md §4.1)

- `await transcribe(audio: bytes, mime: str | None = None) -> str`: any of webm/opus (Chrome's
  MediaRecorder default), ogg, wav, mp3, flac. The format is sniffed from the bytes. Nation
  names are passed as `context_bias`.
- `await speak(text, voice_id, emotion) -> str`: returns `/audio/<hash>.mp3` at once. Synthesis
  streams in the background, and a GET on that URL streams the bytes as they arrive, so first
  audio comes after about 0.3 s. Cached on disk in `voice/cache/` by (text, voice, emotion).
- `await speak_to_file(...)` waits for the whole file (for scripts and pre-rendering).

## Endpoints

| Endpoint | Body / query | Returns |
|---|---|---|
| `POST /call` | §4.6 request: `to`, `audio` (base64) or `text`, `interrupted`, `hesitation_ms` | `{transcript, reply_text, reply_audio_url, emotion, promises, actions}` |
| `GET /wiretap?a=&b=` | two nation ids | `{"lines": [{speaker, text, audio_url}]}` |
| `POST /transcribe` | raw audio body | `{text, seconds, bytes}` |
| `GET /audio/{file}` | from `speak()` | mp3, streamed while still rendering |
| `GET /voice/talk-button.js` | | the talk button module ([TALK_BUTTON.md](TALK_BUTTON.md)) |

If the web dev server proxies `/api` to port 8000 with the prefix kept, set
`VOICE_AUDIO_BASE=/api/audio` so the returned URLs go through the proxy.

## Stand-ins until /agents lands

- `VOICE_MOCK=fixed` (default): `/call` returns the §4.6 example reply.
- `VOICE_MOCK=llm`: one small in-character model call. `VOICE_REPLY_MODEL` picks the model
  (default `mistral-large-4`).

## V0 results (2026-11-21, home network, synthetic player line)

| Test | Result |
|---|---|
| Talk → reply → first audio | **1.8 s** median with `mistral-large-2512` (STT 0.4 + reply 1.0 + TTS first chunk 0.3). **7.6 s** with `mistral-large-4` at `reasoning_effort="low"` (the lowest it accepts; `none` and `minimal` are rejected), range 5–20 s |
| Emotion tag changes the voice | Clips rendered: `voice/v0_out/blind_A/B/C.mp3` (angry, calm, tense, shuffled; key in `blind_key.json`). Needs a teammate to listen blind |
| Browser recording format | Chrome `audio/webm;codecs=opus` from MediaRecorder accepted as-is (1 s). wav, mp3, ogg/opus and flac also accepted. No WAV encoding needed |

Rerun with `python -m voice.v0 all` and the page at `/voice-static/v0.html` (there's a synthetic
button that needs no mic, plus hold-to-record from the mic). Retest in the room on the demo laptop.
