# Crisis files

One JSON file per crisis, named by its id. Only One Berth is offered unless the backend runs with `GAMBIT_EXTRA_CRISES=1`; then `state.available_crises` lists every file here that loads, and `/crisis/start` accepts only those (DECIDED 13:12).

Each file is named by its id (`one_berth.json` loads as `POST /crisis/start {"id": "one_berth"}`). The shape is `CrisisFile` in `contracts/models.py`, §4.8 of the plan. A new file needs no code changes.

```jsonc
{
  "id": "border_shots", "title": "Border Shots", "ticks_total": 12,
  "intro_news": "Shots across the Zarnia–Kessaria border.",
  "deadlines": {"zarnia": 6, "kessaria": 8, "valdoria": 10, "ostrava": 10, "nordhaven": 10},
  "actions":   {"zarnia": ["mobilise", "stand_down"], "kessaria": ["mobilise", "apologise"], "...": []},
  "rules": {
    "public_backdown_cost": {"junta": 3, "democracy": 2, "one_party": 2, "monarchy": 1, "technocracy": 1},
    "payoffs": {                       // how each leader's advisers score its options
      "zarnia": {"mobilise": {"base": 1, "low_resolve": 3}, "stand_down": {"base": 0}}
    },
    "outcomes": [                      // every rule whose "when" matches the decisions fires
      {"when": {"zarnia": "mobilise", "kessaria": "mobilise"},
       "effects": {"war": ["kessaria", "zarnia"], "news": "The border war begins."}},
      {"when": {"zarnia": "stand_down"},
       "effects": {"relations": {"kessaria|zarnia": 10}, "stats": {"zarnia": {"stability": -3}}}}
    ]
  },
  "scripted": [
    {"tick": 1, "type": "incoming_call", "from": "zarnia", "emotion": "tense",
     "opening_line": "Kessaria fired first.", "announces": "mobilise"},
    {"tick": 5, "type": "compare_notes", "between": ["zarnia", "kessaria"]},
    {"tick": 6, "type": "forecast", "text": "Satellites show troops massing."}
  ]
}
```

**Payoffs.** An option's score is `base + low_resolve × (1 − resolve_of_player) + promise_bonus × trust` for each live player promise whose `what` is that option, minus `public_backdown_cost[system]` if the leader is publicly committed to a different option. A leader at its deadline takes the top score, unless its model (`agents.decide`) or a deal on the phone chose first. The needle samples from these scores.

**Outcomes.** A `when` value is one action or a list of allowed actions, and `{}` always fires. Each matching rule can apply:
- `stats`: per-nation stat changes;
- `relations`: changes keyed by sorted `a|b`;
- `war: [a, b]` or `peace: [a, b]`;
- `news`: a line added to the resolution headline.

**Promises.** A player promise whose `what` names one of the recipient's actions counts as kept if that leader chose it. Kept: trust +`kept_trust` (0.15). Broken: `broken_trust` (−0.2). At `compare_notes`, contradictory promises cut trust ×`contradiction_trust_factor` (0.4).

**Scripted events.** `incoming_call` rings the player. With `announces`, the caller's threat becomes a public commitment on the next tick, unless the player interrupts that call. `compare_notes` catches contradictory promises. `forecast` adds a news line.

`one_berth.json` sets `"resolver": "one_berth"` to keep its own berth logic (who docks, tugs for a second berth). Other files use the rules above.

Check a file with `python -c "import json; from contracts.models import CrisisFile; CrisisFile.model_validate(json.load(open('data/crises/<id>.json')))"`, then start it from the page or with `POST /crisis/start`.
