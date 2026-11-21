"""End of session: the score (ideas.md §6b, president seat) and a plain verdict for when
the historian is unavailable."""

from __future__ import annotations

from contracts.models import Score, State


def score(start: State, end: State, months_in_power: int, peace_months: int,
          promises_kept: int, promises_broken: int) -> Score:
    seat = end.seat.nation
    a, b = start.nations[seat].stats, end.nations[seat].stats
    return Score(months_in_power=months_in_power, peace_months=peace_months,
                 gdp_change=round(b.gdp - a.gdp, 1), stability_change=round(b.stability - a.stability, 1),
                 promises_kept=promises_kept, promises_broken=promises_broken)


def plain_verdict(state: State, reason: str, sc: Score, leader: str) -> str:
    name = state.nations[state.seat.nation].name
    how = {
        "voted_out": f"was voted out after {sc.months_in_power} months",
        "coup": f"was overthrown after {sc.months_in_power} months",
        "time": f"served the full {sc.months_in_power} months",
        "ended": f"governed for {sc.months_in_power} months",
    }[reason]
    trend = "richer" if sc.gdp_change > 0 else "poorer" if sc.gdp_change < 0 else "no richer"
    word = "promise" if sc.promises_kept == 1 else "promises"
    return (f"{leader} of {name} {how}, {sc.peace_months} of them at peace, and left the country {trend}. "
            f"{sc.promises_kept} {word} kept, {sc.promises_broken} broken.")
