import { memo } from 'react'
import atlas from '../atlas.json'
import rail from '../../../data/rail.json'
import counties from '../../../data/counties.json'
import infrastructure from '../../../data/infrastructure.json'
import type { GameState } from '../state'
import { nationStyle } from '../theme'
import { useMarkerScale } from './scale'
import './cities.css'

type City = { name: string; resource: string; output: number; capital: boolean }
type Point = [number, number]
export const cities: Record<string, City> = rail.cities
export const cityPoints = new Map(atlas.provinces.map(({ id, center }) => [id, center]))
const names: Record<string, string> = { gdp: 'Economy', food: 'Food', oil: 'Oil', chips: 'Chips' }
const countyName = new Map(counties.flatMap((county) => county.provinces.map((id) => [id, county.name] as const)))

// Roof colours by building kind; each lot picks one of five by its palette index.
const roofs: Record<string, string[]> = {
  house: ['#c9c1b2', '#b4735a', '#a7a39a', '#d8d0bf', '#918d86'],
  commercial: ['#a2b3b9', '#8898a1', '#bcc2bd', '#aaa293', '#809399'],
  tower: ['#c6d2d8', '#a2b7c4', '#dadfd8', '#91aab9', '#b6c4c6'],
  industrial: ['#a9ab9f', '#8d9490', '#b9b4a4', '#9c9182', '#818c88'],
  civic: ['#cdae6d', '#bb8f65', '#d6c391', '#aab78c', '#c79f7c'],
}
const rise: Record<string, number> = { house: 1.3, commercial: 3.2, tower: 7, industrial: 2.2, civic: 2.6 }
const fieldTones = ['#c8b25a', '#7fa24c', '#5e8a44', '#a3804f', '#d9c84a', '#98ad68']

const fixed = (n: number) => Math.round(n * 10) / 10

function corners(x: number, y: number, w: number, d: number, degrees: number): Point[] {
  const a = degrees * Math.PI / 180
  const c = Math.cos(a), s = Math.sin(a)
  return [[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]].map(([u, v]) =>
    [x + c * u - s * v, y + s * u + c * v] as Point)
}

function hull(points: Point[]): Point[] {
  const p = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1])
  const cross = (o: Point, a: Point, b: Point) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
  const lower: Point[] = [], upper: Point[] = []
  for (const q of p) {
    while (lower.length > 1 && cross(lower.at(-2)!, lower.at(-1)!, q) <= 0) lower.pop()
    lower.push(q)
  }
  for (const q of p.reverse()) {
    while (upper.length > 1 && cross(upper.at(-2)!, upper.at(-1)!, q) <= 0) upper.pop()
    upper.push(q)
  }
  return [...lower.slice(0, -1), ...upper.slice(0, -1)]
}

const poly = (points: Point[]) => `M${points.map(([x, y]) => `${fixed(x)},${fixed(y)}`).join('L')}Z`
const shift = (points: Point[], dx: number, dy: number) => points.map(([x, y]) => [x + dx, y + dy] as Point)
const line = (points: number[][]) => `M${points.map((point) => point.join(',')).join('L')}`

type Lot = [number, number, number, number, string, number, number]
const districts = infrastructure.settlements.map((settlement) => {
  const roofPaths: Record<string, string> = {}
  let shadows = '', houseWalls = '', walls = '', ridges = '', plant = ''
  for (const lot of settlement.lots as Lot[]) {
    const [x, y, w, d, kind, palette, angle] = lot
    const base = corners(x, y, w, d, angle)
    const h = rise[kind] + (kind === 'tower' ? palette * 1.6 : 0)
    const top = shift(base, 0, -h)
    shadows += poly(hull([...base, ...shift(base, h * .75, h * .38)]))
    const wall = poly(hull([...base, ...top]))
    if (kind === 'house') houseWalls += wall
    else walls += wall
    const colour = roofs[kind][palette]
    roofPaths[colour] = (roofPaths[colour] ?? '') + poly(top)
    const a = angle * Math.PI / 180
    if (kind === 'house') {
      const ux = Math.cos(a) * (w / 2 - .7), uy = Math.sin(a) * (w / 2 - .7)
      ridges += `M${fixed(x - ux)},${fixed(y - uy - h)}L${fixed(x + ux)},${fixed(y + uy - h)}`
    } else {
      // Rooftop plant: a small box toward one corner of offices, towers and sheds.
      plant += poly(corners(x - Math.cos(a) * w * .2, y - Math.sin(a) * w * .2 - h, Math.min(3, w * .3), Math.min(2.4, d * .3), angle))
    }
  }
  const fields: Record<number, string> = {}
  for (const [x, y, w, d, angle, tone] of settlement.fields) {
    fields[tone] = (fields[tone] ?? '') + poly(corners(x, y, w, d, angle))
  }
  const trees = settlement.parks.flatMap(([px, py, r], k) => Array.from({ length: Math.round(r / 2.4) }, (_, i) => {
    const t = i * 2.399 + k
    const q = r * .82 * Math.sqrt((i + .5) / Math.round(r / 2.4))
    return [px + Math.cos(t) * q, py + Math.sin(t) * q] as Point
  }))
  return {
    id: settlement.id, center: settlement.center, radius: settlement.radius, parks: settlement.parks, trees,
    arterials: settlement.streets.filter(([tier]) => tier === 0).map(([, points]) => line(points as number[][])).join(''),
    streets: settlement.streets.filter(([tier]) => tier === 1).map(([, points]) => line(points as number[][])).join(''),
    shadows, houseWalls, walls, ridges, plant, roofPaths, fields,
  }
})

