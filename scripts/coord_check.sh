#!/usr/bin/env bash
# One-screen digest for the coordinator: who is moving, who is silent, what is waiting.
#
#   scripts/coord_check.sh            # digest
#   scripts/coord_check.sh --smoke    # digest, then run scripts/smoke.sh if it exists
#
# Needs: git, gh (logged in). Works in bash on macOS, Linux and Git Bash.
set -u
REPO="${GAMBIT_REPO:-Infosuii/Mistral-Hackathon}"
BOARD="${GAMBIT_BOARD:-25}"
STALE_MIN="${GAMBIT_STALE_MIN:-20}"

echo "== $(date +%H:%M) · GAMBIT coordinator digest =="

echo
echo "-- Checkpoints (local time) --"
now=$(date +%H%M)
for c in "1230 first tests posted, contracts on main" "1300 world runs 20 turns in a terminal" \
         "1415 playable by voice, backup video" "1515 One Berth plays through" \
         "1600 needle and replay" "1615 FREEZE" "1700 final video" "1745 SUBMIT"; do
  t=${c%% *}; label=${c#* }
  if [ "$now" -lt "$t" ]; then echo "next: ${t:0:2}:${t:2:2}  $label"; break; fi
done

echo
echo "-- Status cards (minutes since last update; QUIET over $STALE_MIN = silent on the board, not necessarily stopped: check Branches) --"
gh api "repos/$REPO/issues/$BOARD/comments?per_page=100" --jq "
  .[] | select(.body | startswith(\"<!-- status:\"))
  | ((now - (.updated_at | fromdateiso8601)) / 60 | floor) as \$age
  | (.body | split(\"\n\")) as \$l
  | (if \$age > $STALE_MIN then \"QUIET \" else \"ok    \" end)
    + (\$age | tostring) + \"m  \" + (\$l[1] | ltrimstr(\"### \"))
    + \"\n        \" + (\$l[2] // \"\") + \"\n        \" + (\$l[5] // \"\")"

echo
echo "-- Open PRs --"
gh pr list -R "$REPO" --state open --json number,title,author,createdAt,files --jq "
  .[] | ((now - (.createdAt | fromdateiso8601)) / 60 | floor) as \$age
  | ([.files[].path | split(\"/\")[0]] | unique | join(\",\")) as \$dirs
  | \"#\" + (.number | tostring) + \"  \" + (\$age | tostring) + \"m  \" + .author.login + \"  [\" + \$dirs + \"]  \" + .title"

echo
echo "-- Branches with work not yet on main (last push, commits ahead) --"
git fetch -q --prune origin 2>/dev/null
found=0
# Squash-merged branches still look "ahead", so skip any branch whose PR is merged.
merged=" $(gh pr list -R "$REPO" --state merged --limit 200 --json headRefName --jq '.[].headRefName' 2>/dev/null | tr '\n' ' ') "
open_prs=" $(gh pr list -R "$REPO" --state open --limit 100 --json headRefName --jq '.[].headRefName' 2>/dev/null | tr '\n' ' ') "
for b in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin | grep -v -E '^origin/(HEAD|main)$' | grep -v '^origin$'); do
  name="${b#origin/}"
  case "$merged" in *" $name "*) continue;; esac
  ahead=$(git rev-list --count "origin/main..$b" 2>/dev/null || echo 0)
  [ "$ahead" -gt 0 ] || continue
  found=1
  case "$open_prs" in *" $name "*) pr="PR open";; *) pr="NO PR YET";; esac
  echo "$name  +$ahead  $pr  $(git log -1 --format='%ad  %an  %s' --date=format:%H:%M "$b" | cut -c1-100)"
done
[ "$found" = 1 ] || echo "none"

echo
echo "-- Open asks (BLOCKED and NEED from the last 20 messages) --"
gh api "repos/$REPO/issues/$BOARD/comments?per_page=100" --jq "
  [.[] | select(.body | startswith(\"<!-- status:\") | not)] | .[-20:] | .[]
  | select(.body | test(\"^(BLOCKED|NEED) \"))
  | .created_at[11:16] + \"Z  \" + (.body | split(\"\n\")[0])"

echo
echo "-- Latest 6 messages --"
gh api "repos/$REPO/issues/$BOARD/comments?per_page=100" --jq "
  [.[] | select(.body | startswith(\"<!-- status:\") | not)] | .[-6:] | .[]
  | .created_at[11:16] + \"Z  \" + (.body | split(\"\n\")[0] | .[0:160])"

echo
echo "-- main --"
git fetch -q origin main 2>/dev/null
git log origin/main -5 --format='%ad  %an  %s' --date=format:%H:%M

if [ "${1:-}" = "--smoke" ]; then
  echo
  if [ -x scripts/smoke.sh ]; then
    echo "-- smoke test --"; scripts/smoke.sh; echo "smoke exit=$?"
  else
    echo "-- smoke test: scripts/smoke.sh is not on main yet --"
  fi
fi
