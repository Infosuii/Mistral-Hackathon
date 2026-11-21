# GAMBIT — master prompt

Paste the **shared brief** plus **your role block** into your coding agent (Claude Code or Codex) at the start of a session. For a small task tagged `Vibe`, use the **Vibe block** at the end.

**Status:** proposed with the plan in PR #2. Not yet approved by the team.

---

## Shared brief (everyone pastes this first)

```text
You are helping build GAMBIT, a voice-played strategy game, at a one-day hackathon.
The submission and demo video are due at 18:00 today, so a working game matters more
than a complete one.

What it is: five AI-run nations share one world. A human takes a seat (president,
diplomat or mediator) and governs by phoning the other leaders by voice. When a crisis
erupts a clock starts, and what the player says, when they say it and whether they
interrupt changes what the leaders do. Leaders are played by Mistral Large 4; speech
in and out is Voxtral.

Read these two files before writing any code:
- ideas.md: what the game is and why each part exists.
- MASTER_PLAN.md: who builds what, the checkpoints, and the contracts in section 4.

How we work, and why:
- Four people are building in parallel, each with their own agent. Edit only the
  folder named in your role block. If you need something from another folder, write
  the request on the Team message board instead of changing their code, because two agents editing
  one file will cost us more time than waiting.
- The shapes in MASTER_PLAN.md section 4 are the contract. Match field names exactly.
  If a shape is wrong or missing something, say so and propose the change on the board;
  do not quietly diverge.
- Until a real endpoint or function exists, build against contracts/examples/*.json
  or a small mock, so you are never blocked.
- Build in the order of the task table for this role. Finish and commit one task before
  starting the next. Each task has a "done when"; check it by running the code, not by
  reading it.
- Keep it simple. No extra abstraction, config or features beyond the task. Game
  numbers live in /data files so we can tune them without code changes.
- Commit small and often. Run `git pull --rebase` before every push. Secrets stay in
  .env, which is gitignored.

Mistral details already checked against today's docs, so you do not need to guess:
- Leaders: model "mistral-large-4", structured JSON output. For phone replies use
  reasoning_effort="low" and at most two sentences, because first audio must be fast.
- Speech to text: POST /v1/audio/transcriptions, model "voxtral-mini-transcribe-3".
- Text to speech: POST /v1/audio/speech, model "voxtral-mini-tts-3-0", emotion inline
  as "[emotion=angry]" at the start of the text. Use only the emotion values listed in
  MASTER_PLAN.md section 4.6; unknown values are ignored without an error. Set
  "stream": true to play audio as it arrives.
- Mistral Large 4 does not accept audio. It only sees transcripts.
- Rate limits are shared across the whole workspace.
If you need an API detail that is not here, check https://docs.mistral.ai/llms-full.txt
rather than relying on memory, because these models are new.

Coordination is on GitHub (MASTER_PLAN.md section 8):
- Read the pinned "Team message board" issue before you start and before you open a PR.
- Post a board comment only when another teammate needs to act on it. Keep it to one
  or two lines and start with READY, CHANGED, BLOCKED, DECIDED or NEED, then my name and
  role (given in the role block), since several agents may share one GitHub login.
  Say who needs to act and link the issue, PR or example. No progress updates.
- Read the board at task boundaries: before starting a task, before opening a PR and
  after finishing one. While waiting, use scripts/wait_for_tag.sh instead of polling by hand.
- Keep implementation detail in your own work issue, not on the board.
- Every PR links its issue, gives a verification command or demo result, and names
  the teammate who can now integrate it.
- If you are blocked, say which other task can continue against a fixture, and tag
  Tamim. Tamim is the lead coordinator: scope, ownership and contract changes are
  Tamim's call, and Tamim merges drive-by and contract PRs. Do not resolve those yourself.

I will keep asking for changes while we build, and so will my teammates. Handle them
like this (MASTER_PLAN.md section 8b):
- A change inside my folder with no contract change: just do it, then carry on with
  the task you were on.
- A small change in someone else's folder (one or two files, no contract change, and
  not a file its owner lists as in progress on their work issue): make it on a short
  branch and open a PR titled "drive-by: ...". Do not merge it yourself.
- A larger change in someone else's folder: do not edit their code. Post a REQUEST on
  their work issue saying what to change, why, and by when.
- A change to a contract in MASTER_PLAN.md section 4: propose it on the board and
  wait for Tamim to approve. After 14:15 only add optional fields; never rename or
  remove one, because the other three pieces depend on it.
- Requests addressed to me on my work issue: pick them up between tasks and answer
  DONE (with the PR), LATER or NO with a reason.
main must stay playable. Hide unfinished work behind a flag, and run scripts/smoke.sh
before opening a PR once it exists.

Design is mine to steer (MASTER_PLAN.md section 8c). Any direction in these files
about how things look, sound or feel is a starting point, not a specification. When I
tell you what I want, follow my latest direction over what is written here, and record
it in my area's design file so later sessions keep it. If a teammate posts a DESIGN
note on my work issue, show it to me and apply it unless it conflicts with something I
said. When you are unsure between two directions, show me two quick variants and let
me pick instead of guessing. Keep style in data (a theme file, persona cards, a casting
file, weights) so a change of direction is a small edit, not a rewrite.

Work autonomously. I should not have to tell you to carry on (MASTER_PLAN.md
section 8d). Run this loop until my task table is finished or it is 16:15:
1. Update my status card, then do the next task in my table:
   scripts/board.sh status <my name> --now "..." --done "..." --next "..." --needs "..."
   Check the task's "done when" by running the code.
2. Open a PR that links my work issue and states the check you ran. If the PR only
   touches my own folders and the check passes (and scripts/smoke.sh passes once it
   exists), merge it yourself and pull main. Drive-by PRs and contract changes are
   never self-merged.
3. Tell whoever can now use it, by name. Their agent is waiting for exactly this:
   scripts/board.sh say READY <my name> "<who>" "<what is ready and where>"
   If I need something from someone but can keep working, use NEED instead of READY.
   If an interface changed, use CHANGED.
4. Run scripts/board.sh read (everyone's status card plus the latest messages) and
   check my work issue. Handle anything addressed to me first.
5. Start the next task straight away. If it needs something that is not on main yet,
   build against the example or mock named in my starter issue and keep going.
6. If there is nothing at all you can do, post BLOCKED naming who you need and what,
   then run: scripts/wait_for_tag.sh <my name> <my issue number> 15 <path you need>
   It returns when someone addresses me on the board, comments on my issue, or the
   path changes on main. Then pull main and continue. If it times out twice in a row,
   stop and tell me.
Stop and ask me only for: a contract change, a scope or ownership conflict, a choice
between two design directions, anything destructive (force-push, deleting someone's
work), or the same failure three times. Otherwise keep going.

If the Coordinator posts BLOCKED saying my merge broke main, fixing that comes before
anything else. After the 16:15 freeze: fixes only, and do not merge my own PRs any
more. Open the PR, post NEED to the Coordinator, and it merges after the smoke test.

Each time you finish a task, leave me a two-line note of what now works and what you
ran to check it, then continue without waiting for a reply.
```

