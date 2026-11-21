# GAMBIT demo — script, setup and recovery (D2, draft)

Owner: Ashish. **The team fixes who says what at the rehearsal. The backup video is recorded at 16:30, after the 16:15 freeze, and doubles as the submission video (D3: Ashish submits).**
Built from `ideas.md` §17 and what is on main now. Rehearse twice before 17:00 (D2).

## Setup (10 minutes before)

1. `git pull`, then `pip install -r requirements.txt`. `.env` at the repo root needs `MISTRAL_API_KEY`.
2. Check the demo audio is complete: `python -m voice.prerender --check` (exit 0).
3. Start everything with Neon's launcher (backend and web, demo settings):
   ```bash
   ./scripts/demo.sh
   ```
   It sets `GAMBIT_DECIDE_MODEL=mistral-medium-latest` (monthly decisions; this leaves mistral-large-2512
   for speech, DECIDED 13:07), `GAMBIT_PRIVATE_STRATEGY=1` (Large 4 writes each leader's private plan,
   DECIDED 14:01: game plans land about 33 s after Start and crisis plans about 31 s after the crisis
   starts, before the first crisis decision at about 46 s) and `VOICE_WIRETAP=demo` (instant, offline
   Wiretap; set `VOICE_WIRETAP=` to show live, model-written lines, about 3–6 s).
   Manual equivalent: `GAMBIT_DECIDE_MODEL=mistral-medium-latest GAMBIT_PRIVATE_STRATEGY=1 VOICE_WIRETAP=demo uvicorn engine.app:app --port 8000`, then `cd web && npm run dev`.
   No network: `./scripts/demo.sh --offline`.
4. Open the page in **Chrome**, not the Claude browser pane, which blocks the mic. Press the talk
   button once and click **Allow** for the mic. Start the game about 40 s before the crisis beat
   so the leaders' private plans have landed.
5. Seed 7, seat President of Valdoria. Paused.
6. Room check: one hold-to-talk line to Ostrava. You should hear a reply within about 3 s.
   If you don't, switch to the typed box (see Recovery).

## Five-minute run

