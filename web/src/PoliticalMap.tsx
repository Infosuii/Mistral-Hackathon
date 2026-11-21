import { useRef, useState, type CSSProperties, type PointerEvent } from 'react'
import map from './map.json'
import { MapOverlays } from './MapOverlays'
import { relationBetween, statLabels, type GameState } from './state'
import { nationStyle } from './theme'
import { CapitalMarkers, CrisisFocus, flagOf, LeaderMedallions, NationalBorders, TerritoryLabels, UnitCounters } from './hud/MapLayers'
import { OrdersBar } from './hud/OrdersBar'
import { BreakingNews, RelationPops } from './hud/Reactions'
import { attackable, useWar, WarMapLayer, WarRoomPanel } from './hud/War'
import { Relief, Sea, TerrainDefs, TerrainFeatures, terrainLabel, terrainOf } from './hud/Terrain'

interface Props {
  state: GameState
  selected: string | undefined
  onSelect: (id: string) => void
}

// The sea runs past the continent to fill the window; the land stays centred between the rails.
const VB = { x: -330, y: -80, w: 1660, h: 840 }
const homeView = { zoom: 1, x: 0, y: 0 }
const maxZoom = 3

function limitView(view: typeof homeView) {
  return {
    zoom: view.zoom,
    x: Math.min(0, Math.max(map.width * (1 - view.zoom), view.x)),
    y: Math.min(0, Math.max(map.height * (1 - view.zoom), view.y)),
  }
}

const modeLabels = { political: 'Political', relations: 'Relations', military: 'Military', unrest: 'Unrest' }
type MapMode = keyof typeof modeLabels

function provinceStyle(state: GameState, owner: string, mode: MapMode): CSSProperties {
  const style = nationStyle(owner)
  if (!owner || !state.nations[owner]) return style
  if (mode === 'military' || mode === 'unrest') {
    const stats = state.nations[owner].stats
    const heat = mode === 'military' ? stats.army : 100 - stats.stability
    const fill = `color-mix(in srgb, var(--heat-low), var(--heat-high) ${Math.round(Math.max(0, Math.min(100, heat)))}%)`
    return { ...style, '--nation-fill': fill } as CSSProperties
  }
  const relations = mode === 'relations'
  if (!relations) return style
  const score = relationBetween(state, state.seat.nation, owner) ?? 0
  const hue = score >= 0 ? '--relation-positive' : '--relation-negative'
  const fill = owner === state.seat.nation
    ? 'var(--relation-own)'
    : `color-mix(in srgb, var(--relation-neutral), var(${hue}) ${Math.abs(score)}%)`
  return { ...style, '--nation-fill': fill, '--nation-accent': 'var(--text)' } as CSSProperties
}

function ProvinceCard({ state, id, x, y }: { state: GameState; id: string; x: number; y: number }) {
  const owner = state.provinces[id]
  const nation = state.nations[owner]
  if (!nation) return null
  const rel = relationBetween(state, state.seat.nation, owner)
  const flag = flagOf(owner)
  const atWar = state.links.some((l) => l.type === 'war' && (l.a === owner || l.b === owner))
  return (
    <div className="province-card" style={{ ...nationStyle(owner), left: x + 18, top: y + 18 } as CSSProperties} role="tooltip">
      <header>
        {flag && <img src={flag} alt="" />}
        <div>
          <strong>{nation.name}</strong>
          <span>Province {id.toUpperCase()} · {terrainLabel[terrainOf[id]]}</span>
        </div>
      </header>
      <dl>
        <div><dt>{statLabels.army}</dt><dd>{Math.round(nation.stats.army)}</dd></div>
        <div><dt>{statLabels.stability}</dt><dd>{Math.round(nation.stats.stability)}</dd></div>
        <div><dt>Provinces</dt><dd>{nation.stats.territory}</dd></div>
        {rel !== undefined && <div><dt>Relations</dt><dd data-sign={Math.sign(rel)}>{rel > 0 ? `+${rel}` : rel}</dd></div>}
      </dl>
      <p>{atWar ? 'At war. ' : ''}{nation.status.includes('PROTESTS') ? 'Protests in the streets. ' : ''}{nation.leader}</p>
      <footer>Click for orders: call, intel, diplomacy</footer>
    </div>
  )
}

