import { memo } from 'react'
import atlas from '../atlas.json'
import rail from '../../../data/rail.json'
import type { GameState } from '../state'
import { nationStyle } from '../theme'
import './cities.css'

type City = { name: string; resource: string; output: number; capital: boolean }
export const cities: Record<string, City> = rail.cities
export const cityPoints = new Map(atlas.provinces.map(({ id, center }) => [id, center]))
const names: Record<string, string> = { gdp: 'Economy', food: 'Food', oil: 'Oil', chips: 'Chips' }

export function RuralSettlements() {
  return <g className="rural-layer map-decoration">
    {atlas.provinces.filter(({ id }) => !cities[id]).map(({ id, center: [x, y] }) => (
      <g key={id} transform={`translate(${x - 11} ${y + 10})`}>
        <path fill="#646b51" opacity=".84" d="M-10-3h26v11h-26Z" />
        <path fill="#ad9776" d="M-8 0h5v5h-5ZM-2-3h5V2h-5ZM5 2h6v4H5ZM9-4h5v4H9Z" />
        <path stroke="#d3b9a3" strokeWidth="1" d="M-9 0h7m0-3h6m1 5h6m-3-6h7" />
        <path fill="#365239" d="M-8 6h3v2h-3ZM2 4h3v2H2Z" />
      </g>
    ))}
  </g>
}

export function CityMarkers({ state, onCity }: { state: GameState; onCity: (id: string) => void }) {
  return <g className="city-markers">
    {Object.entries(cities).map(([id, city]) => {
      const point = cityPoints.get(id)
      const owner = state.provinces[id]
      if (!point || !owner) return null
      return <g key={id} className="city-marker" data-city={id} role="button" tabIndex={0}
        aria-label={`Explore ${city.name}`} transform={`translate(${point.join(' ')})`} style={nationStyle(owner)}
        onClick={() => onCity(id)} onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onCity(id)
          }
        }}>
        <title>{city.name} · {state.nations[owner]?.name}</title>
        <circle r="12" fill="transparent" />
        <path className="city-pin" d={city.capital ? 'M0-6 6 0 0 6-6 0Z' : 'M-3-3H3V3H-3Z'} />
        <text y="-10">{city.name}</text>
      </g>
    })}
  </g>
}

function random(seed: number) {
  let value = seed || 1
  return () => {
    value = (Math.imul(value, 1664525) + 1013904223) >>> 0
    return value / 4294967296
  }
}

const roofs = ['#818b88', '#b7a485', '#72868e', '#a5a288', '#9a7160', '#576872', '#8f9f96', '#c6b58f']
const columns = [-65, -42, -19, 4, 27, 50]
const rows = [-57, -35, -13, 18, 40, 62]
const roadColumns = [-69, -46, -23, 0, 23, 46, 69]
const roadRows = [-61, -39, -17, 14, 36, 58, 80]

function Building({ x, y, width, depth, floors, color, industrial }: {
  x: number; y: number; width: number; depth: number; floors: number; color: string; industrial: boolean
}) {
  const height = floors * 2
  return <g transform={`translate(${x} ${y})`}>
    <path d={`M5 3h${width + 4}v${depth + 4}H5Z`} fill="#152223" opacity=".42" />
    <path d={`M0 0h${width}v${depth + height}H0Z`} fill={color} />
    <path d={`M0 ${depth}h${width}v${height}H0Z`} fill="#3a4c54" />
    <path d={`M${width - 2} 2h2v${depth + height - 2}h-2Z`} fill="#263940" opacity=".45" />
    <path d={`M0 0h${width}v1H0Z`} fill="#d1c7ad" />
    <rect x="2" y="2" width={Math.max(2, width - 5)} height={Math.max(2, depth - 4)} fill="#182e37" opacity=".23" />
    {[1, 2, 3].slice(0, floors).map((row) => (
      <path key={row} d={`M2 ${depth + row * 2 - 1}h${Math.max(2, width - 5)}`}
        stroke="#d3c9a5" strokeWidth=".65" strokeDasharray="1 1" opacity=".75" />
    ))}
    <path d={`M2 2h4v3H2Zm${width - 8} 2h3v4h-3Z`} fill="#bdc4b1" opacity=".66" />
    {industrial && <><path d="M3-2h2v6H3ZM8-3h2v7H8Z" fill="#ac775d" />
      <path d="M3-2h2M8-3h2" stroke="#f0ddbd" strokeWidth="1" /></>}
  </g>
}

