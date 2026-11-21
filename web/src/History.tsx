import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { GameState, MapEvent } from './state'

function eventText(event: MapEvent, state: GameState) {
  const subject = event.nation && (state.nations[event.nation]?.name ?? event.nation)
  const target = event.target && (state.nations[event.target]?.name ?? event.target)
  const activity = (event.action ?? event.type).replaceAll('_', ' ')
  return [subject, activity, target, event.province?.toUpperCase()].filter(Boolean).join(' · ')
}

export function History({ state, online, onLocate }: {
  state: GameState
  online: boolean
  onLocate: (event: MapEvent) => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [open, setOpen] = useState(false)
  const [view, setView] = useState<'history' | 'dispatches'>('history')
  const [nation, setNation] = useState('')
  const [type, setType] = useState('')
  const [items, setItems] = useState<MapEvent[]>([])
  const [error, setError] = useState('')
  const canReadDispatches = online && state.seat.role !== 'mediator'

  useEffect(() => {
    if (!open || !online || (view === 'dispatches' && !canReadDispatches)) return
    const request = new AbortController()
    api<MapEvent[]>(`/${view}`, { signal: request.signal, cache: 'no-store' })
      .then((events) => { if (!request.signal.aborted) { setItems(events); setError('') } })
      .catch(() => {
        if (!request.signal.aborted) setError('Could not load the full log.')
      })
    return () => request.abort()
  }, [open, online, view, canReadDispatches, state.turn, state.crisis?.tick, state.last_call?.call_id])

  const events = view === 'history' && (!online || error) ? state.events : items
  const availableTypes = [...new Set(events.map((event) => event.type))].sort()
  const groups = new Map<number, MapEvent[]>()
  for (const event of [...events].reverse()) {
    if (nation && event.nation !== nation && event.target !== nation) continue
    if (type && event.type !== type) continue
    const group = groups.get(event.turn)
    if (group) group.push(event)
    else groups.set(event.turn, [event])
  }

  function switchView(next: 'history' | 'dispatches') {
    setView(next)
    setType('')
    setItems([])
    setError('')
  }

  return (
    <>
      <button type="button" onClick={() => { setOpen(true); dialog.current?.showModal() }}>History</button>
      <dialog className="session-dialog history-dialog" ref={dialog} onClose={() => setOpen(false)} aria-labelledby="history-title">
        <header>
          <h2 id="history-title">World history</h2>
          <form method="dialog"><button autoFocus>Close</button></form>
        </header>
        {canReadDispatches && (
          <nav className="history-views" aria-label="World log">
            <button type="button" aria-pressed={view === 'history'} onClick={() => switchView('history')}>Timeline</button>
            <button type="button" aria-pressed={view === 'dispatches'} onClick={() => switchView('dispatches')}>Intercepted dispatches</button>
          </nav>
        )}
        <div className="history-views">
          <label>Nation
            <select value={nation} onChange={(event) => setNation(event.target.value)}>
              <option value="">All nations</option>
              {Object.entries(state.nations).map(([id, item]) => <option key={id} value={id}>{item.name}</option>)}
            </select>
          </label>
          {view === 'history' && <label>Event
            <select value={type} onChange={(event) => setType(event.target.value)}>
              <option value="">All events</option>
              {availableTypes.map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}
            </select>
          </label>}
        </div>
        {error && <p role="status">{error}</p>}
        <div className="history-events">
          {groups.size === 0 && <p>{view === 'history' ? 'No recorded events for this view.' : 'No intercepted messages for this view.'}</p>}
          {[...groups].map(([month, entries]) => (
            <section key={month}>
              <h3>Month {month}</h3>
              <ul>{entries.map((event, index) => <li key={index}>
                {view === 'dispatches' ? (
                  <>
                    <strong>{state.nations[event.nation ?? '']?.name} → {state.nations[event.target ?? '']?.name}</strong>
                    <div>{event.text}</div>
                  </>
                ) : event.province || event.nation ? (
                  <button className="history-locate" type="button" onClick={() => {
                    onLocate(event)
                    dialog.current?.close()
                  }}>{eventText(event, state)} <span aria-hidden="true">↗</span></button>
                ) : eventText(event, state)}
              </li>)}</ul>
            </section>
          ))}
        </div>
      </dialog>
    </>
  )
}
