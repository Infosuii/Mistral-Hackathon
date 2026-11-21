#!/usr/bin/env bash
# Smoke test: run before every merge. Exits 0 when main is playable.
#
#   scripts/smoke.sh            # GAMBIT_AGENTS=stub by default: no model calls, about 5 s
#   GAMBIT_AGENTS=live scripts/smoke.sh   # use the real leaders
#
# Starts the backend on the demo seed, checks /state and /turn against the contract,
# and a typed /call once /voice mounts it. Then it validates the contract examples.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${SMOKE_PORT:-8765}"
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
export GAMBIT_AGENTS="${GAMBIT_AGENTS:-stub}"

"$PY" -m contracts.validate >/dev/null || { echo "FAIL contracts: run python -m contracts.validate"; exit 1; }
# Every router a folder ships (voice/api.py, replay/api.py) must mount.
"$PY" - 2>/dev/null <<'PYEOF' || exit 1
import sys
try:
    import engine.app as a
except Exception as e:
    print(f"FAIL engine.app does not import: {type(e).__name__}: {e}")
    sys.exit(1)
for m, e in a.MOUNT_ERRORS.items():
    print(f"FAIL mount {m}: {e} (pip install -r requirements.txt?)")
sys.exit(1 if a.MOUNT_ERRORS else 0)
PYEOF

"$PY" -m uvicorn engine.app:app --port "$PORT" --log-level warning &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT

"$PY" - "$PORT" <<'EOF'
import json, sys, time, urllib.error, urllib.request
from contracts.models import CallResponse, State

base = f"http://127.0.0.1:{sys.argv[1]}"

def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

for _ in range(50):
    try:
        call("GET", "/state"); break
    except Exception:
        time.sleep(0.2)
else:
    sys.exit("FAIL server did not start")

s = State.model_validate(call("POST", "/start", {"seed": 7, "seat": {"role": "president", "nation": "valdoria"}}))
assert s.turn == 0, s.turn
print("ok   /start demo seed 7")
State.model_validate(call("GET", "/state")); print("ok   /state")
for i in range(1, 4):
    s = State.model_validate(call("POST", "/turn"))
    assert s.turn == i, (s.turn, i)
print("ok   /turn x3")
s = State.model_validate(call("POST", "/crisis/start", {"id": "one_berth"}))
assert s.phase == "crisis", s.phase
s = State.model_validate(call("POST", "/turn"))
assert s.crisis.tick == 1, s.crisis.tick
print("ok   /crisis/start one_berth + 1 tick")
try:
    r = call("POST", "/call", json.load(open("contracts/examples/call.request.text.json")))
    CallResponse.model_validate(r); print("ok   /call typed")
except urllib.error.HTTPError as e:
    import os
    if e.code != 404 or os.path.exists("voice/api.py"):
        sys.exit(f"FAIL /call: HTTP {e.code} {e.read()[:300]!r}")
    print("skip /call (voice/api.py does not exist yet)")
s = State.model_validate(call("POST", "/end"))
assert s.phase == "ended" and s.ending is not None, s.phase
print("ok   /end")
print("SMOKE OK")
EOF
