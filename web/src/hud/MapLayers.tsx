// Grand-strategy map layers drawn from the live state: national borders, territory
// labels, unit counters, and each leader's medallion with mood ring and speech bubble.
import { useEffect, useRef, useState, type CSSProperties } from 'react'
import map from '../atlas.json'
import { useMarkerScale, world } from './scale'
import oneBerth from '../../../data/crises/one_berth.json'
import { grainShips, kessarPoint, kessarPort, ShipSilhouette, straitPatrol, tugBerth } from './DecisionMotion'
import { relationBetween, type GameState } from '../state'
import { nationStyle } from '../theme'

const art = import.meta.glob<string>('../nations/*.svg', { eager: true, query: '?url', import: 'default' })
export const portraitOf = (id: string) => art[`../nations/${id}-portrait.svg`]
export const flagOf = (id: string) => art[`../nations/${id}-flag.svg`]

const centers = new Map(map.provinces.map(({ id, center }) => [id, center as number[]]))
const capitals = map.capitals as Record<string, number[]>
const SPEAK_MS = 5200

/** Thick borders where neighbouring provinces belong to different nations. */
export function NationalBorders({ state }: { state: GameState }) {
  const edges = map.borders.filter(({ between: [a, b] }) => state.provinces[a] !== state.provinces[b])
  return (
    <g className="national-borders map-decoration">
      {edges.map(({ between, path }) => <path key={between.join('|')} className="nb-under" d={path} />)}
      {edges.map(({ between, path }) => <path key={`o${between.join('|')}`} className="nb-over" data-home={between.some((id) => state.provinces[id] === state.seat.nation)} d={path} />)}
    </g>
  )
}

/** Large spaced nation names across each nation's territory; they follow conquests. */
export function TerritoryLabels({ state, selected }: { state: GameState; selected?: string; zoom: number }) {
  const m = useMarkerScale()
  const owned = new Map<string, number[][]>()
  for (const [pid, owner] of Object.entries(state.provinces)) {
    const c = centers.get(pid)
    if (c) owned.set(owner, [...(owned.get(owner) ?? []), c])
  }
  return (
    <g className="territory-labels map-decoration">
      {[...owned].map(([id, pts]) => {
        const nation = state.nations[id]
        if (!nation) return null
        const x = pts.reduce((s, p) => s + p[0], 0) / pts.length
        let y = pts.reduce((s, p) => s + p[1], 0) / pts.length
        const cap = capitals[id]
        // The capital carries the leader, units and star: put the name clear of them.
        if (cap && Math.abs(cap[1] - y) < 55 * m && Math.abs(cap[0] - x) < 150 * m) y = cap[1] + (y >= cap[1] ? 62 : -62) * m
        const size = Math.max(22, Math.min(44, 12 + Math.sqrt(pts.length) * 9)) * m
        return (
          <text key={id} x={x} y={y + 6} style={{ ...nationStyle(id), fontSize: size } as CSSProperties}
            data-selected={id === selected}>{nation.name}</text>
        )
      })}
    </g>
  )
}

function Counter({ x, y, army, id }: { x: number; y: number; army: number; id: string }) {
  const stack = Math.max(1, Math.min(4, Math.ceil(army / 25)))
  const m = useMarkerScale()
  return (
    <g className="unit" transform={`translate(${x} ${y}) scale(${m})`} style={nationStyle(id)} filter="url(#unit-shadow)">
      {Array.from({ length: stack }, (_, i) => stack - 1 - i).map((i) => (
        <g key={i} transform={`translate(${i * 3} ${-i * 3})`}>
          <rect x="-15" y="-10" width="30" height="20" rx="2" className="unit-body" />
          <rect x="-11" y="-7" width="14" height="10" className="unit-symbol" />
          <path d="M-11,-7 L3,3 M3,-7 L-11,3" className="unit-symbol-x" />
          <rect x="5" y="-7" width="7" height="10" className="unit-pip" />
        </g>
      ))}
      <g transform="translate(0 16)">
        <rect x="-13" y="-6" width="26" height="12" rx="6" className="unit-plate" />
        <text y="3.5" className="unit-strength">{Math.round(army)}</text>
      </g>
    </g>
  )
}