export const UrbanFabric = memo(function UrbanFabric() {
  return <g className="urban-fabric map-decoration" aria-hidden="true">
    <g className="farm-fields">
      {districts.map(({ id, fields }) => Object.entries(fields).map(([tone, d]) =>
        <path key={`${id}:${tone}`} d={d} fill={fieldTones[Number(tone)]} />))}
    </g>
    {districts.map(({ id, center, radius }) =>
      <circle key={id} className="urban-ground" cx={center[0]} cy={center[1]} r={radius * 1.04} />)}
    {districts.map(({ id, parks, trees, arterials, streets, shadows, houseWalls, walls, ridges, plant, roofPaths }) => (
      <g key={id} data-urban-district={id}>
        {parks.map(([x, y, r], i) => <circle key={i} className="urban-park" cx={x} cy={y} r={r} />)}
        <path className="street-casing" d={streets} />
        <path className="arterial-casing" d={arterials} />
        <path className="street-surface" d={streets} />
        <path className="arterial-surface" d={arterials} />
        <path d={shadows} fill="#14261f" opacity=".42" />
        <path d={houseWalls} fill="#6c675e" />
        <path d={walls} fill="#4c585c" />
        {Object.entries(roofPaths).map(([colour, d]) => <path key={colour} d={d} fill={colour} />)}
        <path d={ridges} className="roof-ridge" />
        <path d={plant} fill="#e3dcc6" opacity=".7" />
        {trees.length > 0 && <path className="park-trees" d={trees.map(([x, y]) =>
          `M${fixed(x - 1.6)},${fixed(y)}a1.6,1.6 0 1,0 3.2,0a1.6,1.6 0 1,0 -3.2,0`).join('')} />}
      </g>
    ))}
  </g>
})

export function CityMarkers({ state, onCity }: { state: GameState; onCity: (id: string) => void }) {
  const m = useMarkerScale()
  return <g className="city-markers">
    {Object.entries(cities).map(([id, city]) => {
      const point = cityPoints.get(id)
      const owner = state.provinces[id]
      if (!point || !owner) return null
      return <g key={id} className="city-marker" data-city={id} role="button" tabIndex={0}
        aria-label={`Select ${city.name}`} transform={`translate(${point.join(' ')}) scale(${m})`} style={nationStyle(owner)}
        onClick={() => onCity(id)} onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onCity(id)
          }
        }}>
        <title>{city.name} · {state.nations[owner]?.name}</title>
        <circle r="10" fill="transparent" />
        <path className="city-pin" d={city.capital ? 'M0-4 4 0 0 4-4 0Z' : 'M-2-2H2V2H-2Z'} />
        <text y="-10">{city.name}</text>
      </g>
    })}
  </g>
}

const describe = (income: Record<string, number> | undefined) => Object.entries(income ?? {})
  .map(([resource, amount]) => `+${amount} ${names[resource] ?? resource}`).join(' · ')

export function FreightSummary({ state, province, onClose }: {
  state: GameState; province: string; onClose: () => void
}) {
  const city = cities[province]
  const owner = state.provinces[province]
  if (!city || !owner) return null
  const running = new Set(state.rail_services)
  const connections = rail.routes.flatMap((route) => {
    if (!running.has(route.id)) return []
    if (route.from === province) return [cities[route.to].name]
    if (route.to === province) return [cities[route.from].name]
    return []
  })
  const roads = (state.road_services ?? []).filter((id) => id.split('|').includes(province)).length
  const fields = new Set((state.buildings ?? []).filter((b) => b.kind === 'airfield' && state.provinces[b.province] === owner)
    .map((b) => b.province))
  const airportName = (p: string) => cities[p]?.name ?? countyName.get(p) ?? p.toUpperCase()
  const flights = (state.air_services ?? []).flatMap((id) => {
    const [a, b] = id.split('|')
    if (!fields.has(a) && !fields.has(b)) return []
    return [airportName(fields.has(a) && !fields.has(b) ? b : fields.has(b) && !fields.has(a) ? a : b)]
  })
  return <section className="city-summary" aria-label="City freight">
    <strong>{city.name} <button type="button" aria-label="Close city information" onClick={onClose}>×</button></strong>
    <span>{connections.length ? `Rail freight to ${connections.join(', ')}` : 'No active rail freight'}</span>
    {state.rail_income?.[owner] && <span>Rail: {describe(state.rail_income[owner])} / month</span>}
    <span>{roads ? `${roads} haulage road${roads > 1 ? 's' : ''} through ${city.name}` : 'No haulage passes through'}
      {state.road_income?.[owner] && ` · Roads: ${describe(state.road_income[owner])} / month`}</span>
    <span>{flights.length ? `Flights to ${[...new Set(flights)].join(', ')}` : 'No scheduled flights'}
      {state.air_income?.[owner] && ` · Air: ${describe(state.air_income[owner])} / month`}</span>
  </section>
}
