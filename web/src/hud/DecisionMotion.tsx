import { useEffect, useRef, useState, type CSSProperties } from 'react'
import map from '../map.json'
import sea from '../../../data/sea_routes.json'
import type { GameState, MapEvent } from '../state'
import { nationStyle } from '../theme'
import './decision-motion.css'

type Point = number[]
type Mark = 'infantry' | 'cargo' | 'signal' | 'ship'
type Cue = {
  kind: string
  label: string
  at: Point
  from?: Point
  mark?: Mark
  nation?: string
  province?: string
  formerOwner?: string
}
type ActiveCue = Cue & { id: number; expires: number; delay: number }

const ports: Record<string, { position: Point }> = sea.ports
const capitals: Record<string, Point> = map.capitals
const provinces = new Map(map.provinces.map((p) => [p.id, p]))
const lifetime = 3700
const cueLimit = 10

export const kessarPort = [612, 548]
export const grainShips: Record<string, { waiting: Point; approach: Point; berth: Point }> = {
  ostrava: { waiting: [693, 577], approach: [644, 554], berth: [629, 548] },
  zarnia: { waiting: [614, 592], approach: [615, 574], berth: [611, 558] },
}
export const tugBerth = [662, 564]
export const straitPatrol = [743, 582]

const labels: Record<string, string> = {
  tariff: 'Tariff imposed',
  trade_deal: 'Trade agreed',
  trade_rejected: 'Trade declined',
  alliance: 'Alliance formed',
  alliance_rejected: 'Alliance declined',
  alliance_left: 'Alliance ended',
  war: 'War declared',
  peace: 'Peace agreed',
  election: 'New government',
  coup: 'Coup',
}

function front(state: GameState, a: string, b: string) {
  const edge = map.borders.find(({ between: [p, q] }) => (
    (state.provinces[p] === a && state.provinces[q] === b)
    || (state.provinces[p] === b && state.provinces[q] === a)
  ))
  if (!edge) return
  const [p, q] = edge.between
  const own = provinces.get(state.provinces[p] === a ? p : q)!.center
  const other = provinces.get(state.provinces[p] === a ? q : p)!.center
  return { own, at: [(own[0] + other[0]) / 2, (own[1] + other[1]) / 2] }
}

function decisionCue(event: MapEvent, state: GameState, oneBerth: boolean): Cue[] {
  const { nation, action } = event
  if (!nation || !action || !capitals[nation]) return []
  const local = { kind: 'decision', label: action.replaceAll('_', ' '), at: capitals[nation], nation }
  if (action === 'stay_out') return [local]

  if (oneBerth) {
    const ship = grainShips[nation]
    if (action === 'wait' && ship) return [{ ...local, at: ship.waiting }]
    if (action === 'dock' && ship) return [{ ...local, label: 'Approaching port', at: ship.approach }]
    if (action === 'send_tugs') return [{ ...local, label: 'Tugs dispatched', at: tugBerth }]
    if (action === 'blockade' && ship) return [{ ...local, kind: 'war', label: 'Blockade ordered', at: straitPatrol }]
    if (action === 'mobilise') {
      const border = front(state, nation, 'ostrava')
      if (border) return [{ ...local, kind: 'war', at: border.at, from: border.own, mark: 'infantry' }]
    }
    if (nation === 'kessaria') return [{ ...local, at: kessarPort }]
  }

  // Grey Fever names the shipment destinations in the committed action.
  if (state.crisis?.id === 'outbreak' && nation === 'nordhaven') {
    const recipients = action === 'split_batch' ? ['zarnia', 'kessaria']
      : action === 'ship_zarnia' ? ['zarnia']
      : action === 'ship_kessaria' ? ['kessaria'] : []
    if (recipients.length) return recipients.flatMap((recipient) => capitals[recipient]
      ? [{ ...local, kind: 'trade_deal', label: 'Vaccine shipment ordered', from: local.at, at: capitals[recipient], mark: 'cargo' }]
      : [])
  }
  return [local]
}

