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
echo "-- Status cards (minutes since last update; STALE over $STALE_MIN) --"
gh api "repos/$REPO/issues/$BOARD/comments?per_page=100" --jq "
  .[] | select(.body | startswith(\"<!-- status:\"))
  | ((now - (.updated_at | fromdateiso8601)) / 60 | floor) as \$age
  | (.body | split(\"\n\")) as \$l
  | (if \$age > $STALE_MIN then \"STALE \" else \"ok    \" end)
    + (\$age | tostring) + \"m  \" + (\$l[1] | ltrimstr(\"### \"))
    + \"\n        \" + (\$l[2] // \"\") + \"\n        \" + (\$l[5] // \"\")"

echo
echo "-- Open PRs --"
gh pr list -R "$REPO" --state open --json number,title,author,createdAt,files --jq "
  .[] | ((now - (.createdAt | fromdateiso8601)) / 60 | floor) as \$age
  | ([.files[].path | split(\"/\")[0]] | unique | join(\",\")) as \$dirs
  | \"#\" + (.number | tostring) + \"  \" + (\$age | tostring) + \"m  \" + .author.login + \"  [\" + \$dirs + \"]  \" + .title"

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
