# contracts (Om)

Pydantic models for every shape in `MASTER_PLAN.md` §4, and one example per endpoint in `examples/`.

```bash
pip install -r requirements.txt
python -m contracts.validate        # every example against its model; exits 1 on any failure
```

```python
from contracts.models import State, CallOutput, LeaderOutput
state = State.model_validate(json.load(open("contracts/examples/state.json")))
state.model_dump(mode="json", by_alias=True)   # by_alias=True so `from_` is written as "from"
```

`validate.py` maps each example file to its model and the endpoint or function it belongs to. A new example without a model listed there fails the check.

## What the models enforce

- Unknown fields are rejected, so a misspelled field fails instead of disappearing. The exceptions are `Event` and the crisis file's `scripted` entries, whose extra fields depend on their type.
- `emotion` must be one of the 15 Voxtral tags in §4.6.
- Relation keys must be two different nation ids, sorted and joined with `|`, with scores between -100 and 100.
- `crisis` is set exactly when `phase` is `crisis`.
- When `provinces` is filled, each nation's `stats.territory` equals the number of provinces it owns.
- `POST /call` takes exactly one of `audio` or `text`.

## Filled in where §4 was silent (confirmed by Tamim, 12:14)

| Shape | Choice |
|---|---|
| `state.incoming_call` | `{from, emotion, opening_line, audio_url}`, the same fields as a scripted `incoming_call` |
| `Advice` (`advise()`, `/leaders` `advice`) | `{action: Action, score}`, from `ideas.md` §10 |
| `LeaderView` (`agents.decide` input) | `{nation, state, advice, messages_received: [{from, text}]}` |
| `CallView` (`agents.call_reply` input) | `{nation, transcript, interrupted, hesitation_ms, state, history?}`; `history` is an optional list of `{role: "player" or "leader", text}`, oldest first |
| `/leaders/{id}` `chosen`, `persona` | `chosen` is a list of Actions (like `LeaderOutput.actions`); `persona` is a string |
| `nations.<seat>.beliefs` | `null` for the player's own nation |
| `Action.target` | optional, because crisis actions such as `dock` have no target |
| `links[].type` | `trade`, `alliance` or `war` (the three map overlays) |
| `belief_updates` | deltas between -1 and 1; the engine clamps the result to 0–1 |

## Split phone replies (decided by Tamim, 12:29)

`/call` answers as soon as the spoken reply is ready, with `pending: true`, a `call_id`, and empty `promises` and `actions` (`examples/call.response.pending.json`). When Mistral Large 4 has interpreted the call, `state.last_call` holds `{call_id, to, pending: false, promises, actions, ends_call}` (`examples/state.crisis.json`). The page already polls `/state`, so it shows the promises when they land. Engine side: `GAME.begin_call(to)` returns a `call_id` and sets `last_call` to pending; `GAME.apply_call(to, out, interrupted, hesitation_ms, call_id=...)` fills it in.
