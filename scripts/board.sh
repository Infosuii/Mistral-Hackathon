#!/usr/bin/env bash
# Talk to the Team message board without hand-writing gh calls.
#
#   scripts/board.sh read                       # status cards + the latest messages
#   scripts/board.sh status <Name> --now "..." --done "..." --next "..." --needs "..."
#   scripts/board.sh say <PREFIX> <Name> "<to>" "<message>"
#        PREFIX is READY, CHANGED, BLOCKED, DECIDED or NEED
#        e.g. scripts/board.sh say READY Om "Tamim, Ashish" "/state is live on main (PR #31)."
#
# Each person has one status card on the board. `status` rewrites your own card in
# place, so four agents never overwrite each other. `say` posts a one-line message;
# name who must act in <to>, because their agent is waiting for exactly that.
# Needs: gh (logged in). Works in bash on macOS, Linux and Git Bash.
set -euo pipefail
REPO="${GAMBIT_REPO:-Infosuii/Mistral-Hackathon}"
BOARD="${GAMBIT_BOARD:-25}"

role_of() { case "$1" in Tamim) echo "lead";; Om) echo "engine";; Abi) echo "leaders";; Ashish) echo "voice";; Coordinator) echo "coordinator";; *) echo "team";; esac; }
issue_of() { case "$1" in Tamim) echo 26;; Om) echo 27;; Abi) echo 28;; Ashish) echo 29;; *) echo "$BOARD";; esac; }

cmd="${1:-help}"; [ $# -gt 0 ] && shift
case "$cmd" in
  status)
    name="${1:?usage: board.sh status <Name> --now .. --done .. --next .. --needs ..}"; shift
    now="—"; done_="—"; next="—"; needs="nothing"
    while [ $# -gt 0 ]; do
      case "$1" in
        --now) now="$2"; shift 2;; --done) done_="$2"; shift 2;;
        --next) next="$2"; shift 2;; --needs) needs="$2"; shift 2;;
        *) echo "unknown option $1" >&2; exit 1;;
      esac
    done
    marker="<!-- status:$name -->"
    body="$marker
### $name / $(role_of "$name") · issue #$(issue_of "$name")
**Now:** $now
**Last done:** $done_
**Next:** $next
**Needs from others:** $needs
_Updated $(date +%H:%M)_"
    id=$(gh api "repos/$REPO/issues/$BOARD/comments?per_page=100" \
          --jq ".[] | select(.body | startswith(\"$marker\")) | .id" | head -n 1)
    if [ -n "$id" ]; then
      gh api -X PATCH "repos/$REPO/issues/comments/$id" -f body="$body" --jq '.html_url'
    else
      gh api -X POST "repos/$REPO/issues/$BOARD/comments" -f body="$body" --jq '.html_url'
    fi
    ;;
  say)
    prefix="${1:?usage: board.sh say <PREFIX> <Name> \"<to>\" \"<message>\"}"; name="${2:?}"; to="${3:?}"; msg="${4:?}"
    case "$prefix" in READY|CHANGED|BLOCKED|DECIDED|NEED) ;; *) echo "PREFIX must be READY, CHANGED, BLOCKED, DECIDED or NEED" >&2; exit 1;; esac
    gh api -X POST "repos/$REPO/issues/$BOARD/comments" \
      -f body="$prefix $name / $(role_of "$name") → $to: $msg" --jq '.html_url'
    ;;
  read)
    echo "== STATUS CARDS =="
    gh api "repos/$REPO/issues/$BOARD/comments?per_page=100" \
      --jq '.[] | select(.body | startswith("<!-- status:")) | (.body | split("\n")[1:] | join("\n")) + "\n"'
    echo "== LATEST MESSAGES (oldest first) =="
    gh api "repos/$REPO/issues/$BOARD/comments?per_page=100" \
      --jq '[.[] | select(.body | startswith("<!-- status:") | not)] | .[-15:] | .[] | (.created_at[11:16]) + "  " + (.body | split("\n")[0])'
    ;;
  *)
    sed -n '2,13p' "$0"
    ;;
esac
