"""Gate for a crisis card (Tamim 15:41): loads, plays through to an outcome, replays. Offline (stub agents).

    python voice/crises/card_check.py coup pipeline_cut
"""
import os, sys
os.environ["GAMBIT_AGENTS"] = "stub"
os.environ["GAMBIT_EXTRA_CRISES"] = "1"
ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
sys.path.insert(0, ROOT); os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8")
from fastapi.testclient import TestClient
from contracts.models import CallOutput
from engine.app import app
from engine.game import GAME

SCEN = {  # (name, [(tick, to, what)]) player promises made through the real call path
    "coup": [("silent", []),
             ("honest: back Dravic only", [(1, "ostrava", "valdoria_backing"), (3, "zarnia", "stay_out")]),
             ("double: back both", [(1, "ostrava", "valdoria_backing"), (3, "zarnia", "valdoria_backing")])],
    "pipeline_cut": [("silent", []),
                     ("honest: Ostrava sole supplier", [(1, "ostrava", "sole_supplier"), (2, "nordhaven", "pay_price")]),
                     ("double: both sole supplier", [(1, "ostrava", "sole_supplier"), (2, "zarnia", "sole_supplier")])],
}


def out(to, what):
    return CallOutput(reply_text="...", emotion="calm",
                      promises=[{"to": to, "what": what, "when": "now", "condition": None}], actions=[],
                      belief_updates={"trust_in_player": 0.05, "resolve_of_player": 0.05})


ok = True
for cid in sys.argv[1:]:
    with TestClient(app) as c:
        avail = [x["id"] for x in c.get("/state").json().get("available_crises") or []]
        print(f"== {cid}: listed={cid in avail}")
        ok &= cid in avail
        for name, calls in SCEN[cid]:
            c.post("/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}})
            r = c.post("/crisis/start", json={"id": cid}); ok &= r.status_code == 200
            s = c.get("/state").json()
            rings = []
            while s.get("phase") == "crisis":
                tick = s["crisis"]["tick"]
                if s.get("incoming_call"):
                    rings.append(tick)
                for t, to, what in calls:
                    if t == tick:
                        cid_ = GAME.begin_call(to)
                        GAME.apply_call(to, out(to, what), interrupted=False, hesitation_ms=400, call_id=cid_)
                s = c.post("/turn").json()
            ev = [e for e in s["events"] if e["type"] == "crisis_resolved"]
            notes = [n["text"] for n in s["news"] if "compare notes" in n["text"]]
            wars = [(l["a"], l["b"]) for l in s.get("links", []) if l["type"] == "war"]
            dec = ev[-1].get("decisions") if ev else None
            rep = c.post("/replay", json={"shift_ticks": 3}); rep0 = c.post("/replay", json={"shift_ticks": 0}); rep5 = c.post("/replay", json={"shift_ticks": 5})
            rj = rep.json() if rep.status_code == 200 else {}
            flips = [(x["nation"], x["was"], x["now"]) for x in rj.get("changed", [])]; f0 = rep0.json().get("changed") if rep0.status_code == 200 else "ERR"; f5 = [(x["nation"], x["was"], x["now"]) for x in rep5.json().get("changed", [])] if rep5.status_code == 200 else "ERR"
            print(f"  {name}: resolved={bool(ev)} rings@{rings} notes={notes[-1:] or '-'} wars={wars}\n"
                  f"     decisions={dec}\n     replay 0 -> {f0}; +3 -> {flips}; +5 -> {f5}")
            ok &= bool(ev) and rep.status_code == 200 and rep5.status_code == 200 and f0 == []
print("GATE", "PASS" if ok else "FAIL")
