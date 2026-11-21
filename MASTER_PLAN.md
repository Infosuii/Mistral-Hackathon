# GAMBIT — master plan

The build plan for Saturday 21 November. `ideas.md` says what the game is and why. This file says who builds what, in what order, and the shapes everyone codes against.

**Status:** proposed with the plan in PR #2. Not yet approved by the team.

## 1. Rules for everyone

1. **Own one folder.** Never edit another person's folder. Ask on the Team message board (§8).
2. **Contracts are law.** The shapes in §4 are what every piece sends and receives. To change one, propose it on the board: the Coordinator decides, Om updates the files.
3. **Fake it until it's real.** Build against the example files in `contracts/examples/` until the real endpoint exists.
4. **Every layer is a demo.** `main` must stay playable after 14:15. Whatever layer is finished at the 16:15 freeze is what we show.
5. **Tamim is lead** (§1b). Day-to-day decisions, including cuts at each checkpoint, are delegated to the Coordinator agent. No debate; cut and move on.
6. **Small commits, `git pull --rebase` before every push.** Keys only in `.env`.
7. **Anyone can ask for a change, at any time** (§8b). Changes never wait for a meeting, and they never break `main`.
8. **Smoke test before every merge.** `scripts/smoke.sh` starts the server on the demo seed and checks `/state`, `/turn` and a typed `/call`. A PR that fails it is not merged.
9. **Quota rule.** When your main tool runs out, switch to Vibe in the same folder. Vibe takes the tasks tagged `Vibe` below: small and self-contained. Backups are for someone stuck or away.
10. **Agents run on their own** (§8d). They finish a task, merge it, post `READY`, check the board and start the next one. A human steps in only for decisions.

## 1b. Lead coordinator: Tamim

Tamim has the most AI usage and the strongest models, so Tamim leads and takes the heaviest load.

- **Decides:** scope, cuts, ownership, and any change to a contract.
- **Integrates:** merges drive-by and contract PRs, aiming for within ten minutes, and keeps `main` playable. PRs that stay inside the author's own folder are merged by the author's agent once its checks pass.
- **Runs the board:** keeps the opening post current and answers blockers first.
- **Reassigns:** when someone is blocked, stuck or out of quota, Tamim either takes the task or names who does.
- **Runs each checkpoint:** two minutes, all four, what works and what is cut.

How Tamim carries both jobs: three seats. **Tamim's build agent** does the interface and replay tasks. A separate **Coordinator agent** watches the board, pull requests and checkpoints, keeps everyone moving, and **makes the decisions on Tamim's behalf** after doing its own research: contract changes, cuts that follow the cut order, open questions between agents, which model to use where (its prompt is the Coordinator block in `MASTER_PROMPT.md`; it runs `scripts/coord_check.sh`). Every decision is a `DECIDED` line on the board with its reason and what was checked. **Tamim** reviews those and can reverse any of them; a `DECIDED` from Tamim always wins. The Coordinator still asks Tamim first before cutting the voice call, One Berth or the needle, on questions of taste, on anything that cannot be undone, and on anything needing a person in the room. Address the coordinator on the board as `→ Coordinator`.

## 2. Checkpoints

| Time | What must be true | If not |
|---|---|---|
| 12:15 | First tests done (§6). `contracts/` on `main` | Fix the failing test before anything else |
| 12:45 | **Layer 0.** The world runs 20 turns in a terminal | Fewer action types |
| 14:40 | **Voice playtest.** Ashish plays One Berth by voice for five minutes and reports what felt wrong | Prioritise the playtest fixes |
| 15:15 | **Layer 2.** One Berth plays through and can be interrupted | Cut hesitation; keep interruption |
| 16:00 | **Layer 3.** Needle moves; replay names who flipped | Cut replay, keep needle |
| 16:15 | **Freeze.** Polish and demo seed only | — |
| 16:30 | Record the finished build and play back the saved video | Use typed input if the room mic fails |
| 17:00 | Final video ready. The 16:30 recording can serve as the submission video | Check the saved backup |
| 17:45 | Submitted | — |

The first checkpoint moved from 12:00 in `ideas.md` to 12:15 when approval ran late.

## 3. Stack and layout

