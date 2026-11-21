![GAMBIT](e2e/assets/gambit-wordmark.svg)

# GAMBIT: every call is a move

GAMBIT is a strategy game you play by voice. Five fictional nations share one continent, and each is run by an AI leader with a public line and a private plan. You govern by picking up the Red Phone and talking to them. What you promise, when you call, whether you cut a leader off mid-sentence and how long you hesitate all change what the nations do next.

Built in one day for Le Chonk in London, the Mistral hackathon, on 21 November 2026. Every model call at runtime goes to Mistral: Voxtral for all speech in and out, Mistral Large 4 and its smaller siblings for the leaders.

## What you do in the game

- **Run a country for a three-year term.** Each month you set tariffs, propose trade and alliances, queue buildings, and decide who to call. Approval, stability, GDP, food, oil, chips and army all move. A democracy that loses its yearly election is out; a country that falls below the stability floor has a coup.
- **Phone the other leaders.** Hold the red button and speak. The leader answers in their own voice within a couple of seconds, and the game records what you committed to. Leaders compare notes with each other, so two promises that contradict are found out.
- **Handle a crisis against the clock.** A crisis card starts a 12-tick clock with a deadline for each leader. Four cards ship: **One Berth** (a storm leaves one berth for two grain ships), **Grey Fever** (one vaccine batch, two countries), **Colonels' Coup** (tanks in Ostrava's capital) and **Pipeline Cut** (Ostrava shuts the northern oil line).
- **See what your deal did.** After a crisis the war-odds needle compares the chance of war in the next six months before and after your moves, from matched-seed rollouts of the same deterministic engine.
- **Ask "what if I'd waited?"** A slider moves your calls up to five ticks earlier or later and reruns the crisis in pure code. It shows which leaders would have decided differently, and why.
- **Look behind the public line.** The Intel drawer shows each leader's public statement next to their private intent and what their advisers ranked. Wiretap plays two leaders talking about you.
- **Go to war, or stop one.** The War Room lets you declare war, march troops province by province, recruit, reinforce a front, and offer peace, tribute or a pact. AI leaders declare wars of their own. War fronts and captured provinces produce at half output.
- **Build an economy.** Queue factories, farms, chip works, rail yards, airfields and bases. You pay when you order, the site opens next month, and the dialog tells you why an order is refused.
- **Face the voters.** The term ends with an election count and a historian's verdict on what you did, written from the session log.

You can also sit as an **independent mediator** with no country and no army: you see public positions only and are judged on your calls alone.

## Run it

You need Python 3.12 or newer, Node.js 20.19+ or 22.12+, and a Mistral API key for live play.

```bash
git clone https://github.com/Infosuii/Mistral-Hackathon.git
cd Mistral-Hackathon
echo "MISTRAL_API_KEY=your_key_here" > .env
./scripts/demo.sh
```

The launcher sets up `.venv` and `web/node_modules` on a fresh clone, starts the backend on port 8000 and the web app on port 5173. Open **http://localhost:5173 in Chrome** and allow the microphone. Hold the red talk button to speak; press it while a leader is talking to interrupt them. A text box under the button does the same job in a noisy room.

To check your key, the models, speech and transcription before a demo:

```bash
source .venv/bin/activate
python scripts/preflight.py
```

No key or no network:

```bash
./scripts/demo.sh --offline
```

Offline mode needs the dependencies installed once while online. Leaders give fixed written replies, the microphone returns a fixed transcript, and the pre-recorded crisis calls and Wiretap lines play from `voice/prerendered/`.

Other ports: `./scripts/demo.sh --backend-port 8010 --web-port 5180`.

## Where Mistral is used

| Product | Model | What it does in GAMBIT |
|---|---|---|
| **Voxtral transcription** | `voxtral-mini-transcribe-3` | Turns each hold-to-talk clip into text. Every request carries `context_bias` with the nations, leaders and crisis words, so "Ostrava" and "Port Kessar" are spelled right and the promise reaches the right leader. |
| **Voxtral speech** | `voxtral-mini-tts-3-0` | Speaks every leader line in one of five cast voices, streamed so playback starts on the first chunk. The leader model picks an inline `[emotion=...]` tag with each reply. Crisis calls and the demo Wiretap are rendered ahead so they play instantly. |
| **Mistral Large 4** | `mistral-large-4` | Writes each leader's private strategy. After every call it works out, in the background, what was promised, what was agreed and how trust moved. It also writes live Wiretap dialogue, the replay explanations and the historian's verdict. |
| **Mistral Large 2512** | `mistral-large-2512` | The fast spoken reply on the phone: two sentences at most, in character. If it is slow, `mistral-medium-latest` races it so the line never goes quiet. |
| **Mistral Medium** | `mistral-medium-latest` | Each leader's monthly and crisis decisions. |
| **Mistral Vibe** | `gambit_mcp/`, `.vibe/skills/` | An MCP server with eight tools lets Vibe read and play a running game. Two skills ship with it: `/gambit-brief` (who is lying, the next deadline, what to say) and `/gambit-crisis-card` (drafts a new crisis file from one sentence). Setup is in [`gambit_mcp/README.md`](gambit_mcp/README.md). |

The leaders are advised by the engine but choose freely: each sees a ranked list of legal moves and may pick any of them. In a crisis the engine holds them to within a set distance of their advisers' ranking, and escalations (blockade, mobilise, close the port) need the advisers' support.

[`voice/VOXTRAL.md`](voice/VOXTRAL.md) lists every Voxtral feature the game uses, where it appears, and what we measured.