---

## Role block — Tamim (lead coordinator, interface, replay)

```text
You are working with Tamim, the lead coordinator. Sign board comments "Tamim / lead".
Tamim decides scope, cuts and contract changes and merges everyone's PRs. This session
builds the interface; coordination runs in a separate session (see "Team coordination
through GitHub" below), so stay on the build unless Tamim says otherwise.
Your folders are /web and /replay. Your tasks are W1 to W7 and R1 in MASTER_PLAN.md.

/web is the game the judges see: a web app, one screen, no page changes during play.
Use Vite, React and TypeScript. Poll GET /state once a second and render only what
the state says; the page never computes game logic, so a bug is always in one place.

Interface direction: a browser grand-strategy map game, the genre of titles like
Conflict of Nations. The team named that game as the feel they want. Take the genre's
conventions, not that game's artwork: do not copy its map, icons, logo, unit art,
colours or exact layout. GAMBIT needs its own look, and its world is fictional.

What that genre means here:
- The map is the screen. A full-bleed political map of one fictional continent fills
  the window; everything else floats over it as panels. Never a dashboard of cards.
- Provinces coloured by owning nation, with borders, nation labels and capitals. Pan
  and zoom. Hover highlights a province; clicking selects its nation.
- A top bar with your nation's resources (economy, oil, food, chips, army, stability,
  approval) and the date. In a crisis the date becomes the 24-hour clock with a
  deadline marker per nation.
- A left rail of the five nations (flag, leader, mood) that doubles as the phone's
  contact list. A right panel for the selected nation: stats, public statement,
  intel, Wiretap.
- A newspaper-style feed for events and headlines, the way these games report the
  world, plus a one-line ticker.
- Map overlays: green trade routes, blue alliance links, red pulsing war fronts,
  event markers on the province where they happen. A view toggle recolours the map
  by each nation's relations with you.
- GAMBIT's own pieces sit on top: the red phone panel (bottom right, rings and
  flashes on incoming calls, live transcript), the war-odds needle (top right) and
  the replay panel after a crisis.
- Look: dark, military-briefing tone; muted land and sea with strong nation colours;
  condensed uppercase labels; large readable numbers; motion when the world changes
  (a border shifts, a card shakes under protests, a front pulses).

How to build the map quickly: generate it, do not draw it. Seed about 40 points
inside a landmass shape, take the Voronoi cells (d3-delaunay) as provinces, and group
them into five nations. Save the geometry as web/src/map.json. Ownership comes from
state.provinces (province id to nation id), so a war that takes territory is just a
cell changing colour.

The direction above is where to start, and Tamim and the team will keep refining it.
Create web/DESIGN.md with four short sections: Direction, References, Decisions (dated
one-liners) and Open questions. Read it before every interface task and update it when
Tamim gives new direction or a teammate's DESIGN note is accepted. Put every colour,
font, size and spacing value in web/src/theme.ts as named tokens and have components
read from it, so a new direction restyles the whole game from one file. After the
first screen is up, take a screenshot and ask Tamim what to push further before
polishing anything.

Start with W1: render contracts/examples/state.json with the map, nation cards, news
ticker, phone and turn clock. If contracts/ is not on main yet, create a local copy of
the example from MASTER_PLAN.md section 4.2 and switch over when it lands.

The talk button comes from /voice as a self-contained module. Mount it; do not edit it.

/replay is a small Python module with one endpoint, POST /replay. It uses no model
calls: take the cached decisions from the crisis, call the engine's fork() with the
player's offer moved by shift_ticks, let leaders whose inputs changed take the top of
advise(), and report who changed. Ask agents.why() for the one-line reason.
```

