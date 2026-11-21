import { memo } from 'react'
import atlas from '../atlas.json'
import infrastructure from '../../../data/infrastructure.json'
import rail from '../../../data/rail.json'
import buildings from '../../../data/buildings.json'
import type { GameState } from '../state'
import { nationStyle } from '../theme'
import sea from '../../../data/sea_routes.json'
import { useMarkerScale } from './scale'
import { Tank, Vessel, Wagon } from './sprites'
import './infrastructure.css'

const centers = new Map(atlas.provinces.map(({ id, center }) => [id, center]))
const catalog = buildings.kinds as Record<string, { name: string }>
type Airport = { at: number[]; angle: number; length: number }
const settlements = new Map(infrastructure.settlements.map((s) => [s.id, s as typeof s & { airport: Airport | null }]))

export const linePath = (points: number[][]) => `M${points.map((point) => point.join(',')).join(' L')}`
export const roads = infrastructure.roads.map((road) => ({ ...road, path: linePath(road.points) }))
export const pace = (kind: string) => kind === 'motorway' ? 1 : .72

/** Where an airfield in this province sits: its generated airport site, or beside the town. */
export function airportOf(province: string): Airport {
  const site = settlements.get(province)?.airport
  if (site) return site
  const [x, y] = centers.get(province) ?? [0, 0]
  return { at: [x + 60, y + 60], angle: 0, length: 70 }
}

export function facilitySite(province: string, slot: number) {
  const sites = settlements.get(province)?.sites ?? []
  if (sites.length) return sites[slot % sites.length] as number[]
  const [x, y] = centers.get(province) ?? [0, 0]
  return [x - 40 + slot * 30, y + 50]
}

function closure(state: GameState, a: string, b: string): 'war' | 'closed' | null {
  const from = state.provinces[a]
  const to = state.provinces[b]
  if (!from || !to || from === to) return null
  const border = state.links.filter((link) => (link.a === from && link.b === to) || (link.a === to && link.b === from))
  if (border.some((link) => link.type === 'war')) return 'war'
  return border.some((link) => link.type === 'trade') ? null : 'closed'
}

export function midpoint(points: number[][]) {
  const lengths = points.slice(1).map((p, i) => Math.hypot(p[0] - points[i][0], p[1] - points[i][1]))
  let half = lengths.reduce((sum, l) => sum + l, 0) / 2
  for (let i = 0; i < lengths.length; i++) {
    if (half <= lengths[i]) {
      const t = half / lengths[i]
      const [a, b] = [points[i], points[i + 1]]
      return { x: a[0] + (b[0] - a[0]) * t, y: a[1] + (b[1] - a[1]) * t, angle: Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI }
    }
    half -= lengths[i]
  }
  return { x: points[0][0], y: points[0][1], angle: 0 }
}

/** The fixed network: roads, interchanges, bridges and rail beds. Memoised: it never changes. */
export const Network = memo(function Network() {
  return <g className="road-network">
    {(['road', 'motorway'] as const).map((kind) => <g key={kind}>
      <path className={`road-edge ${kind}`} d={roads.filter((r) => r.kind === kind).map((r) => r.path).join('')} />
    </g>)}
    {(['road', 'motorway'] as const).map((kind) => <g key={kind}>
      <path className={`road-bed ${kind}`} d={roads.filter((r) => r.kind === kind).map((r) => r.path).join('')} />
    </g>)}
    <path className="road-divider" d={roads.filter((r) => r.kind === 'motorway').map((r) => r.path).join('')} />
    {roads.flatMap(({ id, bridges, kind }) => bridges.map((bridge, index) => (
      <g key={`${id}:${index}`} data-bridge="river" data-road={kind}>
        <path className={`bridge-edge ${kind}`} d={linePath(bridge)} />
        <path className={`bridge-deck ${kind}`} d={linePath(bridge)} />
        {kind === 'motorway' && <path className="road-divider" d={linePath(bridge)} />}
      </g>
    )))}
    {infrastructure.junctions.map(([x, y, angle, kind], i) => (
      <g key={i} className={`junction ${kind}`} transform={`translate(${x} ${y}) rotate(${angle})`}>
        {kind === 'interchange' ? <>
          <path className="ramp-edge" d="M0-15a9 9 0 1 1 0 .1M0 15a9 9 0 1 1 0-.1M-15 0a9 9 0 1 1 .1 0M15 0a9 9 0 1 1-.1 0" />
          <path className="ramp" d="M0-15a9 9 0 1 1 0 .1M0 15a9 9 0 1 1 0-.1M-15 0a9 9 0 1 1 .1 0M15 0a9 9 0 1 1-.1 0" />
          <path className="cross-edge" d="M-26 0H26M0-26V26" />
          <path className="cross" d="M-26 0H26M0-26V26" />
        </> : <>
          <circle className="ramp-edge" r="6.5" />
          <circle className="ramp" r="6.5" />
          <circle className="roundabout-island" r="3" />
        </>}
      </g>
    ))}
    {rail.routes.map(({ id, points, bridges }) => <g key={id} data-rail-bed={id}>
      {(bridges ?? []).map((span, i) => <path key={i} className="rail-bridge" data-bridge="rail" d={linePath(span)} />)}
      <path className="rail-bed" d={linePath(points)} />
      <path className="rail-ties" d={linePath(points)} />
    </g>)}
  </g>
})

