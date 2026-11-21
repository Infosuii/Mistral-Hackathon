import atlas from '../atlas.json'
import infrastructure from '../../../data/infrastructure.json'
import rail from '../../../data/rail.json'
import buildings from '../../../data/buildings.json'
import type { GameState } from '../state'
import { nationStyle } from '../theme'
import './infrastructure.css'

const centers = new Map(atlas.provinces.map(({ id, center }) => [id, center]))
const catalog = buildings.kinds as Record<string, { name: string }>

function location(x: number, y: number) {
  return `translate(${x} ${y})`
}

const linePath = (points: number[][]) => `M${points.map((point) => point.join(',')).join(' L')}`
const roads = infrastructure.roads.map((road) => ({ ...road, path: linePath(road.points) }))

function passable(state: GameState, a: string, b: string) {
  const from = state.provinces[a]
  const to = state.provinces[b]
  if (!from || !to) return false
  if (from === to) return true
  const border = state.links.filter((link) => (link.a === from && link.b === to) || (link.a === to && link.b === from))
  return border.some((link) => link.type === 'trade') && !border.some((link) => link.type === 'war')
}

function Railcar() {
  return (
    <g className="railcar">
      <path fill="#1a3136" d="M-10-2h20v5h-20Z" />
      <path fill="#d8b76d" d="M-9-3h7v4h-7ZM-1-3h6v4h-6ZM6-4h4v5H6Z" />
      <path stroke="#e8e2be" strokeWidth=".7" d="M-7 3h2m7 0h2m3 0h2" />
    </g>
  )
}

export function Transport({ state }: { state: GameState }) {
  const active = new Set(state.rail_services ?? [])
  const railTracks = rail.routes.filter(({ id }) => active.has(id)).map(({ id, points }) => {
    const line = points.map((point) => point.join(','))
    return { id, path: `M${line.join(' L')}`, end: points.at(-1)! }
  })
  const roadTraffic = roads.filter(({ a, b, kind }, i) => (kind === 'motorway' || i % 5 === 0) && passable(state, a, b))
  return (
    <g className="transport map-decoration" aria-hidden="true">
      {roads.map(({ id, path, kind }) => <g key={id} data-road={kind}>
        <path className={`road-edge ${kind}`} d={path} />
        <path className={`road-bed ${kind}`} d={path} />
        {kind === 'motorway' && <path className="road-divider" d={path} />}
      </g>)}
      {roads.flatMap(({ id, bridges }) => bridges.map((bridge, index) => (
        <g key={`${id}:${index}`} data-bridge="river">
          <path className="bridge-edge" d={linePath(bridge)} />
          <path className="bridge-deck" d={linePath(bridge)} />
          <path className="road-divider" d={linePath(bridge)} />
        </g>
      )))}
      {roadTraffic.map(({ id, path, speed, length }, index) => (
        <g key={id} className="mobile-sprite road-traffic" data-traffic={id}>
          <animateMotion path={path} rotate="auto" dur={`${Math.max(8, length / (speed * 10))}s`}
            begin={`-${index % 7}s`} repeatCount="indefinite" />
          <path fill="#202e35" d="M-5-1.5h10v3H-5Z" />
          <path fill={index % 3 === 0 ? '#d4b285' : '#a8bdc5'} d="M-4-1.5h5v3h-5Z" />
          <path fill="#d3e5da" d="M2-1h2v2H2Z" />
        </g>
      ))}
      {railTracks.map(({ id, path, end }, index) => (
        <g key={id} data-freight-route={id}>
          <path className="rail-bed" d={path} />
          <path className="rail-track" d={path} />
          <g className="mobile-sprite">
            <animateMotion path={path} rotate="auto" dur={`${16 + index % 6}s`} begin={`-${index % 8}s`}
              calcMode="linear" keyPoints="0;1;1;0;0" keyTimes="0;.44;.5;.94;1" repeatCount="indefinite" />
            <Railcar />
          </g>
          <g className="static-sprite" transform={location(end[0], end[1])}><Railcar /></g>
        </g>
      ))}
    </g>
  )
}

