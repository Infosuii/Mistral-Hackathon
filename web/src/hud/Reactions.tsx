// Moments that make the world feel live: a breaking-news card when a new month's news
// arrives, and floating relation changes over a capital when a leader warms or cools.
import { useEffect, useRef, useState, type CSSProperties } from 'react'
import map from '../map.json'
import { relationBetween, type GameState } from '../state'
import { nationStyle } from '../theme'

const capitals = map.capitals as Record<string, number[]>

/** Newest headline of a new month (or crisis tick) as a card at the top of the map. */
export function BreakingNews({ state }: { state: GameState }) {
  const latest = state.news[state.news.length - 1]
  const key = latest ? `${latest.turn}|${state.crisis?.tick ?? ''}|${latest.text}` : ''
  const seen = useRef<string | null>(null)
  const [shown, setShown] = useState<{ key: string; text: string; turn: number } | null>(null)

  useEffect(() => {
    if (!latest) return
    if (seen.current === null) { seen.current = key; return } // not on first load
    if (seen.current === key) return
    seen.current = key
    setShown({ key, text: latest.text, turn: latest.turn })
    const timer = window.setTimeout(() => setShown((s) => (s?.key === key ? null : s)), 6000)
    return () => window.clearTimeout(timer)
  }, [key, latest])

  if (!shown) return null
  return (
    <button className="breaking-news" key={shown.key} onClick={() => setShown(null)} aria-live="polite">
      <span className="breaking-label">{state.crisis ? 'Crisis bulletin' : 'Breaking'}</span>
      <strong>{shown.text}</strong>
      <span className="breaking-meta">{state.crisis ? `Hour ${state.crisis.tick}` : `Month ${shown.turn}`} · The World Dispatch</span>
    </button>
  )
}

/** Floating "+5" / "−8" over a capital when that leader's relation with you changes. */
export function RelationPops({ state }: { state: GameState }) {
  const seat = state.seat.nation
  const before = useRef<Record<string, number>>({})
  const [pops, setPops] = useState<{ id: string; delta: number; key: number }[]>([])

  useEffect(() => {
    if (!seat) return
    const fresh: { id: string; delta: number; key: number }[] = []
    for (const id of Object.keys(state.nations)) {
      if (id === seat) continue
      const now = relationBetween(state, seat, id)
      if (now === undefined) continue
      const was = before.current[id]
      if (was !== undefined && now !== was) fresh.push({ id, delta: now - was, key: Date.now() + Math.random() })
      before.current[id] = now
    }
    if (!fresh.length) return
    setPops((p) => [...p, ...fresh])
    const timer = window.setTimeout(() => setPops((p) => p.filter((x) => !fresh.includes(x))), 2600)
    return () => window.clearTimeout(timer)
  }, [state, seat])

  return (
    <g className="relation-pops map-decoration">
      {pops.map(({ id, delta, key }) => {
        const c = capitals[id]
        if (!c) return null
        return (
          <text key={key} x={c[0] - 40} y={c[1] - 58} className="relation-pop" data-sign={Math.sign(delta)}
            style={nationStyle(id) as CSSProperties}>
            {delta > 0 ? `+${delta}` : `−${Math.abs(delta)}`}
          </text>
        )
      })}
    </g>
  )
}
