#!/usr/bin/env bash
# Wait until someone needs you, then exit so your agent can carry on.
#
#   scripts/wait_for_tag.sh <Name> <your-issue-number> [max-minutes] [path-to-watch]
#
# Returns 0 and prints what changed when any of these happen:
#   - a new comment on the Team message board is addressed to <Name> or to all
#   - a new comment appears on your own work issue from someone else
#   - (optional) origin/main changes under <path-to-watch>, e.g. contracts/
# Returns 2 if nothing happens within max-minutes (default 15).
# Needs: git, gh (logged in). Works in bash on macOS, Linux and Git Bash.
set -u
NAME="${1:?usage: wait_for_tag.sh <Name> <issue> [max-minutes] [path]}"
ISSUE="${2:?usage: wait_for_tag.sh <Name> <issue> [max-minutes] [path]}"
MAX_MIN="${3:-15}"
WATCH="${4:-}"
REPO="${GAMBIT_REPO:-Infosuii/Mistral-Hackathon}"
BOARD="${GAMBIT_BOARD:-25}"
EVERY="${GAMBIT_POLL_SECONDS:-45}"
SINCE="${GAMBIT_SINCE:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
START_SHA="$(git rev-parse origin/main 2>/dev/null || echo none)"
DEADLINE=$(( $(date +%s) + MAX_MIN * 60 ))

# "→ Tamim, Om:" or "→ all:" after the arrow, before the colon.
# Keep these patterns free of backslashes: they are pasted into a jq string.
TO_ME="→[^:]*[^A-Za-z](${NAME}|all|everyone|team)([^A-Za-z]|\$)"
# Skip my own posts on my issue: they start with an optional prefix word, then "Name /".
MINE="^[^A-Za-z]*([A-Z]+ +)?${NAME} */"

while :; do
  board=$(gh api "repos/$REPO/issues/$BOARD/comments?since=$SINCE&per_page=100" \
    --jq ".[] | select(.created_at > \"$SINCE\") | select(.body | test(\"$TO_ME\"; \"i\")) | select(.body | test(\"$MINE\"; \"i\") | not) | \"[board] \" + .body" 2>/dev/null) || board=""
  mine=$(gh api "repos/$REPO/issues/$ISSUE/comments?since=$SINCE&per_page=100" \
    --jq ".[] | select(.created_at > \"$SINCE\") | select(.body | test(\"$MINE\"; \"i\") | not) | \"[issue #$ISSUE] \" + .body" 2>/dev/null) || mine=""
  if [ -n "$board$mine" ]; then
    printf '%s\n%s\n' "$board" "$mine" | sed '/^$/d'
    exit 0
  fi
  if [ -n "$WATCH" ]; then
    git fetch -q origin main 2>/dev/null
    if ! git diff --quiet "$START_SHA" origin/main -- "$WATCH" 2>/dev/null; then
      echo "[main] $WATCH changed on origin/main. Pull and carry on."
      exit 0
    fi
  fi
  if [ "$(date +%s)" -ge "$DEADLINE" ]; then
    echo "Nothing for $NAME in $MAX_MIN minutes."
    exit 2
  fi
  sleep "$EVERY"
done