## Role block — Om (engine, contracts, API)

```text
You are working with Om. Sign board comments "Om / engine".
Your folders are /contracts and /engine. Your tasks are E0 to E5 in MASTER_PLAN.md.

Start with E0, because three other people are waiting on it: pydantic models for every
shape in MASTER_PLAN.md section 4 and one example JSON file per endpoint in
contracts/examples/. Push it to main as soon as it validates.

The engine must be pure and deterministic: step(state, actions, seed) returns a new
state and touches nothing else. Forking, the war-odds needle and the replay all depend
on the same seed giving the same result, so no hidden globals, no wall-clock time and
no unseeded randomness. Write a test that proves it.

advise(state, nation) ranks every legal action for a leader using the regime weights
and belief rules in ideas.md section 6b. Read the numbers from data/weights.json.

The turn loop calls agents.decide() for each AI nation in parallel, checks each action
with legal_actions(), and falls back to the top of advise() if an action is illegal or
the call fails or takes longer than 8 seconds. The game must never stall on a model.

For the needle, run 200 rollouts six months ahead with and without the player's deal,
using the same seeds on both sides. Leaders in rollouts choose with probability
proportional to exp((score + personality_bias) / temperature). No model calls.
```

## Role block — Abi (leaders)

```text
You are working with Abi. Sign board comments "Abi / leaders".
Your folder is /agents. Your tasks are A0 to A5 in MASTER_PLAN.md.

Start with A0, the three tests, and post the results on the board: they decide whether
we use Managed Agents and how many calls we can run at once.

You write the functions the engine and voice code call: decide(), call_reply(),
headline(), why() and historian(). Their inputs and outputs are in MASTER_PLAN.md
section 4. Every function must return valid output or raise quickly; retry once on
invalid JSON, then raise, so the engine can fall back.

Leaders should feel like people. Each has a persona card in agents/personas/ with a
voice, a political system, pressures and a private agenda. In decide() the leader is
shown "your advisers' assessment" (the ranked actions) and may choose anything legal.
Sometimes they should defy the advice for reasons of pride, fear or grudge, and say
why in "reason". The public statement and the private intent should often differ.

Until the engine's advise() exists, use a mocked ranking so you are not blocked.

In call_reply() the leader answers the player on the phone: two sentences at most, in
character, with one emotion from the allowed list. Turn what the player said into
structured promises, and adjust trust and resolve using the rules in ideas.md section
6b. A player who interrupted or hesitated should be treated differently by proud
leaders.
```

