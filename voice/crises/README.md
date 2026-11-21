# Crisis drafts (V4)

Drafts of extra crisis files, written by voice so that their phone openings are cast and
pre-rendered before the engine takes them. They move to `data/crises/` when V4 is gated in
(DECIDED 13:07, after private strategy and the mediator seat). Their openings are already in
`voice/prerendered/`, so they ring instantly.

## outbreak.json: Grey Fever

A fever spreads in Zarnia, and Nordhaven has one vaccine batch. Zarnia (tick 1) wants the doses
quietly and denies the fever. Kessaria (tick 3) wants the same doses and threatens to close the
border. They compare notes at tick 5. Ostrava (tick 7) announces it will exploit a sick Zarnia.

Checked with the generic resolver on `om/v4-generic` (seed 7, stub agents):

| Player does | Result |
|---|---|
| Nothing | Zarnia covers up, Ostrava exploits: **Ostrava–Zarnia war** |
| Promises Zarnia the first doses (Nordhaven ships to Zarnia) | Zarnia admits it, **no war**, Zarnia's trust 0.3 → 0.45 |
| Promises the first doses to Zarnia **and** Kessaria | Caught at compare-notes, trust → 0, **war** |
| Zarnia blames Kessaria, Kessaria closes the border | **Two wars** |
| Honest to Zarnia and asks Ostrava to stay out | No war, Ostrava stands down |

Shared action `first_doses` (Zarnia and Kessaria) works like the berth: the same promise to both
contradicts. Interpret records it as `what: first_doses, when: now` (agents/leaders.py vocabulary).
