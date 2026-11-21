// The player's one-sided moves against the selected nation, in Abi's orders bar
// (web/src/hud/OrdersBar.tsx picks this file up). Tariff, war and peace are queued for
// next month (POST /action, DECIDED 13:49); trade and alliances stay phone calls. The
// engine decides what is legal (GET /actions), so the page computes no game logic.
// Renders nothing while GAMBIT_PLAYER_ACTIONS is off, in a crisis, or for a mediator.
import { useEffect, useState } from 'react'
import { api, post } from './api'
import type { GameState } from './state'
import './diplomacy.css'

interface Action {
  type: string
  by: string
  target?: string | null
  params: Record<string, unknown>
}

interface PlayerActions {
  actions: Action[]
  queued: Action | null
}

function label(a: Action) {
  if (a.type === 'set_tariff') return `Tariff ${a.params.pct}%`
  if (a.type === 'declare_war') return 'Declare war'
  if (a.type === 'make_peace') return 'Make peace'
  return a.type.replace(/_/g, ' ')
}

const same = (a: Action | null, b: Action) =>
  !!a && a.type === b.type && a.target === b.target && JSON.stringify(a.params) === JSON.stringify(b.params)

export function Diplomacy({ state, target }: { state: GameState; target: string }) {
  const [moves, setMoves] = useState<PlayerActions | null>(null)
  const [error, setError] = useState('')
  const [off, setOff] = useState(false)
  const [busy, setBusy] = useState(false)
  const strategy = state.phase === 'strategy' && state.seat.nation !== null

  useEffect(() => {
    if (!strategy || off) return
    let live = true
    api<PlayerActions>('/actions')
      .then((r) => { if (live) { setMoves(r); setError('') } })
      .catch((e: Error) => {
        if (!live) return
        if (e.message.includes('404')) setOff(true)
        else setError('Could not load orders.')
      })
    return () => { live = false }
  }, [state.turn, strategy, off])

  if (off || !strategy) return null
  const mine = moves?.actions.filter((a) => a.target === target) ?? []
  if (!mine.length && !error) return null

  async function queue(a: Action) {
    if (busy) return
    setError('')
    setBusy(true)
    try {
      setMoves(await post<PlayerActions>('/action', a))
    } catch {
      setError('Could not queue this order. Check the available moves.')
      // Not legal any more (the month moved on): refresh the list.
      api<PlayerActions>('/actions').then(setMoves).catch(() => undefined)
    } finally {
      setBusy(false)
    }
  }

  return (
    <span className="diplomacy-orders" role="group" aria-label="Your moves, next month">
      {error && <span role="alert">{error}</span>}
      {mine.map((a) => {
        const queued = same(moves?.queued ?? null, a)
        return (
          <button
            key={label(a)}
            type="button"
            className={`order order-${a.type}${queued ? ' order-queued' : ''}`}
            aria-pressed={queued}
            title={queued ? 'Queued for next month' : 'Queue for next month'}
            disabled={busy}
            onClick={() => queue(a)}
          >
            {label(a)}
          </button>
        )
      })}
    </span>
  )
}
