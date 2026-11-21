import atlas from '../atlas.json'
import buildings from '../../../data/buildings.json'
import type { GameState } from '../state'
import { nationStyle } from '../theme'
import './infrastructure.css'

const centers = new Map(atlas.provinces.map(({ id, center }) => [id, center]))
const catalog = buildings.kinds as Record<string, { name: string }>

function location(x: number, y: number) {
  return `translate(${x} ${y})`
}

const connections = atlas.borders.flatMap(({ between: [a, b] }) => {
  const start = centers.get(a)
  const end = centers.get(b)
  if (!start || !end) return []
  const distance = Math.hypot(start[0] - end[0], start[1] - end[1])
  const mx = (start[0] + end[0]) / 2 + (end[1] - start[1]) * .1
  const my = (start[1] + end[1]) / 2 - (end[0] - start[0]) * .1
  return [{ a, b, distance, end, path: `M${start.join(',')} Q${mx},${my} ${end.join(',')}` }]
}).sort((a, b) => a.distance - b.distance)

function roadNetwork(state: GameState) {
  const parent = new Map<string, string>()
  const root = (province: string): string => {
    const next = parent.get(province)
    return next ? root(next) : province
  }
  return connections.filter(({ a, b }) => {
    if (state.provinces[a] !== state.provinces[b]) return false
    const west = root(a)
    const east = root(b)
    if (west === east) return false
    parent.set(east, west)
    return true
  })
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
  const freight = new Set((state.buildings ?? [])
    .filter(({ kind }) => ['arms_factory', 'factory', 'freight_yard'].includes(kind))
    .map(({ province }) => province))
  const roads = roadNetwork(state)
  const railTracks = roads.filter(({ a, b }) => freight.has(a) || freight.has(b))
  const roadTraffic = roads.filter(({ a, b }, i) => i % 5 === 0 && !freight.has(a) && !freight.has(b))
  return (
    <g className="transport map-decoration" aria-hidden="true">
      {roads.map(({ a, b, path }) => <path key={`${a}:${b}`} className="local-road" d={path} />)}
      {roadTraffic.map(({ a, b, path }) => (
        <g key={`truck:${a}:${b}`} className="mobile-sprite road-traffic">
          <animateMotion path={path} rotate="auto" dur="12s" repeatCount="indefinite" />
          <path fill="#30434a" d="M-6-2h12v5H-6Z" />
          <path fill="#d5c49e" d="M-5-2h6v4h-6Z" />
          <path fill="#9bbbba" d="M2-2h3v3H2Z" />
        </g>
      ))}
      {railTracks.map(({ a, b, path, end }, index) => (
        <g key={`${a}:${b}`}>
          <path className="rail-bed" d={path} />
          <path className="rail-track" d={path} />
          <g className="mobile-sprite">
            <animateMotion path={path} rotate="auto" dur={`${8 + index % 4}s`} begin={`-${index % 8}s`} repeatCount="indefinite" />
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
    <g>
      <path fill="#173440" stroke="#0b2025" strokeWidth="1.3" d="M-13-1h9l3-7h3l-1 7h10l2 2-2 2H1l1 6h-3l-3-6h-7l-2 2Z" />
      <path fill="#e7ede3" d="M-12 0h9l3-7h1l-1 7h12l1 1-1 1H0l1 6H0l-3-6h-8l-1 1Z" />
      <path fill="#6392a0" d="M7 0h3v2H7Z" />
    </g>
  )
}

function FacilityArt({ kind }: { kind: string }) {
  if (kind === 'airfield') return (
    <>
      <path fill="#3e5758" d="M-18 2-12-6H22L16 3Z" />
      <path stroke="#e3e4cd" strokeWidth="1.1" strokeDasharray="3 3" d="M-13-1H18" />
      <path fill="#8f9d98" d="M2-7h12v5H2Z" />
      <path fill="#cfdbcc" d="M2-8h11v2H2Z" />
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
