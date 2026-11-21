# GAMBIT — *Every call is a move*

A voice-played grand-strategy and crisis-negotiation game built for the Mistral London Hackathon (21 Nov 2026).

Five fictional nations share one continent, each run by an AI leader with its own political system, public statement, and private agenda. You govern by picking up the **Red Phone** and speaking directly to the other leaders. When a crisis erupts, a 24-hour clock starts — and **what you promise, when you call, whether you interrupt mid-sentence, and how long you hesitate** change what every nation does.

After the crisis resolves, GAMBIT shows the timeline you did **not** take:
- **War-Odds Needle** — 200 matched-seed Monte Carlo rollouts six months ahead comparing war probability before and after your deal (*"War odds 41% → 6%. You did that."*).
- **"What if I'd waited?" Replay** — slide your calls earlier or later in pure deterministic code to see which leader flips and why.
- **Two-Faced Leaders & Wiretap** — inspect public statements vs. private strategy, adviser rankings vs. actual choices, and listen to two AI leaders talking about you.

---

## Run it in two minutes

### Prerequisites
- Python 3.12+ (with `uv` or `pip`)
- Node.js 20+ and `npm`
- A `MISTRAL_API_KEY` (for live mode)

### 1. Clone and add your key

```bash
git clone https://github.com/Infosuii/Mistral-Hackathon.git
cd Mistral-Hackathon
echo "MISTRAL_API_KEY=your_key_here" > .env
```

### 2. Start everything with one command

```bash
./scripts/demo.sh
```

`scripts/demo.sh` checks your API key, bootstraps `.venv` and `web/node_modules` on a fresh clone, verifies/warms pre-rendered crisis and Wiretap audio, starts the FastAPI backend (`http://127.0.0.1:8000`) with the demo settings (`GAMBIT_DECIDE_MODEL=mistral-medium-latest`, `GAMBIT_PRIVATE_STRATEGY=1`, `VOICE_WIRETAP=demo`), and starts the web app at **`http://localhost:5173`**.

Open **`http://localhost:5173`** in **Chrome** (allow microphone access when prompted). Hold the red talk button to speak — or press it while a leader is speaking to interrupt them mid-sentence. A typed fallback box sits directly underneath for noisy rooms.

### Offline mode (no API key or Wi-Fi)

```bash
./scripts/demo.sh --offline
```

Runs the full playable game from deterministic cached replies, adviser-driven turns, and committed pre-rendered audio in `voice/prerendered/` with zero network calls.

---

## Where each Mistral product is used

| Mistral product | Model / feature | Role in GAMBIT |
|---|---|---|
| **Le Chonk (Mistral Large 4)** | `mistral-large-4` | Writes each leader's private strategy at game & crisis start (`GAMBIT_PRIVATE_STRATEGY=1`); interprets every phone call in the background (`agents.interpret`) into structured promises, agreed actions, and trust/resolve updates; writes live Wiretap dialogues, replay `"why"` explanations, and the end-of-session Historian verdict. |
| **Mistral Large 2512** | `mistral-large-2512` | Fast spoken phone replies (`agents.speak_fast`, ~1 s, two sentences max with Voxtral emotion tags) so the leader starts talking quickly enough to be interrupted mid-sentence. |
| **Mistral Medium** | `mistral-medium-latest` | Strategy & crisis turn decisions (`GAMBIT_DECIDE_MODEL=mistral-medium-latest`, keeping 2512's 30 RPM quota dedicated to voice) and hedge race model so turns never stall. |
| **Voxtral STT** | `voxtral-mini-transcribe-3` | Transcribes hold-to-talk browser audio (`webm/opus`, `wav`, `mp3`, `ogg`, `flac`) via `POST /call` and `POST /transcribe`, biased with `context_bias` for nation names and crisis terms. |
| **Voxtral TTS** | `voxtral-mini-tts-3-0` | Five distinct cast leader voices with inline `[emotion=...]` tags (`angry`, `tense`, `proud`, `warm`, `assertive`, etc.) and streamed first-chunk playback (`stream: true`), plus pre-rendered crisis rings and Wiretap audio. |
| **Mistral Vibe** | CLI coding agent | Built self-contained game data, persona cards, SVG nation artwork, and unit tests. |

*(Note: Mistral Managed Agents was evaluated in `agents/A0_RESULTS.md` and ruled no-go at 9.6 s/turn, so GAMBIT uses direct chat completions with structured JSON output and explicit session memory.)*

---

## Verify end to end

```bash
# Fast smoke check (~5 s, stub turns)
scripts/smoke.sh

# Full 5-minute demo path against a live backend (typed + WAV speech-to-text + honest split)
python -m e2e.demo_path --mode both --scenario both

# Verify against a running `./scripts/demo.sh` instance
python -m e2e.demo_path --url http://127.0.0.1:8000
```

---

## Architecture

- **`/engine`** — Pure deterministic simulation (`step`, `advise`, `crisis_step`, `snapshot`, `fork`, 200-rollout `futures`, FastAPI `engine.app:app`).
- **`/agents`** — Five leader personas (`agents/personas/*.md`), `decide`, `strategize_all`, split phone path (`speak_fast` + `interpret`), `wiretap`, `why`, and `historian`.
- **`/voice`** — Voxtral `transcribe` & streaming `speak`, `POST /call`, `GET /wiretap`, `GET /audio/{file}`, pre-rendered demo clips, and standalone `talk-button.js` (interruption + hesitation tracking).
- **`/web`** — Full-bleed Voronoi political map, top resource bar, crisis clock with deadline markers, war-odds needle, Red Phone, Intel drawer + Wiretap, Replay slider, and Historian end screen.
- **`/replay`** — `POST /replay` counterfactual crisis rerun from cached decisions + `agents.why`.
- **`/contracts`** — Pydantic schemas and validated JSON fixtures for every API endpoint.
- **`/data`** — Tunable game data (`nations.json`, `weights.json`, `crises/one_berth.json`, `crises/outbreak.json`).
- **`/e2e`** — Demo-path test (`demo_path.py`), offline ASGI server (`offline_app.py`), timings, and browser walk-through.
