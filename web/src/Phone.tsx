import { useEffect, useRef, useState } from 'react'
import callRequest from '../../contracts/examples/call.request.text.json'
import callResponse from '../../contracts/examples/call.response.json'
import { mountTalkButton, type TalkButton, type TalkButtonEvents, type TalkState } from '../../voice/talk-button.js'
import type { GameState } from './state'

type Line = { role: 'player' | 'leader'; text: string }
export type PhoneActivity = { busy: boolean; waitingForState: boolean }
type ReplyDetail = TalkButtonEvents['reply']['detail'] & { pending?: boolean }

function useRinger(ringing: string | undefined) {
  const audio = useRef<AudioContext | null>(null)
  useEffect(() => {
    function unlock() {
      try {
        audio.current ??= new AudioContext()
        void audio.current.resume().catch(() => {})
      } catch {
        // The visual ring is still available when the browser blocks audio.
      }
    }
    window.addEventListener('pointerdown', unlock, { once: true })
    window.addEventListener('keydown', unlock, { once: true })
    return () => {
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('keydown', unlock)
      void audio.current?.close().catch(() => {})
    }
  }, [])

  useEffect(() => {
    const context = audio.current
    if (!ringing || context?.state !== 'running') return
    const signal = context.createOscillator()
    const volume = context.createGain()
    signal.frequency.value = 440
    const now = context.currentTime
    volume.gain.setValueAtTime(0.075, now)
    volume.gain.setValueAtTime(0, now + 0.17)
    volume.gain.setValueAtTime(0.075, now + 0.3)
    volume.gain.setValueAtTime(0, now + 0.47)
    signal.connect(volume).connect(context.destination)
    signal.start(now)
    signal.stop(now + 0.48)
    return () => signal.disconnect()
  }, [ringing])
}

