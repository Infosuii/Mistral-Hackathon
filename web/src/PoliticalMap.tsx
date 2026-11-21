import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from 'react'
import map from './atlas.json'
import counties from '../../data/counties.json'
import { MapOverlays } from './MapOverlays'
import { Facilities, Transport } from './hud/Infrastructure'
import { NavalFleets } from './hud/NavalFleets'
import { DecisionMotion, kessarPort } from './hud/DecisionMotion'
import './hud/world-map.css'
import { relationBetween, statLabels, type GameState, type MapEvent } from './state'
import { nationStyle } from './theme'
import { CapitalMarkers, CrisisFocus, flagOf, LeaderMedallions, NationalBorders, TerritoryLabels, UnitCounters } from './hud/MapLayers'
import { OrdersBar } from './hud/OrdersBar'
import { BreakingNews, RelationPops } from './hud/Reactions'
import { Biomes, coastPath, OffshoreIslands, Relief, Rivers, Sea, TerrainDefs, TerrainFeatures, terrainLabel, terrainOf } from './hud/Terrain'

interface Props {
  state: GameState
  online: boolean
  historyFocus: MapEvent | null
  selected: string | undefined
  onSelect: (id: string) => void
}

const VB = { x: -80, y: 30, w: 1240, h: 860 }
const centerX = VB.x + VB.w / 2
const centerY = VB.y + VB.h / 2
const homeView = { zoom: 1.45, x: centerX - 446 * 1.45, y: centerY - 547 * 1.45 }
const maxZoom = 4
const minZoom = .7

function limitView(view: typeof homeView) {
  return {
    zoom: view.zoom,
    x: Math.max(centerX + 120 - map.width * view.zoom, Math.min(centerX - 120, view.x)),
    y: Math.max(centerY + 100 - map.height * view.zoom, Math.min(centerY - 100, view.y)),
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
  const facilities = (state.buildings ?? []).filter((site) => site.province === id)
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
      {facilities.length > 0 && <p>{facilities.map((site) => site.kind.replaceAll('_', ' ')).join(' · ')}</p>}
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
    setView(limitView({ zoom, x: centerX - center[0] * zoom, y: centerY - center[1] * zoom }))
  }, [historyFocus])

  const crisisId = state.crisis?.id
  useEffect(() => {
    if (crisisId !== 'one_berth') return
    const zoom = 1.45
    setMode('political')
    setView(limitView({ zoom, x: centerX - kessarPort[0] * zoom, y: centerY - kessarPort[1] * zoom }))
  }, [crisisId])

  function zoom(delta: number) {
    setView((current) => {
      const next = Math.max(minZoom, Math.min(maxZoom, current.zoom + delta))
      const factor = next / current.zoom
      return limitView({
        zoom: next,
        x: centerX + (current.x - centerX) * factor,
        y: centerY + (current.y - centerY) * factor,
      })
    })
  }

  function startDrag(event: PointerEvent<SVGSVGElement>) {
    if (event.button !== 0 || !event.isPrimary) return
    suppressClick.current = false
    if (!globe) {
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
      <svg className="political-map" data-zoomed={!globe} viewBox={`${VB.x} ${VB.y} ${VB.w} ${VB.h}`}
        preserveAspectRatio="xMidYMid slice"
        aria-label={`${modeLabels[shownMode]} map`} onPointerDown={startDrag}
        tabIndex={0} onKeyDown={(event) => {
          const offset = { ArrowLeft: [55, 0], ArrowRight: [-55, 0], ArrowUp: [0, 55], ArrowDown: [0, -55] }[event.key]
          if (!globe && offset) {
            event.preventDefault()
            setView((current) => limitView({ ...current, x: current.x + offset[0], y: current.y + offset[1] }))
          }
        }} onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag}
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
          <clipPath id="globe-disc"><ellipse cx="540" cy="460" rx="530" ry="377" /></clipPath>
          <radialGradient id="globe-ocean" cx="39%" cy="30%" r="72%">
            <stop offset="0%" stopColor="#307487" />
            <stop offset="65%" stopColor="#123c57" />
            <stop offset="100%" stopColor="#091f35" />
          </radialGradient>
        </defs>
        {globe && (
          <g className="world-disc map-decoration" clipPath="url(#globe-disc)">
            <ellipse cx="540" cy="460" rx="530" ry="377" fill="url(#globe-ocean)" />
            {[120, 200, 270, 410, 480, 560].map((y) => (
              <path key={y} d={`M10 460 Q540 ${2 * y - 260} 1070 460`} />
            ))}
            {[95, 190, 295, 390].map((rx) => <ellipse key={rx} cx="540" cy="460" rx={rx} ry="377" />)}
          </g>
        )}
        <g data-map-camera transform={globe ? 'translate(90 185) scale(.51)' : `translate(${view.x} ${view.y}) scale(${view.zoom})`}>
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
            <Rivers />
            <Transport state={state} />
            {shownMode === 'regions' && <g className="county-borders map-decoration">
              {countyEdges.map(({ between, path }) => <path key={between.join('|')} d={path} />)}
            </g>}
            <NationalBorders state={state} />
          </g>
          <path d={coastPath} className="coastline map-decoration" />
          <text className="water-label map-decoration" x="655" y="210">North Sea</text>
          <text className="water-label map-decoration" x="878" y="508">Meridian Ocean</text>
          <text className="water-label map-decoration" x="431" y="359">Northern Passage</text>
          <text className="water-label map-decoration" x="788" y="866">Kessar Strait</text>
          <text className="water-label map-decoration" x="151" y="906">Western Ocean</text>
          {shownMode === 'regions' ? (
            <g className="county-labels map-decoration">
              {counties.map((county) => {
                const centers = map.provinces.filter(({ id }) => county.provinces.includes(id)).map(({ center }) => center)
                const x = centers.reduce((sum, center) => sum + center[0], 0) / centers.length
                const y = centers.reduce((sum, center) => sum + center[1], 0) / centers.length
                return <text key={county.name} x={x} y={y + 18}>{county.name}</text>
              })}
            </g>
          ) : <TerritoryLabels state={state} selected={selected} zoom={globe ? 1 : view.zoom} />}
          <MapOverlays state={state} onSelect={onSelect} />
          <NavalFleets state={state} />
          <CrisisFocus state={state} />
          <Facilities state={state} />
          <CapitalMarkers state={state} />
          <UnitCounters state={state} />
          <LeaderMedallions state={state} selected={selected} onSelect={onSelect} />
          <RelationPops state={state} />
          <DecisionMotion state={state} online={online} />
        </g>
        {globe && <ellipse className="world-limb map-decoration" cx="540" cy="460" rx="530" ry="377" />}
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
            <button onClick={() => zoom(-0.5)} disabled={globe || view.zoom === minZoom} aria-label="Zoom out">−</button>
            <button onClick={() => setView(homeView)} disabled={globe} aria-label="Centre on the western continent">Home</button>
            <button onClick={() => zoom(0.5)} disabled={globe || view.zoom === maxZoom} aria-label="Zoom in">+</button>
          </div>
        </div>
        <OrdersBar state={state} selected={selected} />
      </div>
    </div>
  )
}