const CityBlocks = memo(function CityBlocks({ id, capital, industrial }: { id: string; capital: boolean; industrial: boolean }) {
  const rng = random(Number(id.slice(1)) * 4051)
  const blocks = rows.flatMap((y, row) => columns.map((x, col) => ({ x, y, row, col, key: `${row}:${col}` })))
  return <>
    <path d="M-77-66H76V85H-77Z" fill="#757759" />
    {roadColumns.map((x) => <path key={x} d={`M${x}-66V85`} className="city-street" />)}
    {roadRows.map((y) => <path key={y} d={`M-77 ${y}H76`} className="city-street" />)}
    {roadColumns.map((x) => <path key={x} d={`M${x}-66V85`} className="city-lane" />)}
    {roadRows.map((y) => <path key={y} d={`M-77 ${y}H76`} className="city-lane" />)}
    {blocks.map(({ x, y, row, col, key }) => {
      const seed = rng()
      const park = (row === 2 && col === 3) || ((row === 0 || row === 5) && seed < .15)
      const yard = (row === 2 && col >= 4) || (industrial && col > 3 && seed > .61)
      const houses = !yard && (row === 0 || row === 5 || col === 0) && seed > .33
      const civic = row === 3 && col === 3
      const color = roofs[Math.floor(rng() * roofs.length)]
      const floors = capital && row > 0 && row < 5 ? 2 + Math.floor(rng() * 4) : 1 + Math.floor(rng() * 3)
      const deep = row === 2 ? 10 : 7
      return <g key={key}>
        <rect x={x - .5} y={y - .5} width="17" height={row === 2 ? 23 : 16}
          fill={park ? '#59754e' : yard ? '#686f68' : houses ? '#737951' : '#aba18b'} />
        {park ? <>
          <path d={`M${x} ${y + 10}h16M${x + 8} ${y}v19`} stroke="#b7b38e" strokeWidth="1.4" />
          {[0, 1, 2, 3, 4, 5].map((i) => <circle key={i} cx={x + 3 + i % 3 * 5} cy={y + 4 + Math.floor(i / 3) * 10} r="1.7" fill="#334e39" />)}
        </> : yard ? <>
          <Building x={x + 2} y={y + 1} width={13} depth={5} floors={1} color="#87928c" industrial />
          {['#af735c', '#4d7078', '#bd9b62', '#9d5549'].map((shade, i) => (
            <rect key={shade} x={x + 2 + (i % 2) * 7} y={y + 10 + Math.floor(i / 2) * 4} width="5.4" height="2.4" fill={shade} />
          ))}
        </> : houses ? <>
          {[0, 1, 2].map((i) => <Building key={i} x={x + 1 + (i % 2) * 8} y={y + 1 + Math.floor(i / 2) * 7}
            width={6} depth={3} floors={1} color={roofs[(i + Math.floor(seed * roofs.length)) % roofs.length]} industrial={false} />)}
          <circle cx={x + 13} cy={y + 11} r="2" fill="#3c563b" />
        </> : <>
          <Building x={x + (civic ? 1 : 2 - Math.floor(seed * 2))} y={y + 1} width={civic ? 15 : 8 + Math.floor(rng() * 7)}
            depth={deep} floors={civic ? 2 : floors} color={civic ? '#c4b293' : color} industrial={industrial && col % 2 === 0} />
          {civic && <path d={`M${x + 4} ${y + 5}h8v1h-8Zm3-2h2v5h-2Z`} fill="#757a68" />}
          <path d={`M${x + 3} ${y + 13}h2m2 0h2m2 0h2`} stroke="#e2d7b8" strokeWidth="1.15" />
        </>}
      </g>
    })}
    <path d="M-77 6H76" stroke="#657955" strokeWidth="4" />
    <path d="M-77 14H76" stroke="#c3b293" strokeWidth="3" />
    <path d="M-77 10H76" stroke="#303a3c" strokeWidth="5" />
    <path d="M-77 8H76M-77 12H76" stroke="#ad9a78" strokeWidth=".8" strokeDasharray=".8 1.1" />
    <rect x="-20" y="3" width="37" height="4" fill="#b9a787" />
    <rect x="-17" y="3" width="27" height="2.5" fill="#4c717b" />
  </>
})

export function CityDistrict({ id, railActive }: { id: string; railActive: boolean }) {
  const city = cities[id]
  const point = cityPoints.get(id)
  if (!city || !point) return null
  return <g className="city-district map-decoration" data-city-detail={id} transform={`translate(${point.join(' ')})`}>
    <rect x="-80" y="-69" width="159" height="157" rx="2" fill="#202a2c" />
    <CityBlocks id={id} capital={city.capital} industrial={city.resource === 'economy' || city.resource === 'oil'} />
    {railActive && <g className="mobile-sprite">
      <animateMotion path="M-70 10 H69" dur="8s" repeatCount="indefinite" />
      <path d="M-12-1h23v3h-23Z" fill="#242d31" />
      <path d="M-12-2h6v3h-6Zm7 0h6v3h-6Zm7 0h6v3H2Zm7-1h5v4H9Z" fill="#b77552" />
    </g>}
    <rect x="-77" y="-78" width="153" height="10" fill="#15292d" />
    <text className="district-name" x="-73" y="-71">{city.name}</text>
    <text className="district-name district-right" x="72" y="-71">{railActive ? 'Freight station' : 'Station inactive'}</text>
  </g>
}

export function FreightSummary({ state, province }: { state: GameState; province: string }) {
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
    <strong>{city.name}</strong>
    <span>{connections.length ? `Freight to ${connections.join(', ')}` : 'No active freight connections'}</span>
    <span>{income.length > 0 ? `National rail income: ${income.map(([resource, amount]) => `+${amount} ${names[resource] ?? resource}`).join(' · ')} / month`
      : 'Rail income is shown after the next month.'}</span>
  </section>
}
