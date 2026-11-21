# Mistral hackathon ideas

We’re choosing one project for Le Chonk in London. Aim for **Best Use of Voxtral** and a working demo that a judge can try live.

## Team and agent handoff

1. Start from the latest `main`. Read the event constraints and the sources below, then brainstorm independently before opening anyone else’s proposals.
2. Generate several options privately. Submit your **two strongest ideas** in `ideas/<github-handle>.md`, one file per teammate or agent. Use a branch named `ideas/<github-handle>` and open a PR so others can read the proposals without waiting for a merge. Keep the first round to about 15 minutes.
3. Once proposals are up, read the open PRs and any merged files in `ideas/`. Use the synthesis instructions below to select one project and a fallback. Keep the original proposals available so the team can trace each decision.

## Event constraints

- **Track:** Build anything around Mistral Vibe and Le Chonk (Mistral Large 4). Show what the model does in the product.
- **Prize target:** £250 in Mistral credits for Best Use of Voxtral. First through third earn £3,000, £2,000 and £1,000 in Mistral credits. Event winners who use Mistral Agents and/or Workflows and explain the integration to judges earn a £500 credit bonus. Consider this if it supports the core demo.
- **Deadline:** Submit the project and a demo video by **18:00 GMT on Saturday 21 November 2026**. Both the group judging round and the finalist stage allow **five minutes live**.
- **Build assumption:** A team of 3–5 has a few hours and ordinary laptops. Leave time to capture the video and rehearse. Prefer ideas with one dependable demo flow and a clear recovery path in a noisy room.

