"""Build data/nations.json from Tamim's map so the engine and the page agree.

    python -m engine.gen_nations

Province ids and neighbours come from web/src/map.json (two cells are neighbours when
their outlines share an edge). Starting owners, stats, leaders, relations and links
come from contracts/examples/state.json, the fixture the page renders. Run again
whenever the map or that example changes.
"""

from __future__ import annotations

import json
import re
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NEUTRAL_BELIEFS = {"trust_in_player": 0.5, "resolve_of_player": 0.5}


def main() -> None:
    m = json.loads((ROOT / "web/src/map.json").read_text())
    example = json.loads((ROOT / "contracts/examples/state.json").read_text())

    corners = {}
    for p in m["provinces"]:
        nums = re.findall(r"-?\d+(?:\.\d+)?", p["path"])
        corners[p["id"]] = set(zip(nums[::2], nums[1::2]))
    ids = sorted(corners)
    neighbours = {i: [j for j in ids if j != i and len(corners[i] & corners[j]) >= 2] for i in ids}

    nations = {}
    for nid, n in example["nations"].items():
        nations[nid] = {
            "name": n["name"], "system": n["system"], "leader": n["leader"],
            "voice_id": n["voice_id"],
            "stats": {k: v for k, v in n["stats"].items() if k != "territory"},
            "beliefs": n["beliefs"] or NEUTRAL_BELIEFS,
            "public_statement": n.get("public_statement", ""),
        }
    relations = dict(example["relations"])
    for a, b in combinations(sorted(nations), 2):
        relations.setdefault(f"{a}|{b}", 0)

    out = {
        "nations": dict(sorted(nations.items())),
        "relations": dict(sorted(relations.items())),
        "links": example["links"],
        "provinces": {p: example["provinces"][p] for p in ids},
        "neighbours": neighbours,
    }
    path = ROOT / "data/nations.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {path.relative_to(ROOT)}: {len(nations)} nations, {len(ids)} provinces")


if __name__ == "__main__":
    main()
