# /agents — leaders (Abi)

The five AI leaders. Personalities live in `personas/*.md` and how often each one overrules its advisers in `personas/temper.json` (edit those, not the code).

## Functions (all async, `from agents import ...`)

| Function | Input | Output | Notes |
|---|---|---|---|
| `decide(view)` | `contracts.LeaderView` | `LeaderOutput` (§4.5) | ~4.5 s; raises `agents.llm.LLMError` within 7.5 s (engine waits 8). The leader picks one of `view.advice` by number, so the action is always one the engine ranked; `followed_advice` is false only when its pick scores below `advice[0]`. A chosen `wait` gives `actions: []` |
| `speak_fast(view)` | `contracts.CallView` | `{reply_text, emotion}` | ~1.2 s on `mistral-large-2512`; `mistral-medium-latest` races it after 2.5 s or on failure, all within 6 s. Two sentences max, emotion from the enum, uses `history` |
| `interpret(view, reply_text)` | `CallView`, the line spoken | `CallOutput` | Large 4 (medium joins after 12 s), ~8 s, run in the background by `/call`. Promises: only those made to the leader on the line; in a crisis `what` is `berth` or that leader's crisis action and a berth's `when` is `morning`/`afternoon`/`evening`/`all_day`, matching `engine/crisis.py`. Also agreed actions (from `engine.core.advise`), belief deltas: model's read of trust and resolve, plus `resolve +0.10` if interrupted, `−0.15` if hesitation > 2.5 s, `trust −0.05` when a proud leader is interrupted (the engine applies the −5 relations itself). `reply_text` is echoed, `emotion` is a placeholder |
| `call_reply(view)` | `CallView` | `CallOutput` | both in one fast call, for when the split path is off |
| `strategize(state, nation)` / `strategize_all(state)` | State | strategy str / `{nation: str}` | DECIDED 13:06/13:07. Large 4 writes each leader's private plan (~20-35 s for all five; medium joins at 30 s, `GAMBIT_STRATEGY_HEDGE_S`); never raises (persona agenda fallback). Call in the background at game start and at crisis start; the engine stores the result per session and passes it back as `LeaderView.private_strategy`. agents keeps no copy. `decide()` follows it only while `GAMBIT_PRIVATE_STRATEGY=1`. For a mediator seat (`nation: null`) all five leaders get one |
| `wiretap(a, b, state=None, messages=None)` | two nation ids | `[{speaker, text, emotion}]`, four lines | never raises. Reads the live `engine.game.GAME` state and private intents when `state` is not given |
| `headline(event)` | event dict | str | never raises (template fallback) |
| `why(change)` | `{nation, was, now, inputs?}` | one line | never raises |
| `historian(log)` | list of events | paragraph | never raises |

## Seats

Prompts describe the player by `state.seat.role` (`SEAT_STYLE` in `leaders.py`): a president commits their nation, a diplomat can be overruled by their president, a mediator has only their word and is tested for neutrality.

## Models (DECIDED 12:29 and 12:43)

decide() is selectable with `GAMBIT_DECIDE_MODEL`: **`mistral-medium-latest` by default and in the demo** (DECIDED 13:07), one request per decision, which keeps 2512's 30 requests/minute for speech. `mistral-large-4` and `mistral-large-2512` are supported. Large 4 for interpret and everything else except the spoken reply; `mistral-large-2512` for the spoken reply. Large 4 cannot turn reasoning off and takes 26-72 s on a leader prompt (`A0_RESULTS.md`), so latency-bound calls are **hedged**: the chosen model starts first and, if it has not answered after `GAMBIT_HEDGE_AFTER_S` (decide: 2.5 s when its model is Large 4, 3.5 s for 2512), `mistral-medium-latest` races it; the first valid answer wins. With decide() on Large 4 the hedge model answers nearly every time; with 2512 it covers 429s. interpret() and historian() are answered by Large 4. `llm.STATS["by_model"]` counts who answered.

Rate limits on this workspace are per model: `mistral-large-2512` 30 requests/minute (keep it for speech only); Large 4 and medium 2,000.

```
GAMBIT_DECIDE_MODEL=mistral-medium-latest  # decide (default; also the hedge model, so one request)
GAMBIT_PRIVATE_STRATEGY=1                  # decide follows LeaderView.private_strategy (off by default)
GAMBIT_LEADER_MODEL=mistral-large-4        # interpret, headline, why, historian, wiretap
GAMBIT_HEDGE_MODEL=mistral-medium-latest   # races Large 4 when it is slow
GAMBIT_HEDGE_AFTER_S=3.5                   # decide's head start (default 2.5 if Large 4)
GAMBIT_FAST_MODEL=mistral-large-2512       # speak_fast, call_reply
GAMBIT_FAST_FALLBACK=mistral-medium-latest  # races 2512 after GAMBIT_SPEAK_HEDGE_S=2.5, one 6 s deadline
GAMBIT_AGENTS_DECIDE_S=7.5   GAMBIT_AGENTS_CALL_S=6   GAMBIT_AGENTS_INTERPRET_S=45
```

## Checks

```
source .venv/bin/activate && set -a && source .env && set +a
python -m agents.test_decide     # issue #28: 10/10 valid, at least one defies advice with two faces
python -m agents.test_turns      # A1: engine turn loop, seed 7, 20 months with live leaders → A1_RESULTS.md
python -m agents.test_phone      # A2: ten lines through speak_fast + interpret
python -m agents.test_talk       # A3/A4: wiretap, why, historian, headline
python -m agents.test_strategy   # strategize_all (mediator: all five), flag on/off, reset on same seed, crisis strategy, mediator call
python -m agents.test_promises   # One Berth: promises in engine vocabulary; double promise caught at compare-notes
python -m agents.a0_test         # A0: 10 sequential, 8 parallel, call latency → A0_RESULTS.md
python -m agents.probe           # raw decide prompt per model: finish_reason and token usage
uv run --no-project --python 3.13 --with "mistralai-agents==1.1.0" --env-file .env python agents/a0_managed.py
```

Inputs come from `contracts/examples/*.json` and `engine.core.advise` (`agents/fixtures.py`).
