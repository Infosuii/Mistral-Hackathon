import { useRef, useState, type CSSProperties, type PointerEvent } from 'react'
import map from './map.json'
import { MapOverlays } from './MapOverlays'
import { relationBetween, type GameState } from './state'
import { nationStyle } from './theme'

interface Props {
  state: GameState
  selected: string | undefined
  onSelect: (id: string) => void
}

const homeView = { zoom: 1, x: 0, y: 0 }
const maxZoom = 3

function limitView(view: typeof homeView) {
  return {
    zoom: view.zoom,
    x: Math.min(0, Math.max(map.width * (1 - view.zoom), view.x)),
    y: Math.min(0, Math.max(map.height * (1 - view.zoom), view.y)),
  }
}

function provinceStyle(state: GameState, owner: string, relations: boolean): CSSProperties {
  const style = nationStyle(owner)
  if (!relations || !owner) return style
  const score = relationBetween(state, state.seat.nation, owner) ?? 0
  const hue = score >= 0 ? '--relation-positive' : '--relation-negative'
  const fill = owner === state.seat.nation
    ? 'var(--relation-own)'
    : `color-mix(in srgb, var(--relation-neutral), var(${hue}) ${Math.abs(score)}%)`
  return { ...style, '--nation-fill': fill, '--nation-accent': 'var(--text)' } as CSSProperties
}

export function PoliticalMap({ state, selected, onSelect }: Props) {
  const [view, setView] = useState(homeView)
  const [relations, setRelations] = useState(false)
  const drag = useRef<{ id: number; x: number; y: number; view: typeof homeView; moved: boolean } | null>(null)
  const suppressClick = useRef(false)

  function zoom(delta: number) {
    setView((current) => {
      const next = Math.max(1, Math.min(maxZoom, current.zoom + delta))
      const factor = next / current.zoom
      return limitView({
        zoom: next,
        x: map.width / 2 + (current.x - map.width / 2) * factor,
        y: map.height / 2 + (current.y - map.height / 2) * factor,
      })
    })
  }

  function startDrag(event: PointerEvent<SVGSVGElement>) {
    if (event.button !== 0 || !event.isPrimary) return
    suppressClick.current = false
    if (view.zoom > 1) {
      drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, view, moved: false }
    }
  }

  function moveDrag(event: PointerEvent<SVGSVGElement>) {
    const origin = drag.current
    if (!origin || origin.id !== event.pointerId) return
    const dx = event.clientX - origin.x
    const dy = event.clientY - origin.y
    if (!origin.moved) {
      if (Math.hypot(dx, dy) < 4) return
      event.currentTarget.setPointerCapture(event.pointerId)
      origin.moved = true
    }
    const factor = map.width / event.currentTarget.getBoundingClientRect().width
    setView(limitView({ zoom: origin.view.zoom, x: origin.view.x + dx * factor, y: origin.view.y + dy * factor }))
  }

  function endDrag(event: PointerEvent<SVGSVGElement>) {
    if (drag.current?.id !== event.pointerId) return
    suppressClick.current = drag.current.moved
    drag.current = null
  }

  return (
    <div className="map-window">
      <div className="map-mode" role="group" aria-label="Map view">
        <button aria-pressed={!relations} onClick={() => setRelations(false)}>Political</button>
        <button aria-pressed={relations} onClick={() => setRelations(true)}>Relations</button>
      </div>
      <svg className="political-map" data-zoomed={view.zoom > 1} viewBox={`0 0 ${map.width} ${map.height}`}
        aria-label={relations ? 'Relations map' : 'Political map'} onPointerDown={startDrag}
        onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag}
        onPointerLeave={(event) => { if (!drag.current?.moved) endDrag(event) }}
        onClickCapture={(event) => {
          if (suppressClick.current) {
            suppressClick.current = false
            event.stopPropagation()
          }
        }}>
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
        <g data-map-camera transform={`translate(${view.x} ${view.y}) scale(${view.zoom})`}>
          <path d={map.coast} className="coast-halo" />
          <g clipPath="url(#land)">
            {map.provinces.map(({ id, path }) => {
              const owner = state.provinces[id]
              const nation = state.nations[owner]
              return (
                <path key={id} d={path} className="province" style={provinceStyle(state, owner, relations)}
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
          <MapOverlays state={state} onSelect={onSelect} />
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
        </g>
      </svg>
      <div className="map-footer">
        <div className="map-legend" aria-label={relations ? 'Relations legend' : 'Map legend'}>
          {relations ? (
            <>
              <span className="negative">Hostile</span>
              <span className="neutral">Neutral</span>
              <span className="positive">Friendly</span>
              <span className="own-nation">Your nation</span>
            </>
          ) : (
            <>
              <span className="trade">Trade</span>
              <span className="alliance">Alliance</span>
              <span className="war">War front</span>
              <span className="event">Event</span>
            </>
          )}
        </div>
        <div className="map-zoom" role="group" aria-label="Map zoom">
          <button onClick={() => zoom(-0.5)} disabled={view.zoom === 1} aria-label="Zoom out">−</button>
          <button onClick={() => setView(homeView)} disabled={view.zoom === 1} aria-label="Reset map view">{view.zoom}×</button>
          <button onClick={() => zoom(0.5)} disabled={view.zoom === maxZoom} aria-label="Zoom in">+</button>
        </div>
      </div>
    </div>
  )
}
