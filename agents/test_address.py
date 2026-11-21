"""Phone manner check (PR #89, from the mic playtest):  python -m agents.test_address

Ashish's three questions to Nordhaven, as one conversation, for a president and for a
mediator, then one line to each leader as a mediator. Passes if no mediator reply says
"President", no reply reads out a stat value from the state (like "80 points" or "41
stability"), and no reply has invented travel times ("three days", "a long tow").
"""
import asyncio
import os
import re

from contracts.models import Seat

from . import fixtures, leaders, llm

QUESTIONS = ["How are things in Nordhaven?",
             "Could your tugs help at Port Kessar?",
             "Should we trade chips for Ostrava's oil?"]
INVENTED = re.compile(r"\b(\w+[- ])?days? (each way|away|to tow|of towing)|long tow|before the ice|"
                      r"\d+ points|\d+(\.\d+)? stability|probability", re.I)


def seat_state(role: str):
    s = fixtures.state("state.crisis")
    s.seat = Seat(role=role, nation=None if role == "mediator" else "valdoria")
    return s


async def conversation(nation: str, role: str, questions: list[str]) -> list[str]:
    s, history, replies = seat_state(role), [], []
    for q in questions:
        out = await leaders.speak_fast(fixtures.call_view(nation, q, s=s, history=history or None))
        history += [{"role": "player", "text": q}, {"role": "leader", "text": out["reply_text"]}]
        replies.append(out["reply_text"])
    return replies


async def main() -> None:
    if not os.environ.get("MISTRAL_API_KEY"):
        raise SystemExit("Set MISTRAL_API_KEY (source .env).")
    bad = []
    for role in ("president", "mediator"):
        print(f"Nordhaven, {role}:")
        for q, r in zip(QUESTIONS, await conversation("nordhaven", role, QUESTIONS)):
            print(f"  > {q}\n    {r}")
            if INVENTED.search(r) or (role == "mediator" and "president" in r.lower()):
                bad.append((role, r))
    print("Each leader, mediator:")
    for n in ("ostrava", "zarnia", "kessaria", "valdoria"):
        r = (await conversation(n, "mediator", ["I represent no one. What would it take for you to back down?"]))[0]
        print(f"  {n:9s} {r}")
        if INVENTED.search(r) or "president" in r.lower():
            bad.append(("mediator", r))
    print(f"\nflagged: {bad}\nanswered by {llm.STATS['by_model']}")
    print("PASS" if not bad else "FAIL")
    await llm.client().aclose()


if __name__ == "__main__":
    asyncio.run(main())
