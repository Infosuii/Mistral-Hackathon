# Working on GAMBIT / Red Phone

Start at the [team tracker](https://github.com/Infosuii/Mistral-Hackathon/issues/4). It lists the four owners, linked work and London checkpoints. The five-nation build uses the game proposal in [PR #2](https://github.com/Infosuii/Mistral-Hackathon/pull/2) and tracks proposed changes in [PR #3](https://github.com/Infosuii/Mistral-Hackathon/pull/3). The brainstorming instructions in `ideas.md` describe the earlier idea round.

| Owner | First ticket | Handoff |
|---|---|---|
| Tamim | [#6 · situation room](https://github.com/Infosuii/Mistral-Hackathon/issues/6) | Owns the interface, integration and demo freeze. |
| Om | [#5 · API fixtures](https://github.com/Infosuii/Mistral-Hackathon/issues/5) | Owns the API, engine, snapshots and paired futures. |
| Abi | [#7 · leader trial](https://github.com/Infosuii/Mistral-Hackathon/issues/7) | Owns country agents, promises and leader replay explanations. |
| Ashish | [#8 · voice trial](https://github.com/Infosuii/Mistral-Hackathon/issues/8) | Owns Voxtral, the talk control, backup recording and submission. |

## From an issue to a PR

1. Open the human owner's assigned issue, check for an existing PR and apply the `in progress` label when work starts. Build against the example fixtures while dependencies land.
2. Branch from current `main`. Put the issue number in the branch name. One small PR should satisfy one issue's acceptance checks.
3. Post shared payload changes on the issue and tag the consuming owner. If blocked, use the `blocked` label and say exactly what input or decision would unblock the work.
4. Link the PR with `Closes #NUMBER`. Include a verification command, screenshot or recording and the next owner's handoff. Ask the consumer or listed backup to review.
5. Keep service keys server-side. Share sanitized sample payloads and team-recorded demo audio. Label mock fixtures, cached replays and measured live runs in the handoff.

The tracker holds the current scope and cut decisions. The feature freeze is 16:15 GMT and the project and video are due at 18:00 GMT on 21 November.