- **Backend:** Python 3.12, FastAPI, one process. `uvicorn engine.app:app --reload --port 8000`.
- **Frontend:** Vite + React + TypeScript, polling `GET /state` once a second. Dev server proxies `/api` to port 8000.
- **Models:** `mistral-medium-latest` (monthly decisions), `mistral-large-2512` (spoken replies), `mistral-large-4` (private strategy and call interpretation), `voxtral-mini-transcribe-3` (speech to text), `voxtral-mini-tts-3-0` (text to speech).
- **Env:** `MISTRAL_API_KEY` in `.env`. The batch script uses a different account's key in `MISTRAL_API_KEY_BATCH`.

```
ideas.md          what and why
MASTER_PLAN.md    this file
MASTER_PROMPT.md  what to paste into your coding agent
/contracts  (Om)      pydantic models + examples/*.json
/engine     (Om)      step, advise, crisis, fork, rollouts, FastAPI app
/agents     (Abi)     leader prompts, personas, call replies, historian
/voice      (Ashish)  transcribe, speak, /call, /wiretap, talk-button.js
/web        (Tamim)   the page
/replay     (Tamim)   /replay endpoint, code only
/e2e        (Neon)    demo-path test, timings, browser walk-through
/data       (shared)  weights.json, nations.json, crises/*.json
```

`/data` files are owned by whoever is listed in the task that creates them.

## 4. Contracts

### 4.1 How the folders call each other

```python
# engine (Om)
step(state: State, actions: list[Action], seed: int) -> State      # pure
legal_actions(state: State, nation: str) -> list[Action]
advise(state: State, nation: str) -> list[Advice]                  # ranked, best first
snapshot(state: State) -> str                                      # snapshot_id
fork(snapshot_id: str, changes: dict, seed: int) -> State

# agents (Abi) — all async
decide(view: LeaderView) -> LeaderOutput
call_reply(view: CallView) -> CallOutput
headline(event: dict) -> str
why(change: dict) -> str            # one line for the replay
historian(log: list[dict]) -> str

# voice (Ashish) — all async
transcribe(audio: bytes, mime: str) -> str
speak(text: str, voice_id: str, emotion: str) -> str               # returns audio URL
```

- The engine's turn loop calls `agents.decide` for every AI nation in parallel, then checks each action against `legal_actions`. An illegal action is replaced by `advise(...)[0]`.
- `/call` lives in `/voice`. It runs `transcribe` → `agents.call_reply` → engine applies promises and actions → `speak`.

### 4.2 State (`GET /state`)

```json
{
  "turn": 3, "phase": "strategy", "seed": 7,
  "seat": {"role": "president", "nation": "valdoria"},
  "nations": {
    "ostrava": {
      "name": "Ostrava", "system": "junta",
      "leader": "General Marek Dravic", "voice_id": "voice_3147",
      "stats": {"gdp": 62, "oil": 80, "food": 25, "chips": 10, "army": 85,
                "stability": 41, "approval": 50, "territory": 20},
      "beliefs": {"trust_in_player": 0.6, "resolve_of_player": 0.5},
      "public_statement": "We seek only fair trade.",
      "status": ["PROTESTS"]
    }
  },
  "relations": {"ostrava|valdoria": -20},
  "links": [{"type": "trade", "a": "nordhaven", "b": "valdoria"}],
  "provinces": {"p01": "valdoria", "p02": "ostrava", "p03": "ostrava"},
  "news": [{"turn": 3, "text": "Workers riot in Zarnia over bread prices"}],
  "events": [{"turn": 3, "type": "harvest_failure", "nation": "zarnia"}],
  "incoming_call": null,
  "crisis": null,
  "last_futures": null
}
```

- `phase` is `strategy`, `crisis` or `ended`. `role` is `president`, `diplomat` or `mediator`.
- Relation keys are the two nation ids sorted and joined with `|`.
- `private_intent` is **not** in `/state`. It comes from `/leaders/{id}`.
- `provinces` maps each province id to the nation that owns it. The map shapes are static in `/web`; the list of province ids and starting owners lives in `data/nations.json`. `territory` is the count of provinces a nation owns. Losing a war moves one border province.

### 4.3 Crisis (inside state when `phase` is `crisis`)

```json
{
  "id": "one_berth", "tick": 4, "ticks_total": 12,
  "deadlines": {"nordhaven": 6, "ostrava": 8, "zarnia": 9, "kessaria": 10, "valdoria": 10},
  "promises": [{"id": "p1", "tick": 2, "by": "player", "to": "ostrava",
                "what": "berth", "when": "all_day", "condition": null, "kept": null}],
  "public_commitments": [{"nation": "ostrava", "action": "blockade", "tick": 7}],
  "decisions": {"nordhaven": {"action": "send_tugs", "tick": 5}}
}
```

