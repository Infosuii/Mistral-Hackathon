#!/usr/bin/env bash
# One-command launcher for GAMBIT (N2).
#
#   ./scripts/demo.sh            # live mode (requires MISTRAL_API_KEY in .env or env)
#   ./scripts/demo.sh --offline  # offline mode (cached responses + pre-rendered audio, no network)
#
# Options:
#   --offline            Run without network or API key using cached replies and pre-rendered audio
#   --backend-port PORT  Backend port (default: 8000)
#   --web-port PORT      Web UI port (default: 5173)
#   --backend-only       Start only the backend (skip Vite web server)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OFFLINE=0
BACKEND_ONLY=0
BACKEND_PORT="${BACKEND_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

while [ $# -gt 0 ]; do
  case "$1" in
    --offline) OFFLINE=1; shift ;;
    --backend-only) BACKEND_ONLY=1; shift ;;
    --backend-port) BACKEND_PORT="$2"; shift 2 ;;
    --web-port) WEB_PORT="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1 (try --help)" >&2
      exit 1
      ;;
  esac
done

# Load .env in live mode without overriding exported shell variables.
if [ "$OFFLINE" -eq 0 ] && [ -f "$ROOT/.env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"  # a .env saved on Windows ends each line with CR; keep it out of the key
    line="${line#"${line%%[![:space:]]*}"}"
    [ -z "$line" ] && continue
    case "$line" in \#*) continue ;; esac
    case "$line" in *=*)
      key="${line%%=*}"
      val="${line#*=}"
      key="${key%"${key##*[![:space:]]}"}"
      val="${val%"${val##*[![:space:]]}"}"
      val="${val#\"}" ; val="${val%\"}"
      val="${val#\'}" ; val="${val%\'}"
      if [ -z "${!key:-}" ]; then
        export "$key=$val"
      fi
      ;;
    esac
  done < "$ROOT/.env"
fi

if [ "$OFFLINE" -eq 0 ] && [ -z "${MISTRAL_API_KEY:-}" ]; then
  cat >&2 <<'EOF'
ERROR: MISTRAL_API_KEY is not set.
  1. Add MISTRAL_API_KEY=<your-key> to .env at the repo root (or export it).
  2. Or run offline with cached replies and pre-rendered audio: ./scripts/demo.sh --offline
EOF
  exit 1
fi

# Locate or bootstrap a Python environment with requirements installed.
pick_python() {
  if [ -n "${PYTHON:-}" ] && command -v "$PYTHON" >/dev/null 2>&1; then
    echo "$PYTHON"; return
  fi
  local venv_python="$ROOT/.venv/bin/python"
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) venv_python="$ROOT/.venv/Scripts/python.exe" ;;
  esac
  if [ -x "$venv_python" ]; then
    echo "$venv_python"; return
  fi
  for cand in python3.12 python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then
      if "$cand" -c "import fastapi, uvicorn, httpx, pydantic" >/dev/null 2>&1; then
        command -v "$cand"; return
      fi
    fi
  done
  # Fresh clone bootstrap: create .venv and install requirements.txt
  if [ "$OFFLINE" -eq 1 ]; then
    echo "ERROR: no Python environment with requirements.txt installed and --offline cannot download packages." >&2
    exit 1
  fi
  echo "[demo] Bootstrapping .venv and installing requirements.txt..." >&2
  if command -v uv >/dev/null 2>&1; then
    uv venv "$ROOT/.venv" >&2
    uv pip install --python "$venv_python" -r "$ROOT/requirements.txt" >&2
  else
    base_py="$(command -v python3.12 || command -v python3 || command -v python)"
    "$base_py" -m venv "$ROOT/.venv" >&2
    "$venv_python" -m pip install -q -r "$ROOT/requirements.txt" >&2
  fi
  echo "$venv_python"
}

PY="$(pick_python)"

# Bootstrap web dependencies on a fresh clone if needed.
if [ "$BACKEND_ONLY" -eq 0 ] && [ ! -d "$ROOT/web/node_modules" ]; then
  if [ "$OFFLINE" -eq 1 ]; then
    echo "ERROR: web/node_modules is missing; run 'cd web && npm ci' once before --offline." >&2
    exit 1
  fi
  echo "[demo] Installing web dependencies (npm ci)..."
  (cd "$ROOT/web" && npm ci)
fi

# Check / warm pre-rendered audio.
if "$PY" -m voice.prerender --check >/dev/null 2>&1; then
  echo "[demo] Pre-rendered audio ready (voice/prerendered/)."
elif [ "$OFFLINE" -eq 0 ]; then
  echo "[demo] Warming missing pre-rendered audio lines..."
  "$PY" -m voice.prerender
else
  echo "[demo] Warning: some pre-rendered audio files are missing; continuing offline with available clips."
fi

BACKEND_PID=""
WEB_PID=""
cleanup() {
  [ -n "$WEB_PID" ] && kill "$WEB_PID" 2>/dev/null || true
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Stage feature flags & needle budget (DECIDED 14:57, 15:25, 15:41):
# Orders player actions, crisis picker, mediator seat, and 120 rollouts on by default
# (override with e.g. GAMBIT_ROLLOUTS=80 on a slower laptop).
export GAMBIT_PLAYER_ACTIONS="${GAMBIT_PLAYER_ACTIONS:-1}"
export GAMBIT_EXTRA_CRISES="${GAMBIT_EXTRA_CRISES:-1}"
export GAMBIT_MEDIATOR="${GAMBIT_MEDIATOR:-1}"
export GAMBIT_ROLLOUTS="${GAMBIT_ROLLOUTS:-120}"

if [ "$OFFLINE" -eq 1 ]; then
  export GAMBIT_AGENTS=stub
  export VOICE_WIRETAP=demo
  export VOICE_MOCK=fixed
  unset MISTRAL_API_KEY || true
  APP_TARGET="e2e.offline_app:app"
  MODE_LABEL="OFFLINE (cached replies, stub turns, pre-rendered audio, actions=${GAMBIT_PLAYER_ACTIONS}, extra_crises=${GAMBIT_EXTRA_CRISES}, mediator=${GAMBIT_MEDIATOR}, rollouts=${GAMBIT_ROLLOUTS})"
else
  # Demo settings (DECIDED 13:07, 13:48, 14:57, 15:25, 15:41): Medium for turns so 2512's 30 RPM stays for voice;
  # Large 4 for private strategy, call interpretation, wiretap, replay why, and historian.
  export GAMBIT_DECIDE_MODEL="${GAMBIT_DECIDE_MODEL:-mistral-medium-latest}"
  export GAMBIT_PRIVATE_STRATEGY="${GAMBIT_PRIVATE_STRATEGY:-1}"
  export VOICE_WIRETAP="${VOICE_WIRETAP:-demo}"
  APP_TARGET="engine.app:app"
  MODE_LABEL="LIVE (decide=${GAMBIT_DECIDE_MODEL}, private_strategy=${GAMBIT_PRIVATE_STRATEGY}, actions=${GAMBIT_PLAYER_ACTIONS}, extra_crises=${GAMBIT_EXTRA_CRISES}, mediator=${GAMBIT_MEDIATOR}, rollouts=${GAMBIT_ROLLOUTS}, wiretap=${VOICE_WIRETAP})"
fi

echo "[demo] Starting backend ($APP_TARGET) on http://127.0.0.1:${BACKEND_PORT} ..."
"$PY" -m uvicorn "$APP_TARGET" --host 127.0.0.1 --port "$BACKEND_PORT" --log-level warning &
BACKEND_PID=$!

# Wait for backend to answer GET /state.
for _ in $(seq 1 60); do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "ERROR: backend exited unexpectedly." >&2
    exit 1
  fi
  if "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${BACKEND_PORT}/state', timeout=2)" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

if ! "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${BACKEND_PORT}/state', timeout=2)" >/dev/null 2>&1; then
  echo "ERROR: backend did not become ready on port ${BACKEND_PORT}." >&2
  exit 1
fi

# Warm one pre-rendered audio route through the live HTTP server.
FIRST_MP3="$(ls "$ROOT/voice/prerendered"/*.mp3 2>/dev/null | head -n 1 || true)"
if [ -n "$FIRST_MP3" ]; then
  BASENAME="$(basename "$FIRST_MP3")"
  "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${BACKEND_PORT}/audio/${BASENAME}', timeout=5).read()" >/dev/null 2>&1 || true
fi

if [ "$BACKEND_ONLY" -eq 0 ]; then
  export BACKEND_PORT
  export GAMBIT_BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
  echo "[demo] Starting web app on http://localhost:${WEB_PORT} (proxy /api -> ${GAMBIT_BACKEND_URL}) ..."
  (cd "$ROOT/web" && exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$WEB_PORT" --strictPort) >/tmp/gambit_web_${WEB_PORT}.log 2>&1 &
  WEB_PID=$!
  for _ in $(seq 1 60); do
    if ! kill -0 "$WEB_PID" 2>/dev/null; then
      echo "ERROR: web app exited unexpectedly. Log:" >&2
      cat "/tmp/gambit_web_${WEB_PORT}.log" >&2 || true
      exit 1
    fi
    if "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${WEB_PORT}/', timeout=2)" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
fi

echo ""
echo "================================================================"
echo "  GAMBIT is running — ${MODE_LABEL}"
if [ "$BACKEND_ONLY" -eq 0 ]; then
  echo "  Web UI:   http://localhost:${WEB_PORT}   (open in Chrome for mic)"
fi
echo "  Backend:  http://127.0.0.1:${BACKEND_PORT}"
echo "  Press Ctrl-C to stop."
echo "================================================================"
echo ""

wait
