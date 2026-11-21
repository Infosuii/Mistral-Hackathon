"""A0 part 3: Managed Agents go/no-go (20-minute time box).

The Agents SDK needs Python 3.12-3.14 (not 3.15):
  uv run --no-project --python 3.13 --with "mistralai-agents==1.1.0" --env-file .env python agents/a0_managed.py [model]

Pass = an Ostrava agent calls a real tool that reads its received offers, a second turn
in the same session remembers the first, and each turn fits the 8 s turn-loop budget.
Anything else = no-go; we keep plain chat completions with our own history
(agents/leaders.py), which already works.
"""
import asyncio
import sys
import time

OFFERS = {"ostrava": ["Kessaria: close the strait to Valdorian grain in exchange for oil.",
                      "Valdoria: grain at a 10% discount if you stand down your border divisions."]}
BUDGET_S = 8.0
CAP_S = 20 * 60


try:
    from mistralai import agents  # type: ignore
except Exception as _e:  # noqa: BLE001
    agents = None
    IMPORT_ERROR = _e

called: list[str] = []

if agents is not None:
    @agents.tool
    async def get_offers(nation: str) -> list[str]:
        """Offers this nation has received from other leaders this month."""
        called.append(nation)
        return OFFERS.get(nation, [])


async def run(model: str) -> str:
    called.clear()
    agent = agents.Agent(model=model, name=f"ostrava-a0-{model}", tools=[get_offers],
                         instructions="You are General Marek Dravic of Ostrava (nation id: ostrava). "
                                      "Check your offers before deciding. Answer in two sentences.")
    async with agents.local_runtime():
        session = await agent.start_session()
        t = time.perf_counter()
        r1 = await session.run("Which offer will you accept this month, and why?")
        t1 = time.perf_counter() - t
        print(f"[{model}] turn 1 ({t1:.1f}s): {r1.text}\n  tool called: {called}", flush=True)
        t = time.perf_counter()
        r2 = await session.run("Remind me: which offer did you just say you would accept? One sentence.")
        t2 = time.perf_counter() - t
        print(f"[{model}] turn 2 ({t2:.1f}s): {r2.text}", flush=True)
        await session.cancel()
    remembered = any(w in (r2.text or "").lower() for w in ("kessaria", "valdoria", "strait", "grain", "discount"))
    ok = bool(called) and remembered
    fast = max(t1, t2) <= BUDGET_S
    verdict = ("GO" if ok and fast else "NO-GO") + (
        f": tool {'yes' if called else 'no'}, memory {'yes' if remembered else 'no'}, "
        f"turns {t1:.1f}s/{t2:.1f}s vs {BUDGET_S:.0f}s budget")
    return verdict


async def main() -> None:
    models = sys.argv[1:] or ["mistral-large-4", "mistral-large-2512"]
    if agents is None:
        print(f"NO-GO: cannot import mistralai agents SDK ({IMPORT_ERROR})")
        return
    for m in models:
        try:
            v = await asyncio.wait_for(run(m), timeout=CAP_S / len(models))
        except Exception as e:  # noqa: BLE001
            v = f"NO-GO: {type(e).__name__}: {str(e)[:300]}"
        print(f"RESULT {m}: {v}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
