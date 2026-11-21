# /agents — leaders (Abi)

The five AI leaders. Personalities live in `personas/*.md` and how often each one overrules its advisers in `personas/temper.json` (edit those, not the code).

## Functions (all async, `from agents import ...`)

| Function | Input | Output | Notes |
|---|---|---|---|
| `decide(view)` | `contracts.LeaderView` | `LeaderOutput` (§4.5) | ~3 s; raises `agents.llm.LLMError` within 7.5 s. The leader picks one of `view.advice` by number, so the action is always one the engine ranked; `followed_advice` is true exactly when it picked `advice[0]`. A chosen `wait` gives `actions: []` |
| `call_reply(view)` | `contracts.CallView` | `CallOutput` (§4.6) | ~1.4 s; raises within 6 s. Two sentences max, emotion always from the enum, uses `history`. Legal actions from `engine.core.advise`. Belief deltas: model's read of trust and resolve, plus `resolve +0.10` if interrupted, `−0.15` if hesitation > 2.5 s, and `trust −0.05` when a proud leader is interrupted (the engine applies the −5 relations itself) |
| `wiretap(a, b, state=None, messages=None)` | two nation ids | `[{speaker, text, emotion}]`, four lines | never raises. Reads the live `engine.game.GAME` state and private intents when `state` is not given |
| `headline(event)` | event dict | str | never raises (template fallback) |
| `why(change)` | `{nation, was, now, inputs?}` | one line | never raises |
| `historian(log)` | list of events | paragraph | never raises |

## Model

Default `mistral-large-2512` (no reasoning, 2-4 s). `mistral-large-4` cannot turn reasoning off and took 26-72 s per decision (see `A0_RESULTS.md`), which the 8 s turn loop cannot absorb. Switch without code changes:

```
GAMBIT_LEADER_MODEL=mistral-large-4   # decide, headline, why, historian, wiretap
GAMBIT_CALL_MODEL=...                 # call_reply only (defaults to the leader model)
GAMBIT_AGENTS_DECIDE_S=7.5            # decide budget, inside the engine's 8 s
GAMBIT_AGENTS_CALL_S=6                # call_reply budget
```

## Checks

```
source .venv/bin/activate && set -a && source .env && set +a
python -m agents.test_decide     # issue #28: 10/10 valid, at least one defies advice with two faces
python -m agents.a0_test         # A0: 10 sequential, 8 parallel, call_reply latency → A0_RESULTS.md
python -m agents.probe           # raw decide prompt per model: finish_reason and token usage
uv run --no-project --python 3.13 --with "mistralai-agents==1.1.0" --env-file .env python agents/a0_managed.py
```

Inputs come from `contracts/examples/*.json` and `engine.core.advise` (`agents/fixtures.py`).
