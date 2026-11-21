# Voxtral in GAMBIT

Every word a leader says and every word the player says goes through Voxtral. Owner: Ashish (`/voice`).

## What we use, and where

| Feature | Model and call | Where in the game | Code |
|---|---|---|---|
| **Transcription** | `voxtral-mini-transcribe-3`, `POST /v1/audio/transcriptions`, `language=en` | Hold-to-talk on the phone: the clip goes to `POST /call` (the leader answers it) or `POST /transcribe` (live transcript in the phone). Chrome's webm/opus is sent as recorded, with no conversion. | `voice/audio.py` `transcribe()`, `voice/api.py` |
| **Context bias** | `context_bias` on every transcription | The game's names (Ostrava, Zarnia, Nordhaven, Kessaria, Valdoria, Port Kessar, the five leaders) and crisis words (berth, blockade, tugs) are spelled right, so a promise reaches the right leader. | `voice/audio.py` `BIAS_TERMS` |
| **Speech** | `voxtral-mini-tts-3-0`, `POST /v1/audio/speech`, `stream: true` | Every leader reply on the phone. The page starts playing at the first streamed chunk while the rest renders; `GET /audio/<file>` replays chunks to the player as they arrive. | `voice/audio.py` `stream_speech()`, `start_speech()` |
| **Emotion tags** | `[emotion=...]` inline, one of 15 values | The leader model picks the emotion with each reply (Ostrava's tick-1 ring is `angry`); proud leaders (Ostrava, Zarnia) take an interruption as an insult and a pause as weakness, and it shows in the tag they pick. | `voice/audio.py` `tagged()`, `EMOTIONS` |
| **Cast voices** | Five preset voices, one per leader | Ostrava Howard, Zarnia Fred, Nordhaven Sheila, Kessaria Harriet, Valdoria Mary, chosen so the leaders who argue most sound different. | `voice/casting.json`, `voice/CASTING.md` |
| **Wiretap** | Speech, two voices | Two leaders discussing the player, written by `agents.wiretap()` and spoken in their cast voices (or the pre-rendered demo script, `VOICE_WIRETAP=demo`). | `voice/api.py` `/wiretap` |
| **Pre-rendered lines** | Speech, rendered ahead and committed | Crisis rings (Ostrava's tick-1 and tick-7 calls, the Grey Fever openings), the demo Wiretap, and each leader's "The line is breaking up" fallback, so they play instantly and offline. | `voice/prerender.py`, `voice/prerendered/` |

Interruption and hesitation are measured by the talk button (`voice/talk-button.js`): holding to talk
while a leader speaks cuts the audio and sends `interrupted=true`; the gap before the player speaks is
sent as `hesitation_ms`. The leaders react to both.

## Measured

| What | Result | Source |
|---|---|---|
| Typed line to first leader audio | about 1.8 s (spoken reply 1.39 s median + first speech chunk 0.39 s median) | `e2e/timings.py`, #113, 10 live calls |
| Spoken reply, worst / first chunk, worst | 3.11 s / 1.27 s | same |
| Transcription of a 220 KB WAV upload | 3.32 s median, 8.72 s worst | same |
| Transcription of a Chrome mic clip | 0.25–0.37 s over 6 calls; reply 0.86–1.49 s | room mic test, 13:15 |
| Human playtest, One Berth by voice | 13 of 13 transcriptions and 13 of 13 speech requests succeeded, no fallback line | 14:45 playtest, Chrome mic |
| Word accuracy in noise (18 lines) | clean 98.1%, 20 dB 98.1%, 10 dB 98.4%, 0 dB 83.3%; game names 25/26 down to 10 dB | `voice/noise_test.py`, #132 |
| Emotion, blind listen | 6 of 6 tags identified; pitch rises from calm to angry by 32% (Howard) and 37% (Harriet) | `voice/v0.py emotion`, `voice/static/blind.html` |

## What we do not use

We do not send audio to a Voxtral chat model to understand tone: interruption and hesitation come from
the talk button's timing, and each clip is transcribed after the player lets go, not while they speak.
