---
name: gambit-crisis-card
description: Write a new GAMBIT crisis from one sentence. Creates data/crises/<id>.json in the same shape as one_berth.json and outbreak.json, using only the five existing nations, checks it loads with the CrisisFile model, and says how to play it. Never edits engine code.
user-invocable: true
allowed-tools:
  - read_file
  - write_file
  - bash
---

# GAMBIT: write a crisis card

The player gives you one sentence, for example `/gambit-crisis-card a cyberattack takes
down Nordhaven's chip fabs`. Turn it into one new crisis file that the game can load with
no code changes.

## Hard rules

- Create exactly one new file: `data/crises/<id>.json`. Do not edit any other file. Never
  touch `engine/`, `agents/`, `voice/`, `contracts/`, `web/` or the existing crisis files.
  If the idea seems to need new engine code, simplify the idea instead.
- Use only the five nations: `valdoria`, `ostrava`, `kessaria`, `nordhaven`, `zarnia`.
  Every one of them needs a deadline and a list of actions.
- `<id>` is short snake_case (for example `chip_blackout`), matches the `id` field, and
  must not be an existing file name. Do not set `"resolver"`; that is One Berth's own logic.

## Steps

1. Read `data/crises/README.md`, `data/crises/outbreak.json` and `data/crises/one_berth.json`.
   `outbreak.json` is the template to copy: it uses the generic rules (`payoffs` and
   `outcomes`) that any new file must use. Skim `class CrisisFile` and `class ScriptedEvent`
   in `contracts/models.py`.
2. Write the file. Keep it the size of `outbreak.json`:
   - `id`, `title` (two or three words), `ticks_total: 12`, `intro_news` (one sentence the
     news ticker shows).
   - `deadlines`: one tick per nation, staggered between 5 and 10, the most exposed nation
     first. The player's nation (`valdoria`) usually decides last, at 10.
   - `actions`: two to four snake_case verbs per nation, each one a real choice.
   - `rules`: copy `public_backdown_cost`, `promise_bonus`, `contradiction_trust_factor`,
     `kept_trust` and `broken_trust` from `outbreak.json`. Give every action of every nation
     a `payoffs` entry with a `base` score (and `low_resolve` for actions a leader takes
     when the player looks weak). Write four to seven `outcomes` whose `when` combines two
     nations' choices, with `stats`, `relations` (keys are two nation ids sorted and joined
     by `|`), `war`/`peace` pairs and a `news` line. Make at least one outcome a war and at
     least one a good ending that the player can reach by phoning the right leader.
   - `scripted`: two or three `incoming_call` events (with `from`, `emotion`,
     `opening_line`, and `announces` set to one of the caller's actions when it is a threat),
     one `compare_notes` between two nations the player is likely to promise conflicting
     things to, and one `forecast`. `emotion` must be one of: angry, anxious, assertive,
     calm, confident, critical, determined, disappointed, frustrated, proud, sarcastic,
     skeptical, tense, urgent, warm.
   - Leaders' lines should sound like them: Ostrava's general is proud and threatens first,
     Zarnia's chairman is defensive about bread, Kessaria's queen bargains, Nordhaven's
     chancellor is cool and technical, Valdoria is the player.
3. Check it from the repo root (replace `<id>`):

   ```bash
   python -c "import json; from contracts.models import CrisisFile; CrisisFile.model_validate(json.load(open('data/crises/<id>.json'))); print('CrisisFile OK')"
   GAMBIT_EXTRA_CRISES=1 python -c "from engine.game import available_crises; ids=[c['id'] for c in available_crises()]; print(ids); assert '<id>' in ids"
   ```

   Also check by eye that every nation in `deadlines` appears in `actions`, every action in
   `payoffs` and `outcomes` exists in that nation's `actions`, and every `announces` names
   one of the caller's actions. Fix the file until both commands pass.
4. Tell the player, in a few lines: the crisis in one sentence, who decides when, the
   best and worst ending, and how to try it:

   ```bash
   GAMBIT_EXTRA_CRISES=1 uvicorn engine.app:app --port 8000
   curl -s -X POST localhost:8000/start -H 'content-type: application/json' -d '{"seed": 7, "seat": {"role": "president", "nation": "valdoria"}}' >/dev/null
   curl -s -X POST localhost:8000/crisis/start -H 'content-type: application/json' -d '{"id": "<id>"}' | head -c 300
   ```

   Or, with the gambit MCP server connected, call `gambit_start` then
   `gambit_start_crisis` with `crisis_id` set to `<id>`. Without `GAMBIT_EXTRA_CRISES=1`
   the backend offers One Berth only.
