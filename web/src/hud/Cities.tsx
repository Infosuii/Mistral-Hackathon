import { memo } from 'react'
import atlas from '../atlas.json'
import rail from '../../../data/rail.json'
import infrastructure from '../../../data/infrastructure.json'
import type { GameState } from '../state'
import { nationStyle } from '../theme'
import './cities.css'

type City = { name: string; resource: string; output: number; capital: boolean }
export const cities: Record<string, City> = rail.cities
export const cityPoints = new Map(atlas.provinces.map(({ id, center }) => [id, center]))
const names: Record<string, string> = { gdp: 'Economy', food: 'Food', oil: 'Oil', chips: 'Chips' }
const roofs = ['#adb7b5', '#8c9da0', '#c6bda4', '#91a299', '#a98776']
const districts = infrastructure.settlements.map((settlement) => {
  const roofPaths = roofs.map(() => '')
  let shadows = '', windows = '', walls = '', details = ''
  for (const lot of settlement.lots) {
    const [x, y, w, h, kind, palette] = lot as [number, number, number, number, string, number]
    const rise = kind === 'tower' ? 2.8 + palette * .35 : kind === 'commercial' ? 1.35 : .65
    const roofY = (y - rise).toFixed(1)
    const rect = (xx: number | string, yy: number | string, width: number, height: number) =>
      `M${xx},${yy}h${width.toFixed(1)}v${height.toFixed(1)}h-${width.toFixed(1)}Z`
    shadows += rect((x + rise*.77).toFixed(1), (y + .55).toFixed(1), w + rise*.6, h + 1)
    walls += rect(x, roofY, w, h + rise)
    roofPaths[palette] += rect(x, roofY, w, h)
    if (kind === 'tower' || kind === 'commercial') {
      windows += `M${(x+.45).toFixed(1)},${(y+h-.1).toFixed(1)}h${(w-.8).toFixed(1)}`
      details += rect((x + .55).toFixed(1), (y - rise + .45).toFixed(1), w*.37, h*.28)
    }
    if (kind === 'industrial') {
      details += rect((x+1).toFixed(1), (y-rise+.55).toFixed(1), 2.7, .6)
    }
  }
  return { ...settlement, shadows, walls, windows, details, roofPaths }
})

const streetPath = (points: number[][]) => {
  const [a, b, c] = points
  return `M${a.join(',')} Q${b.join(',')} ${c.join(',')}`
}

export const UrbanFabric = memo(function UrbanFabric() {
  return <g className="urban-fabric map-decoration" aria-hidden="true">
    {districts.map(({ id, streets, shadows, walls, windows, details, roofPaths }) => (
      <g key={id} data-urban-district={id}>
        {streets.map((street, i) => (
          <path key={i} className="urban-street" d={streetPath(street)} />
        ))}
        <path d={shadows} fill="#142722" opacity=".51" />
        <path d={walls} fill="#4b5e62" />
        {roofPaths.map((d, index) => <path key={index} d={d} fill={roofs[index]} />)}
        <path d={details} fill="#e1d9bc" opacity=".73" />
        <path d={windows} stroke="#d6c78f" strokeWidth=".36" strokeDasharray=".55 .58" />
      </g>
    ))}
  </g>
})

export function CityMarkers({ state, onCity }: { state: GameState; onCity: (id: string) => void }) {
  return <g className="city-markers">
    {Object.entries(cities).map(([id, city]) => {
      const point = cityPoints.get(id)
      const owner = state.provinces[id]
      if (!point || !owner) return null
      return <g key={id} className="city-marker" data-city={id} role="button" tabIndex={0}
        aria-label={`Select ${city.name}`} transform={`translate(${point.join(' ')})`} style={nationStyle(owner)}
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
  const income = Object.entries(state.rail_income?.[owner] ?? {})
  return <section className="city-summary" aria-label="City freight">
    <strong>{city.name} <button type="button" aria-label="Close city information" onClick={onClose}>×</button></strong>
    <span>{connections.length ? `Freight to ${connections.join(', ')}` : 'No active freight connections'}</span>
    {income.length > 0 && <span>Rail income: {income.map(([resource, amount]) =>
      `+${amount} ${names[resource] ?? resource}`).join(' · ')} / month</span>}
  </section>
}