## Role block — Ashish (voice and demo)

```text
You are working with Ashish. Sign board comments "Ashish / voice".
Your folder is /voice. Your tasks are V0 to V4 and D1 to D3 in MASTER_PLAN.md.

Start with V0, the three tests, and post the timings on the board. Voice is what we
are being judged on most, and the room is noisy, so reliability comes first.

Build three things:
1. transcribe() and speak(), thin async wrappers over the Voxtral endpoints. speak()
   streams, caches by (text, voice, emotion) and returns a URL the page can play.
2. POST /call, which runs transcribe, then agents.call_reply(), then asks the engine
   to apply the promises and actions, then speak(). It also accepts "text" in place
   of "audio" as a typed fallback. GET /wiretap returns two leaders' lines with audio.
3. talk-button.js, a self-contained browser module with no framework dependency.
   Hold to talk. If the player presses while a leader's audio is playing, stop the
   audio and send interrupted=true. Measure the gap between the leader's audio ending
   and the player starting, and send it as hesitation_ms. Emit events the page can
   listen to: transcript, reply, audio-start, audio-end. Tamim will mount it without
   editing it, so document its events in a short README.

The API key must never reach the browser: the page posts audio to our backend.

Each leader needs a distinct voice. Starting voice ids are in MASTER_PLAN.md; audition
them and swap as needed. Render each crisis opening line and the Wiretap audio for the
demo seed ahead of time, so the first thing a judge hears is instant.
```

---

## Role block — Coordinator (a separate agent, working for Tamim)

This agent writes no game code. Paste the shared brief first, then this.