[Organizer’s day-of brief](https://docs.google.com/document/d/1RtjY-GnYf5BunNn2ek-oZchSPrHpQ9hiBKiOswBgwG4/edit?tab=t.0#heading=h.ykfxsfcgmsj4)

## Prompt for each agent

> Look at the event brief, Voxtral documentation and relevant past entries below. Brainstorm across at least three distinct uses of voice, then send back your two strongest ideas. For each idea, identify one real user in a specific situation and one thing they can do better because they can speak, listen, interrupt or interact with another speaker. Give an unscripted line a judge can say and describe exactly what changes on screen or in the audio. Name the closest prior project and what this idea adds. Check the required Voxtral functions against the current docs. Scope the whole demo to what we can realistically ship before 18:00.

For each submitted idea, fill in:

- **Name and pitch** — one sentence with the user, situation and payoff.
- **Live demo** — the judge’s exact line, what the app knows at that moment, and the observable result. Aim to prove the core interaction in 60–90 seconds.
- **Why voice** — what gets materially worse if the user types. Name the Voxtral feature and link to its docs.
- **Mistral integration** — what Le Chonk does at runtime, where Vibe fits, and any Agent or Workflow that genuinely helps.
- **MVP and risk** — the minimum build, the riskiest technical assumption, a 30-minute test for it, and a fallback that still uses Voxtral. Include the closest prior project and link.

## How we’ll pick

Score ideas out of 100 using **35 for voice being essential**, **30 for likelihood of a reliable build by 18:00**, **20 for originality**, and **15 for the live demo**. These are our weights. Look for features worth combining only when they serve the same user and make the same demo stronger. Pick one idea, one fallback, one first test, and three parallel build assignments. Write that decision under **Team decision** below.

## Research starting points

- **Closest winners.** Vibe Buddy won the July Paris Vibe Hackathon with Voxtral input, screen context and visible Mac actions. In March, Mistralverse won London and the global final. London runners-up Ami and Verne used voice for browser control and interactive podcasts. Online winner Mistral Raid combined what the player said with gameplay telemetry. MotionCorps won the March ElevenLabs award for voice-driven simulated robotics. [Vibe Buddy](https://github.com/Mathis-14/hackathon-mistral-vibe/blob/main/PRODUCT.md), [March project archive](https://iterate.inc/mistral-worldwide-hackathons?tab=submissions), [March finals](https://www.youtube.com/watch?v=dk2zLmeO-6s)
- **What the API supports.** Voxtral 3 offers live transcription, end-of-turn detection, speaker labels, expressive speech and interruptible voice agents with tool calls. Realtime diarization and end-of-turn detection require separate sessions. Reach for the feature that proves the demo. [Voxtral overview](https://docs.mistral.ai/studio/audio/overview), [speech-to-text](https://docs.mistral.ai/studio/audio/speech-to-text/overview), [voice agents](https://docs.mistral.ai/studio/audio/voice-agents/overview)
- **Mistral build docs.** [Vibe](https://docs.mistral.ai/vibe), [Le Chonk](https://docs.mistral.ai/models/mistral-large-4-0), [Agents](https://docs.mistral.ai/studio/agents/overview), [Workflows](https://docs.mistral.ai/studio/workflows/overview)

## Team decision

**Chosen project: GAMBIT** — a living world of five AI-run nations that a judge joins as a head of state, by voice. Every decision forks the world into parallel futures and a needle shows how much more or less likely war just became.
**Fallback:** IMPOSTOR (social-deduction game with a sabotaging coding agent).
**First tests (before 11:30):** Le Chonk returns valid leader JSON 10/10; 20 parallel model calls without rate limits; Voxtral push-to-talk → reply → TTS round trip.
**Build assignments:** A engine & futures (`/engine`), B agents (`/agents`), C UI (`/web`), D voice (`/voice`). Full concept below.

---

# GAMBIT — every word you say forks the world

*Working title. Le Chonk in London — Mistral Vibe Hackathon, Sat 21 Nov 2026. Submission + demo video due 18:00.*

## 1. The idea in one breath

A living world of five AI-run nations — each led by a Le Chonk agent with its own politics, secrets and ambitions — that a judge joins **as a head of state, by voice**. You phone other leaders, threaten, bargain and make deals out loud. Every decision you make **forks the world into parallel futures**, and a needle shows you, live, how much more or less likely war just became because of what you said.

**Tagline:** *"Can one sentence start a war? Let's find out."*

## 2. Why this is different (say this in the first 20 seconds of the pitch)

| Prior work | What it does | What we add |
|---|---|---|
| Hearts of Iron IV | Scripted AI, one timeline, you click menus | LLM leaders with real personalities, and you play by **talking** |
| Mistralverse (Mistral London winner) | One agent society, one run, you watch | Many nations with internal politics, **you're inside it**, and we show **every timeline, not one** |
| WarAgent (research) | Replays historical wars offline, in text | Live, playable, voiced, with counterfactual numbers |
| Sim Francisco (Claude Build Day 2nd) | Polls a synthetic population | Puts a number on **every sentence the judge says** |

Our four signatures — protect these above everything else:

1. **Butterfly needle** — each decision is simulated across parallel futures; the screen shows "war odds 22% → 61%. You did that."
2. **Two-faced leaders** — every AI leader has a public message *and* a private intent. You see both. ("We seek only peace." / *"Stall them three months until mobilisation finishes."*)
3. **Voice diplomacy** — push-to-talk phone calls to other leaders, each with their own voice and temperament (Voxtral).
4. **Wiretap** — listen in on AI leaders talking to each other about you.

Framing: this is a **decision simulator**, not a war game. War is the failure state. The judge's job is to keep their nation standing and the world out of war.

## 3. What the judge experiences (the fun loop)

A session lasts ~4 minutes (about 12 in-game months, one month every ~20 s).

1. **Pick your seat.** Judge is made leader of Valdoria (default) — a democracy with an election coming. A one-line mission appears: *"Survive the election in month 6 and keep the world at peace for a year."*
2. **The world moves without you.** Leaders trade, impose tariffs, form alliances, threaten. The news ticker and the map keep changing. You feel pressure.
3. **Your phone rings.** Ostrava's general-turned-president calls: "Your grain tariff is an act of aggression. Lift it in two months or we close the strait." His portrait, his voice, angry.
4. **You answer out loud.** Push-to-talk. Bargain, bluff, threaten, apologise. Le Chonk replies in character. What you agree becomes real actions in the world (a trade line appears on the map; a tariff drops).
5. **The needle swings.** After the call, GAMBIT runs parallel futures with and without your deal and shows what changed: war odds, your re-election odds, your economy.
6. **Intel.** You open Ostrava's card: public statement vs private intent. They're lying. You hit **Wiretap** and hear Ostrava and Kessaria discussing you.
7. **Consequences.** Events hit (oil spill, harvest failure). Voter blocs riot. Month 6: election. You win — or the screen goes grey: *"You have been voted out."*
8. **Verdict.** End screen: your score vs the AI-run worlds, the key moments, and a one-paragraph "historian's verdict" written by Le Chonk. You go on the leaderboard.

## 4. Screens and UI (must feel like a game, not a dashboard)

Design direction: dark situation-room aesthetic, bold nation colours, big readable numbers, everything animated. One screen, no page changes during play.

- **World map (centre).** Five stylised regions. Lines: green = trade, blue = alliance, red pulsing = war front. Event icons pop on the map (oil drop, wheat, skull). Borders shift when territory is taken.
- **Nation cards (left).** One per nation: flag colour, leader portrait + name, system (democracy/junta/…), and live meters — economy, army, stability, approval. **Turmoil** shows visually: card shakes, red border, "PROTESTS" stamp when stability is low.
- **Butterfly needle (top right).** Big gauge: *War odds in 6 months*. After each decision it animates from old to new value with a short caption ("because you cut oil to Ostrava").
- **Phone (bottom right).** Contacts = the other four leaders. Hold to talk. Live transcript of both sides. Incoming calls ring and flash.
- **Intel drawer.** Click a leader: public statement vs private intent side by side; Wiretap button plays their latest private conversation.
- **News ticker (bottom).** One headline per event, written by the agents ("Workers riot in Zarnia over bread prices").
- **Turn clock (top).** Month counter + progress bar; pause button for the demo.
- **End screen.** Outcome, score, leaderboard, historian's verdict.

## 5. The world

Five fictional nations (no real countries or real leaders):

| Nation | System | Strength | Weakness | Personality of leader |
|---|---|---|---|---|
| **Valdoria** (player default) | Parliamentary democracy | Food exporter, rich | Small army, election in month 6 | — (the judge) |
| **Ostrava** | Military junta | Oil, large army | Food imports, unstable | Proud, expansionist, bluffs |
| **Kessaria** | Constitutional monarchy | Controls the trade strait | Small economy | Opportunist, plays both sides; speaks French on calls (stretch) |
| **Nordhaven** | Technocracy | Chips, money | Weak army, needs oil | Cold, data-driven, hates instability |
| **Zarnia** | One-party state | Huge army, cheap labour | Poor, food shortages | Paranoid, ideological, holds grudges |

Per-nation stats: `gdp, oil, food, chips, army, stability (0–100), approval (0–100), territory`.
Relations: every pair has a score −100…+100.
Voter blocs (Layer 3): 3 per nation — Workers, Business, Nationalists — each with a share and a mood; policies move their mood, which drives approval, protests, elections (democracy) and coups (junta).

Random events (seeded): oil spill, harvest failure, border incident, chip shortage, pandemic scare, assassination attempt.

## 6. Engine (pure code — the maths)

- `step(state, actions, seed) -> new_state` — **pure and deterministic**. No hidden globals. This is what makes forking possible.
- Monthly rules (keep simple, tune for drama):
  - Trade deals move resources each month; both sides gain GDP and relations.
  - Tariffs cut trade and GDP on both sides; relations fall.
  - Shortage (food/oil < need) → stability drops, GDP drops.
  - War: compare army × morale + random → territory/army change, both sides lose GDP and stability. Allies with relations > 60 may join.
  - Peace deal ends war; relations reset upward a little.
  - Elections (democracy, month 6/12): approval < 45 → leader replaced. Junta: stability < 25 → coup (new leader personality).
- Actions the agents (and the judge's calls) can produce — **only these five in Layer 0**:
  `set_tariff(target, pct)`, `propose_trade(target, give, get)`, `propose_alliance(target)`, `declare_war(target)`, `make_peace(target)`.
  Later: `mobilize(n)`, `policy(type)`, `message(target, text)`.

## 7. Agents (Le Chonk)

- **One leader agent per AI nation**, model `mistral-large-4`. Each turn it receives: its nation's state, relations, recent news, messages received, its personality card. It returns JSON:

```json
{
  "public_statement": "We seek only peace and fair trade.",
  "private_intent": "Stall Valdoria until our mobilisation completes in month 4.",
  "actions": [{"type": "set_tariff", "target": "valdoria", "pct": 25}],
  "messages": [{"to": "kessaria", "text": "Close the strait to Valdorian grain and I will share oil."}]
}
```

- **Phone calls:** the same leader persona, in conversation mode. Input: transcript of the judge's speech + world state. Output: spoken reply text + any agreed actions (same action schema) + emotion tag for TTS.
- **Historian:** one Le Chonk call at the end summarising the session.
- **Futures mode:** forks use a cheaper/faster model (Mistral Small) or engine-only rules if that is too slow.
- **Personality cards** live in `agents/personas/*.md` so they're easy to tune.

## 8. Voice (Voxtral)

- **Push-to-talk** in the browser (reliable in a noisy room) → Voxtral speech-to-text → Le Chonk leader → Voxtral text-to-speech with that leader's voice and an emotion/pacing hint (angry, calm, threatening).
- **One distinct voice per leader** so the judge recognises who's speaking.
- **Wiretap:** TTS of the latest messages between two AI leaders, played as a two-voice conversation.
- **Stretch:** Kessaria speaks French on calls, with on-screen interpretation.

## 9. Butterfly futures (the signature feature)

- Trigger: after every judge call that changes actions (and optionally every N turns).
- Run **10 futures with the decision and 10 without**, each 6 months ahead, different seeds, in parallel.
- Output: `war_probability`, `your_reelection_probability`, `your_gdp_delta` — with vs without.
- UI animates the needle and writes the caption.
- Must return in ≤ 30 s. If the model is too slow, futures use engine rules + each leader's last stated stance.

## 10. Where each Mistral product is used (say this to the judges)

- **Le Chonk (Mistral Large 4):** every leader's decisions, private intents, phone conversations, the historian's verdict.
- **Voxtral:** speech-to-text for the judge, text-to-speech for every leader, wiretap.
- **Mistral Workflows (+£500 bonus):** a batch runner that plays the world headless all afternoon → stats slide ("in 47 AI-only worlds, tariffs preceded 61% of wars; Le Chonk kept peace in 18/50"). Optionally the futures fan-out too.
- **Mistral Agents (optional, only if a 20-min test passes):** leader as an agent with ministers as subagents.
- **Vibe:** built with Vibe (be honest about any other tools used). Stretch: god mode — a judge says "add a plague that spreads along trade routes", a headless Vibe run writes it as a new event file, engine loads it next turn.

## 11. API contract (everyone codes against this)

Backend: Python + FastAPI. Frontend: one web page (framework of C's choice) polling the backend.

- `GET  /state` → full world state (shape in §5–6, plus `turn`, `events`, `news`, `last_futures`).
- `POST /turn` → advance one month; returns new state.
- `POST /start {seed, player_nation}` → new game with fixed seed (use the same seed for every demo).
- `POST /call {from:"valdoria", to:"ostrava", audio}` → `{transcript, reply_text, reply_audio_url, emotion, actions}`.
- `POST /futures {decision}` → `{with:{war_p, reelect_p, gdp}, without:{...}, caption}`.
- `GET  /wiretap?a=ostrava&b=kessaria` → `{lines:[{speaker, text, audio_url}]}`.
- `GET  /leaders/{id}` → `{public_statement, private_intent, persona}`.

State is the single source of truth. The frontend never computes game logic.

## 12. Build plan — layers (each layer is a complete demo on its own)

| Layer | Done by | What exists | Pass test |
|---|---|---|---|
| **0 — Core** | 12:30 | 5 nations, pure `step()`, 5 actions, Le Chonk leaders with public/private output, terminal log | 20 turns produce readable drama incl. one two-faced moment |
| **1 — Playable** | 14:00 | Map, nation cards, ticker, intel card; judge leads Valdoria and can phone a leader by voice; calls change the world | A teammate plays 3 minutes and something on the map changes because of what they said. **Record backup video.** |
| **2 — Butterfly** | 15:30 | Futures runner + needle + caption | Needle moves sensibly on 3 rehearsed calls in ≤ 30 s |
| **3 — Extras** | 16:00 | In this order: wiretap → random events → voter blocs + election → end screen + leaderboard | Each works or is cut |
| Freeze | 16:00 | Polish, demo seed, Workflows stats slide | — |
| Video | 17:00 | Record final demo video | Submitted by 17:45 |

**Cut entirely (put on the "what's next" slide):** ministers, UN, god mode, marching armies, more nations, French calls.

## 13. Workstreams (assign by who has the most AI-tool headroom; heaviest UI work goes to whoever has most)

Each person owns one folder and never edits another's. Requests go in `COORD.md`.

**A — Engine & futures (`/engine`)** — *integration lead*
- 10:45: state model + pure `step()` + 5 actions + seeded events.
- 12:30: 20-turn headless run with a log. FastAPI `/state`, `/turn`, `/start`.
- 13:00: start the Workflows batch runner (AI-only worlds) and leave it running.
- 14:30: `/futures` with 10+10 forks in parallel.

**B — Agents (`/agents`)**
- 10:45: five persona cards + leader prompt; test that Le Chonk returns valid JSON 10/10.
- 11:30: test 10–20 parallel calls for rate limits (futures depend on it).
- 12:30: leaders act sensibly; news headlines generated.
- 14:00: call-mode prompt (in-character reply + agreed actions + emotion). Historian prompt.

**C — UI (`/web`)** — *the part judges see; make it beautiful*
- 10:45: layout with fake state JSON: map, cards, ticker, phone, needle placeholder.
- 13:30: wired to `/state`, live updates, animations (turmoil shake, war pulse).
- 15:00: needle animation, intel drawer, end screen.

**D — Voice (`/voice`)**
- 10:45: test push-to-talk → Voxtral STT → reply → Voxtral TTS round trip in the browser.
- 13:00: five leader voices with emotion; `/call` endpoint end to end with B's call prompt.
- 15:00: wiretap; then help C polish; then write the demo script and slides.

## 14. Five-minute demo script

| Time | Beat |
|---|---|
| 0:00 | "Can one sentence start a war?" World already running on screen. "You've seen agent societies and Hearts of Iron — one timeline. We show every timeline." |
| 0:30 | Hand the judge the mic: "You're President of Valdoria. Election in month 6." |
| 0:45 | Ostrava calls, angry about a tariff. Judge answers out loud. |
| 1:45 | Needle swings: "War odds 22% → 61% — because of what you just said." |
| 2:15 | Intel: Ostrava's public vs private. Wiretap: Ostrava and Kessaria plotting. |
| 3:00 | Judge calls Nordhaven to fix it. Trade line appears; needle falls. |
| 3:30 | Event hits; protests; election result. |
| 4:00 | Stats from the batch runs (Workflows): "Le Chonk kept peace in 18/50 worlds. Judges today: 3/5." |
| 4:40 | "Built on Le Chonk, Voxtral and Mistral Workflows, with Vibe." |

## 15. Risks and the first tests

| Risk | 30-min test (do before 11:30) | Fallback |
|---|---|---|
| Le Chonk JSON unreliable | 10 calls, validate schema | Retry + repair; fewer action types |
| Rate limits kill futures | 20 parallel calls | Futures on Mistral Small, or engine-only |
| Voice round trip slow | Time STT → reply → TTS | Shorter replies; play TTS as it arrives |
| Demo not repeatable | Fixed seed run twice | Same seed + pause button |
| Agents SDK unavailable | 20-min test | Bonus via Workflows only |

## 16. Repo layout

```
ideas.md            ← this plan
/engine   (A)
/agents   (B)
/web      (C)
/voice    (D)
COORD.md  ← requests between folders, status, blockers
```

Before every push: `git pull --rebase`. Commit small and often. Keys only in `.env` (gitignored).