export function Phone({ state, selected, online, onActivity }: {
  state: GameState
  selected?: string
  online: boolean
  onActivity: (change: Partial<PhoneActivity>) => void
}) {
  const [dismissed, setDismissed] = useState<string>()
  const [showPreview, setShowPreview] = useState(false)
  const [logs, setLogs] = useState<Record<string, Line[]>>({})
  const [talkState, setTalkState] = useState<TalkState>('disabled')
  const [contactId, setContactId] = useState<string | null>(null)
  const mount = useRef<HTMLDivElement>(null)
  const talk = useRef<TalkButton | null>(null)
  const playedOpening = useRef<string | undefined>(undefined)
  const transcriptList = useRef<HTMLOListElement>(null)

  const incoming = state.incoming_call
  const incomingKey = incoming ? `${state.turn}|${incoming.from}|${incoming.opening_line}` : undefined
  const ringing = incomingKey !== dismissed ? incomingKey : undefined
  const destination = (ringing && incoming?.from) || selected
  const target = destination && destination !== state.seat.nation && state.nations[destination] ? destination : null
  const contact = target ? state.nations[target] : undefined
  const transcript = target ? logs[target] ?? [] : []
  const lastCall = target && target === state.last_call?.to ? state.last_call : undefined
  const canPreview = !online && !ringing && target === callRequest.to && Boolean(contact)
  useRinger(ringing)

  useEffect(() => {
    const el = mount.current!
    function append(nation: string, line: Line) {
      setLogs((previous) => ({ ...previous, [nation]: [...(previous[nation] ?? []), line].slice(-12) }))
    }
    const onTranscript = (event: Event) => {
      const { to, text } = (event as TalkButtonEvents['transcript']).detail
      append(to, { role: 'player', text })
    }
    const onReply = (event: Event) => {
      const { to, reply_text, pending } = (event as CustomEvent<ReplyDetail>).detail
      if (pending) onActivity({ waitingForState: true })
      append(to, { role: 'leader', text: reply_text })
    }
    const onState = (event: Event) => {
      const { state } = (event as TalkButtonEvents['talk-state']).detail
      setTalkState(state)
      onActivity({ busy: state !== 'idle' && state !== 'disabled' })
    }
    // Keep the hold shortcut on the phone so Space still operates the game's other buttons.
    const onKey = (event: KeyboardEvent) => {
      if (event.repeat || !['Space', 'Enter'].includes(event.code) ||
          !(event.target instanceof HTMLElement) || !event.target.matches('.tb-talk')) return
      event.preventDefault()
      event.target.dispatchEvent(new PointerEvent(event.type === 'keydown' ? 'pointerdown' : 'pointerup', { button: 0 }))
    }
    el.addEventListener('transcript', onTranscript)
    el.addEventListener('reply', onReply)
    el.addEventListener('talk-state', onState)
    el.addEventListener('keydown', onKey)
    el.addEventListener('keyup', onKey)
    talk.current = mountTalkButton(el, { to: null, apiBase: '/api', spaceBar: false })
    return () => {
      el.removeEventListener('transcript', onTranscript)
      el.removeEventListener('reply', onReply)
      el.removeEventListener('talk-state', onState)
      el.removeEventListener('keydown', onKey)
      el.removeEventListener('keyup', onKey)
      talk.current?.destroy()
      talk.current = null
      onActivity({ busy: false })
    }
  }, [onActivity])

  useEffect(() => setShowPreview(false), [target])
  useEffect(() => {
    const list = transcriptList.current
    if (list) list.scrollTop = list.scrollHeight
  }, [logs, target])

  useEffect(() => {
    const desired = online ? target : null
    if (!talk.current || talkState === 'recording' || talkState === 'thinking' || desired === contactId) return
    talk.current.setTo(desired)
    setContactId(desired)
  }, [target, online, talkState, contactId])

  useEffect(() => {
    if (!ringing || !incoming?.audio_url || contactId !== incoming.from || talkState !== 'idle' ||
        playedOpening.current === ringing) return
    playedOpening.current = ringing
    void talk.current?.playLine(incoming.audio_url, incoming.from)
  }, [ringing, incoming, contactId, talkState])

  return (
    <section className="panel phone" aria-labelledby="phone-heading" data-ringing={Boolean(ringing)} data-speaking={talkState === 'speaking'}>
      <header className="phone-heading">
        <svg className="symbol" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M3.5 3h5l2.1 5.3-3 1.8a15.5 15.5 0 0 0 6.3 6.3l1.8-3L21 15.5v5l-1 .5C10.6 21 3 13.4 3 4Z" />
        </svg>
        <h2 id="phone-heading">Red Phone</h2>
      </header>
      <div className="phone-line" aria-live="polite">
        <span className="subtle">{ringing ? 'Incoming call' : contact ? 'Direct line' : 'Select a foreign leader'}</span>
        {contact && <strong>{contact.leader}</strong>}
        {ringing && incoming && (
          <div className="incoming-call">
            <p>{incoming.opening_line}</p>
            {incoming.audio_url && contactId === incoming.from && (
              <button className="plain-control" onClick={() => void talk.current?.playLine(incoming.audio_url ?? null, incoming.from)}>
                Play opening line
              </button>
            )}
            <button className="plain-control" onClick={() => setDismissed(ringing)}>Dismiss</button>
          </div>
        )}
        {lastCall?.pending && <p className="phone-promises" role="status">Checking commitments…</p>}
        {!!lastCall?.promises.length && !lastCall.pending && (
          <ul className="phone-promises" aria-label="Promises from last call">
            {lastCall.promises.map(({ to, what, when }, index) => (
              <li key={index}>{state.nations[to]?.name ?? to}: {what.replaceAll('_', ' ')} · {when.replaceAll('_', ' ')}</li>
            ))}
          </ul>
        )}
        {transcript.length > 0 && (
          <ol ref={transcriptList} className="transcript" aria-label="Call transcript">
            {transcript.map((line, index) => (
              <li key={index}><b>{line.role === 'player' ? 'You' : contact?.name}</b> {line.text}</li>
            ))}
          </ol>
        )}
        {canPreview && showPreview && (
          <div className="transcript">
            <p><b>You</b> {callResponse.transcript}</p>
            <p><b>{contact?.name}</b> {callResponse.reply_text}</p>
          </div>
        )}
      </div>
      <div id="phone-controls">
        <div ref={mount} hidden={!contact || !online} />
        {canPreview && (
          <button className="preview-call" onClick={() => setShowPreview((visible) => !visible)} aria-expanded={showPreview}>
            {showPreview ? 'Close preview' : 'Preview call'}
          </button>
        )}
        {contact && !online && !canPreview && <p className="subtle">Voice offline</p>}
      </div>
    </section>
  )
}
