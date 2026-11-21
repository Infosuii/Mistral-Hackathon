import map from './map.json'
import type { GameState } from './state'
import { nationStyle } from './theme'

interface Props {
  state: GameState
  selected: string | undefined
  onSelect: (id: string) => void
}

export function PoliticalMap({ state, selected, onSelect }: Props) {
  return (
    <svg className="political-map" viewBox={`0 0 ${map.width} ${map.height}`} aria-label="Political map">
      <defs>
        <clipPath id="land"><path d={map.coast} /></clipPath>
        <filter id="paper-grain" x="0%" y="0%" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency=".45" numOctaves="3" stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <radialGradient id="land-light">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity=".13" />
          <stop offset="100%" stopColor="var(--sea-deep)" stopOpacity=".22" />
        </radialGradient>
      </defs>
      <path d={map.coast} className="coast-halo" />
      <g clipPath="url(#land)">
        {map.provinces.map(({ id, path }) => {
          const owner = state.provinces[id]
          const nation = state.nations[owner]
          return (
            <path key={id} d={path} className="province" style={nationStyle(owner)}
              data-province={id} data-owner={owner} data-selected={Boolean(nation && owner === selected)}
              onClick={() => nation && onSelect(owner)}>
              <title>{nation?.name ?? 'Unclaimed'} · {id.toUpperCase()}</title>
            </path>
          )
        })}
        <rect className="map-decoration" width={map.width} height={map.height} fill="url(#land-light)" />
        <rect className="map-grain map-decoration" width={map.width} height={map.height} filter="url(#paper-grain)" />
      </g>
      <path d={map.coast} className="coastline map-decoration" />
      <text className="water-label map-decoration" x="500" y="65">North Sea</text>
      <text className="water-label map-decoration" x="665" y="590">Kessar Strait</text>
      <g className="map-decoration">
        {Object.entries(map.capitals).map(([id, [x, y]]) => {
          const nation = state.nations[id]
          if (!nation) return null
          return (
            <g className="map-capital" key={id} transform={`translate(${x} ${y})`}
              data-selected={id === selected} style={nationStyle(id)}>
              <path d="M0,-6 L6,0 L0,6 L-6,0 Z" />
              <text y="-14">{nation.name}</text>
            </g>
          )
        })}
      </g>
    </svg>
  )
}
