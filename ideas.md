# Mistral hackathon ideas

We’re choosing one project for Le Chonk in London. Aim for **Best Use of Voxtral** and a working demo that a judge can try live.

## Team and agent handoff

1. Start from the latest `main`. Read the event constraints and the sources below, then brainstorm independently before opening anyone else’s proposals.
2. Generate several options privately. Submit your **two strongest ideas** in `ideas/<github-handle>.md`, one file per teammate or agent. Use a branch named `ideas/<github-handle>` and open a PR so others can read the proposals without waiting for a merge. Keep the first round to about 15 minutes.
3. Once proposals are up, read the open PRs and any merged files in `ideas/`. Use the synthesis instructions below to select one project and a fallback. Keep the original proposals available so the team can trace each decision.

## Event constraints

- **Track:** Build anything around Mistral Vibe and Le Chonk (Mistral Large 4). Show what the model does in the product.
- **Prize target:** £250 in Mistral credits for Best Use of Voxtral. First through third earn £3,000, £2,000 and £1,000 in Mistral credits. Event winners who use Mistral Agents and/or Workflows and explain the integration to judges earn a £500 credit bonus. Consider this if it supports the core demo.
- **Deadline:** Submit the project and a demo video by **18:00 GMT on Saturday 21 November 2026**. Both the group judging round and the finalist stage allow **five minutes live**.
- **Build assumption:** A team of 3–5 has a few hours and ordinary laptops. Leave time to capture the video and rehearse. Prefer ideas with one dependable demo flow and a clear recovery path in a noisy room.

[Organizer’s day-of brief](https://docs.google.com/document/d/1RtjY-GnYf5BunNn2ek-oZchSPrHpQ9hiBKiOswBgwG4/edit?tab=t.0#heading=h.ykfxsfcgmsj4)

## Prompt for each agent

> Look at the event brief, Voxtral documentation and relevant past entries below. Brainstorm across at least three distinct uses of voice, then send back your two strongest ideas. For each idea, identify one real user in a specific situation and one thing they can do better because they can speak, listen, interrupt or interact with another speaker. Give an unscripted line a judge can say and describe exactly what changes on screen or in the audio. Name the closest prior project and what this idea adds. Check the required Voxtral functions against the current docs. Scope the whole demo to what we can realistically ship before 18:00.

For each submitted idea, fill in:

- **Name and pitch** — one sentence with the user, situation and payoff.
- **Live demo** — the judge’s exact line, what the app knows at that moment, and the observable result. Aim to prove the core interaction in 60–90 seconds.
- **Why voice** — what gets materially worse if the user types. Name the Voxtral feature and link to its docs.
- **Mistral integration** — what Le Chonk does at runtime, where Vibe fits, and any Agent or Workflow that genuinely helps.
- **MVP and risk** — the minimum build, the riskiest technical assumption, a 30-minute test for it, and a fallback that still uses Voxtral. Include the closest prior project and link.

## How we’ll pick

Score ideas out of 100 using **35 for voice being essential**, **30 for likelihood of a reliable build by 18:00**, **20 for originality**, and **15 for the live demo**. These are our weights. Look for features worth combining only when they serve the same user and make the same demo stronger. Pick one idea, one fallback, one first test, and three parallel build assignments. Write that decision under **Team decision** below.

## Research starting points

- **Closest winners.** Vibe Buddy won the July Paris Vibe Hackathon with Voxtral input, screen context and visible Mac actions. In March, Mistralverse won London and the global final. London runners-up Ami and Verne used voice for browser control and interactive podcasts. Online winner Mistral Raid combined what the player said with gameplay telemetry. MotionCorps won the March ElevenLabs award for voice-driven simulated robotics. [Vibe Buddy](https://github.com/Mathis-14/hackathon-mistral-vibe/blob/main/PRODUCT.md), [March project archive](https://iterate.inc/mistral-worldwide-hackathons?tab=submissions), [March finals](https://www.youtube.com/watch?v=dk2zLmeO-6s)
- **What the API supports.** Voxtral 3 offers live transcription, end-of-turn detection, speaker labels, expressive speech and interruptible voice agents with tool calls. Realtime diarization and end-of-turn detection require separate sessions. Reach for the feature that proves the demo. [Voxtral overview](https://docs.mistral.ai/studio/audio/overview), [speech-to-text](https://docs.mistral.ai/studio/audio/speech-to-text/overview), [voice agents](https://docs.mistral.ai/studio/audio/voice-agents/overview)
- **Mistral build docs.** [Vibe](https://docs.mistral.ai/vibe), [Le Chonk](https://docs.mistral.ai/models/mistral-large-4-0), [Agents](https://docs.mistral.ai/studio/agents/overview), [Workflows](https://docs.mistral.ai/studio/workflows/overview)

## Team decision

Pending the first round of proposals.
