import { useEffect, useState } from 'react'
import intelExample from '../../contracts/examples/leader.response.json'
import wiretapExample from '../../contracts/examples/wiretap.response.json'
import { api, audioSource } from './api'
import type { GameState } from './state'

type Action = { type: string; target?: string | null }
type Intel = {
  private_intent: string
  private_strategy?: string | null
  advice: { action: Action; score: number }[]
  chosen: Action[]
  reason: string
}
type Wiretap = { lines: { speaker: string; text: string; audio_url?: string | null }[] }

export function Intelligence({ state, id, online }: { state: GameState; id: string; online: boolean }) {
  const [tab, setTab] = useState<'intel' | 'wiretap'>()
  const [intel, setIntel] = useState<Intel>()
  const [lines, setLines] = useState<Wiretap['lines']>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const contacts = Object.entries(state.nations).filter(([nation]) => nation !== id && nation !== state.seat.nation)
  const [contact, setContact] = useState(contacts[0]?.[0] ?? '')
  const strategy = intel?.private_strategy?.trim()

  useEffect(() => {
    if (tab !== 'intel') return
    setIntel(undefined)
    setError('')
    if (!online) {
      setIntel(id === 'ostrava' ? intelExample : undefined)
      return
    }
    const controller = new AbortController()
    let loading = false
    async function refresh() {
      if (loading) return
      loading = true
      try {
        const result = await api<Intel>(`/leaders/${encodeURIComponent(id)}`, { signal: controller.signal, cache: 'no-store' })
        if (!controller.signal.aborted) {
          setIntel(result)
          setError('')
        }
      } catch {
        if (!controller.signal.aborted) setError('Unable to load the briefing.')
      } finally {
        loading = false
      }
    }
    // Strategy is written in the background and lives only in this endpoint.
    void refresh()
    const timer = window.setInterval(refresh, 2_000)
    return () => {
      window.clearInterval(timer)
      controller.abort()
    }
  }, [tab, id, online])

  async function listen() {
    if (!contact || busy) return
    setError('')
    setLines(undefined)
    if (!online) {
      const sample = [contact, id].sort().join('|') === 'kessaria|ostrava'
      setLines(sample ? wiretapExample.lines : [])
      return
    }
    setBusy(true)
    try {
      const query = new URLSearchParams({ a: id, b: contact })
      setLines((await api<Wiretap>(`/wiretap?${query}`)).lines)
    } catch {
      setError('Wiretap could not connect.')
    } finally {
      setBusy(false)
    }
  }

  function actionName(action: Action) {
    const text = action.type.replaceAll('_', ' ')
    return action.target ? `${text} · ${state.nations[action.target]?.name ?? action.target}` : text
  }

  return (
    <div className="intelligence">
      <div className="intelligence-controls">
        <button className="plain-control" aria-expanded={tab === 'intel'} onClick={() => setTab(tab === 'intel' ? undefined : 'intel')}>Intel</button>
        {contacts.length > 0 && (
          <button className="plain-control" aria-expanded={tab === 'wiretap'} onClick={() => { setError(''); setTab(tab === 'wiretap' ? undefined : 'wiretap') }}>Wiretap</button>
        )}
      </div>
      {tab === 'intel' && (
        <section className="intel-drawer" aria-label="Leader intel">
          {intel ? (
            <dl>
              {strategy && <><dt>Private strategy</dt><dd className="intel-strategy">{strategy}</dd></>}
              <dt>Private intent</dt><dd>{intel.private_intent || 'No private intent recorded.'}</dd>
              <dt>Advisers recommend</dt><dd>{intel.advice[0] ? actionName(intel.advice[0].action) : 'No advice recorded.'}</dd>
              <dt>Chosen action</dt><dd>{intel.chosen.map(actionName).join(', ') || 'No action recorded.'}</dd>
              {intel.reason && <><dt>Reason</dt><dd>{intel.reason}</dd></>}
            </dl>
          ) : error ? null : <p role="status">{online ? 'Loading intel' : 'No archived briefing for this leader.'}</p>}
        </section>
      )}
      {tab === 'wiretap' && (
        <section className="intel-drawer" aria-label="Wiretap">
          <div className="wiretap-controls">
            <select aria-label="Second leader" value={contact}
              onChange={(event) => { setContact(event.target.value); setLines(undefined); setError('') }} disabled={busy}>
              {contacts.map(([nation, leader]) => <option key={nation} value={nation}>{leader.name}</option>)}
            </select>
            <button className="plain-control" onClick={() => void listen()} disabled={!contact || busy}>{busy ? 'Listening' : 'Listen'}</button>
          </div>
          {lines && (lines.length === 0 ? <p>No intercepted lines.</p> : (
            <ol className="transcript">
              {lines.map((line, index) => (
                <li key={index}>
                  <b>{state.nations[line.speaker]?.name ?? line.speaker}</b> {line.text}
                  {online && line.audio_url && <audio controls preload="none" src={audioSource(line.audio_url)} />}
                </li>
              ))}
            </ol>
          ))}
        </section>
      )}
      {error && <p className="call-error" role="alert">{error}</p>}
    </div>
  )
}