function eventCues(event: MapEvent, state: GameState, before: GameState): Cue[] {
  const { type, nation, target, province } = event
  const at = (province && provinces.get(province)?.center) || (nation && capitals[nation])
  const targetAt = target && capitals[target]
  const oneBerth = (state.crisis?.id ?? before.crisis?.id) === 'one_berth'
  if (nation && target && ['fleet_deployed', 'fleet_recalled', 'fleet_returned', 'blockade_started', 'blockade_lifted'].includes(type)) {
    const port = ports[type === 'fleet_deployed' || type === 'fleet_returned' ? nation : target]
    if (port) return [{ kind: type.startsWith('blockade') ? 'war' : 'decision',
      label: type.replaceAll('_', ' '), at: port.position, nation }]
  }
  if (type === 'crisis_decision') return decisionCue(event, state, oneBerth)
  if (type === 'crisis_start' && event.crisis === 'one_berth')
    return [{ kind: 'decision', label: 'Storm closes the port', at: kessarPort }]
  if (type === 'forecast' && oneBerth)
    return [{ kind: 'decision', label: 'Storm update', at: kessarPort }]
  if (type === 'public_commitment' && at)
    return [{ kind: 'tariff', label: `${event.action?.replaceAll('_', ' ') ?? 'Public commitment'} announced`,
      at: oneBerth && event.action === 'blockade' ? straitPatrol : at }]
  if (type === 'compare_notes' && at && targetAt)
    return [{ kind: event.contradiction ? 'tariff' : 'diplomacy',
      label: event.contradiction ? 'Conflicting promises exposed' : 'Leaders compare notes',
      from: at, at: targetAt, mark: 'signal' }]
  if (type === 'province_taken' && province && nation && at) {
    const neighbor = map.borders.find(({ between: [p, q] }) => (
      (p === province && before.provinces[q] === nation)
      || (q === province && before.provinces[p] === nation)
    ))?.between.find((id) => id !== province)
    return [{ kind: 'capture', label: `${province.toUpperCase()} captured`, province, nation, at, formerOwner: target ?? before.provinces[province],
      from: neighbor ? provinces.get(neighbor)?.center : undefined, mark: 'infantry' }]
  }
  if (type === 'crisis_resolved' && event.crisis === 'one_berth') {
    return Object.entries(event.holders ?? {}).flatMap(([id, slot]) => {
      const ship = grainShips[id]
      return ship && (slot === 'berth' || slot === 'half_berth')
        ? [{ kind: 'trade_deal', label: slot === 'half_berth' ? 'Docked · half day' : 'Docked',
          nation: id, from: ship.approach, at: ship.berth, mark: 'ship' }]
        : []
    })
  }
  if (!at || type === 'incoming_call') return [] // Abi's leader ring already handles incoming calls.
  if ((type === 'war' || type === 'peace') && nation && target) {
    return [{ kind: type, label: labels[type], at: front(state, nation, target)?.at ?? at, nation }]
  }
  if (targetAt && ['trade_deal', 'trade_rejected', 'alliance', 'alliance_rejected', 'alliance_left', 'tariff'].includes(type)) {
    const mark = type === 'trade_deal' ? 'cargo' : 'signal'
    // A signed deal is bilateral. One cargo counter illustrates it without inventing volumes.
    return [{ kind: type, label: labels[type], from: at, at: targetAt, mark, nation: nation ?? undefined }]
  }
  return [{ kind: labels[type] ? type : 'decision', label: labels[type] ?? type.replaceAll('_', ' '), at, nation: nation ?? undefined }]
}

// The API returns a rolling event log. Match its retained prefix to the old suffix,
// so repeated polls and events aged out of the buffer do not replay old animations.
function appendedEvents(before: GameState, state: GameState) {
  const old = before.events.map((event) => JSON.stringify(event))
  const next = state.events.map((event) => JSON.stringify(event))
  for (let keep = Math.min(old.length, next.length); keep > 0; keep--) {
    if (old.slice(-keep).every((entry, index) => entry === next[index])) return state.events.slice(keep)
  }
  return state.events.filter((event) => event.turn >= before.turn)
}

function crisisWarChanges(before: GameState, state: GameState, events: MapEvent[]): Cue[] {
  if (!events.some(({ type }) => type === 'crisis_resolved')) return []
  const wars = (snapshot: GameState) => new Map(snapshot.links.filter(({ type }) => type === 'war')
    .map((link) => [[link.a, link.b].sort().join('|'), link]))
  const old = wars(before)
  const current = wars(state)
  return [...current.entries(), ...old.entries()].flatMap(([id, { a, b }]) => {
    if (old.has(id) === current.has(id)) return []
    const at = front(state, a, b)?.at ?? capitals[a]
    const kind = current.has(id) ? 'war' : 'peace'
    return at ? [{ kind, label: labels[kind], at, nation: a }] : []
  })
}

