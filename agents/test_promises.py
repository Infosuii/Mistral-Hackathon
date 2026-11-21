"""Done check for Ashish's NEED (promises must use the engine's vocabulary):
    python -m agents.test_promises

Starts One Berth in the real engine, sends player lines through interpret() and
GAME.apply_call(), then ticks past compare-notes (advisers decide, no model calls).
Passes if every recorded promise uses what="berth" (or a crisis action) with a slot from
morning/afternoon/evening/all_day, the double promise is caught when Ostrava and Zarnia
compare notes, and an honest split (morning / evening) is not.
"""
import asyncio
import os

from engine.game import Game

from . import fixtures, leaders, llm

DOUBLE = [("ostrava", "I promise you the berth for the whole day, General."),
          ("zarnia", "Chairman, the berth is yours all day. You have my word.")]
HONEST = [("ostrava", "General, the berth is yours in the morning, and Zarnia gets it in the evening."),
          ("zarnia", "Chairman, you get the berth this evening; Ostrava unloads in the morning.")]


async def run(lines) -> tuple[list, list[str]]:
    g = Game(seed=7, use_agents=False)
    g.start_crisis("one_berth")
    for to, said in lines:
        view = fixtures.call_view(to, said, s=g.state)
        spoken = await leaders.speak_fast(view)
        out = await leaders.interpret(view, spoken["reply_text"])
        g.apply_call(to, out)
        print(f"  {to:8s} player: {said}\n           [{spoken['emotion']}] {spoken['reply_text']}\n"
              f"           promises {[p.model_dump() for p in out.promises]}")
    while g.state.phase == "crisis" and g.state.crisis.tick < 6:
        await g.turn()
    promises = list(g.state.crisis.promises) if g.state.crisis else []
    return promises, [n.text for n in g.state.news]


async def main() -> None:
    if not os.environ.get("MISTRAL_API_KEY"):
        raise SystemExit("Set MISTRAL_API_KEY (source .env).")
    print("double promise:")
    p1, news1 = await run(DOUBLE)
    print("honest split:")
    p2, news2 = await run(HONEST)
    slots = {"morning", "afternoon", "evening", "all_day"}
    vocab_ok = all(p.what == "berth" and p.when in slots for p in p1 + p2) and len(p1) >= 2 and len(p2) >= 2
    caught = any("compare notes: you promised" in t for t in news1)
    clean = not any("compare notes: you promised" in t for t in news2)
    print(f"\ncompare-notes news, double: {[t for t in news1 if 'compare notes' in t]}")
    print(f"compare-notes news, honest: {[t for t in news2 if 'compare notes' in t]}")
    print(f"vocabulary {vocab_ok}, double caught {caught}, honest clean {clean}; answered by {llm.STATS['by_model']}")
    print("PASS" if vocab_ok and caught and clean else "FAIL")
    await llm.client().aclose()


if __name__ == "__main__":
    asyncio.run(main())
