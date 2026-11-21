import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from 'react'
import map from './map.json'
import counties from '../../data/counties.json'
import { MapOverlays } from './MapOverlays'
import { NavalFleets } from './hud/NavalFleets'
import { DecisionMotion } from './hud/DecisionMotion'
import './hud/world-map.css'
import { relationBetween, statLabels, type GameState, type MapEvent } from './state'
import { nationStyle } from './theme'
import { CapitalMarkers, CrisisFocus, flagOf, LeaderMedallions, NationalBorders, TerritoryLabels, UnitCounters } from './hud/MapLayers'
import { OrdersBar } from './hud/OrdersBar'
import { BreakingNews, RelationPops } from './hud/Reactions'
import { Biomes, coastPath, OffshoreIslands, Relief, Sea, TerrainDefs, TerrainFeatures, terrainLabel, terrainOf } from './hud/Terrain'

interface Props {
  state: GameState
  online: boolean
  historyFocus: MapEvent | null
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

const modeLabels = { political: 'Political', relations: 'Relations', military: 'Military', unrest: 'Unrest', regions: 'Regions', world: 'World' }
type MapMode = keyof typeof modeLabels
const countyOf = new Map(counties.flatMap((county) => county.provinces.map((id) => [id, county] as const)))
const countyEdges = map.borders.filter(({ between: [a, b] }) => countyOf.get(a) !== countyOf.get(b))

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
  const county = countyOf.get(id)
  const controlled = county?.provinces.filter((province) => state.provinces[province] === owner).length ?? 0
  const contested = !!county && controlled < county.provinces.length
  const morale = county ? Math.min(100, Math.max(0, Math.round(nation.stats.stability + county.morale - (contested ? 8 : 0)))) : 0
  const atWar = state.links.some((l) => l.type === 'war' && (l.a === owner || l.b === owner))
  return (
    <div className="province-card" style={{ ...nationStyle(owner), left: x + 18, top: y + 18 } as CSSProperties} role="tooltip">
      <header>
        {flag && <img src={flag} alt="" />}
        <div>
          <strong>{nation.name}</strong>
          <span>{county?.name ?? id.toUpperCase()} · {terrainLabel[terrainOf[id]]}</span>
        </div>
      </header>
      <dl>
        <div><dt>{statLabels.army}</dt><dd>{Math.round(nation.stats.army)}</dd></div>
        <div><dt>{statLabels.stability}</dt><dd>{Math.round(nation.stats.stability)}</dd></div>
        <div><dt>Provinces</dt><dd>{nation.stats.territory}</dd></div>
        {county && <>
          <div><dt>County morale</dt><dd>{morale}%</dd></div>
          <div><dt>County output</dt><dd>{county.output.toFixed(1)} {county.resource}/mo</dd></div>
          <div><dt>Controlled</dt><dd>{controlled}/{county.provinces.length}</dd></div>
        </>}
        {rel !== undefined && <div><dt>Relations</dt><dd data-sign={Math.sign(rel)}>{rel > 0 ? `+${rel}` : rel}</dd></div>}
      </dl>
      <p>{atWar ? 'At war. ' : ''}{nation.status.includes('PROTESTS') ? 'Protests in the streets. ' : ''}{nation.leader}</p>
      <footer>Click for orders: call, intel, diplomacy</footer>
    </div>
  )
}

