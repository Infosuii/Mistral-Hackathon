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

**Proposed project: GAMBIT** — a voice-played strategy game. Five AI-run nations share one world. You take a seat as a president, a diplomat or an outside mediator and govern by phoning the other leaders. When a crisis erupts a clock starts, and what you say, when you say it and whether you interrupt decides what happens next.
**Status:** proposal (v2 of this PR, updated 11:45 with the accepted points from Abi's review in PR #3; see §0b). It replaces the first draft below the line. React 👍 on the PR or comment with objections so we can lock it and build.
**Fallback:** IMPOSTOR (social-deduction game with a sabotaging coding agent).
**First tests (before 12:00):** Le Chonk returns valid leader JSON 10/10; 8 parallel model calls timed; Voxtral talk → reply → speech round trip timed; one emotion tag audibly changes a voice.
**Build assignments:** Tamim lead coordinator + interface + replay (`/web`, `/replay`), Om engine + futures (`/engine`), Abi leaders + batch (`/agents`), Ashish voice + demo (`/voice`). Full concept below.
**How we build it:** `MASTER_PLAN.md` (tasks, checkpoints, contracts, coordination) and `MASTER_PROMPT.md` (what each person pastes into their coding agent). Where they differ from this file, they win.

---

# GAMBIT — every call is a move

*Le Chonk in London — Mistral Vibe Hackathon, Sat 21 Nov 2026. Submission + demo video due 18:00.*

## 0. What changed from the first draft, and why

The first draft (BUTTERFLY) was a year-long world with a war-odds needle. This version keeps that world and puts a tense, timed crisis mode ("Red Phone") inside it.

| | First draft | GAMBIT v2 | Why it's better |
|---|---|---|---|
| **Why voice matters** | Voice was how you talked; typing would have worked the same | Interrupting, hesitating and timing change the outcome | Our prize target is Best Use of Voxtral. Voice has to be something the game needs |
| **Signature moment** | Needle after a call | Needle **plus** "What if I'd waited?" replay | The replay names the leader who flipped and why. A percentage alone can't |
| **How the odds are computed** | 10 futures with, 10 without, each needing model calls (about 480 calls, up to 30 s) | Hundreds of rollouts in code with the same seeds on both sides | Answers in seconds, and the number is a real difference, not noise. Judges who are scientists will ask |
| **How leaders decide** | Le Chonk picks actions freely | The engine advises, Le Chonk decides, and we show when a leader defies the advice | Still free and in character, but every decision can be explained on screen |
| **Pace** | One month every 20 s for a year | Strategy months, then a crisis with a 24-hour clock | Gives a 90-second high point a judge can play inside a five-minute slot |
| **Seats** | President of Valdoria | President, diplomat or mediator | Same engine, three ways to play |
| **Team** | Four workstreams, A carrying four jobs | Four named roles sized to each person's AI usage | Integration moves off the critical-path seat |
| **Docs fixes** | "threatening" emotion; shared batch key | Supported emotion tags only; batch on a separate account | "threatening" is not a Voxtral tag and is ignored silently. Rate limits are shared per workspace |

Kept from the first draft: the five nations, two-faced leaders, Wiretap, the pure deterministic engine, the layered build, the fixed demo seed.

## 0b. Review decisions (from Abi's review, PR #3)

| # | Suggestion | Decision |
|---|---|---|
| 1 | Move `/replay` from Om to Abi | **Changed.** `/replay` moves off Om, but to Tamim, who has the most AI usage. Om keeps `fork`, rollouts and the needle |
| 2 | Give Ashish crisis-deck files and the end screen after 14:15 | **Half.** Crisis-deck data files, yes. The end screen stays in `/web` |
| 3 | When a tool's quota runs out, switch to Vibe in the same folder | **Taken**, with Vibe limited to small, self-contained tasks (§16) |
| 4 | Most headroom takes the engine | **Not taken.** No role swap. Extra work goes to Tamim first |
| 5 | Make live replay a stretch goal; pre-record it | **Half.** Original decisions are cached and the needle is built first. The replay runs in code, not from a recording, because the judge speaks live (§7) |
| 6 | Treat latency as the top demo risk | **Taken** (§8, §18) |
| 7 | Abi mocks the advisers' ranking until `advise()` lands | **Taken** (§11) |
| 8 | Typed-input fallback and cached responses for the demo seed | **Taken.** Cache only scripted parts; replies to the judge are live (§8) |
| 9 | Don't claim "each nation is a Mistral Agent" unless the test passes | **Taken** (§13, §17) |
| 10 | Stats slide optional; batch on a separate account | **Taken** (§13, §15) |

## 1. The idea in one breath

A living world of five AI-run nations, each led by a Le Chonk agent with its own politics, secrets and pressures. You join it by voice. In calm months you trade, ally and threaten like any strategy game. Then a crisis hits, the phones ring, and you have minutes to talk leaders down before their deadlines pass.

**Tagline:** *"Every call is a move."*

## 2. Why this is different (say this in the first 20 seconds of the pitch)

| Prior work | What it does | What we add |
|---|---|---|
| Hearts of Iron IV | Scripted AI, one timeline, you click menus | LLM leaders with real personalities, and you play by **talking** |
| Mistralverse (March London winner) | One agent society, one timeline, humans join by typing | Many nations, played by **voice**, and we show the timeline you didn't take |
| PerrySphere (March, online, unplaced) | Five nation-agents on a map, text, you watch | You're inside it, by voice, with timing that matters |
| WarAgent (research) | Replays historical wars offline, in text | Live, playable, voiced, with counterfactuals |

Our five signatures — protect these above everything else:

1. **Red Phone crisis mode** — a clock, deadlines, and calls where interrupting and hesitating count.
2. **"What if I'd waited?"** — replay the same crisis with your offer arriving earlier or later; see who changes their decision and why.
3. **War-odds needle** — "war odds 22% → 61%. You did that."
4. **Two-faced leaders** — public statement and private intent, side by side, plus what their advisers recommended and what they chose.
5. **Wiretap** — listen to two AI leaders talking about you.

Framing: a **decision simulator**, not a war game. War is the failure state.

## 3. The loop

1. **Pick a seat** (see §4). Default: President of Valdoria.
2. **Strategy phase.** The world advances month by month. Leaders trade, set tariffs, form alliances, threaten. You act and make calls when you choose.
3. **A crisis erupts.** The month clock stops. A 24-hour crisis clock starts. Phones ring. Each nation has a decision deadline.
4. **You talk.** Hold to talk. Leaders answer in their own voices. You can cut them off. What you promise is recorded.
5. **Resolution.** Each nation commits. The map and meters change.
6. **Debrief.** The needle shows war odds before and after your deal. Then "What if I'd waited?" replays the crisis with your timing changed.
7. **Back to the world**, changed by what happened, until the next crisis or the end screen with the historian's verdict.

A demo session is two crises in about five minutes.

## 4. Seats

| Seat | You control | You see | You win by |
|---|---|---|---|
| **President** | Your nation's actions and calls | Your own stats and intel | Staying in power and out of war |
| **Diplomat** | Negotiations only; your AI president can overrule you | Less intel | Getting deals your president accepts |
| **Mediator** | Nothing but your word | Both sides' public positions | Keeping the peace |

A seat is a small config: which decisions are human, what is visible, the win condition. Build president first, mediator second, diplomat third.

## 5. How leaders decide: advised, but free

- **The engine advises.** For each leader it scores every legal action from that nation's payoffs and current beliefs, and ranks them.
- **Le Chonk decides.** The leader gets the ranking as "your advisers' assessment", plus personality and political pressures, and may choose any legal action.
- **Deviations are shown.** "Advisers recommended waiting. He chose the blockade: pride." This is where personality shows, and it stays explainable.
- **The engine validates.** An illegal action falls back to the top recommendation.

## 6. Red Phone crisis mode

- **Clock:** 24 in-game hours in about 12 ticks.
- **Deadlines:** each nation must commit by a fixed tick.
- **Promises:** Le Chonk turns each thing you say into a structured promise (to whom, what, when, on what condition). Contradictory promises are caught in code when diplomats compare notes at a fixed tick.
- **Public commitment rule:** once a threat is public, backing down costs that leader face (voters for a democracy, the general for a junta). Before it is public, conceding is cheap. This is why interrupting matters.
- **Hesitation:** a long pause after an ultimatum lowers that leader's belief in your resolve.

**First crisis: One Berth.** A storm closes Kessaria's port to a single berth for 24 hours. Two grain ships wait, both carrying Valdorian grain.

| Nation | Why it must act | What it can do |
|---|---|---|
| **Ostrava** (junta) | Three days of bread left; riots mean a coup | Dock, wait, or blockade the strait |
| **Zarnia** (one-party) | Also short of food; holds grudges | Dock, wait, or mobilise at the border |
| **Kessaria** (monarchy) | Owns the port; wants a price | Give the berth to one side, split the day, or close the port |
| **Valdoria** (democracy) | Sold grain to both; election coming | Honour both contracts, favour one, or split the cargo |
| **Nordhaven** (technocracy) | Hates instability; owns the only tugs | Send tugs to open a second berth, if asked in time |

The hard call: Ostrava's president learns you promised the berth to both sides and starts announcing a blockade. You have until he finishes the sentence. Tell the truth and offer half a day, breaking your word to Zarnia, or bluff about a second berth Nordhaven hasn't agreed to.

Why waiting is a real choice: calling Nordhaven early buys capacity (the tugs need lead time); waiting buys information (a mid-round forecast says whether the storm clears).

**Crisis deck** (each is a data file: who is affected, a clock, one or two special actions, payoff changes):

- **One Berth** — storm, one dock, two hungry nations. *Build this one first.*
- **Outbreak** — close borders or share Nordhaven's vaccine doses.
- **Coup in Ostrava** — recognise the new leader or back the old one.
- **Pipeline cut** — Nordhaven runs short of oil and blames someone.
- **Border shots** — Zarnia and Kessaria, with a mobilisation deadline.

## 6b. How strategy works (the numbers)

All values below are starting points to tune in playtests. They live in data files, not code.

**What each regime cares about.** A leader's score for an action is the weighted sum of the changes it expects, minus any cost of breaking a public commitment.

| Weight on | Democracy | Junta | Monarchy | Technocracy | One-party |
|---|---|---|---|---|---|
| Economy (`gdp`) | 2 | 1 | 3 | 3 | 1 |
| Supply (`food`, `oil`) | 2 | 3 | 1 | 2 | 3 |
| `stability` | 1 | 3 | 2 | 3 | 3 |
| `approval` | 3 | 0 | 1 | 1 | 0 |
| `army`, `territory` | 1 | 3 | 1 | 0 | 2 |
| Cost of backing down in public | 2 | 3 | 1 | 1 | 2 |

`score(action) = Σ weight × expected change − public back-down cost (if it applies)`

**Expected change depends on beliefs.** Each leader estimates what the others will do from relations, public commitments and what you promised:

- A promise from you raises a leader's belief that it will happen by `0.5 × trust_in_player`.
- A kept promise: `trust_in_player + 0.15`. A contradiction caught when diplomats compare notes: `trust_in_player × 0.4`.
- Hesitating more than 2.5 s after an ultimatum: `resolve_of_player − 0.15`.
- Interrupting: `resolve_of_player + 0.10`, and relations −5 with proud leaders (Ostrava, Zarnia).
- A leader who believes your resolve is low rates escalation against you as cheaper.

Trust and resolve carry over between crises. Lying can win one crisis and lose the next.

**Levers in the strategy phase**

| Lever | Effect on the maths | Use it to |
|---|---|---|
| Trade deal | Both sides gain `gdp` each month; war between them now costs that trade | Make war expensive for a rival |
| Tariff | Both sides lose `gdp`; relations fall | Apply pressure, at a price |
| Alliance | An attacker must expect to fight both armies | Deter a stronger neighbour |
| Phone call | Changes trust, resolve and relations before a crisis | Bank goodwill you can spend later |
| Wiretap, intel | Shows private intent and what advisers recommended | Find who is bluffing |

**Ways to play** (the game should let all of these work, and each should have a counter):

- **Honest broker:** keep every promise. Slow, but deals hold and trust compounds.
- **Bluffer:** promise freely to buy time. Strong early, collapses when notes are compared.
- **Deterrence:** alliances and army so rivals' advisers rank war last. Costs economy.
- **Interdependence:** trade with everyone so war is costly for all. Weak against a leader who ignores advice.
- **Divide:** use Wiretap and selective truth to split two rivals. High risk to trust.

**How the AI picks in rollouts.** For the needle, leaders choose with probability proportional to `exp((score + personality_bias) / temperature)`. Personality bias is per leader: Ostrava +2 on escalation, Nordhaven +2 on waiting, Kessaria +1 on whoever paid most recently, Zarnia +2 against anyone who broke a promise.

**Worked example, One Berth, Ostrava at its deadline.** Advisers score `wait` at +4 if Ostrava believes it gets the berth (belief 0.7) and `blockade` at +1. You are caught double-promising: trust drops, belief falls to 0.3, `wait` drops to −1 and `blockade` now leads. If the blockade is already public, backing down costs a further 3, so only a concrete offer (half a day now, or confirmed tugs) brings `wait` back on top. Interrupting before it is public removes that 3.

**Score at the end**

- **President:** months in power, peace months, change in `gdp` and `stability`, promises kept.
- **Mediator:** wars avoided and average trust across leaders.
- **Diplomat:** deals your president accepted.

## 7. Two "what if" tools, one mechanism

Both fork the world from a saved snapshot. This works because the engine is pure and seeded.

- **War-odds needle.** Hundreds of rollouts in code, six months ahead, with and without your deal, using the same seeds on both sides. Leaders in rollouts follow their advisers plus a personality bias, so no model calls are needed. It is a forecast: the real leaders can defy it, and when they do, say so on screen.
- **"What if I'd waited?"** One replay of the crisis with your offer moved earlier or later, run entirely in code. Every leader's original decision is cached. Leaders whose inputs did not change keep theirs; leaders whose inputs changed follow their advisers plus personality bias. Le Chonk only writes the one-line "why". No model call decides anything in a replay, so it is instant and repeats exactly. Output: which nation changed its decision, from what to what, and the payoff line that flipped it.
- **Order:** build the needle first, then the replay on the same fork function. If Layer 3 runs short, the replay is cut before the needle.

## 8. Voice (Voxtral)

- **Hold to talk** in the browser. Reliable in a noisy room.
- **Live transcript** of both sides.
- **Interrupting is a move.** Pressing talk while a leader speaks cuts the audio and sends `interrupted: true`.
- **Hesitation is a signal.** The gap between the leader finishing and you starting is sent as `hesitation_ms`.
- **One distinct voice per leader**, with an emotion tag that tracks the escalation level.
- **Wiretap:** the latest messages between two AI leaders, played as a two-voice conversation. Can be rendered ahead of time.
- **Fast first audio.** Latency is the top demo risk, because the interrupt moment needs the leader to start speaking quickly. Calls use `reasoning_effort="low"`, replies of two sentences at most, and streamed speech. Each leader's opening line in a crisis is written and rendered ahead of time.
- **Typed fallback.** A text box posts to the same call endpoint. Emergency use only, if the room or the API fails.
- **Cached for the demo seed:** opening lines, Wiretap audio and the AI-to-AI turns. Replies to what the judge says are always live.

Checked against the Voxtral 3 docs on the day:

- Speech to text: realtime WebSocket, model `voxtral-mini-transcribe-realtime-3`, 16-bit mono PCM, proxied through our backend so the key never reaches the browser. Simpler fallback: upload the clip to `/v1/audio/transcriptions` with `voxtral-mini-transcribe-3`. The docs do not list accepted upload formats, so test the browser's recording format and encode WAV if it fails.
- Text to speech: `voxtral-mini-tts-3-0` on `/v1/audio/speech`. Emotion goes inline as `[emotion=angry]`. Use only supported values, as a schema enum: `angry, anxious, assertive, calm, confident, critical, determined, disappointed, frustrated, proud, sarcastic, skeptical, tense, urgent, warm` (34 exist in total). Unknown tags are ignored without an error. Pace: `[pace=slow]` or `[pace=fast]`. Set `stream: true` to play audio as it arrives. Style instructions are not available.
- Mistral Large 4 takes text and images, not audio, so it only ever sees transcripts.
- Rate limits are per workspace and shared by all its keys.

## 9. The world

Five fictional nations (no real countries or leaders):

| Nation | System | Strength | Weakness | Leader |
|---|---|---|---|---|
| **Valdoria** (default seat) | Parliamentary democracy | Food exporter, rich | Small army, election in month 6 | The player, or an AI moderate |
| **Ostrava** | Military junta | Oil, large army | Imports food, unstable | Proud, expansionist, bluffs |
| **Kessaria** | Constitutional monarchy | Controls the trade strait and port | Small economy | Opportunist, plays both sides |
| **Nordhaven** | Technocracy | Chips, money, tugs | Weak army, needs oil | Cold, data-driven, hates instability |
| **Zarnia** | One-party state | Huge army, cheap labour | Poor, food shortages | Paranoid, ideological, holds grudges |

Per-nation stats: `gdp, oil, food, chips, army, stability (0–100), approval (0–100), territory`.
Relations: every pair has a score −100…+100.
Beliefs: each leader holds `trust_in_player (0–1)` and `resolve_of_player (0–1)`.

## 10. Engine (pure code — the maths)

- `step(state, actions, seed) -> new_state` — **pure and deterministic**. No hidden globals. This is what makes forking and replay possible.
- `advise(state, nation) -> [{action, score}]` — ranked legal actions from payoffs and beliefs.
- `snapshot()` / `fork(snapshot, changes, seed)` — used by both the needle and the replay.
- Monthly rules (keep simple, tune for drama): trade deals move resources and raise relations; tariffs cut GDP on both sides; shortages cut stability; war compares army × morale + random; elections replace a democratic leader below 45 approval; a junta below 25 stability gets a coup.
- Strategy actions (Layer 0, only these five): `set_tariff(target, pct)`, `propose_trade(target, give, get)`, `propose_alliance(target)`, `declare_war(target)`, `make_peace(target)`.
- Crisis actions come from the crisis file (for One Berth: `dock`, `wait`, `blockade`, `mobilise`, `assign_berth`, `split_day`, `close_port`, `send_tugs`).

## 11. Agents (Le Chonk)

- **One leader per AI nation**, model `mistral-large-4`. Each turn it receives its nation's state, relations, recent news, messages received, its personality card and the advisers' ranking. It returns JSON:

```json
{
  "public_statement": "We seek only peace and fair trade.",
  "private_intent": "Stall Valdoria until our mobilisation completes in month 4.",
  "actions": [{"type": "set_tariff", "target": "valdoria", "pct": 25}],
  "followed_advice": false,
  "reason": "Backing down after the general's speech would look weak.",
  "messages": [{"to": "kessaria", "text": "Close the strait to Valdorian grain and I will share oil."}]
}
```

- **Phone calls:** the same persona in conversation, with `reasoning_effort="low"` and replies of two sentences at most. Input: your transcript, `interrupted`, `hesitation_ms`, world state. Output: reply text, one emotion from the enum, structured promises, any agreed actions, and updated `trust_in_player` and `resolve_of_player`.
- **Historian:** one call at the end summarising the session.
- **Personality cards** live in `agents/personas/*.md`.
- **Until `advise()` lands (12:45),** Abi uses a mocked advisers' ranking so prompt work is not blocked.
- **Managed Agents:** each nation as an agent with its own session memory, only if a 20-minute test passes. Fallback: plain chat completions with the history we keep.

## 12. Screens and UI (must feel like a game, not a dashboard)

Dark situation-room look, bold nation colours, big readable numbers, everything animated. One screen, no page changes during play.

- **World map (centre).** Five stylised regions. Green lines for trade, blue for alliance, red pulsing for a war front. Event icons pop on the map.
- **Nation cards (left).** Leader portrait and name, system, live meters. Low stability shakes the card and stamps "PROTESTS".
- **Phone (bottom right).** Contacts are the other leaders. Hold to talk. Live transcript. Incoming calls ring and flash.
- **Crisis bar (top).** Appears in crisis mode: the 24-hour clock and each nation's deadline marker.
- **Needle (top right).** War odds in six months, animating from old to new with a one-line caption.
- **Intel drawer.** Public statement versus private intent; advisers' recommendation versus what the leader chose; Wiretap button.
- **Replay panel.** After a crisis: a slider for when your offer arrived, and who changed their decision.
- **News ticker (bottom).** One headline per event, written by the agents.
- **End screen.** Outcome, key moments, historian's verdict.

## 13. Where each Mistral product is used (say this to the judges)

- **Le Chonk (Mistral Large 4):** every leader's decisions and private intents, phone conversations, turning speech into promises, the historian.
- **Voxtral:** live transcription of the player, a voice for every leader with emotion tags, Wiretap.
- **Mistral Agents (bonus):** one Managed Agent per nation, if the 20-minute test passes. Do not claim it in the pitch otherwise.
- **Mistral Workflows (bonus, optional):** the headless batch that plays AI-only worlds for the stats slide, which is optional. Start it as a plain script; wrap it in a Workflow only if there is time. Run it on a separate account.
- **Vibe:** say honestly which parts Vibe built. Everyone has Vibe Pro from the event. Vibe takes small, self-contained tasks (see §16).

## 14. API contract (everyone codes against this)

Backend: Python + FastAPI. Frontend: one web page polling the backend. Om puts one example response per endpoint on `main` first, so nobody waits on the engine.

- `POST /start {seed, seat:{role, nation}}` → new game with a fixed seed.
- `GET  /state` → full world state, plus `turn`, `events`, `news`, `crisis` (`id, clock, deadlines, public_commitments`) and `last_futures`.
- `POST /turn` → advance one month, or one tick in crisis mode.
- `POST /crisis/start {id}` → enter crisis mode.
- `POST /call {to, audio | text, interrupted, hesitation_ms}` → `{transcript, reply_text, reply_audio_url, emotion, promises, actions}`.
- `POST /futures {snapshot_id}` → `{before:{war_p}, after:{war_p}, caption}`.
- `POST /replay {shift_ticks}` → `{changed:[{nation, was, now, why}]}`. Code only; lives in `/replay` (Tamim) and calls Om's `fork()` and `advise()`.
- `GET  /wiretap?a=ostrava&b=kessaria` → `{lines:[{speaker, text, audio_url}]}`.
- `GET  /leaders/{id}` → `{public_statement, private_intent, advice, chosen, reason, persona}`.

State is the single source of truth. The frontend never computes game logic.

## 15. Build plan — layers (each layer is a complete demo on its own)

| Layer | Done by | What exists | Pass test |
|---|---|---|---|
| **0 — World** | 12:45 | Five nations, pure `step()`, `advise()`, leaders with public/private output, terminal log | 20 turns of readable drama, including one leader defying advice |
| **1 — Playable** | 14:15 | Map, cards, ticker, intel; president seat; voice calls that change the world; Wiretap | Everyone plays three minutes by voice. **Record backup video.** |
| **2 — Red Phone** | 15:15 | One Berth: crisis clock, deadlines, promises, interruption, hesitation | The double-promise scene plays out and can be interrupted |
| **3 — What if** | 16:00 | Snapshot and fork: needle first, then replay | Needle moves on three rehearsed calls; replay names who flipped, or is cut |
| **4 — More** | if time | Second crisis, mediator seat, diplomat seat, end screen | Each works or is cut |
| Freeze | 16:15 | Polish, demo seed, stats slide | — |
| Video | 17:00 | Record final demo video | Submitted by 17:45 |

Whatever layer is finished at the freeze is what we show. Tamim calls the cuts at each checkpoint.

**Cut first if time is short:** diplomat seat, extra crises, voter blocs, leaderboard, French calls, Workflows wrapper, stats slide, then the replay (before the needle).

## 16. Roles (sized to each person's AI usage)

Each person owns one folder. Requests and coordination go through the Team message board on GitHub (`MASTER_PLAN.md` §8). Tamim is lead coordinator.

| Person | Owns | Delivers | Backup |
|---|---|---|---|
| **Tamim** | Interface (`/web`), replay (`/replay`), integration, cut decisions | 12:00 layout on fake state · 13:45 wired to `/state` · 15:30 crisis bar, needle, intel · 16:00 `/replay` and its panel | Om |
| **Om** | Engine and futures (`/engine`), API | 12:00 example responses on `main` · 12:45 20-turn headless run with `advise()` · 15:00 crisis rules · 15:30 `fork` · 15:45 rollouts and `/futures` | Tamim |
| **Abi** | Leaders (`/agents`), headless batch | 12:00 valid JSON 10/10, parallel-call test · 12:45 leaders act sensibly (on a mocked ranking until `advise()` lands), headlines · 14:15 call prompt with promises · 15:30 historian, replay "why" line, batch script | Ashish |
| **Ashish** | Voice (`/voice`), demo | 12:00 talk-to-reply round trip timed · 13:30 leader voices and `/call` · 14:15 Wiretap, talk button with interruption and hesitation, typed fallback · then crisis-deck data files, script, video, submission | Abi |

- The talk button is a self-contained module from Ashish that Tamim mounts without editing.
- Tamim has the most AI usage, so extra work goes to Tamim first, not to the single-plan seats.
- Protect the single-plan seats: work in one folder and avoid asking the agent to read the whole repo.
- **Quota rule:** when a tool runs out, switch to Vibe in the same folder. Backups are for someone who is stuck or away, not for quota.
- **What Vibe builds:** small, self-contained tasks only, such as data files, persona cards, headlines and tests. Core engine, voice and interface work stays on each person's main tool. Tasks will be tagged "Vibe" in the master plan.

## 17. Five-minute demo script

| Time | Beat |
|---|---|
| 0:00 | "Every call is a move." World already running. "You've seen agent societies with one timeline. We show the one you didn't take." |
| 0:25 | Hand the judge the mic: "You're President of Valdoria." One quick call in the strategy phase; a trade line appears. |
| 1:00 | The storm hits. Crisis clock starts. Ostrava calls, angry. |
| 1:20 | Judge answers. Ostrava starts announcing a blockade; judge interrupts with an offer. |
| 2:10 | Intel: public versus private, advisers versus choice. Wiretap: Ostrava and Kessaria discussing the judge. |
| 2:50 | Deadlines pass. Outcome on the map. Needle: war odds before and after. |
| 3:20 | "What if you'd waited?" Slide the offer later; Kessaria closes the port. |
| 4:00 | Stats from the AI-only worlds, if the batch ran. Otherwise the end screen and historian's verdict. |
| 4:30 | "Le Chonk runs every leader and Voxtral is every voice." Add "each nation is a Mistral Agent" only if that is built. |

## 18. Risks and the first tests

| Risk | Test (before 12:00) | Fallback |
|---|---|---|
| Le Chonk JSON unreliable | 10 calls, validate schema | Retry and repair; fewer action types |
| **Latency (top demo risk)** | Time talk → reply → first audio | Low reasoning effort, two-sentence replies, streamed speech, pre-rendered opening lines |
| Emotion tags make no audible difference | Same line with `angry`, `calm`, `tense` | Different voices carry the temper |
| Browser recording format rejected | Upload one clip | Encode WAV in the page |
| Rate limits during the demo | 8 parallel calls timed | Batch on a separate account, stopped before judging |
| Demo not repeatable | Fixed seed run twice | Same seed and a pause button |
| Room noise or API outage | Try the typed box and the cached scripted lines | Typed fallback, cached demo-seed responses, backup video |
| Managed Agents unavailable | 20-minute test | Plain chat completions |
| Scope | Checkpoints in §15 | Show the last finished layer |

## 19. Repo layout

```
ideas.md            ← this plan
/engine   (Om)
/agents   (Abi)
/web      (Tamim)
/replay   (Tamim)
/voice    (Ashish)
MASTER_PLAN.md    ← tasks, checkpoints, contracts, coordination
MASTER_PROMPT.md  ← what to paste into your coding agent
```

Before every push: `git pull --rebase`. Commit small and often. Keys only in `.env` (gitignored).