export function PoliticalMap({ state, selected, onSelect }: Props) {
  const [view, setView] = useState(homeView)
  const [mode, setMode] = useState<MapMode>('political')
  const warCtl = useWar(state)
  const targets = warCtl.attackMode ? attackable(state, warCtl.war) : null
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null)
  const relations = mode === 'relations' && Boolean(state.seat.nation)
  const shownMode: MapMode = mode === 'relations' && !relations ? 'political' : mode
  const drag = useRef<{ id: number; x: number; y: number; view: typeof homeView; moved: boolean } | null>(null)
  const suppressClick = useRef(false)
  const windowRef = useRef<HTMLDivElement>(null)

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
    const rect = event.currentTarget.getBoundingClientRect()
    const factor = 1 / Math.max(rect.width / VB.w, rect.height / VB.h)
    setView(limitView({ zoom: origin.view.zoom, x: origin.view.x + dx * factor, y: origin.view.y + dy * factor }))
  }

  function endDrag(event: PointerEvent<SVGSVGElement>) {
    if (drag.current?.id !== event.pointerId) return
    suppressClick.current = drag.current.moved
    drag.current = null
  }

  function hoverProvince(id: string, event: PointerEvent<SVGPathElement>) {
    if (drag.current?.moved) return setHover(null)
    const box = windowRef.current?.getBoundingClientRect()
    if (box) setHover({ id, x: event.clientX - box.left, y: event.clientY - box.top })
  }

  return (
    <div className="map-window" ref={windowRef} onPointerLeave={() => setHover(null)}>
      <svg className="political-map" data-zoomed={view.zoom > 1} viewBox={`${VB.x} ${VB.y} ${VB.w} ${VB.h}`}
        preserveAspectRatio="xMidYMid slice"
        aria-label={`${modeLabels[shownMode]} map`} onPointerDown={startDrag}
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
          <TerrainDefs />
        </defs>
        <g data-map-camera transform={`translate(${view.x} ${view.y}) scale(${view.zoom})`}>
          <Sea x={VB.x - 1200} y={VB.y - 900} width={VB.w + 2400} height={VB.h + 1800} />
          <path d={map.coast} className="coast-halo" />
          <path d={map.coast} className="coast-shelf" />
          <g clipPath="url(#land)">
            {map.provinces.map(({ id, path }) => {
              const owner = state.provinces[id]
              const nation = state.nations[owner]
              return (
                <path key={id} d={path} className="province" style={provinceStyle(state, owner, shownMode)}
                  data-province={id} data-owner={owner} data-selected={Boolean(nation && owner === selected)}
                  data-hover={hover?.id === id}
                  onPointerMove={(event) => hoverProvince(id, event)}
                  onPointerLeave={() => setHover(null)}
                  data-war-target={Boolean(targets?.has(id))}
                  onClick={() => {
                    if (targets?.has(id)) void warCtl.attack(id)
                    else if (nation) onSelect(owner)
                  }}>
                  <title>{nation?.name ?? 'Unclaimed'} · {id.toUpperCase()}</title>
                </path>
              )
            })}
            <Relief />
            <TerrainFeatures />
            <NationalBorders state={state} />
          </g>
          <path d={map.coast} className="coastline map-decoration" />
          <text className="water-label map-decoration" x="500" y="45">North Sea</text>
          <text className="water-label map-decoration" x="665" y="625">Kessar Strait</text>
          <text className="water-label map-decoration" x="120" y="640">Western Ocean</text>
          <TerritoryLabels state={state} selected={selected} />
          <MapOverlays state={state} onSelect={onSelect} />
          <CrisisFocus state={state} />
          <CapitalMarkers state={state} />
          <UnitCounters state={state} />
          <WarMapLayer state={state} controls={warCtl} showAll={shownMode === 'military'} />
          <LeaderMedallions state={state} selected={selected} onSelect={onSelect} />
          <RelationPops state={state} />
        </g>
        <rect className="map-decoration" x={VB.x} y={VB.y} width={VB.w} height={VB.h} fill="url(#vignette)" />
      </svg>
      {hover && <ProvinceCard state={state} id={hover.id} x={hover.x} y={hover.y} />}
      <WarRoomPanel state={state} selected={selected} controls={warCtl} />
      <div className="map-hud-top">
        <div className="map-mode" role="group" aria-label="Map view">
          {(Object.keys(modeLabels) as MapMode[])
            .filter((m) => m !== 'relations' || state.seat.nation)
            .map((m) => <button key={m} aria-pressed={shownMode === m} onClick={() => setMode(m)}>{modeLabels[m]}</button>)}
        </div>
        <BreakingNews state={state} />
      </div>
      <div className="map-bottom">
        <div className="map-footer">
          <div className="map-legend" aria-label={`${modeLabels[shownMode]} legend`}>
            {shownMode === 'military' || shownMode === 'unrest' ? (
              <>
                <span className="heat-low">{shownMode === 'military' ? 'Weak army' : 'Stable'}</span>
                <span className="heat-high">{shownMode === 'military' ? 'Strong army' : 'Unrest'}</span>
              </>
            ) : relations ? (
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
        <OrdersBar state={state} selected={selected} />
      </div>
    </div>
  )
}