/** Engine buildings placed on the map: airfields at their airport, the rest on industrial sites. */
export function facilityPlacements(state: GameState) {
  const slots = new Map<string, number>()
  return (state.buildings ?? []).flatMap((building) => {
    const owner = state.provinces[building.province]
    if (!owner || !centers.get(building.province)) return []
    if (building.kind === 'airfield') {
      const { at, angle, length } = airportOf(building.province)
      return [{ ...building, owner, x: at[0], y: at[1], angle, length }]
    }
    const slot = slots.get(building.province) ?? 0
    slots.set(building.province, slot + 1)
    const [x, y] = facilitySite(building.province, slot)
    return [{ ...building, owner, x, y, angle: 0, length: 0 }]
  })
}

/** Smokestack tops, relative to a district's origin, for the motion layer's smoke. */
export const kindNames = catalog

export const STACKS: Record<string, number[][]> = {
  arms_factory: [[13, -4], [21, -4]], factory: [[13, -4], [21, -4]], chip_works: [[22, -13]],
}

/** Ports with the bearing out to open water, taken from the first leg of their sea lanes. */
export const harbours = Object.entries(sea.ports).map(([nation, { province, position }]) => {
  const lane = Object.entries(sea.routes as Record<string, number[][]>).find(([key]) => key.split('|').includes(nation))
  const route = lane ? (lane[0].split('|')[0] === nation ? lane[1] : [...lane[1]].reverse()) : [position, [position[0] + 1, position[1]]]
  const next = route.find((point) => Math.hypot(point[0] - position[0], point[1] - position[1]) > 30) ?? route[1]
  const angle = Math.atan2(next[1] - position[1], next[0] - position[0]) * 180 / Math.PI
  return { nation, province, x: position[0], y: position[1], angle }
})

export function TransportStatic({ state }: { state: GameState }) {
  const m = useMarkerScale()
  const active = new Set(state.rail_services ?? [])
  const barriers = roads.flatMap((road) => {
    const status = closure(state, road.a, road.b)
    return status ? [{ ...road, status, mid: midpoint(road.points) }] : []
  })
  return (
    <g className="transport map-decoration" aria-hidden="true">
      <Network />
      {rail.routes.filter(({ id }) => active.has(id)).map(({ id, points }) =>
        <path key={id} className="rail-track" data-freight-route={id} d={linePath(points)} />)}
      {barriers.map(({ id, status, mid }) => (
        <g key={id} className="border-barrier" data-closed={status} data-road-closed={id}
          transform={`translate(${mid.x} ${mid.y}) rotate(${mid.angle}) scale(${Math.max(1, m * .8)})`}>
          <title>{status === 'war' ? 'Border closed by war' : 'Border closed: no trade agreement'}</title>
          <path className="barrier-arm" d="M0-9V9" />
          <path className="barrier-stripe" d="M0-9V9" />
        </g>
      ))}
    </g>
  )
}

/** Used by capture animations. */
export function TankSprite() {
  return <g transform="scale(1.4)"><Tank /></g>
}

/** A runway, parallel taxiway, apron, terminal and hangars, laid out along the runway heading. */
function AirportArt({ length }: { length: number }) {
  const half = length / 2
  return <>
    <path fill="#8b927f" d={`M${-half - 8}-11H${half + 8}V27H${-half - 8}Z`} opacity=".6" />
    <path fill="#2c3537" d={`M${-half}-5H${half}V5H${-half}Z`} />
    <path stroke="#e9e2c6" strokeWidth=".8" strokeDasharray="5 4" d={`M${-half + 8} 0H${half - 8}`} />
    <path stroke="#f2ead3" strokeWidth="1.1" d={`M${-half + 2}-3.5v7m2-7v7m2-7v7M${half - 2}-3.5v7m-2-7v7m-2-7v7`} />
    <path fill="none" stroke="#596366" strokeWidth="2.4" d={`M${-half + 6} 3V10H${half - 6}V3M-12 10v4m24-4v4`} />
    <path fill="#8a908b" d="M-30 13H30V24H-30Z" />
    <path fill="#d5d9d0" d="M-24 15H8V22H-24Z" />
    <path fill="#4e7a93" d="M-23 16H7V18H-23Z" />
    <path fill="#b8b1a4" d="M12 14H27V23H12Z" />
    <path fill="#6e6a60" d="M12 14H27V15.5H12Z" />
    <path stroke="#e9c46a" strokeWidth=".7" d="M-28 25H28" />
    <g transform="translate(-14 19) scale(.55)"><path fill="#eef1ec" d="M-13-1.2h20l6 1.2-6 1.2h-20ZM-2-1-8-12h3l9 11ZM-2 1-8 12h3l9-11Z" /></g>
  </>
}