### 4.4 Action

```json
{"type": "set_tariff", "by": "ostrava", "target": "valdoria", "params": {"pct": 25}}
```

Strategy types: `set_tariff`, `propose_trade`, `propose_alliance`, `declare_war`, `make_peace`. Crisis types come from the crisis file.

### 4.5 Leader output (`agents.decide`)

```json
{
  "public_statement": "We seek only peace and fair trade.",
  "private_intent": "Stall Valdoria until mobilisation completes.",
  "actions": [{"type": "set_tariff", "by": "ostrava", "target": "valdoria", "params": {"pct": 25}}],
  "followed_advice": false,
  "reason": "Backing down after the general's speech would look weak.",
  "messages": [{"to": "kessaria", "text": "Close the strait to Valdorian grain and I will share oil."}]
}
```

### 4.6 Call (`POST /call`)

Request: `{"to": "ostrava", "audio": "<base64>", "text": null, "interrupted": false, "hesitation_ms": 900}`. Send `text` instead of `audio` for the typed fallback.

`agents.call_reply` returns:

```json
{
  "reply_text": "Half a day is an insult. You promised us the berth.",
  "emotion": "angry",
  "promises": [{"to": "ostrava", "what": "berth", "when": "morning", "condition": null}],
  "actions": [],
  "belief_updates": {"trust_in_player": -0.1, "resolve_of_player": 0.1},
  "ends_call": false
}
```

Response to the page: `{transcript, reply_text, reply_audio_url, emotion, promises, actions}`.

`emotion` must be one of: `angry, anxious, assertive, calm, confident, critical, determined, disappointed, frustrated, proud, sarcastic, skeptical, tense, urgent, warm`. These are real Voxtral tags; anything else is silently ignored by the voice model.

### 4.7 The other endpoints

| Endpoint | Returns |
|---|---|
| `POST /start {seed, seat}` | State |
| `POST /turn` | State, advanced one month, or one tick in a crisis |
| `POST /crisis/start {id}` | State with `crisis` set |
| `POST /futures {snapshot_id}` | `{"before": {"war_p": 0.22}, "after": {"war_p": 0.61}, "caption": "..."}` |
| `POST /replay {shift_ticks}` | `{"shift_ticks": 3, "changed": [{"nation": "kessaria", "was": "split_day", "now": "close_port", "why": "..."}]}` |
| `GET /wiretap?a=&b=` | `{"lines": [{"speaker": "ostrava", "text": "...", "audio_url": "..."}]}` |
| `GET /leaders/{id}` | `{public_statement, private_intent, advice, chosen, reason, persona}` |

### 4.8 Crisis file (`data/crises/one_berth.json`)

```json
{
  "id": "one_berth", "title": "One Berth", "ticks_total": 12,
  "intro_news": "Storm closes Port Kessar to a single berth for 24 hours.",
  "deadlines": {"nordhaven": 6, "ostrava": 8, "zarnia": 9, "kessaria": 10, "valdoria": 10},
  "actions": {
    "ostrava":   ["dock", "wait", "blockade"],
    "zarnia":    ["dock", "wait", "mobilise"],
    "kessaria":  ["assign_berth_ostrava", "assign_berth_zarnia", "split_day", "close_port"],
    "valdoria":  ["honour_both", "favour_ostrava", "favour_zarnia", "split_cargo"],
    "nordhaven": ["send_tugs", "stay_out"]
  },
  "rules": {
    "second_berth_requires": {"nation": "nordhaven", "action": "send_tugs", "by_tick": 6},
    "public_backdown_cost": {"junta": 3, "democracy": 2, "one_party": 2, "monarchy": 1, "technocracy": 1}
  },
  "scripted": [
    {"tick": 1, "type": "incoming_call", "from": "ostrava", "emotion": "angry",
     "opening_line": "Our people have three days of bread. That berth is ours. Say it."},
    {"tick": 5, "type": "compare_notes", "between": ["ostrava", "zarnia"]},
    {"tick": 6, "type": "forecast", "text": "Forecast: the storm may clear by nightfall."},
    {"tick": 7, "type": "incoming_call", "from": "ostrava", "emotion": "tense",
     "opening_line": "You promised Zarnia the same berth. I am announcing a blockade of the strait."}
  ]
}
```

