"""A0: the leader tests (MASTER_PLAN.md section 6).   python -m agents.a0_test

1. decide() returns valid leader JSON: 10 sequential calls across the four AI nations, target 10/10.
2. 8 parallel decide() calls: no rate-limit errors, wall time.
3. call_reply() latency on 3 lines (first audio must be fast).
Writes agents/A0_RESULTS.md with a board line to paste.
"""
from __future__ import annotations

import asyncio
import os
import statistics
import time
from pathlib import Path

from . import fixtures, leaders, llm

AI = ["ostrava", "zarnia", "kessaria", "nordhaven"]  # valdoria is the player's seat


async def timed(coro):
    t = time.perf_counter()
    try:
        return await coro, time.perf_counter() - t, None
    except Exception as e:  # noqa: BLE001
        return None, time.perf_counter() - t, f"{type(e).__name__}: {e}"


async def main() -> None:
    if not os.environ.get("MISTRAL_API_KEY"):
        raise SystemExit("Set MISTRAL_API_KEY (source .env).")
    model = llm.MODEL
    print(f"model {model}; decide budget {leaders.DECIDE_BUDGET_S}s, call budget {leaders.CALL_BUDGET_S}s")

    print("1/3 ten sequential decide() calls...")
    ok, times, errs, defied, samples = 0, [], [], 0, []
    for i in range(10):
        n = AI[i % len(AI)]
        out, dt, err = await timed(leaders.decide(fixtures.leader_view(n)))
        times.append(dt)
        if out:
            ok += 1
            defied += not out.followed_advice
            if len(samples) < 4:
                samples.append((n, out))
        else:
            errs.append(f"{n}: {err}")
        print(f"  {n:9s} {dt:5.1f}s {'OK' if out else 'FAIL ' + str(err)[:160]}")
    retries = llm.STATS["retries"]

    print("2/3 eight parallel decide() calls...")
    t0 = time.perf_counter()
    res = await asyncio.gather(*[timed(leaders.decide(fixtures.leader_view(AI[i % len(AI)]))) for i in range(8)])
    wall = time.perf_counter() - t0
    par_ok = sum(1 for r in res if r[0])
    par_errs = [r[2] for r in res if r[2]]
    par_max = max(r[1] for r in res)
    rate_limited = sum(1 for e in par_errs if "429" in e)

    print("3/3 call_reply() latency...")
    crisis = fixtures.state("state.crisis")
    call_lines = [("ostrava", "General, Ostrava gets the berth this morning. You have my word.", False, 600, None),
                  ("ostrava", "Wait, General, before you announce anything, hear my offer.", True, 0, crisis),
                  ("kessaria", "Your Majesty, what would it take to split the day between both ships?", False, 3200, crisis)]
    call_res = []
    for n, said, intr, hes, s in call_lines:
        out, dt, err = await timed(leaders.call_reply(fixtures.call_view(n, said, intr, hes, s)))
        call_res.append((n, said, out, dt, err))
        print(f"  {n:9s} {dt:5.1f}s {(out.emotion + ': ' + out.reply_text) if out else 'FAIL ' + str(err)[:160]}")

    med = statistics.median(times)
    call_ok = [r for r in call_res if r[2]]
    call_med = statistics.median([r[3] for r in call_ok]) if call_ok else float("nan")
    lines = [f"# A0 results ({time.strftime('%H:%M')})", "",
             f"- **Model:** `{model}`, JSON mode, no reasoning. (`mistral-large-4` was 26-72 s per decision: see README.)",
             f"- **Valid leader JSON:** {ok}/10 sequential (retries used: {retries}). Median {med:.1f}s, max {max(times):.1f}s. Defied advice: {defied}/{ok}.",
             f"- **8 parallel calls:** {par_ok}/8 OK, {wall:.1f}s wall (slowest {par_max:.1f}s); rate-limited: {rate_limited}.",
             f"- **call_reply latency:** median {call_med:.1f}s over {len(call_ok)}/3 lines (before TTS).", ""]
    if errs or par_errs:
        lines += ["## Errors", ""] + [f"- {e[:200]}" for e in errs + par_errs] + [""]
    lines += ["## Samples", ""]
    for n, o in samples:
        a = o.actions[0].model_dump(mode="json") if o.actions else "wait"
        lines += [f"**{n}** public: {o.public_statement}  ", f"private: {o.private_intent}  ",
                  f"action: {a}; followed advice: {o.followed_advice}; reason: {o.reason}", ""]
    for n, said, o, dt, err in call_res:
        if o:
            lines += [f"**call {n}** ({dt:.1f}s) player: \"{said}\" → [{o.emotion}] {o.reply_text}  "
                      f"beliefs {o.belief_updates.model_dump()}  promises {[p.model_dump() for p in o.promises]}", ""]
    verdict = "PASS" if ok == 10 and par_ok == 8 else "CHECK"
    board = (f"A0 {verdict}: `{model}` JSON {ok}/10, median {med:.1f}s; 8 parallel {par_ok}/8 in {wall:.1f}s "
             f"({rate_limited} rate-limited); call_reply median {call_med:.1f}s.")
    lines += ["## Board line", "", board, ""]
    Path(__file__).with_name("A0_RESULTS.md").write_text("\n".join(lines))
    print("\n" + board + "\n\nWrote agents/A0_RESULTS.md")
    await llm.client().aclose()


if __name__ == "__main__":
    asyncio.run(main())
