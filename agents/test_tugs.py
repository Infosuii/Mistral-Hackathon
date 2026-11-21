"""Reviewer's REQUEST on #28 (14:04): the tugs request must always register.
    python -m agents.test_tugs

The Reviewer's exact line to Nordhaven, five times through speak_fast() + interpret():
each must record a promise to nordhaven with what=send_tugs. Then the engine check: that
promise at tick 2 (advisers decide, no model) must make Nordhaven send the tugs by hour 6.
"""
import asyncio
import os

from engine.game import Game

from . import fixtures, leaders, llm

LINE = ("I need your tugs at Port Kessar today to open a second berth. Valdoria pays the full cost of the tow. "
        "Will you send them now?")


async def main() -> None:
    if not os.environ.get("MISTRAL_API_KEY"):
        raise SystemExit("Set MISTRAL_API_KEY (source .env).")
    g = Game(seed=7, use_agents=False)
    g.start_crisis("one_berth")
    await g.turn()  # tick 1
    view = fixtures.call_view("nordhaven", LINE, s=g.state)
    got = 0
    last = None
    for i in range(5):
        spoken = await leaders.speak_fast(view)
        out = await leaders.interpret(view, spoken["reply_text"])
        ok = any(p.to == "nordhaven" and p.what == "send_tugs" for p in out.promises)
        got += ok
        last = out
        print(f"  run {i + 1}: [{spoken['emotion']}] {spoken['reply_text'][:90]}\n         promises {[p.model_dump() for p in out.promises]}")
    g.apply_call("nordhaven", last)
    while g.state.crisis and g.state.crisis.tick < 6:
        await g.turn()
    dec = (g.state.crisis.decisions.get("nordhaven") if g.state.crisis else None)
    print(f"\nsend_tugs recorded {got}/5; engine: Nordhaven decided {dec.action if dec else None} at tick {dec.tick if dec else None}")
    print("PASS" if got == 5 and dec and dec.action == "send_tugs" else "FAIL")
    await llm.client().aclose()


if __name__ == "__main__":
    asyncio.run(main())
