# talk-button.js

A framework-free ES module for the red phone. Mount it without editing it. Types are in
`talk-button.d.ts`.

## Mount (React, in the Phone panel)

```tsx
import { useEffect, useRef } from 'react'
import { mountTalkButton, type TalkButton } from '../../voice/talk-button.js'

const ref = useRef<HTMLDivElement>(null)
const tb = useRef<TalkButton>()
useEffect(() => {
  const el = ref.current!
  tb.current = mountTalkButton(el, { to: contactId ?? null, apiBase: '/api' })
  const onReply = (e: Event) => setReply((e as CustomEvent).detail)
  el.addEventListener('reply', onReply)
  return () => { el.removeEventListener('reply', onReply); tb.current?.destroy() }
}, [])
useEffect(() => tb.current?.setTo(contactId ?? null), [contactId])
// incoming call: tb.current?.playLine(incoming.audio_url, incoming.from)
return <div id="phone-controls" ref={ref} />
```

Vite already allows files from the repo root (`server.fs.allow`). The backend also serves the
module at `/voice/talk-button.js` (and `/api/voice/talk-button.js`) for plain pages.

## Options

| Option | Default | Meaning |
|---|---|---|
| `to` | `null` | Nation id on the line. `null` disables the button |
| `apiBase` | `'/api'` | Prefix for `POST /call`. Relative audio URLs from the backend (`/audio/...`) get the same prefix |
| `typed` | `true` | Show the typed-fallback field |
| `spaceBar` | `true` | Holding space also talks (ignored while typing in a field) |

## Methods

- `setTo(nation | null)`: switch the call. Stops any leader audio and resets timing.
- `playLine(url, speaker?)`: play a leader line (an incoming call's opening line, Wiretap). The
  player's hesitation is timed from the end of this line. Returns a promise that resolves
  when it ends or is cut off.
- `stop()`: stop leader audio now.
- `state`: `idle | recording | thinking | speaking | disabled`.
- `destroy()`: remove the button, release the mic.

## Events (CustomEvent on the mount element, bubbling)

| Event | `detail` | When |
|---|---|---|
| `transcript` | `{text, to}` | What the player said, as transcribed |
| `reply` | the `/call` response plus `to` | The leader answered. Show `reply_text`, `emotion`, `promises` |
| `audio-start` | `{url, speaker}` | Leader audio began playing |
| `audio-end` | `{url, speaker, interrupted}` | Leader audio finished, or was cut off by the player |
| `talk-state` | `{state}` | Button state changed (use it for a ringing or speaking style) |
| `error` | `{message}` | Mic denied, call failed or audio failed. The button stays usable |

## What it sends

`POST {apiBase}/call` with `{to, audio, text, interrupted, hesitation_ms}` (MASTER_PLAN.md §4.6):

- `audio`: base64 of the MediaRecorder clip (Chrome: webm/opus, accepted as-is), or `text` from
  the typed field.
- `interrupted`: true when the press, or the typed send, began while a leader line was playing.
  That line stops at once.
- `hesitation_ms`: ms from the end of the leader's last line to the press. `null` when the
  player interrupted or no line has played yet in this call.
- Presses shorter than 350 ms are ignored as accidental taps.

The mic opens on the first press (the browser asks once) and stays open, so later presses
start instantly. If the mic is denied, the typed field takes over.

## Try it

`uvicorn voice.app:app --port 8000`, then open `http://localhost:8000/voice-static/talk.html`
in Chrome. Add `?fakemic=1` to feed a recorded line instead of the microphone.