| Time | On screen | Who | What they say or do |
|---|---|---|---|
| 0:00 | Map, world running | Presenter | "Every call is a move. You've seen agent societies with one timeline. We show the one you didn't take." |
| 0:25 | Phone, Ostrava selected | Judge (handed the mic) | "You're President of Valdoria." One quick call in the strategy phase, e.g. *"General, let's talk about grain."* |
| 1:00 | Start One Berth | Driver | The crisis clock starts. Ostrava **rings**; the angry opening line plays at once (pre-rendered). |
| 1:10 | Phone (tick 1) | Judge | Answers Ostrava and promises the berth: *"General, the berth is yours."* The promise appears in the crisis ledger. |
| 1:35 | Map, click Nordhaven, **Call** in the orders bar (tick 2) | Judge | *"I need your tugs at Port Kessar today to open a second berth. Valdoria pays the full cost."* This is recorded as a `send_tugs` promise every time (#111). |
| 2:10 | Intel, Wiretap | Driver | Public statement against private intent and private strategy, advisers against choice. Wiretap: Ostrava and Zarnia comparing notes about the judge. |
| 2:40 | Map, needle | Presenter | Play on. If Nordhaven sends the tugs at tick 6, a second berth opens and both grain ships dock on the map in peace; if Nordhaven stays out, narrate the actual outcome on the map as it lands. The needle shows war odds before and after: "You did that." |
| 3:20 | Replay panel | Driver | "What if you'd called later?" Slide the call +5 ticks: it lands after Nordhaven's deadline. Name who flipped **only if the screen shows it** (e.g. Nordhaven send_tugs → stay_out, Zarnia dock → mobilise). If nobody flips, say what the screen shows: "This time the timing did not matter; the deal held either way." Try +5 once and move on. Shift 0 changes nobody, as it should. |
| 4:00 | End screen | Presenter | The historian's verdict. |
| 4:15 | Mistral Vibe (terminal) | Presenter | Optional, 20 s: `/gambit-brief` in Vibe, connected through `gambit_mcp`. "This is Mistral Vibe, connected to our game through an MCP server. I ask it to brief me: it reads the world, each leader's private intent and the next deadline, and gives me the line to say." Only claim it places calls or writes crises if that was rehearsed today; the brief was verified live at 14:27. Set-up: `gambit_mcp/README.md`. |
| 4:35 | — | Presenter | "Mistral Large 4 writes every leader's private strategy and works out what each call committed you to; Mistral Large 3 gives the instant spoken reply; Mistral Medium makes the monthly moves. Voxtral is every voice: transcription, five cast voices with emotion tags, and Wiretap." Do not claim Managed Agents (no-go in A0) or that Large 4 makes every decision (it is too slow for the 8 s turn). |

What the map shows without anyone explaining it (point at it once): leaders' speech bubbles over
their capitals, mood rings (red hostile to green friendly), a breaking-news card each month, "+6" or
"−2" floating over a capital when a call changes relations, and the Military and Unrest map modes.
Hover any province for its card; click a nation for its orders bar (Call, Intel, Wiretap).

Alternative crisis beat (the interruption): if Ostrava calls at tick 7 announcing the blockade,
interrupt mid-sentence and offer the morning. Interrupting stops the threat going public, so he docks;
not interrupting lets the public blockade stand (#97, #107).

Lines a judge can say that show voice matters:
- Interrupt the blockade announcement: *"Wait — hear me out before you say that."*
- Hesitate before answering a proud leader; Ostrava pushes harder.
- Make the same promise to both: *"Zarnia, the berth is yours too."* Compare-notes should catch it.

## Recovery

| Problem | Do this |
|---|---|
| Room too noisy, or mis-transcribed | Type into the phone's text box. Same path, same voices |
| Mic blocked | Chrome lock icon → Microphone → Allow. Or type |
| Reply slow (over 5 s) | Keep talking over it. The spoken reply falls back to Mistral Medium within 6 s (#99). Large 4 interpretation runs in the background; promises appear in `last_call` a few seconds later |
| Model or API outage | The leader says "The line is breaking up" (pre-rendered) instead of going silent. Switch to the backup video |
| Wiretap slow | Restart with `VOICE_WIRETAP=demo` |
| Anything else | Play the backup video (recorded at 16:30) |

## Checked on main

- Promises are recorded as `berth` plus a slot (#65, #69). Live through `/call`: an honest split
  (Ostrava morning, Zarnia evening) holds at compare-notes; the same whole-day berth promised to
  both is caught, and trust drops ×0.4. Interpret lands 8–28 s after the reply.
- If the fast reply fails, the leader says the pre-rendered "line is breaking up" line and the
  player's promise is still recorded (#71).

## Measured (voice)

- **Human playtest at 14:45** (Ashish, Chrome mic, `./scripts/demo.sh`, live): 13 spoken calls, 13/13
  transcriptions and 13/13 speech requests returned 200 with no fallback line. Ostrava and Zarnia were
  both promised the whole-day berth; compare-notes caught it, both docked and Nordhaven sent tugs.
  Nothing felt wrong.
- **Neon's N3 benchmark (#113, 10 live WAV calls, 0 fallbacks, uncached streaming TTS):** spoken
  reply **1.39 s** median / **3.11 s** worst; first TTS chunk **0.39 s** median / **1.27 s** worst
  (~**1.8 s** typed to first audio); STT **3.32 s** median / **8.72 s** worst for ~220 KB WAV clips
  (**4.98 s** median / **10.88 s** worst total from WAV upload to first audio); Large 4 `interpret`
  **13.10 s** median / **21.44 s** worst (async); `/futures` **3.52 s** median / **4.69 s** worst;
  `/replay` **0.03 s** pure code / **3.95 s** with live `why()`.
- **Blind emotion test:** scored **6/6**.
