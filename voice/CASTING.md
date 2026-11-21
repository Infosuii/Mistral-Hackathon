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
| Nordhaven | Chancellor Aino Lindqvist (technocracy) | Sheila `voice_478`, US female | Picked by ear at the playtest; distinct from Harriet (Kessaria, UK female) |
| Kessaria | — | Harriet `voice_590`, UK female | Starting pick |
| Valdoria | — | Mary `voice_1787`, UK female | Starting pick |

Other English presets to audition if two leaders sound alike: Hugo `voice_3149` (UK male), Margaret `voice_447` (US female); Rob `voice_485`, James `voice_3150` (US male); Sky `voice_1786` (UK female); David `voice_1788` (UK male).

## Decisions

- 2026-11-21: started from the plan's five voices; Rob `voice_485` is only the synthetic "player" for tests.
- 2026-11-21: Nordhaven recast from Hugo (male) to Sheila: the leader is a woman, and a US voice stands apart from Harriet. Chosen by ear from Sky, Sheila and Margaret.

## Open questions

- Two UK males (Howard, Fred) argue the most; if they sound too close, audition with `python -m voice.v0 emotion` and swap one for a US voice if needed.