export function TankSprite() {
  return (
    <g>
      <path fill="#263a32" d="M-9-4h18v8H-9Z" />
      <path fill="var(--nation-fill, #466c59)" d="M-8-3H7v6H-8Z" />
      <path fill="var(--nation-accent, #b7c891)" d="M-3-3h6v6h-6ZM2-1h9v2H2Z" />
      <path stroke="#93aa80" strokeWidth=".8" d="M-9-4h17M-9 4h17" />
    </g>
  )
}

function PlaneSprite() {
  return (
    <g className="fighter-sprite">
      <path fill="#20383e" opacity=".5" transform="translate(3 3)" d="M-19-2h9l5-8h3l-1 8 11 1 8 2-8 2-11 1 1 8h-3l-5-8h-9l2-3Z" />
      <path fill="#1d373e" d="M-19-2h9l5-8h3l-1 8 11 1 8 2-8 2-11 1 1 8h-3l-5-8h-9l2-3Z" />
      <path fill="#afbcb1" d="M-17-1h8l5-8h1l-1 8 11 1 5 1-5 1-11 1 1 8h-1l-5-8h-8l1-2Z" />
      <path fill="#778b89" d="M-8-1-4-7-5 0h8v2h-9v5l-2-4h-4V0Z" />
      <path fill="#365968" d="M4 0h4l2 1-2 1H4Z" />
      <path fill="#e1a666" d="M-16 0h2v2h-2Z" />
      <path fill="#b45143" d="M-5-8h1v1h-1Z" />
      <path fill="#85a786" d="M-5 8h1v1h-1Z" />
    </g>
  )
}

function FacilityArt({ kind }: { kind: string }) {
  if (kind === 'airfield') return (
    <>
      <path fill="#788079" d="M-25-12H30V14H-25Z" />
      <path fill="#a3a59a" d="M-24-8h48v1h-48ZM-20 5h43v2h-43ZM17-7h2v12h-2ZM-15-7h2v12h-2Z" />
      <path fill="#3b494b" d="M-24-6h52v8h-52Z" />
      <path stroke="#e6ddbd" strokeWidth=".75" strokeDasharray="3 2" d="M-22-2H25" />
      <path stroke="#f0e7ce" strokeWidth="1.3" d="M-21-5v2m2-2v2m42-2v2m2-2v2" />
      <path fill="#536568" d="M-8 8H12v4H-8ZM17 8h8v4h-8Z" />
      <path fill="#c4c7b6" d="M-9 7H13v2H-9ZM17 7h8v2h-8Z" />
      <path stroke="#d8c89e" strokeWidth=".65" d="M-5 5v2m4-2v2m4-2v2m4-2v2m4-2v2" />
    </>
  )
  if (kind === 'farm') return (
    <>
      <path fill="#767a45" d="M-11-4h18l5 8H-8Z" />
      <path stroke="#e2c277" strokeWidth="1.3" d="m-8-3 4 6m0-6 4 6m0-6 4 6m0-6 4 6" />
      <path fill="#9c644b" d="M7-6h7v8H7Z" />
      <path fill="#d5aa7e" d="M6-7h9v2H6Z" />
    </>
  )
  if (kind === 'army_base') return (
    <>
      <path fill="#545941" d="M-13-6h25v11h-25Z" />
      <path fill="#b8ad81" d="M-12-5h11v4h-11ZM2-5h9v4H2Z" />
      <path fill="#243e37" d="M-11 0h6v4h-6ZM4 0h6v4H4Z" />
      <path fill="var(--nation-accent)" d="M-2-12h6v3h-6Z" />
      <path stroke="#ded3ac" strokeWidth="1" d="M-2-12v7" />
    </>
  )
  if (kind === 'freight_yard') return (
    <>
      <path fill="#5a6660" d="M-12-5h22v8h-22Z" />
      <path fill="#c6ae67" d="M-10-4h7v5h-7ZM-1-4h7v5h-7Z" />
      <path stroke="#dfd9b7" d="M-13 3h27m-26 2h25" />
    </>
  )
  return (
    <>
      <path fill="#655142" d="M-12-4h18v10h-18Z" />
      <path fill={kind === 'chip_works' ? '#81b9c3' : '#bda390'} d="M-12-6h6v3h2v-3h6v3h3v6h-17Z" />
      <path fill="#303f46" d="M-9 0h2v3h-2ZM-4 0h2v3h-2ZM1 0h2v3H1Z" />
      <path fill={kind === 'arms_factory' ? '#df815c' : '#9e7a65'} d="M7-11h4v16H7Z" />
      <path fill="#ddd2a8" d="M7-11h4v2H7Z" />
    </>
  )
}