We tried Mistral Managed Agents for the leaders and did not use them: a turn took 9.6 seconds ([`agents/A0_RESULTS.md`](agents/A0_RESULTS.md)). The game uses chat completions with JSON output and keeps each leader's memory itself.

## How voice changes the game

- **Promises** you speak are recorded per leader and checked against what you later do. At tick 5 of One Berth the leaders compare notes; a double promise costs you most of their trust.
- **Interrupting** a leader takes effect the moment you press the button. Cut General Dravic off while he announces a blockade and the threat never becomes a public commitment, though a proud leader likes you less for it.
- **Hesitating** before you answer is measured by the talk button and passed to the leader. Proud leaders read it as weakness.
- **Timing** matters because each leader decides at their own deadline. A request that arrives after the deadline arrives too late, which is what the replay slider shows.

## A five-minute run to try

On seed 7 as President of Valdoria:

1. Call Queen Isolde of Kessaria and offer a trade deal.
2. Start **One Berth**. General Dravic of Ostrava rings at once. Promise him the berth.
3. Call Chairman Oryn of Zarnia and promise him the same berth.
4. Call Chancellor Lindqvist of Nordhaven and ask for tugs to open a second berth before her deadline.
5. At tick 5 the leaders compare notes and catch the double promise. Open Intel and play the Wiretap.
6. At tick 7 Dravic rings to announce a blockade. Press talk while he is speaking and offer him the morning slot.
7. Let the deadlines resolve, read the war-odds needle, then drag the replay slider to +3 and see who flips.
8. End the session for the election count and the verdict.

This is the path `e2e/demo_path.py` plays against live models.

## What we measured

On the final build (17:23, live models, the launcher's settings), the automated demo path passed all 11 steps in 139 seconds. The spoken reply to a typed line came back in 1.4 to 3.4 seconds, the war-odds forecast took 2.5 seconds for 120 rollouts, and the replay took 4.6 seconds including the written explanations.

Earlier in the day, on an earlier build, across 10 live voice calls (`python -m e2e.timings`):

| Step | Median | Worst |
|---|---|---|
| Spoken reply text | 1.39 s | 3.11 s |
| First chunk of speech | 0.39 s | 1.27 s |
| Transcription, Chrome microphone clip | 0.25 to 0.37 s | |
| Transcription, 220 KB WAV upload | 3.32 s | 8.72 s |
| Working out what a call agreed (background) | 13.10 s | 21.44 s |

A human playtest of One Berth by voice had 13 of 13 transcriptions and 13 of 13 spoken replies succeed. Word accuracy held at 98% down to a 10 dB signal-to-noise ratio in a **simulated** noisy room (synthetic babble and hum, not a recording of the venue).

## Check it yourself

```bash
python -m pytest -q                      # 167 tests, no network
scripts/smoke.sh                         # a few seconds, stub leaders
python -m e2e.demo_path                  # the demo path against live models
python -m e2e.demo_path --url http://127.0.0.1:8000   # against a running game
python -m e2e.timings                    # live latency benchmark
```

The browser walkthroughs (`python -m e2e.walkthrough --offline`, `python -m e2e.crisis_cards`) need Playwright: `python -m pip install playwright` then `python -m playwright install chromium`.

## How it is built

| Folder | What is in it |
|---|---|
| `engine/` | The simulation. `step()` is pure and deterministic: same seed and same moves give the same world, which is what makes the forecast and the replay possible. Also the crisis clock, the rollouts, saves, construction, transport and the FastAPI app. |
| `agents/` | The five leader personas and every model call: monthly decisions, the fast phone reply, call interpretation, private strategy, Wiretap, replay explanations, the historian. |
| `voice/` | Voxtral transcription and streamed speech, `POST /call`, `GET /wiretap`, the talk button with interruption and hesitation timing, the cast voices and the pre-rendered lines. |
| `war/` | The War Room: garrisons, marching armies, battles, recruitment, peace terms. |
| `replay/` | `POST /replay`: reruns the last crisis with your calls shifted in time. |
| `web/` | The React app: the campaign map with terrain, cities, rail, sea routes and fleets, the crisis clock, the Red Phone, Intel and Wiretap, the War Room, construction, the replay panel and the election finale. |
| `contracts/` | Pydantic models and example payloads for every endpoint. |
| `data/` | Nations, tuning weights, buildings, the map, and one JSON file per crisis card. A new crisis is a new file. |
| `gambit_mcp/`, `.vibe/` | The MCP server and skills for Mistral Vibe. |
| `e2e/` | The demo-path test, the offline server, timings and browser walkthroughs. |

The five nations: **Valdoria** (democracy, Prime Minister Elena Varga), **Ostrava** (junta, General Marek Dravic), **Zarnia** (one-party state, Chairman Tomas Oryn), **Kessaria** (monarchy, Queen Isolde of Kessar) and **Nordhaven** (technocracy, Chancellor Aino Lindqvist).

## Known limits

- The War Room runs on a real-time clock, so battles are not part of the deterministic replay. The replay covers crisis decisions.
- The war, economy and election features were merged in the last hour of the hackathon. They pass their tests and an offline browser check, but have had far less live play than the phone and One Berth.
- Three of the four crisis cards (all but One Berth) have been played through offline; only One Berth has been run end to end against live models many times.
- Interruption and hesitation come from the talk button's timing. Audio is transcribed after you let go, not while you speak.
- The End session button is not shown while a crisis is running.
- All leaders share one API key, and the fast phone model allows 30 requests a minute. Several people playing at once on one key will see slower replies.

## Team

Tamim Atiqur, Om Dhande, Abi and Ashish Kadari.
