"""Test inputs from contracts/examples and the engine, shared by the A0-A4 checks."""
from __future__ import annotations

import json
from pathlib import Path

from contracts.models import Advice, CallView, LeaderView, State

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "contracts" / "examples"


def state(name: str = "state") -> State:
    return State.model_validate(json.loads((EX / f"{name}.json").read_text()))


def advice(s: State, nation: str) -> list[Advice]:
    """engine.advise() when it is importable, else the leader_view example's ranking."""
    try:
        from engine.core import advise
        return advise(s, nation)
    except Exception:  # noqa: BLE001
        lv = json.loads((EX / "leader_view.json").read_text())
        return [Advice.model_validate(dict(a, action=dict(a["action"], by=nation))) for a in lv["advice"]]


def leader_view(nation: str, s: State | None = None, inbox: list[dict] | None = None) -> LeaderView:
    s = s or state()
    return LeaderView(nation=nation, state=s, advice=advice(s, nation),
                      messages_received=inbox or [])


def call_view(nation: str, said: str, interrupted: bool = False, hesitation_ms: int | None = None,
              s: State | None = None, history: list[dict] | None = None) -> CallView:
    return CallView(nation=nation, state=s or state(), transcript=said, interrupted=interrupted,
                    hesitation_ms=hesitation_ms, history=history)