export function Facilities({ state }: { state: GameState }) {
  const slots = new Map<string, number>()
  return (
    <g className="facility-layer map-decoration">
      {(state.buildings ?? []).map(({ province, kind }) => {
        const center = centers.get(province)
        const owner = state.provinces[province]
        if (!center || !owner) return null
        const slot = slots.get(province) ?? 0
        slots.set(province, slot + 1)
        return (
          <g key={`${province}:${kind}`} data-facility={kind} data-province-site={province}
            transform={location(center[0] - 18 + slot * 20, center[1] + 8 + (slot % 2) * 16)} style={nationStyle(owner)}>
            <title>{catalog[kind]?.name ?? kind} · {state.nations[owner]?.name}</title>
            <ellipse cy="4" rx="16" ry="4" fill="#173c36" opacity=".36" />
            <FacilityArt kind={kind} />
            {kind === 'army_base' && state.nations[owner]?.stats.army > 0 && (
              <g transform="translate(12 15)">
                <g className="mobile-sprite">
                  <animateMotion path="M0 0 C14 3 21 4 23 13 S10 24 0 0" dur="13s" rotate="auto" repeatCount="indefinite" />
                  <TankSprite />
                </g>
                <g className="static-sprite"><TankSprite /></g>
              </g>
            )}
            {kind === 'airfield' && (
              <g transform="translate(12 -14)">
                <g className="mobile-sprite">
                  <animateMotion path="M0 0 C47 -42 72 -22 58 5 S0 48 -30 15 S-18 -18 0 0" dur="19s" rotate="auto" repeatCount="indefinite" />
                  <PlaneSprite />
                </g>
                <g className="static-sprite"><PlaneSprite /></g>
              </g>
            )}
          </g>
        )
      })}
    </g>
  )
}

export function CityArt({ economy }: { economy: number }) {
  return (
    <g className="city-skyline">
      <ellipse cy="7" rx="28" ry="7" fill="#1b463a" opacity=".45" />
      <path fill="#936b54" d="M-24 7V1h7v6ZM-15 8V-1h8v9ZM12 8V1h7v7ZM21 5v-6h6v6Z" />
      <path fill="#dfc58f" d="M-24 0h7v3h-7ZM-15-2h8v3h-8ZM12 0h7v3h-7ZM21-2h6v2h-6Z" />
      <path fill="#6f7f7d" d="M-11 4v-15h6v15Zm18 0v-16h7V4Z" />
      <path fill="#a7b0a1" d="M-11-11h5v2h-5ZM7-13h7v2H7Z" />
      <path fill="#b59a71" d="M-6 7V-6h3v-9h6v9h4V7Z" />
      <path fill="var(--nation-accent)" d="M-2-16h5v-3h-5Z" />
      <path fill="#213439" d="M-9-7h1v2h-1Zm0 4h1v2h-1Zm2-4h1v2h-1Zm0 4h1v2h-1Zm16-5h2v2H9Zm0 4h2v2H9ZM-1 3h3v4h-3Z" />
      <path stroke="#e2c991" d="M-8 7H9" />
      {economy >= 55 && <path fill="#7b928a" d="M-21 3v-7h4v7Zm35 4v-10h5V7Z" />}
      {economy >= 75 && <path fill="#bbc4b2" d="M-20-1h2v1h-2ZM16-1h2v2h-2Zm0 4h2v2h-2ZM-15-3v-5h4v7Z" />}
    </g>
  )
}