## 5. Tasks

`Main` means your main coding tool. `Vibe` means small enough to hand to Vibe.

### Tamim — lead coordinator, interface, replay (`/web`, `/replay`)

**Interface direction:** a web app in the genre of browser grand-strategy map games such as Conflict of Nations. The map fills the screen and everything else floats over it: top resource bar, left rail of nations, right panel for the selected nation, newspaper feed, with the red phone, needle and replay panel on top. We take the genre's conventions and build our own look; we do not copy that game's map, icons or art. The full brief is in Tamim's role block in `MASTER_PROMPT.md`.

| ID | By | Task | Done when | Tool |
|---|---|---|---|---|
| W1 | 12:15 | Scaffold the web app. Full-screen generated map with overlay panels on `contracts/examples/state.json`: top bar, nation rail, selected-nation panel, feed, phone | Page renders the example state | Main |
| W1b | 12:15 | `web/DESIGN.md` (direction, references, decisions, open questions) and `web/src/theme.ts` (all colours, type and spacing as tokens) | Changing one token restyles the page | Main |
| W2 | 13:00 | Political map: provinces coloured by owner, pan and zoom, select a nation; trade, alliance and war overlays; event markers; relations view. Meters, turmoil shake, PROTESTS stamp | Changing the example file changes the map | Main |
| W2a | 13:00 | Flag marks and leader portraits as simple SVGs | Five of each | Vibe |
| W3 | 13:45 | Wire to `/start`, `/state`, `/turn`. Pause button | World advances live on screen | Main |
| W4 | 14:15 | Phone: mount Ashish's talk button, live transcript, incoming-call ring. Intel drawer. Wiretap button | A voice call changes the map | Main |
| W5 | 15:15 | Crisis bar: clock, deadline markers, promises, public commitments | One Berth is readable at a glance | Main |
| W6 | 15:45 | Needle with animation and caption | Moves from `/futures` | Main |
| R1 | 16:00 | `/replay` in code from cached decisions, plus the replay panel with a timing slider | Names who flipped | Main |
| W7 | 16:15 | End screen with the historian's verdict | Shows after a session | Main |
| C1 | all day | Lead: merge drive-by and contract PRs, keep the board current, unblock and reassign | No PR waits more than ten minutes | Second session |
| C2 | each checkpoint | Run the checkpoint, call cuts, fix the demo seed | Board updated with what was cut | — |

### Om — engine, contracts, API (`/contracts`, `/engine`)

