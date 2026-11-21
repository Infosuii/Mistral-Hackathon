# Casting — how the leaders sound

Owner: Ashish. Voice ids live in `voice/casting.json`; change them there, not in code.

## Direction

- Every leader must be recognisable blind within one sentence: different gender, pitch or accent from the leader they argue with most (Ostrava vs Zarnia, Kessaria vs everyone at the port).
- Emotion comes from `[emotion=...]` tags chosen by the leader model (`call_reply().emotion`), from the enum in MASTER_PLAN.md §4.6 only.
- Replies are at most two sentences so first audio is fast.

## Current cast (starting voices from MASTER_PLAN.md, still to audition)

| Nation | Leader | Voice | Why |
|---|---|---|---|
| Ostrava | General Marek Dravic (junta) | Howard `voice_3147`, UK male | Starting pick |
| Zarnia | — | Fred `voice_591`, UK male | Starting pick; must stay distinct from Howard |
| Nordhaven | — | Hugo `voice_3149`, UK male | Starting pick |
| Kessaria | — | Harriet `voice_590`, UK female | Starting pick |
| Valdoria | — | Mary `voice_1787`, UK female | Starting pick |

Other English presets to audition if two leaders sound alike: Sheila `voice_478`, Margaret `voice_447` (US female); Rob `voice_485`, James `voice_3150` (US male); Sky `voice_1786` (UK female); David `voice_1788` (UK male).

## Decisions

- 2026-11-21: started from the plan's five voices; Rob `voice_485` is only the synthetic "player" for tests.

## Open questions

- Three UK males (Howard, Fred, Hugo) may be too close. Audition with `python -m voice.v0 emotion` and swap one for a US voice if needed.