const STAMP = 'M-34-26H34V26H-34Z'
function District({ kind }: { kind: string }) {
  if (kind === 'army_base') return <>
    <ellipse rx="62" ry="44" fill="none" stroke="#8e7f5c" strokeWidth="3.2" opacity=".85" />
    <path d={STAMP} fill="#59633f" />
    <path d={STAMP} fill="none" stroke="#ddd6b2" strokeWidth=".8" strokeDasharray="2.2 1.6" />
    <path fill="#8d8b70" d="M-30-22h24v18h-24Z" />
    <path fill="#c4b98f" d="M0-22h30v5H0Zm0 8h30v5H0Zm0 8h30v5H0Z" />
    <path stroke="#7c7258" strokeWidth=".5" d="M0-19.5h30M0-11.5h30M0-3.5h30" />
    <path fill="#454c3b" d="M-30 1h30v9h-30Z" />
    <path fill="#2f3529" d="M-28 2.5h5v6h-5Zm7 0h5v6h-5Zm7 0h5v6h-5Zm7 0h5v6h-5Z" />
    <g transform="translate(-24 18)"><Tank /></g>
    <g transform="translate(-12 18)"><Tank /></g>
    <g transform="translate(0 18)"><Tank /></g>
    <circle cx="19" cy="13" r="7.5" fill="#3b4237" stroke="#e0d9b8" strokeWidth=".8" />
    <path stroke="#e0d9b8" strokeWidth="1.1" d="M16.5 10v6m5-6v6m-5-3h5" />
    <path stroke="#e7e1c4" strokeWidth=".7" d="M-31-23v-9" />
    <path fill="var(--nation-accent)" d="M-31-32h7v4h-7Z" />
    <path fill="#3f4636" d="M28 20h5v5h-5Z" />
  </>
  if (kind === 'arms_factory' || kind === 'factory') {
    const accent = kind === 'arms_factory' ? '#c4573d' : '#c99556'
    return <>
      <path d="M-34-24H34V24H-34Z" fill="#5d6260" />
      <path fill="#a3a596" d="M-30-20H4V4h-34Z" />
      <path stroke="#6e716a" strokeWidth="1" d="M-30-15H4M-30-10H4M-30-5H4M-30 0H4" />
      <path fill="#f0ead6" opacity=".35" d="M-30-20H4v2h-34Z" />
      <path fill="#8f938a" d="M8-20h22v12H8Z" />
      <path fill={accent} d="M8-20h22v2H8Z" />
      <circle cx="13" cy="-4" r="2.8" fill="#4f4438" /><circle cx="21" cy="-4" r="2.8" fill="#4f4438" />
      <circle cx="13" cy="-4" r="1.4" fill="#1d1a16" /><circle cx="21" cy="-4" r="1.4" fill="#1d1a16" />
      <circle cx="-20" cy="14" r="6" fill="#cfc9b3" /><circle cx="-6" cy="14" r="6" fill="#cfc9b3" />
      <circle cx="-20" cy="14" r="3" fill="#b5ae96" /><circle cx="-6" cy="14" r="3" fill="#b5ae96" />
      <path fill="#3f6f8f" d="M6 10h8v3.5H6Z" /><path fill={accent} d="M15 10h8v3.5h-8Z" /><path fill="#7a9a5c" d="M6 15h8v3.5H6Z" />
      <path fill="#d0b25e" d="M15 15h8v3.5h-8Z" /><path fill="#3f6f8f" d="M24 15h7v3.5h-7Z" />
      {kind === 'arms_factory' && <g transform="translate(27 2)"><Tank /></g>}
    </>
  }
  if (kind === 'chip_works') return <>
    <path d="M-34-24H34V24H-34Z" fill="#6c7774" />
    <path fill="#e7ebe6" d="M-30-20h40v22h-40Z" />
    <path fill="#7eb6c9" d="M-28-17h36v3h-36Zm0 6h36v3h-36Zm0 6h36v3h-36Z" opacity=".8" />
    <path fill="#d9ded8" d="M14-20h16v12H14Z" />
    <circle cx="22" cy="-13" r="2.2" fill="#8b9693" />
    <path fill="#3b4547" d="M-30 6h60v16h-60Z" />
    <path stroke="#e3e0cc" strokeWidth=".5" d="M-26 6v16m6-16v16m6-16v16m6-16v16m6-16v16m6-16v16m6-16v16m6-16v16m6-16v16" />
  </>
  if (kind === 'farm') return <>
    <path d="M-34-24H34V24H-34Z" fill="#8a8a4e" />
    <path stroke="#c8b36a" strokeWidth="2" d="M-32-20H32M-32-14H32M-32-8H32" />
    <path fill="#a33f32" d="M-28 0h20v14h-20Z" /><path fill="#d1b48c" d="M-28 0h20v2h-20Z" />
    <circle cx="4" cy="6" r="6" fill="#cfcabb" /><circle cx="16" cy="6" r="6" fill="#cfcabb" /><circle cx="28" cy="6" r="5" fill="#b9b4a5" />
    <circle cx="4" cy="6" r="2" fill="#a8a291" /><circle cx="16" cy="6" r="2" fill="#a8a291" />
  </>
  if (kind === 'freight_yard') return <>
    <path d="M-34-24H34V24H-34Z" fill="#5b5f58" />
    <path stroke="#c9bfa0" strokeWidth=".8" d="M-34-16H34M-34-8H34M-34 0H34M-34 8H34" />
    <g transform="translate(-20 -16)"><Wagon kind={0} /></g><g transform="translate(-6 -16)"><Wagon kind={2} /></g>
    <g transform="translate(10 -8)"><Wagon kind={1} /></g><g transform="translate(-14 0)"><Wagon kind={4} /></g>
    <g transform="translate(18 8)"><Wagon kind={0} /></g>
    <path fill="none" stroke="#e0a83a" strokeWidth="1.6" d="M-30 14V-22M-30-22H6V14" />
    <path fill="#3f6f8f" d="M-26 14h8v4h-8Z" /><path fill="#c4573d" d="M-16 14h8v4h-8Z" /><path fill="#7a9a5c" d="M-6 14h8v4h-8Z" />
  </>
  return null
}

