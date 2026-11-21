"""Headless run: every nation, the seat included, takes the top of advise().

    python -m engine.run --seed 7 --turns 20

The same seed prints byte-identical output. The last line is a hash of the final state.
"""

from __future__ import annotations

import argparse
import hashlib

from contracts.models import NATION_IDS, Seat
from engine.core import advise, new_game, step


def describe(a) -> str:
    if a.type == "wait":
        return "wait"
    extra = f" {a.params['pct']}%" if a.type == "set_tariff" else ""
    return f"{a.type}{extra} -> {a.target}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--turns", type=int, default=20)
    args = ap.parse_args()

    state = new_game(args.seed, Seat(role="president", nation="valdoria"))
    for _ in range(args.turns):
        actions = [advise(state, n)[0].action for n in NATION_IDS]
        state = step(state, actions, args.seed)
        print(f"== month {state.turn}")
        print("   " + "; ".join(f"{a.by}: {describe(a)}" for a in actions))
        for item in state.news:
            if item.turn == state.turn:
                print(f"   * {item.text}")
        for n in NATION_IDS:
            st = state.nations[n].stats
            flags = " " + ",".join(state.nations[n].status) if state.nations[n].status else ""
            print(f"   {n:9} gdp {st.gdp:5.1f} food {st.food:5.1f} oil {st.oil:5.1f} army {st.army:5.1f} "
                  f"stab {st.stability:5.1f} appr {st.approval:5.1f} prov {st.territory:2d}{flags}")
    digest = hashlib.sha256(state.model_dump_json(by_alias=True).encode()).hexdigest()[:16]
    print(f"final state {digest}")


if __name__ == "__main__":
    main()
