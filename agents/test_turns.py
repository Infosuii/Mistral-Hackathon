"""Done check for A1:  python -m agents.test_turns [turns]

Runs the real engine (engine.game.Game, demo seed 7) for 20 months with the live
decide(). Passes if no leader fell back to its advisers (decide() never failed or
timed out) and at least one leader defied advice.
Prints one line per leader per month and writes agents/A1_RESULTS.md.
"""
import asyncio
import sys
import time
from pathlib import Path

from engine.game import Game

from . import leaders, llm


async def main(turns: int = 20) -> None:
    calls: list[float] = []

    async def timed_decide(view):
        t = time.perf_counter()
        try:
            return await leaders.decide(view)
        finally:
            calls.append(time.perf_counter() - t)

    g = Game(seed=7, decide=timed_decide)
    lines, fallbacks, defied, acted = [], 0, 0, 0
    t0 = time.perf_counter()
    for _ in range(turns):
        t = time.perf_counter()
        await g.turn()
        dt = time.perf_counter() - t
        s = g.state
        lines.append(f"## Month {s.turn} ({dt:.1f}s)")
        for n, d in g.leaders.items():
            a = d.chosen[0] if d.chosen else None
            act = f"{a.type} {a.target or ''}".strip() if a else "wait"
            top = d.advice[0].action if d.advice else None
            top_s = f"{top.type} {top.target or ''}".strip() if top else "-"
            fb = d.reason.startswith("Fell back")
            fallbacks += fb
            pick = next((x.score for x in d.advice if (x.action == a) or (a is None and x.action.type == "wait")), None)
            followed = pick is None or not d.advice or pick >= d.advice[0].score - 0.05
            defied += (not followed) and not fb
            acted += a is not None
            lines.append(f"- **{n}** {act}{'' if followed else f'  (advisers: {top_s})'}"
                         f"{'  FALLBACK' if fb else ''}  \n  says: {d.public_statement}  \n"
                         f"  means: {d.private_intent}  \n  why: {d.reason}")
        lines.append(f"- news: {' | '.join(x.text for x in s.news if x.turn == s.turn) or '-'}")
        print("\n".join(lines[-(len(g.leaders) * 1 + 2):]).replace("  \n", "\n   "), flush=True)
    wall = time.perf_counter() - t0
    calls.sort()
    ok = fallbacks == 0 and defied > 0
    head = [f"# A1 results ({time.strftime('%H:%M')}): {'PASS' if ok else 'FAIL'}", "",
            f"- {turns} months, seed 7, model `{llm.MODEL}`, {len(calls)} decide() calls, {wall:.0f}s wall "
            f"({wall / turns:.1f}s per month with leaders in parallel).",
            f"- decide() median {calls[len(calls) // 2]:.1f}s, max {calls[-1]:.1f}s; fallbacks to advisers: {fallbacks}; answered by {llm.STATS['by_model']}.",
            f"- Leaders defied advice {defied} times; took an action (not wait) {acted} times.", ""]
    Path(__file__).with_name("A1_RESULTS.md").write_text("\n".join(head + lines) + "\n")
    print("\n".join(head))
    print("PASS" if ok else "FAIL")
    await llm.client().aclose()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 20))
