"""Load every example in contracts/examples/ against its model.

    python -m contracts.validate

Exits non-zero if any example fails, or if an example has no model listed here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel, ValidationError

from contracts import models as m

EXAMPLES = Path(__file__).parent / "examples"

# file name -> (model, where it is used)
SCHEMAS: dict[str, tuple[type[BaseModel], str]] = {
    "state.json": (m.State, "GET /state, POST /start, POST /turn"),
    "state.crisis.json": (m.State, "GET /state during a crisis, POST /crisis/start"),
    "start.request.json": (m.StartRequest, "POST /start body"),
    "crisis_start.request.json": (m.CrisisStartRequest, "POST /crisis/start body"),
    "action.json": (m.Action, "engine step(), agents.decide actions"),
    "leader_view.json": (m.LeaderView, "agents.decide input"),
    "leader_output.json": (m.LeaderOutput, "agents.decide output"),
    "leader.response.json": (m.LeaderDetail, "GET /leaders/{id}"),
    "call.request.json": (m.CallRequest, "POST /call body (audio)"),
    "call.request.text.json": (m.CallRequest, "POST /call body (typed fallback)"),
    "call_view.json": (m.CallView, "agents.call_reply input"),
    "call_reply.output.json": (m.CallOutput, "agents.call_reply output"),
    "call.response.json": (m.CallResponse, "POST /call response"),
    "futures.request.json": (m.FuturesRequest, "POST /futures body"),
    "futures.response.json": (m.FuturesResponse, "POST /futures response"),
    "replay.request.json": (m.ReplayRequest, "POST /replay body"),
    "replay.response.json": (m.ReplayResponse, "POST /replay response"),
    "wiretap.response.json": (m.WiretapResponse, "GET /wiretap?a=&b="),
    "crisis_file.one_berth.json": (m.CrisisFile, "data/crises/*.json"),
}


def main() -> int:
    failed = ok = 0
    files = sorted(p.name for p in EXAMPLES.glob("*.json"))
    for name in files:
        if name not in SCHEMAS:
            print(f"FAIL {name}: no model listed in contracts/validate.py")
            failed += 1
            continue
        model, used = SCHEMAS[name]
        try:
            model.model_validate(json.loads((EXAMPLES / name).read_text()))
        except (ValidationError, json.JSONDecodeError) as e:
            print(f"FAIL {name} ({model.__name__}):\n{e}")
            failed += 1
        else:
            ok += 1
            print(f"ok   {name:30} {model.__name__:18} {used}")
    for name in sorted(set(SCHEMAS) - set(files)):
        print(f"FAIL {name}: listed but missing from contracts/examples/")
        failed += 1
    print(f"\n{ok}/{len(SCHEMAS)} examples valid")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
