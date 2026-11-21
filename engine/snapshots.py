"""snapshot() and fork(): the base of the needle and the replay.

    sid = snapshot(state)                         # "s_" + hash of the state, stable
    s2 = fork(sid, {"crisis": {"promises": [...]}}, seed=7)
    step(fork(snapshot(s), {}, s.seed), a, s.seed) == step(s, a, s.seed)

`changes` is a partial state, merged into the snapshot: dicts merge key by key, and
anything else (lists, numbers, strings, null) replaces the old value.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from typing import Any

from contracts.models import State

_STORE: "OrderedDict[str, str]" = OrderedDict()
MAX_SNAPSHOTS = 2000


def clear_snapshots() -> None:
    _STORE.clear()


def snapshot(state: State) -> str:
    js = state.model_dump_json(by_alias=True)
    sid = "s_" + hashlib.sha256(js.encode()).hexdigest()[:12]
    _STORE[sid] = js
    _STORE.move_to_end(sid)
    while len(_STORE) > MAX_SNAPSHOTS:
        _STORE.popitem(last=False)
    return sid


def load(snapshot_id: str) -> State:
    try:
        return State.model_validate_json(_STORE[snapshot_id])
    except KeyError:
        raise KeyError(f"unknown snapshot {snapshot_id!r}") from None


def _merge(base: Any, changes: Any) -> Any:
    if isinstance(base, dict) and isinstance(changes, dict):
        out = dict(base)
        for k, v in changes.items():
            out[k] = _merge(base.get(k), v) if k in base else v
        return out
    return changes


def fork(snapshot_id: str, changes: dict, seed: int) -> State:
    base = json.loads(_STORE[snapshot_id]) if snapshot_id in _STORE else None
    if base is None:
        raise KeyError(f"unknown snapshot {snapshot_id!r}")
    merged = _merge(base, changes or {})
    merged["seed"] = seed
    return State.model_validate(merged)