export function Facilities({ state }: { state: GameState }) {
  return (
    <g className="facility-layer map-decoration">
      {facilityPlacements(state).map(({ province, kind, owner, x, y, angle, length }) => (
        <g key={`${province}:${kind}`} data-facility={kind} data-province-site={province} style={nationStyle(owner)}
          transform={`translate(${x} ${y})${kind === 'airfield' ? ` rotate(${angle})` : ''}`}>
          <title>{catalog[kind]?.name ?? kind} · {state.nations[owner]?.name}</title>
          {kind === 'airfield' ? <AirportArt length={length} /> : <District kind={kind} />}
        </g>
      ))}
    </g>
  )
}

/** Quays, cranes, container stacks and a naval pier at each national port. */
export function Harbours({ state }: { state: GameState }) {
  return (
    <g className="harbour-layer map-decoration">
      {harbours.map(({ nation, province, x, y, angle }) => {
        const owner = state.provinces[province] ?? nation
        return (
          <g key={nation} data-harbour={nation} transform={`translate(${x} ${y}) rotate(${angle})`} style={nationStyle(owner)}>
            <path fill="#6f746d" d="M-18-46H8V46h-26Z" />
            <path fill="#9a9c92" d="M8-44h46v8H8Zm0 22h52v8H8Zm0 22h52v8H8Zm0 22h46v8H8Z" />
            <path fill="#53595a" d="M8-38h46v2H8Zm0 22h52v2H8Zm0 22h52v2H8Zm0 22h46v2H8Z" />
            <path fill="#3f6f8f" d="M-14-40h8v5h-8Zm0 7h8v5h-8Z" /><path fill="#c4573d" d="M-4-40h8v5h-8Zm0 14h8v5h-8Z" />
            <path fill="#d0b25e" d="M-14-26h8v5h-8Zm10 7h8v5h-8Z" /><path fill="#7a9a5c" d="M-14-12h8v5h-8Z" />
            <path fill="none" stroke="#e0a83a" strokeWidth="1.8" d="M20-46v14M40-24v14" />
            <path fill="none" stroke="#e0a83a" strokeWidth="1.1" d="M14-46h14M34-24h14" />
            <g transform="translate(32 -29)"><Vessel kind="cargo" /></g>
            <g transform="translate(30 17) rotate(180)"><Vessel kind="frigate" /></g>
            <g transform="translate(28 39)"><Vessel kind="destroyer" /></g>
            <path fill="var(--nation-accent)" d="M-16 30h6v4h-6Z" />
          </g>
        )
      })}
    </g>
  )
}