/** Unit counters: a stack at each capital sized by army, plus counters on war fronts. */
export function UnitCounters({ state }: { state: GameState }) {
  const m = useMarkerScale()
  const wars = state.links.filter((l) => l.type === 'war')
  const front: { id: string; at: number[] }[] = []
  for (const { a, b } of wars) {
    for (const edge of map.borders) {
      const [p, q] = edge.between
      const op = state.provinces[p]
      const oq = state.provinces[q]
      if ((op === a && oq === b) || (op === b && oq === a)) {
        front.push({ id: op, at: centers.get(p)! }, { id: oq, at: centers.get(q)! })
      }
    }
  }
  const seen = new Set<string>()
  return (
    <g className="unit-layer">
      {Object.entries(state.nations).map(([id, n]) => {
        const c = capitals[id]
        return c ? <Counter key={id} id={id} x={c[0] + 34 * m} y={c[1] + 18 * m} army={n.stats.army} /> : null
      })}
      {front.filter(({ id, at }) => {
        const k = `${id}${at}`
        if (seen.has(k)) return false
        seen.add(k)
        return true
      }).slice(0, 8).map(({ id, at }) => (
        <Counter key={`f${id}${at}`} id={id} x={at[0]} y={at[1]} army={state.nations[id]?.stats.army / 3} />
      ))}
    </g>
  )
}

export function mood(state: GameState, id: string): { tone: string; label: string } {
  const rel = relationBetween(state, state.seat.nation, id)
  const trust = state.nations[id]?.beliefs?.trust_in_player
  const score = rel ?? (trust !== undefined ? (trust - 0.5) * 100 : 0)
  if (score <= -30) return { tone: 'hostile', label: 'Hostile' }
  if (score < -5) return { tone: 'wary', label: 'Wary' }
  if (score < 20) return { tone: 'neutral', label: 'Neutral' }
  return { tone: 'friendly', label: 'Friendly' }
}

/** Each leader at their capital: portrait medallion, mood ring, live speech bubble. */
export function LeaderMedallions({ state, selected, onSelect }: {
  state: GameState; selected?: string; onSelect: (id: string) => void
}) {
  // One leader speaks at a time: fresh statements first, then round-robin, so the map
  // always feels inhabited. A bubble stays up for SPEAK_MS.
  const last = useRef<Record<string, string>>({})
  const fresh = useRef<string[]>([])
  const turnOrder = useRef(0)
  const [speaker, setSpeaker] = useState<string | null>(null)
  const nationsRef = useRef(state.nations)
  nationsRef.current = state.nations

  useEffect(() => {
    for (const [id, n] of Object.entries(state.nations)) {
      const said = n.public_statement?.trim() ?? ''
      if (said && last.current[id] !== undefined && last.current[id] !== said && !fresh.current.includes(id)) fresh.current.push(id)
      last.current[id] = said
    }
  }, [state.nations])

  useEffect(() => {
    const tick = () => {
      const ids = Object.keys(nationsRef.current).filter((id) => id !== state.seat.nation && nationsRef.current[id].public_statement)
      if (!ids.length) return setSpeaker(null)
      const next = fresh.current.shift() ?? ids[turnOrder.current++ % ids.length]
      setSpeaker(next)
    }
    tick()
    const timer = window.setInterval(tick, SPEAK_MS)
    return () => window.clearInterval(timer)
  }, [state.seat.nation])

  const caller = state.incoming_call?.from
  const m = useMarkerScale()
  return (
    <g className="leader-layer">
      {Object.entries(state.nations).map(([id, n]) => {
        const c = capitals[id]
        if (!c || id === state.seat.nation) return null
        const { tone, label } = mood(state, id)
        const x = c[0] - 40 * m
        const y = c[1] - 30 * m
        const portrait = portraitOf(id)
        const decision = state.crisis?.decisions[id]?.action
        const bubble = speaker === id ? n.public_statement : ''
        return (
          <g key={id} className="leader" data-mood={tone} data-calling={caller === id} data-selected={id === selected}
            transform={`translate(${x} ${y}) scale(${m})`} style={nationStyle(id)} onClick={() => onSelect(id)}>
            <title>{n.leader} · {label}</title>
            <circle r="21" className="leader-pulse" />
            <circle r="18" className="leader-ring" />
            <clipPath id={`face-${id}`}><circle r="15" /></clipPath>
            {portrait
              ? <image href={portrait} x="-15" y="-17" width="30" height="36" clipPath={`url(#face-${id})`} preserveAspectRatio="xMidYMin slice" />
              : <circle r="15" className="leader-face" />}
            {caller === id && <g transform="translate(0 -31)"><rect x="-26" y="-8" width="52" height="15" rx="3" className="call-tag" /><text y="3" className="call-tag-text">CALLING</text></g>}
            {decision && <g transform="translate(0 30)"><rect x="-38" y="-8" width="76" height="15" rx="3" className="decision-tag" /><text y="3" className="decision-tag-text">{decision.replaceAll('_', ' ')}</text></g>}
            {bubble && (
              <foreignObject x="-110" y="-118" width="220" height="92" className="bubble-wrap">
                <div className="speech-bubble"><b>{n.leader.split(' ').slice(-1)[0]}:</b> {bubble}</div>
              </foreignObject>
            )}
          </g>
        )
      })}
    </g>
  )
}