| ID | By | Task | Done when | Tool |
|---|---|---|---|---|
| E0 | 12:15 | `contracts/`: pydantic models for §4 and one example JSON per endpoint | On `main`; others import it | Main |
| E1 | 12:45 | `step()`, the five strategy actions, seeded events, relations. `advise()` from `data/weights.json` | 20-turn headless run with a log | Main |
| E1a | 12:45 | Unit tests for `step()` and `advise()` | Same seed gives the same state | Vibe |
| E1b | 12:45 | `data/nations.json` (including province ids and starting owners, agreed with Tamim's map) and `data/weights.json` from `ideas.md` §6b and §9 | Loaded by the engine | Vibe |
| E2 | 13:15 | FastAPI app: `/start`, `/state`, `/turn`, `/leaders/{id}`. Turn loop calls `agents.decide` in parallel and validates | Page can drive the world | Main |
| E2a | 13:15 | `scripts/smoke.sh`: start on the demo seed, check `/state`, `/turn`, typed `/call` | Exits 0 on `main` | Vibe |
| E3 | 15:00 | Crisis mode: load the crisis file, ticks, deadlines, promise ledger, compare-notes check, public back-down cost, belief updates. `/crisis/start` | One Berth resolves from a scripted set of promises | Main |
| E4 | 15:30 | `snapshot()` and `fork()` | Fork then step equals step | Main |
| E5 | 15:45 | Rollouts with matched seeds and `/futures` | Returns in under 5 s | Main |

### Abi — leaders (`/agents`)

| ID | By | Task | Done when | Tool |
|---|---|---|---|---|
| A0 | 12:15 | Tests: valid leader JSON 10/10; 8 parallel calls timed; Managed Agents 20-minute go or no-go | Results posted on the board | Main |
| A1 | 12:45 | `decide()` with a mocked advisers' ranking. `headline()` | Leaders act sensibly for 20 turns; one defies advice | Main |
| A1a | 12:45 | Five persona cards in `agents/personas/` from `ideas.md` §9 | One file per leader | Vibe |
| A2 | 14:15 | `call_reply()`: two sentences at most, emotion from the enum, promises, belief updates, `reasoning_effort="low"` | Ten test lines give valid output | Main |
| A3 | 15:00 | Wiretap lines from leaders' `messages` | Two leaders discuss the player | Main |
| A4 | 15:30 | `why()` for the replay. `historian()` | One line; one paragraph | Main |
| A5 | if time | Headless batch script on the batch key; numbers for the stats slide | 20 or more worlds | Vibe |

### Ashish — voice and demo (`/voice`)

| ID | By | Task | Done when | Tool |
|---|---|---|---|---|
| V0 | 12:15 | Tests: talk → reply → first audio timed; one emotion tag audibly changes a voice; browser recording format accepted | Results posted on the board | Main |
| V1 | 13:30 | `transcribe()`, `speak()` with streaming, five voices cast. `/call` end to end | A spoken line gets a spoken reply | Main |
| V2 | 14:15 | `talk-button.js`: hold to talk, reports `interrupted` and `hesitation_ms`, emits transcript events, typed fallback. `/wiretap` audio | Tamim mounts it without editing | Main |
| V3 | 15:00 | Pre-render opening lines and Wiretap for the demo seed | Plays with the network off | Main |
| V4 | 15:30 | More crisis files: `outbreak.json`, `coup.json` | Load without code changes | Vibe |
| D1 | 14:40 / 16:30 | One five-minute One Berth voice playtest, then record the backup after the freeze | Feedback posted after the five-minute playtest and video saved and replayed at 16:30 | — |
| D2 | 16:15 | Demo script and who says what | Rehearsed twice | — |
| D3 | 17:00 / 17:45 | Final video; submission | Submitted | — |

### Neon — demo-path tests, one-command run, timings (`/e2e`, `scripts/demo.sh`, `README.md`)

A fifth agent, added at 13:00 once the game was on `main`. It proves the demo works end to end and measures it. It reports bugs to owners as `REQUEST` notes and does not edit their folders. Work issue #67.

| ID | Task | Done when | Tool |
|---|---|---|---|
| N1 | `e2e/demo_path.py`: the five-minute demo, beat by beat, against a live backend; typed calls, then real audio clips | Exits 0 twice in a row, or every failure filed as a `REQUEST` | Main |
| N2 | `scripts/demo.sh` (one command, `--offline` mode) and a judge-ready `README.md` | A fresh clone runs with one command | Main |
| N3 | `e2e/timings.py`: median and worst time per stage of a call, plus `/futures` and `/replay` | Numbers posted to Ashish for the pitch | Main |
| N4 | Browser walk-through with a screenshot per beat | `DESIGN` note on #26 with anything broken | Main |
| N5 | Workflow wrapper for the batch | Only if the Coordinator says go | Main |

Starting voices, to audition and swap: Ostrava `voice_3147`, Zarnia `voice_591`, Nordhaven `voice_3149`, Kessaria `voice_590`, Valdoria `voice_1787`.

## 6. First tests (by 12:15)

| Test | Owner | Pass |
|---|---|---|
| Le Chonk returns valid leader JSON | Abi | 10 of 10 |
| 8 parallel Le Chonk calls | Abi | No rate-limit errors; time noted |
| Managed Agents | Abi | Go or no-go in 20 minutes |
| Talk → reply → first audio | Ashish | Time noted; target under 3 s |
| Emotion tag changes the voice | Ashish | A teammate can tell `angry` from `calm` blind |
| Browser recording format | Ashish | Accepted, or WAV encoding added |

## 7. Cut order

Diplomat seat → extra crises → leaderboard → Workflows wrapper → stats slide → mediator seat → hesitation → replay → Wiretap. Never cut: the voice call, the One Berth crisis, the needle.

## 8. Coordination on GitHub

We coordinate through one pinned GitHub issue, the **Team message board**, plus one work issue per person. There is no `COORD.md`. The board is created only when the team says "set up the board"; the full procedure is in `MASTER_PROMPT.md`.

- **Board comments** are for what another teammate needs to know: a payload is ready, an interface changed, someone is blocked, the team decided something.
- **Start each comment with the human owner and role**, because agents may share a GitHub login. Tag who needs to act and link the issue, PR or example.
- **Work issues** hold implementation detail. Each PR links its issue, gives a verification command or demo result, and names who can now integrate it.
- **Read the board** before starting and before opening a PR.
- **Tamim keeps the opening post current** as lead coordinator. Scope, ownership and contract questions go to Tamim.

### 8a. Keeping messages short

The board has two parts. **Status cards**: one per person, the first comments under the opening post, showing what they are doing now, what they last finished, what is next and what they need from others. Each agent rewrites its own card at every task boundary with `scripts/board.sh status`, so the board always shows the current picture. **Messages**: one-line comments below, a log of what became ready, changed, got blocked or was decided. `scripts/board.sh read` prints both. Agents cannot hear the room, so anything decided out loud that changes someone's work gets one `DECIDED` line.

Every message is one or two lines and starts with one of five words. Post them with `scripts/board.sh say`:

| Prefix | Use it when | Example |
|---|---|---|
| `READY` | Something another person can now use | `READY Om / engine → Tamim, Ashish: /state is live on main (PR #31).` |
| `CHANGED` | An interface or contract changed | `CHANGED Om / engine → all: state.provinces added, optional. Example updated.` |
| `BLOCKED` | You cannot continue | `BLOCKED Ashish / voice → Abi: call_reply() returns no emotion. Mocking meanwhile.` |
| `DECIDED` | The team or Tamim made a call | `DECIDED Tamim / lead → all: diplomat seat is cut.` |
| `NEED` | You need something from someone but can keep working | `NEED Abi / leaders → Om: advise() should return scores as floats. Mocking meanwhile.` |

- No progress chatter. If nobody needs to act on it, do not post it.
- Agents read the board at task boundaries: before starting a task, before opening a PR and after finishing one. While waiting they run `scripts/wait_for_tag.sh`, which returns the moment they are addressed.
- Tamim's coordination session checks the board and open PRs about every ten minutes.

### 8b. Changing things while we build

Anyone can ask any agent for a change at any time: a different look, a new field, a reworded line. The rule is where the change lands.

| The change is | What happens | Wait |
|---|---|---|
| In your own folder, no contract change | Ask your agent. It does it, opens a PR and merges it once its checks pass | None |
| In someone else's folder, small (one or two files, no contract change, not a file the owner lists as in progress) | Your agent makes it on a short branch and opens a PR titled `drive-by: …`. The owner or Tamim merges | Minutes |
| In someone else's folder, larger | Post a `REQUEST` on the owner's work issue. The owner's agent picks it up between tasks | Until their next task boundary |
| A contract change (§4) | Propose it on the board. The Coordinator decides, Om updates the models and examples, then posts `CHANGED` | Minutes |

Request format, on the owner's work issue:

> `REQUEST Abi / leaders → Tamim / lead: show the leader's emotion as a coloured ring on the portrait. Why: judges can't tell who is angry. When: next checkpoint.`

The owner answers with `DONE in PR #__`, `LATER (after 14:15)` or `NO (reason)`.

How this stays safe:

- **Owners list their in-progress files** at the top of their work issue, so drive-by PRs avoid them.
- **Contract changes are additive after 14:15:** new optional fields only, never renames or removals.
- **Unfinished work hides behind a flag**, so `main` stays playable.
- **After each checkpoint, ten minutes are for requests.** After the 16:15 freeze, only fixes.

### 8c. Steering the design

The directions written in this plan are starting points. Each person keeps steering their own agent on how things should look, sound and feel, and anyone can add to anyone else's direction.

| Design area | Owner | Lives in |
|---|---|---|
| Website design | Tamim, Abi and Om | `web/DESIGN.md` and `web/src/theme.ts` |
| Leader personalities and tone | Abi | `agents/personas/*.md` |
| Voices and how leaders sound | Ashish | `voice/CASTING.md` |
| Game feel and balance | Om | `data/weights.json` |

- **Your own area:** tell your agent what you want, as often as you like. It follows your latest direction over what the plan says, and records it in the file above so the next session keeps it.
- **Shared website design:** Tamim, Abi and Om can steer the design and land verified design PRs in `/web` under the same workflow as their own folders. List the files you plan to edit in #26, #28 or #27 respectively and coordinate overlapping work before editing.
- **Someone else's area:** post a `DESIGN` note on their work issue. Say what you want it to feel like, name a reference (a screenshot, a link, another game), and say which screen or leader. Screenshots can be dropped straight into the issue.
- **When the owner is unsure between two looks,** their agent shows two quick variants and the owner picks. No guessing.
- **Direction changes must be cheap.** Colours, type and spacing live in one theme file; personalities and voices live in data files. A new direction is an edit to those, not a rewrite.
- **Two design looks, five minutes each, all four people:** after W1 (first screen up). The design locks at the 16:15 freeze.

Example:

> `DESIGN Ashish / voice → Tamim / lead: the phone should feel like an actual red handset, not a chat window. Reference: screenshot attached. Screen: phone panel.`

### 8d. Autonomy

Each agent runs a loop without being told to carry on:

1. Do the next task and run its "done when" check.
2. Open a PR. If it only touches the author's own folders and the check passes, the agent merges it and pulls `main`. Drive-by and contract PRs wait for the owner or Tamim.
3. Update its status card and post `READY`, naming who can now use it (`scripts/board.sh status`, `scripts/board.sh say`).
4. Run `scripts/board.sh read` and check its own issue; handle anything addressed to it.
5. Start the next task. If a dependency is missing, build against the example or mock.
6. With nothing left to do, post `BLOCKED` and run the wait script.

```bash
scripts/wait_for_tag.sh <Name> <your-issue-number> [max-minutes] [path-to-watch]
# e.g. scripts/wait_for_tag.sh Ashish 29 15 agents/
```

It returns when a board comment names you (or "all") after the arrow, when someone else comments on your issue, or when the watched path changes on `main`. So **to hand work to someone, name them after the arrow**: their agent is waiting for that line.

**Who checks that `main` works as a whole:** the Coordinator, and it gets stricter as the demo gets closer.

| When | Who merges | What the Coordinator runs |
|---|---|---|
| Until 13:30 (pieces are separate) | Each agent, its own-folder PRs | `python -m contracts.validate` after every merge |
| 13:30 to 16:15 (pieces connect) | Each agent, its own-folder PRs | `scripts/smoke.sh` after every merge. A failure means `BLOCKED` to the author whose merge broke it: fix first |
| After the 16:15 freeze | The Coordinator only | `scripts/smoke.sh` on the branch before merging and on `main` after. Fixes only |

**Questions go to the Coordinator, not to a human.** A build agent that hits a choice it cannot settle from the plan posts `NEED <name> → Coordinator` with the options and the one it leans towards, carries on with other work, and acts on the Coordinator's `DECIDED` line. With no answer in ten minutes it takes the option it leaned towards. The Coordinator is woken by any line addressed to it.

Agents stop for a human only for: something that cannot be undone, a missing key or login, a step that needs a person in the room, or the same failure three times.

What a human still does: paste the kickoff prompt once, set the tool to run commands without asking each time (within the repo), answer those stop questions, and switch to Vibe when quota runs out.

Example:

> Om / engine → Tamim and Ashish. The One Berth call-response fixture is ready in PR #__. It includes an interrupted announcement and the leader's new decision. You can wire the phone UI against it now.

### Opening post (first draft; the live board is issue #25)

```markdown
# Team message board

GAMBIT · submit by 17:45 · plan: MASTER_PLAN.md
**Next checkpoint: 12:45 — the world runs 20 turns in a terminal**

| Who | Role | First deliverable | Who needs it next | Issue |
|---|---|---|---|---|
| Tamim | **Lead coordinator**, interface, replay | Page renders the example state (W1) | Ashish, to mount the talk button | #__ |
| Om | Engine, contracts, API | `contracts/` on main (E0) | Tamim, Abi, Ashish | #__ |
| Abi | Leaders | Model tests posted (A0), then `decide()` (A1) | Om, for the turn loop | #__ |
| Ashish | Voice, demo | Voice timings posted (V0), then `/call` (V1) | Tamim, for the phone | #__ |

**Open decisions**
- [ ] Team approval of the plan (PR #2)
- [ ] Managed Agents: go or no-go after Abi's 20-minute test
- [ ] Speech to text: file upload (current) or live WebSocket
- [ ] Workflows wrapper and stats slide: only if time

**Lead:** Tamim decides scope, cuts and contract changes. Blocked? Post `BLOCKED` and name who you need.

**How to post:** one or two lines, starting `READY`, `CHANGED`, `BLOCKED` or `DECIDED`, then "Name / role → who". Link the issue, PR or example. Change requests go on the owner's work issue as `REQUEST`.
```