export function PoliticalMap({ state, online, historyFocus, selected, onSelect }: Props) {
  const [view, setView] = useState(homeView)
  const [mode, setMode] = useState<MapMode>('political')
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null)
  const relations = mode === 'relations' && Boolean(state.seat.nation)
  const globe = mode === 'world'
  const shownMode: MapMode = mode === 'relations' && !relations ? 'political' : mode
  const drag = useRef<{ id: number; x: number; y: number; view: typeof homeView; moved: boolean } | null>(null)
  const suppressClick = useRef(false)
  const windowRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!historyFocus) return
    const center = historyFocus.province
      ? map.provinces.find(({ id }) => id === historyFocus.province)?.center
      : historyFocus.nation && (map.capitals as Record<string, number[]>)[historyFocus.nation]
    if (!center) return
    const zoom = 2
    setMode('political')
    setHover(null)
    setView(limitView({ zoom, x: 500 - center[0] * zoom, y: 340 - center[1] * zoom }))
  }, [historyFocus])

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
    if (!globe && view.zoom > 1) {
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
          <clipPath id="land"><path d={coastPath} /></clipPath>
          <TerrainDefs />
          <clipPath id="globe-disc"><ellipse cx="500" cy="340" rx="445" ry="355" /></clipPath>
          <radialGradient id="globe-ocean" cx="39%" cy="30%" r="72%">
            <stop offset="0%" stopColor="#307487" />
            <stop offset="65%" stopColor="#123c57" />
            <stop offset="100%" stopColor="#091f35" />
          </radialGradient>
        </defs>
        {globe && (
          <g className="world-disc map-decoration" clipPath="url(#globe-disc)">
            <ellipse cx="500" cy="340" rx="445" ry="355" fill="url(#globe-ocean)" />
            {[120, 200, 270, 410, 480, 560].map((y) => (
              <path key={y} d={`M55 340 Q500 ${2 * y - 340} 945 340`} />
            ))}
            {[95, 190, 295, 390].map((rx) => <ellipse key={rx} cx="500" cy="340" rx={rx} ry="355" />)}
          </g>
        )}
        <g data-map-camera transform={globe ? 'translate(165 112) scale(.67)' : `translate(${view.x} ${view.y}) scale(${view.zoom})`}>
          {!globe && <Sea x={VB.x - 1200} y={VB.y - 900} width={VB.w + 2400} height={VB.h + 1800} />}
          <OffshoreIslands />
          <path d={coastPath} className="coast-halo" />
          <path d={coastPath} className="coast-shelf" />
          <path d={coastPath} className="coast-reef" />
          <g clipPath="url(#land)">
            <path d={coastPath} className="coast-land" />
            {map.provinces.map(({ id, path }) => {
              const owner = state.provinces[id]
              const nation = state.nations[owner]
              return (
                <path key={id} d={path} className="province" style={provinceStyle(state, owner, shownMode)}
                  data-province={id} data-county={countyOf.get(id)?.name} data-owner={owner} data-home={owner === state.seat.nation} data-selected={Boolean(nation && owner === selected)}
                  data-hover={hover?.id === id}
                  onPointerMove={(event) => hoverProvince(id, event)}
                  onClick={() => nation && onSelect(owner)}>
                  <title>{nation?.name ?? 'Unclaimed'} · {id.toUpperCase()}</title>
                </path>
              )
            })}
            <Biomes />
            <Relief />
            <TerrainFeatures />
            {shownMode === 'regions' && <g className="county-borders map-decoration">
              {countyEdges.map(({ between, path }) => <path key={between.join('|')} d={path} />)}
            </g>}
            <NationalBorders state={state} />
          </g>
          <path d={coastPath} className="coastline map-decoration" />
          <text className="water-label map-decoration" x="500" y="45">North Sea</text>
          <text className="water-label map-decoration" x="665" y="625">Kessar Strait</text>
          <text className="water-label map-decoration" x="120" y="640">Western Ocean</text>
          {shownMode === 'regions' ? (
            <g className="county-labels map-decoration">
              {counties.map((county) => {
                const centers = map.provinces.filter(({ id }) => county.provinces.includes(id)).map(({ center }) => center)
                const x = centers.reduce((sum, center) => sum + center[0], 0) / centers.length
                const y = centers.reduce((sum, center) => sum + center[1], 0) / centers.length
                return <text key={county.name} x={x} y={y + 18}>{county.name}</text>
              })}
            </g>
          ) : <TerritoryLabels state={state} selected={selected} />}
          <MapOverlays state={state} onSelect={onSelect} />
          <NavalFleets state={state} />
          <CrisisFocus state={state} />
          <CapitalMarkers state={state} />
          <UnitCounters state={state} />
          <LeaderMedallions state={state} selected={selected} onSelect={onSelect} />
          <RelationPops state={state} />
          <DecisionMotion state={state} online={online} />
        </g>
        {globe && <ellipse className="world-limb map-decoration" cx="500" cy="340" rx="445" ry="355" />}
        <rect className="map-decoration" x={VB.x} y={VB.y} width={VB.w} height={VB.h} fill="url(#vignette)" />
      </svg>
      {hover && <ProvinceCard state={state} id={hover.id} x={hover.x} y={hover.y} />}
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
            <button onClick={() => zoom(-0.5)} disabled={globe || view.zoom === 1} aria-label="Zoom out">−</button>
            <button onClick={() => setView(homeView)} disabled={globe || view.zoom === 1} aria-label="Reset map view">{view.zoom}×</button>
            <button onClick={() => zoom(0.5)} disabled={globe || view.zoom === maxZoom} aria-label="Zoom in">+</button>
          </div>
        </div>
        <OrdersBar state={state} selected={selected} />
      </div>
    </div>
  )
}