export function CapitalMarkers({ state }: { state: GameState }) {
  const m = useMarkerScale()
  return (
    <g className="map-decoration">
      {Object.entries(capitals).map(([id, [x, y]]) => state.nations[id] && (
        <g key={id} className="capital-settlement" data-home={id === state.seat.nation} transform={`translate(${x} ${y}) scale(${m})`} style={nationStyle(id)}>
          <title>{state.nations[id].name} capital</title>
          {id === state.seat.nation && <text className="home-map-label" y="-28">YOUR NATION</text>}
        </g>
      ))}
    </g>
  )
}

function Ship({ at: [x, y], from, id, label, kind }: { at: number[]; from?: number[]; id: string; label: string; kind?: 'grain' | 'tug' | 'patrol' }) {
  const m = useMarkerScale()
  const dx = from ? from[0] - x : 0
  const dy = from ? from[1] - y : 0
  return (
    <g className="ship" style={nationStyle(id)}>
      <title>{label}</title>
      <g className="crisis-ship" style={{ transform: `translate(${x}px, ${y}px)` }}>
        <g className="crisis-ship" data-arriving={Boolean(from)} style={{
          '--cue-x': `${dx}px`, '--cue-y': `${dy}px`,
          '--cue-mid-x': `${dx / 2}px`, '--cue-mid-y': `${dy / 2}px`,
        } as CSSProperties}>
          <g transform={`scale(${1.45 * Math.max(1, m)})`}><g className="ship-bob"><ShipSilhouette kind={kind} /></g></g>
        </g>
      </g>
    </g>
  )
}

/** One Berth has a physical map location. Other crises use their own decision indicators. */
export function CrisisFocus({ state }: { state: GameState }) {
  const c = state.crisis
  if (c?.id !== 'one_berth') return null
  const tugRule = oneBerth.rules.second_berth_requires
  const tugs = c.decisions[tugRule.nation]
  const secondBerth = tugs?.action === tugRule.action && tugs.tick <= tugRule.by_tick
  const blockade = c.decisions.ostrava?.action === 'blockade'
  const closed = c.decisions.kessaria?.action === 'close_port'
  const [x, y] = kessarPort
  const m = useMarkerScale()
  return (
    <g className="crisis-focus map-decoration">
      <circle cx={x} cy={y} r={14 * m} className="focus-pulse" />
      <circle cx={x} cy={y} r={7 * m} className="focus-core" />
      <g transform={`translate(${x} ${y - 20 * m}) scale(${m})`}>
        <rect x="-74" y="-10" width="148" height="16" rx="3" className="focus-tag" />
        <text y="2" className="focus-tag-text">Port Kessar · {closed ? 'Closed' : secondBerth ? '2 berths' : '1 berth'}</text>
      </g>
      {Object.entries(grainShips).map(([id, ship]) => {
        if (!state.nations[id]) return null
        const name = state.nations[id].name
        const approaching = !closed && c.decisions[id]?.action === 'dock' && !(blockade && id === 'zarnia')
        return <Ship key={id} id={id} at={approaching ? ship.approach : ship.waiting}
          label={`${name} grain ship · ${approaching ? 'approaching port' : 'offshore'}`} />
      })}
      {secondBerth && <Ship id="nordhaven" kind="tug" at={tugBerth} from={kessarPoint(780, 649)} label="Nordhaven tugs · second berth available" />}
      {blockade && <Ship id="ostrava" kind="patrol" at={straitPatrol} from={kessarPoint(782, 633)} label="Ostrava blockade patrol" />}
      <path className="storm" transform={`translate(${kessarPort.join(' ')}) scale(${world(1)}) translate(-612 -548)`} d="M700,520 q14,-12 28,0 q14,12 28,0 M712,536 q12,-10 24,0 q12,10 24,0" />
    </g>
  )
}