"""Done check for A3 and A4:  python -m agents.test_talk

wiretap(): two leaders discuss the player (four lines, both speakers, emotions in the enum).
why(): one line for the replay. historian(): one paragraph. headline(): one headline.
Passes if each returns real model text rather than its template fallback.
"""
import asyncio
import os
import time

from contracts.models import Emotion

from . import fixtures, leaders, llm

EMOTIONS = set(Emotion.__args__)  # type: ignore[attr-defined]


async def timed(coro):
    t = time.perf_counter()
    out = await coro
    return out, time.perf_counter() - t


async def main() -> None:
    if not os.environ.get("MISTRAL_API_KEY"):
        raise SystemExit("Set MISTRAL_API_KEY (source .env).")
    crisis = fixtures.state("state.crisis")
    (lines, t_w), (why, t_y), (hist, t_h), (head, t_l) = await asyncio.gather(
        timed(leaders.wiretap("ostrava", "zarnia", state=crisis)),
        timed(leaders.why({"nation": "kessaria", "was": "split_day", "now": "close_port",
                           "inputs": {"player_offer_tick": 7, "was_tick": 4, "ostrava_blockade_public": True,
                                      "zarnia_mobilised": True}})),
        timed(leaders.historian([
            {"turn": 1, "text": "Valdoria signs a grain deal with Nordhaven"},
            {"turn": 3, "text": "Player promises the One Berth to Ostrava all day"},
            {"turn": 3, "text": "Player promises the same berth to Zarnia for the morning"},
            {"turn": 3, "text": "Ostrava and Zarnia compare notes; the double promise is exposed"},
            {"turn": 3, "text": "Ostrava announces a blockade of the strait; the player interrupts with half a day"},
            {"turn": 4, "text": "Nordhaven's tugs open a second berth; both ships dock; no war"},
            {"turn": 6, "text": "Valdoria's election: the president is re-elected with 51%"}])),
        timed(leaders.headline({"turn": 3, "type": "harvest_failure", "nation": "zarnia"})))
    print(f"wiretap ({t_w:.1f}s):")
    for ln in lines:
        print(f"  {ln['speaker']:8s} [{ln['emotion']}] {ln['text']}")
    print(f"why ({t_y:.1f}s): {why}")
    print(f"historian ({t_h:.1f}s): {hist}")
    print(f"headline ({t_l:.1f}s): {head}")
    ok_w = len(lines) == 4 and {l["speaker"] for l in lines} == {"ostrava", "zarnia"} \
        and all(l["emotion"] in EMOTIONS for l in lines)
    ok_y = not why.endswith("to close_port.") and len(why.split()) <= 30
    ok_h = not hist.startswith("History records a short") and len(hist.split()) >= 50
    ok_l = head != "Harvest Failure in Zarnia"
    print(f"\nwiretap {ok_w}, why {ok_y}, historian {ok_h}, headline {ok_l}; answered by {llm.STATS['by_model']}")
    print("PASS" if ok_w and ok_y and ok_h and ok_l else "FAIL")
    await llm.client().aclose()


if __name__ == "__main__":
    asyncio.run(main())