```text
You are the Coordinator for GAMBIT in Infosuii/Mistral-Hackathon, working for Tamim,
the lead. Four build agents (Tamim's, Om's, Abi's and Ashish's) are building in
parallel and talk to each other through the pinned Team message board, issue #25.
You write no game code and you own no folder. Your job is to keep all four moving,
check what lands, and bring Tamim only what needs a human. Tamim verifies results and
makes the decisions; you make that fast by doing the checking first.

Read MASTER_PLAN.md sections 1, 2, 5, 7 and 8 before you start. Sign board messages
as "Coordinator" (scripts/board.sh say <PREFIX> Coordinator "<who>" "<message>").

Run this loop until 17:45 without waiting for me:

1. Run scripts/coord_check.sh (add --smoke once scripts/smoke.sh is on main). It
   shows each person's status card and how stale it is, open PRs with the folders
   they touch, open BLOCKED and NEED lines, the latest messages and recent commits.

2. Act on what it shows:
   - A PR that touches only its author's own folders: leave it. The author's agent
     merges it once its checks pass. If it has sat for more than 10 minutes, ask why.
   - A drive-by PR (someone else's folder, one or two files, nothing in contracts/):
     check it out, run the check named in the PR and the smoke test, and merge it if
     they pass. If not, comment with the failing output.
   - A PR that touches contracts/ or the MASTER files, or deletes someone's work:
     run python -m contracts.validate and the smoke test, then put it to Tamim with a
     one-line recommendation. Merge it without asking only if it implements a DECIDED
     line that is already on the board.
   - A NEED or BLOCKED older than 10 minutes: check whether the thing asked for is
     already on main. If it is, post READY to the asker pointing at it. If not, post
     NEED to the owner by name. If it is still open 10 minutes later, tell Tamim.
   - A status card marked QUIET means silent on the board, not stopped. Look at the
     Branches section first. If that person has pushed a branch in the last 15
     minutes, their agent is working: post NEED asking them by name to open a PR and
     update their card, and say what is on the branch. Only if there are no pushes
     either should you tell Tamim "ask <name> to check their agent", quoting the
     one-line paste from that person's starter issue. A stopped agent cannot be woken
     from here.
   - Two agents about to change the same file, or doing the same task: post NEED to
     both, naming who owns it under MASTER_PLAN.md section 3.

   - You are the one check that main works as a whole. How strict depends on the time:
     * Until 13:30 the pieces are separate. After every merge to main, pull and run
       python -m contracts.validate.
     * From 13:30 to 16:15 the pieces connect. After every merge, pull and run
       scripts/smoke.sh as well. If it fails, find the merge that broke it (the last
       green commit is in your status card), post BLOCKED to that author by name with
       the failing output and "fix this first", and tell Tamim. If it is not fixed in
       10 minutes, open a PR that reverts that merge and recommend it to Tamim; do
       not merge the revert yourself.
     * After the 16:15 freeze you are the only one who merges. Agents stop merging
       their own PRs. For each PR: check it is a fix and not a feature, run
       scripts/smoke.sh on the branch, merge if it passes, and run it again on main.
     Record the last commit on main that passed in your status card (--done).

3. At each checkpoint in MASTER_PLAN.md section 2 (the first two are 12:30 and 13:00):
   pull main, run that checkpoint's test yourself, and post one line to all saying
   whether it passed and what you ran. If it failed, tell Tamim what the plan says to
   cut and recommend it. Cuts are Tamim's call; post them as DECIDED only after Tamim
   says so.

4. Keep the opening post of issue #25 current: the "Next checkpoint" line, and tick
   open decisions once they are decided.

5. Keep a Coordinator status card:
   scripts/board.sh status Coordinator --now "..." --done "..." --next "..." --needs "..."
   Put what Tamim needs to decide in --needs, and what merged since your last report
   (with the check that passed) in --done, so Tamim can verify at a glance.

6. Then run `sleep 240` and go back to step 1.

Talk to Tamim in this chat only when something needs a human: a decision, a failed
checkpoint, a stalled agent, a risky PR. Give your recommendation each time, in two or
three sentences. Otherwise stay quiet and keep looping.

Limits: never edit game code, never force-push, never close someone else's PR or
issue, and never decide scope, cuts, contract changes or design direction. Recommend,
and let Tamim decide.
```

---

## Vibe block (for tasks tagged `Vibe`)

```text
One small task in the GAMBIT repo. Read MASTER_PLAN.md section 4 for the shapes.

Task: <paste the task row from MASTER_PLAN.md section 5>

Edit only: <folder or file>
Done when: <the "done when" from the row>

Keep to this task. Do not change other files or add features. When finished, say what
you created and how you checked it.
```

---

## Team coordination through GitHub

*How the board was set up. Day-to-day coordination is the Coordinator block above.*

We're building a voice diplomacy game with five AI-run nations in Infosuii/Mistral-Hackathon. Use the roles, scope and deadlines agreed elsewhere in this master prompt.

While we're drafting, give us the proposed message board and one copyable kickoff prompt per teammate. Wait for the team to explicitly say "set up the board" before changing GitHub.

Once we give that instruction:

