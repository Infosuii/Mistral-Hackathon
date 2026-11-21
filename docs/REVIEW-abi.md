# Review of GAMBIT v2 (from Abi, for the reviewer)

Verdict: keep the plan. Do not restart. Ten small changes, each with the reason. Apply the ones you agree with.

## Role changes
1. **Move `/replay` from Om to Abi.** Why: Om holds engine, advise(), crisis rules, rollouts, fork, needle and API, which is the critical path. /replay mostly re-asks the leaders whose inputs changed, which is leader work. Om keeps rollouts and the needle.
2. **Give Ashish more after 14:15** (crisis-deck data files, end screen). Why: voice work is front-loaded and he is mostly on the script afterwards.
3. **Quota rule: when a tool runs out, switch to Vibe in the same folder.** Backups are for people who are stuck or away, not for quota. Why: everyone has Vibe Pro, so no handover is needed.
4. **Least headroom takes the narrowest folder; most headroom takes the engine.** Why: the engine is the critical path.

## Plan changes
5. **Make the live replay a stretch goal.** Ship a pre-recorded replay for the demo seed, keep the live needle. Why: Om's load, and Mistral `random_seed` is best-effort, so replays may not reproduce exactly. Cache the original leader decisions for the demo seed.
6. **Treat latency as the top demo risk.** Use low reasoning and short replies for calls, stream the TTS, and keep a pre-written first line ready to play. Why: the interrupt moment needs a quick first audio.
7. **Abi mocks the advisers' ranking until Om's `advise()` lands (12:45).** Why: leader prompts need it, and it would otherwise block the 12:00 and 12:45 deliveries.
8. **Add a typed-input fallback and cached responses for the demo seed.** Why: venue noise or an API outage should not end the demo. The plan only has a backup video.
9. **Do not claim "each nation is a Mistral Agent" in the pitch unless the 20-minute Managed Agents test passes.** Why: say only what is built.
10. **Mark the stats slide optional and run the batch on a separate account.** Why: it depends on the batch script, and rate limits are shared per workspace.

## Housekeeping
- Merge PR #2 so every agent pulls the same plan.
- `docs/GAMBIT.md` (first draft) is superseded by v2; ignore it.
