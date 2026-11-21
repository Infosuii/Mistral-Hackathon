"""Tamim's DECIDED 13:51 / Coordinator 13:52: do private strategies land before the first
crisis decision, and do decisions use them? Real server, real leaders, UI pacing.

    GAMBIT_PRIVATE_STRATEGY=1 uvicorn engine.app:app --port 8771 &
    python -m agents.test_strategy_timing [base_url]

/start, then a month every 20 s (the page's clock) for two months, then /crisis/start
and a tick every 7.5 s until the first crisis decision. Polls /leaders/{id} for
private_strategy and reports when each plan landed versus the decisions.
"""
import asyncio
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8771"
AI = ["ostrava", "kessaria", "nordhaven", "zarnia"]


async def plans(c) -> dict[str, str]:
    out = {}
    for n in AI:
        d = (await c.get(f"{BASE}/leaders/{n}")).json()
        if d.get("private_strategy"):
            out[n] = d["private_strategy"]
    return out


async def wait_for(c, t0, label, until_s, seen: dict) -> None:
    """Poll plans every 0.5 s until until_s (relative to t0); record first-seen times."""
    while time.perf_counter() - t0 < until_s:
        now = await plans(c)
        for n, text in now.items():
            if seen.get(n, (None, None))[1] != text:
                seen[n] = (time.perf_counter() - t0, text)
                print(f"  {label}: {n} plan landed at {seen[n][0]:.1f}s")
        await asyncio.sleep(0.5)


async def main() -> None:
    async with httpx.AsyncClient(timeout=60) as c:
        t0 = time.perf_counter()
        (await c.post(f"{BASE}/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}})).raise_for_status()
        game: dict = {}
        print("game start (first month at 20 s):")
        await wait_for(c, t0, "game", 20, game)
        for month in (1, 2):
            (await c.post(f"{BASE}/turn")).raise_for_status()
            used = {n: bool((await c.get(f"{BASE}/leaders/{n}")).json().get("private_strategy")) for n in AI}
            print(f"  month {month} decided at {time.perf_counter() - t0:.1f}s; plan available to {sum(used.values())}/4")
            if month == 1:
                await wait_for(c, t0, "game", 40, game)
        t1 = time.perf_counter()
        (await c.post(f"{BASE}/crisis/start", json={"id": "one_berth"})).raise_for_status()
        crisis: dict = {}
        print("crisis start (a tick every 7.5 s):")
        first = None
        for tick in range(1, 9):
            await wait_for(c, t1, "crisis", tick * 7.5, crisis)
            s = (await c.post(f"{BASE}/turn")).json()
            dec = (s.get("crisis") or {}).get("decisions") or {}
            if dec and first is None:
                first = (time.perf_counter() - t1, dec)
                n = next(iter(dec))
                d = (await c.get(f"{BASE}/leaders/{n}")).json()
                print(f"  first crisis decision at {first[0]:.1f}s (tick {tick}): {n} {dec[n]['action']}")
                print(f"    its plan: {(d.get('private_strategy') or 'NONE')[:160]}")
                print(f"    its intent: {d.get('private_intent')}\n    reason: {d.get('reason')}")
                break
        landed = [t for t, _ in crisis.values()]
        print(f"\nGame plans: {len(game)}/4, last at {max([t for t, _ in game.values()] or [float('nan')]):.1f}s after start "
              f"(month 1 decides at 20 s). Crisis plans: {len(crisis)}/4, last at {max(landed or [float('nan')]):.1f}s after "
              f"crisis start; first crisis decision at {first[0] if first else float('nan'):.1f}s.")


if __name__ == "__main__":
    asyncio.run(main())
