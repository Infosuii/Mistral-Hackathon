# GAMBIT demo — script, setup and recovery (D2, draft)

Owner: Ashish. **Draft for the 14:15 playtest; the team fixes who says what at the rehearsal.**
Built from `ideas.md` §17 and what is on main now. Rehearse twice before 17:00 (D2).

## Setup (10 minutes before)

1. `git pull`, then `pip install -r requirements.txt`. `.env` at the repo root needs `MISTRAL_API_KEY`.
2. Check the demo audio is complete: `python -m voice.prerender --check` (exit 0).
3. Start the backend with the demo settings:
   ```bash
   GAMBIT_DECIDE_MODEL=mistral-medium-latest VOICE_WIRETAP=demo uvicorn engine.app:app --port 8000
   ```
   `mistral-medium-latest` runs the monthly decisions, which leaves mistral-large-2512 for speech (DECIDED 13:07).
   `VOICE_WIRETAP=demo` makes Wiretap instant and offline (the pre-rendered script). Drop it to
   show live, model-written Wiretap lines (about 3–6 s).
4. Start the web app (`cd web && npm run dev`). Open it in **Chrome**, not the Claude browser
   pane, which blocks the mic. Press the talk button once and click **Allow** for the mic.
5. Seed 7, seat President of Valdoria. Paused.
6. Room check: one hold-to-talk line to Ostrava. You should hear a reply within about 3 s.
   If you don't, switch to the typed box (see Recovery).

## Five-minute run

| Time | On screen | Who | What they say or do |
|---|---|---|---|
| 0:00 | Map, world running | Presenter | "Every call is a move. You've seen agent societies with one timeline. We show the one you didn't take." |
| 0:25 | Phone, Ostrava selected | Judge (handed the mic) | "You're President of Valdoria." One quick call in the strategy phase, e.g. *"General, let's talk about grain."* |
| 1:00 | Start One Berth | Driver | The crisis clock starts. Ostrava **rings**; the angry opening line plays at once (pre-rendered). |
| 1:20 | Phone | Judge | Answers. When Ostrava announces the blockade, the judge **holds to talk mid-sentence**: the leader cuts off, and the reply reacts to the interruption. |
| 2:10 | Intel, Wiretap | Driver | Public statement against private intent, advisers against choice. Wiretap: Ostrava and Zarnia comparing notes about the judge. |
| 2:50 | Map, needle | Presenter | Deadlines pass, and the outcome lands on the map. The needle shows war odds before and after: "You did that." |
| 3:20 | Replay panel | Driver | "What if you'd waited?" Slide the offer later. Name who flipped (on seed 7, +3 ticks flipped Nordhaven and Zarnia). |
| 4:00 | End screen | Presenter | The historian's verdict. |
| 4:30 | — | Presenter | "Mistral Large runs every leader; Voxtral is every voice: transcription, five cast voices with emotion tags, and Wiretap." Do not claim Managed Agents (no-go in A0). |

Lines a judge can say that show voice matters:
- Interrupt the blockade announcement: *"Wait — hear me out before you say that."*
- Hesitate before answering a proud leader; Ostrava pushes harder.
- Make the same promise to both: *"Zarnia, the berth is yours too."* Compare-notes should catch it.

## Recovery

| Problem | Do this |
|---|---|
| Room too noisy, or mis-transcribed | Type into the phone's text box. Same path, same voices |
| Mic blocked | Chrome lock icon → Microphone → Allow. Or type |
| Reply slow (over 5 s) | Keep talking over it. Large 4 interpretation runs in the background; promises appear in `last_call` a few seconds later |
| Model or API outage | The leader says "The line is breaking up" (pre-rendered) instead of going silent. Switch to the backup video |
| Wiretap slow | Restart with `VOICE_WIRETAP=demo` |
| Anything else | Play the backup video (D1, recorded at the 14:15 playtest) |

## Checked on main

- Promises are recorded as `berth` plus a slot (#65, #69). Live through `/call`: an honest split
  (Ostrava morning, Zarnia evening) holds at compare-notes; the same whole-day berth promised to
  both is caught, and trust drops ×0.4. Interpret lands 8–28 s after the reply.
- If the fast reply fails, the leader says the pre-rendered "line is breaking up" line and the
  player's promise is still recorded (#71).

## Measured (voice)

Talk to first audio is about 1.8 s with typed or recorded input (STT 0.4 s + reply 1.0 s +
TTS first chunk 0.3 s). On main with the real leaders, a reply took 1.7–3.0 s. The blind emotion
test scored 6/6.