function useCues(state: GameState, online: boolean) {
  const previous = useRef<GameState | null>(null)
  const seq = useRef(0)
  const [active, setActive] = useState<ActiveCue[]>([])

  useEffect(() => {
    const before = previous.current
    previous.current = online ? state : null
    if (!before || !online || state.seed !== before.seed || state.turn < before.turn) {
      setActive((cues) => cues.length ? [] : cues)
      return
    }
    const events = appendedEvents(before, state)
    const cues = [...events.flatMap((event) => eventCues(event, state, before)),
      ...crisisWarChanges(before, state, events)].slice(-cueLimit)
    if (!cues.length) return
    const now = Date.now()
    const batch = cues.map((cue, i) => ({
      ...cue, id: seq.current++, delay: 110 * i, expires: now + lifetime + 110 * i,
    }))
    setActive((current) => [...current.filter((cue) => cue.expires > now), ...batch].slice(-cueLimit))
  }, [state, online])

  useEffect(() => {
    if (!active.length) return
    const next = Math.min(...active.map((cue) => cue.expires))
    const timer = window.setTimeout(() => {
      setActive((current) => current.filter((cue) => cue.expires > Date.now()))
    }, Math.max(1, next - Date.now()))
    return () => window.clearTimeout(timer)
  }, [active])
  return active
}

export function ShipSilhouette({ kind = 'grain' }: { kind?: 'grain' | 'tug' | 'patrol' }) {
  return (
    <g className="pixel-ship" data-ship-kind={kind}>
      <path className="ship-wake" d="M15 3h9 m-4 3h13 m-14 3h7" />
      <path className="ship-hull" d="M-16-1h3v-2h11v-1h14v4h3v4h-3v2h-22V4h-3V2h-3Z" />
      <path className="ship-shadow" d="M-13 2h25v2h-3v2h-19V4h-3Z" />
      {kind === 'grain' && <path className="ship-cargo" d="M-11-5h6v4h-6Zm7 0h6v4h-6Z" />}
      {kind === 'patrol' && <path className="ship-cargo" d="M-14-4h7v-2h2v4h-9Z" />}
      <path className="ship-deck" d="M3-2v-6h7v2h2v4Z" />
      <path className="ship-window" d="M4-7h4v2H4Z" />
      <path className="ship-mast" d="M8-8v-4h4" />
    </g>
  )
}

function Symbol({ mark }: { mark?: Mark }) {
  if (mark === 'ship') return <ShipSilhouette />
  return (
    <>
      <rect className="motion-counter" x="-11" y="-8" width="22" height="16" rx="2" />
      {mark === 'infantry' && <path d="M-6,-4 H6 V4 H-6 Z M-6,-4 L6,4 M6,-4 L-6,4" />}
      {mark === 'cargo' && <path d="M-5,-4 H5 V4 H-5 Z M0,-4 V4 M-5,0 H5" />}
      {mark === 'signal' && <path d="M-6,-4 H6 V4 H-6 Z M-6,-4 L0,1 L6,-4" />}
    </>
  )
}

function MotionCue({ cue, lane }: { cue: ActiveCue; lane: number }) {
  const [x, y] = cue.at
  const dx = cue.from ? cue.from[0] - x : 0
  const dy = cue.from ? cue.from[1] - y : 0
  const bend = cue.mark === 'ship' || cue.mark === 'infantry' ? 0 : Math.min(32, Math.hypot(dx, dy) * 0.15)
  const tagWidth = Math.max(78, cue.label.length * 6.2 + 16)
  const province = cue.province && provinces.get(cue.province)
  const style = {
    ...(cue.nation ? nationStyle(cue.nation) : {}),
    '--cue-delay': `${cue.delay}ms`, '--cue-x': `${dx}px`, '--cue-y': `${dy}px`,
    '--cue-mid-x': `${dx / 2}px`, '--cue-mid-y': `${dy / 2 - bend}px`,
  } as CSSProperties
  return (
    <g className="motion-cue" data-motion={cue.kind} style={style}>
      {province && <path className="motion-capture" d={province.path} style={cue.formerOwner ? nationStyle(cue.formerOwner) : undefined} />}
      {cue.from && <path className="motion-trail" d={`M${cue.from.join(',')} Q${x + dx / 2},${y + dy / 2 - 2 * bend} ${x},${y}`} />}
      <g transform={`translate(${x} ${y})`}>
        <circle className="motion-ping" r="18" />
        {cue.from && <g className="motion-symbol"><Symbol mark={cue.mark} /></g>}
        <g className="motion-tag" transform={`translate(0 ${-20 * lane})`}>
          <rect x={-tagWidth / 2} y="-32" width={tagWidth} height="17" rx="3" />
          <text y="-20">{cue.label}</text>
        </g>
      </g>
    </g>
  )
}

export function DecisionMotion({ state, online }: { state: GameState; online: boolean }) {
  const cues = useCues(state, online)
  return (
    <g className="decision-motion" aria-hidden="true">
      {cues.map((cue, index) => {
        const lane = cues.slice(0, index).filter(({ at }) =>
          Math.abs(at[0] - cue.at[0]) < 100 && Math.abs(at[1] - cue.at[1]) < 28).length
        return <MotionCue key={cue.id} cue={cue} lane={lane} />
      })}
    </g>
  )
}
