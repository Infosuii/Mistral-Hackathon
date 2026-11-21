// GAMBIT talk button (Ashish / voice). Framework-free ES module; see voice/TALK_BUTTON.md.
//
//   import { mountTalkButton } from '../../voice/talk-button.js'
//   const tb = mountTalkButton(document.getElementById('phone-controls'), { to: 'ostrava' })
//   el.addEventListener('reply', (e) => console.log(e.detail.reply_text))
//
// Hold the button (or the space bar) to talk. Pressing while a leader is speaking cuts
// them off and sends interrupted=true. The gap between the leader's audio ending and the
// player starting is sent as hesitation_ms. A typed line is the fallback.

const STYLE_ID = 'gambit-talk-button-style'
const MIN_RECORD_MS = 350
const LABELS = {
  idle: 'Hold to talk',
  recording: 'Listening… release to send',
  thinking: 'Sending…',
  speaking: 'Hold to interrupt',
  disabled: 'Select a leader',
}

const CSS = `
.tb { display: grid; gap: 8px; font: inherit; }
.tb-talk {
  width: 100%; min-height: 56px; padding: 10px 12px; border-radius: 6px;
  border: 1px solid var(--phone-edge, #79434b); background: var(--signal, #ff978c);
  color: #1a0d10; font: 700 15px/1.2 inherit; letter-spacing: .06em; text-transform: uppercase;
  cursor: pointer; touch-action: none; user-select: none; -webkit-user-select: none;
  display: flex; align-items: center; justify-content: center; gap: 10px;
}
.tb-talk:focus-visible { outline: 2px solid var(--text, #fff); outline-offset: 2px; }
.tb-talk[data-state="recording"] { background: #ff4f45; color: #fff; animation: tb-pulse 1s infinite; }
.tb-talk[data-state="thinking"] { opacity: .7; cursor: progress; }
.tb-talk[data-state="speaking"] { background: transparent; color: var(--signal, #ff978c); }
.tb-talk[data-state="disabled"] { opacity: .45; cursor: not-allowed; }
.tb-level { width: 6px; height: 18px; border-radius: 3px; background: currentColor; transform-origin: bottom; transform: scaleY(.15); }
.tb-typed { display: flex; gap: 6px; }
.tb-typed input {
  flex: 1; min-width: 0; padding: 8px; border-radius: 4px; font: inherit;
  border: 1px solid var(--phone-edge, #79434b); background: transparent; color: inherit;
}
.tb-typed button {
  padding: 8px 10px; border-radius: 4px; border: 1px solid var(--phone-edge, #79434b);
  background: transparent; color: inherit; font: inherit; cursor: pointer;
}
.tb-note { font-size: 12px; opacity: .75; min-height: 1em; }
@keyframes tb-pulse { 50% { box-shadow: 0 0 0 6px rgba(255, 79, 69, .25); } }
`

function injectStyle() {
  if (document.getElementById(STYLE_ID)) return
  const s = document.createElement('style')
  s.id = STYLE_ID
  s.textContent = CSS
  document.head.appendChild(s)
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(String(r.result).split(',')[1] || '')
    r.onerror = () => reject(r.error)
    r.readAsDataURL(blob)
  })
}

/**
 * @param {HTMLElement} el  where the button goes; events are dispatched on it
 * @param {{to?: string|null, apiBase?: string, typed?: boolean, spaceBar?: boolean}} opts
 */