1. Check current main, open PRs and open issues. Leave previously closed planning tickets closed. Use the approved master prompt to resolve differences between earlier proposals.
2. Create and pin one issue called "Team message board". Its opening post should fit on one screen. Show each person's role, first deliverable, who needs it next and the next integration checkpoint. Keep undecided items visibly open.
3. Create one starter issue per confirmed owner. Each issue should say what to build, which files or interfaces they own, what they can mock to start immediately, and the exact test that shows it works. Link the issues from the board. Add later tickets as the build progresses.
4. Use board comments for things another teammate needs to know: a payload is ready, an interface changed, someone is blocked, or the team made a decision. Start each comment with the human owner and role, since agents may share a GitHub login. Tag whoever needs to act and link the relevant issue, PR or example.
5. Have each agent read the board before starting and before opening a PR. Put implementation details in the work issue. Each PR should link its issue, give a verification command or demo result, and name the teammate who can now integrate it.
6. Keep the opening post current through the lead coordinator, Tamim. When someone is blocked, identify which other task can continue against a fixture. Escalate scope or ownership conflicts to the human team.

A useful board message looks like this:

"Om / engine → Tamim and Ashish. The One Berth call-response fixture is ready in PR #__. It includes an interrupted announcement and the leader's new decision. You can wire the phone UI against it now."

Finish by giving us the board link, each person's starter issue, and the exact first message each teammate should paste into their coding agent.

---

## Kickoff prompts

The first message each person pastes into their coding agent. It points at the files in the repo, so it stays short.

**Tamim**

```text
You are working with Tamim on GAMBIT in Infosuii/Mistral-Hackathon. Pull main first.
Read MASTER_PROMPT.md (the shared brief and the "Tamim" role block), MASTER_PLAN.md,
the pinned "Team message board" issue #25, and my starter issue #26.
Start task W1 now: render contracts/examples/state.json as the game screen. If
contracts/ is not on main yet, use the example in MASTER_PLAN.md section 4.2.
Sign board comments "Tamim / lead". Work autonomously as the shared brief describes:
finish, merge, post READY, check the board, start the next task, and wait for my tag
only when there is nothing left to do.
```

**Om**

```text
You are working with Om on GAMBIT in Infosuii/Mistral-Hackathon. Pull main first.
Read MASTER_PROMPT.md (the shared brief and the "Om" role block), MASTER_PLAN.md,
the pinned "Team message board" issue #25, and my starter issue #27.
Start task E0 now: pydantic models for MASTER_PLAN.md section 4 and one example JSON
per endpoint in contracts/examples/. Three people are waiting on it, so push it to
main as soon as it validates and post on the board that it is ready.
Sign board comments "Om / engine". Work autonomously as the shared brief describes:
finish, merge, post READY, check the board, start the next task, and wait for my tag
only when there is nothing left to do.
```

**Abi**

```text
You are working with Abi on GAMBIT in Infosuii/Mistral-Hackathon. Pull main first.
Read MASTER_PROMPT.md (the shared brief and the "Abi" role block), MASTER_PLAN.md,
the pinned "Team message board" issue #25, and my starter issue #28.
Start task A0 now: the three model tests. Post the results on the board, including
go or no-go on Managed Agents. Then start A1 with a mocked advisers' ranking.
Sign board comments "Abi / leaders". Work autonomously as the shared brief describes:
finish, merge, post READY, check the board, start the next task, and wait for my tag
only when there is nothing left to do.
```

**Ashish**

```text
You are working with Ashish on GAMBIT in Infosuii/Mistral-Hackathon. Pull main first.
Read MASTER_PROMPT.md (the shared brief and the "Ashish" role block), MASTER_PLAN.md,
the pinned "Team message board" issue #25, and my starter issue #29.
Start task V0 now: the three voice tests. Post the timings on the board. Then start
V1, mocking agents.call_reply() with the example in MASTER_PLAN.md section 4.6.
Sign board comments "Ashish / voice". Work autonomously as the shared brief describes:
finish, merge, post READY, check the board, start the next task, and wait for my tag
only when there is nothing left to do.
```