export function mountTalkButton(el, opts = {}) {
  injectStyle()
  const apiBase = (opts.apiBase ?? '/api').replace(/\/$/, '')
  let to = opts.to ?? null
  let state = 'idle'
  let audio = null           // the leader line now playing
  let lastAudioEnd = null    // performance.now() when the last leader line finished
  let stream = null          // mic stream, kept open after first use so later presses are instant
  let recorder = null
  let chunks = []
  let pressStart = 0
  let pressInterrupted = false
  let pressHesitation = null
  let pressing = false
  let level = null

  const root = document.createElement('div')
  root.className = 'tb'
  root.innerHTML = `
    <button type="button" class="tb-talk" aria-live="polite"><span class="tb-level" aria-hidden="true"></span><span class="tb-label"></span></button>
    ${opts.typed === false ? '' : `<form class="tb-typed"><input type="text" placeholder="Or type to the leader…" aria-label="Type a line to the leader"><button type="submit">Send</button></form>`}
    <div class="tb-note" role="status"></div>`
  el.appendChild(root)
  const btn = root.querySelector('.tb-talk')
  const label = root.querySelector('.tb-label')
  const bar = root.querySelector('.tb-level')
  const form = root.querySelector('.tb-typed')
  const note = root.querySelector('.tb-note')

  const emit = (type, detail) => el.dispatchEvent(new CustomEvent(type, { detail, bubbles: true }))

  function setState(next) {
    state = to ? next : 'disabled'
    btn.dataset.state = state
    label.textContent = LABELS[state]
    btn.disabled = state === 'thinking'
    emit('talk-state', { state })
  }

  function say(msg) { note.textContent = msg || '' }

  // ------------------------------------------------------------------ leader audio
  function stopAudio(interrupted) {
    if (!audio) return false
    const a = audio
    audio = null
    a.onended = a.onerror = a.onplaying = null // clearing src would otherwise fire onerror
    a._done?.()
    a.pause()
    a.removeAttribute('src')
    a.load()
    emit('audio-end', { url: a.dataset.url, speaker: a.dataset.speaker, interrupted })
    lastAudioEnd = interrupted ? null : performance.now()
    return true
  }

  function resolveUrl(url) {
    return url.startsWith('/') && !url.startsWith(apiBase + '/') ? apiBase + url : url
  }

  function playLine(url, speaker = to) {
    stopAudio(true)
    if (!url) return Promise.resolve()
    const a = new Audio(resolveUrl(url))
    a.dataset.url = url
    a.dataset.speaker = speaker || ''
    audio = a
    setState('speaking')
    return new Promise((resolve) => {
      a._done = resolve
      a.onplaying = () => emit('audio-start', { url, speaker })
      a.onended = () => {
        if (audio !== a) return resolve()
        audio = null
        lastAudioEnd = performance.now()
        emit('audio-end', { url, speaker, interrupted: false })
        setState('idle')
        resolve()
      }
      a.onerror = () => {
        if (audio === a) { audio = null; setState('idle') }
        emit('error', { message: `could not play ${url}` })
        resolve()
      }
      a.play().catch((e) => {
        // Autoplay blocked before the first click: show it, the next press will work.
        if (audio === a) { audio = null; setState('idle') }
        say('Click once to enable sound')
        emit('error', { message: String(e) })
        resolve()
      })
    })
  }

  // ------------------------------------------------------------------ sending
  async function send(body) {
    if (!to) return
    setState('thinking')
    say('')
    try {
      const r = await fetch(`${apiBase}/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to, ...body }),
      })
      const j = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(j.detail ? JSON.stringify(j.detail) : `HTTP ${r.status}`)
      emit('transcript', { text: j.transcript, to })
      emit('reply', { ...j, to })
      if (state === 'thinking') setState('idle')
      if (j.reply_audio_url) playLine(j.reply_audio_url, to)
    } catch (e) {
      setState('idle')
      say(`Call failed: ${e.message}. Try again or type.`)
      emit('error', { message: String(e.message || e) })
    }
  }

  // Measured at the moment the player starts: cut-off and silence before speaking.
  function capturePressContext() {
    pressInterrupted = stopAudio(true)
    pressHesitation = !pressInterrupted && lastAudioEnd != null
      ? Math.round(performance.now() - lastAudioEnd) : null
    lastAudioEnd = null
  }

  // ------------------------------------------------------------------ recording
  async function ensureMic() {
    if (stream && stream.active) return stream
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })
    level = meter(stream)
    return stream
  }

  function meter(s) {
    try {
      const ctx = new AudioContext()
      const an = ctx.createAnalyser()
      an.fftSize = 256
      ctx.createMediaStreamSource(s).connect(an)
      const buf = new Uint8Array(an.fftSize)
      let raf = 0
      const tick = () => {
        an.getByteTimeDomainData(buf)
        let peak = 0
        for (const v of buf) peak = Math.max(peak, Math.abs(v - 128))
        bar.style.transform = `scaleY(${state === 'recording' ? Math.max(0.15, Math.min(1, peak / 50)) : 0.15})`
        raf = requestAnimationFrame(tick)
      }
      tick()
      return { stop: () => { cancelAnimationFrame(raf); ctx.close() } }
    } catch { return null }
  }

  async function startTalking() {
    if (!to || state === 'thinking' || pressing) return
    pressing = true
    capturePressContext()
    pressStart = performance.now()
    setState('recording')
    try {
      await ensureMic()
    } catch (e) {
      pressing = false
      setState('idle')
      say('Microphone unavailable. Type your line below.')
      emit('error', { message: `microphone: ${e.message || e}` })
      form?.querySelector('input')?.focus()
      return
    }
    if (!pressing) { setState('idle'); return } // released before the mic opened
    chunks = []
    recorder = new MediaRecorder(stream)
    recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data) }
    recorder.start()
  }

  async function stopTalking() {
    if (!pressing) return
    pressing = false
    const rec = recorder
    recorder = null
    if (!rec) return
    const held = performance.now() - pressStart
    const done = new Promise((r) => { rec.onstop = r })
    rec.stop()
    await done
    if (held < MIN_RECORD_MS) {
      setState('idle')
      say('Hold the button while you speak.')
      return
    }
    const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' })
    await send({ audio: await blobToBase64(blob), text: null,
                 interrupted: pressInterrupted, hesitation_ms: pressHesitation })
  }

  // ------------------------------------------------------------------ input wiring
  const onDown = (e) => { if (e.button === 0 || e.pointerType !== 'mouse') { e.preventDefault(); startTalking() } }
  const onUp = () => stopTalking()
  btn.addEventListener('pointerdown', onDown)
  btn.addEventListener('pointerup', onUp)
  btn.addEventListener('pointercancel', onUp)
  btn.addEventListener('pointerleave', onUp)
  btn.addEventListener('contextmenu', (e) => e.preventDefault())

  const typingInField = (e) => e.target instanceof HTMLElement &&
    (e.target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName))
  const onKeyDown = (e) => {
    if (e.code !== 'Space' || e.repeat || typingInField(e)) return
    e.preventDefault()
    startTalking()
  }
  const onKeyUp = (e) => { if (e.code === 'Space' && !typingInField(e)) { e.preventDefault(); stopTalking() } }
  if (opts.spaceBar !== false) {
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
  }

  form?.addEventListener('submit', (e) => {
    e.preventDefault()
    const input = form.querySelector('input')
    const text = input.value.trim()
    if (!text || !to || state === 'thinking') return
    input.value = ''
    capturePressContext()
    send({ audio: null, text, interrupted: pressInterrupted, hesitation_ms: pressHesitation })
  })

  setState('idle')

  return {
    /** Change who the phone is talking to; resets the timing for a new call. */
    setTo(nation) {
      if (nation === to) return
      stopAudio(true)
      to = nation || null
      lastAudioEnd = null
      setState('idle')
    },
    /** Play a leader line (an incoming call's opening line, a Wiretap line). Hesitation is timed from its end. */
    playLine,
    /** Stop any leader audio now. */
    stop() { stopAudio(true); if (state === 'speaking') setState('idle') },
    get state() { return state },
    destroy() {
      stopAudio(true)
      if (opts.spaceBar !== false) {
        window.removeEventListener('keydown', onKeyDown)
        window.removeEventListener('keyup', onKeyUp)
      }
      level?.stop()
      stream?.getTracks().forEach((t) => t.stop())
      root.remove()
    },
  }
}
