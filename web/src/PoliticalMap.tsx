import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type PointerEvent } from 'react'
import map from './atlas.json'
import counties from '../../data/counties.json'
import { MapOverlays } from './MapOverlays'
import infrastructure from '../../data/infrastructure.json'
import { CityMarkers, FreightSummary, UrbanFabric } from './hud/Cities'
import { Facilities, Harbours, TransportStatic } from './hud/Infrastructure'
import { Military, PublicLife, WarFronts, WaterMotion } from './hud/Life'
import { SiteLabels } from './hud/SiteLabels'
import { Minimap } from './hud/Minimap'
import { NavalFleets } from './hud/NavalFleets'
import { DecisionMotion, kessarPort } from './hud/DecisionMotion'
import './hud/world-map.css'
import './hud/scale.css'
import './hud/stage.css'
import { MarkerScale, markerScaleFor, WORLD } from './hud/scale'
import { relationBetween, statLabels, type GameState, type MapEvent } from './state'
import { nationStyle } from './theme'
import { CapitalMarkers, CrisisFocus, flagOf, LeaderMedallions, NationalBorders, TerritoryLabels, UnitCounters } from './hud/MapLayers'
import { OrdersBar } from './hud/OrdersBar'
import { BreakingNews, RelationPops } from './hud/Reactions'
import { attackable, useWar, WarMapLayer, WarRoomPanel } from './hud/War'
import { Biomes, coastPath, GroundCover, Lakes, Mountains, polar, Relief, Rivers, Sea, SeaIce, TerrainDefs, TerrainFeatures, terrainOf } from './hud/Terrain'

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
const minZoom = .64 / WORLD
const flatOverview = { zoom: minZoom, x: centerX - map.width * minZoom / 2, y: centerY - map.height * minZoom / 2 }
const maxZoom = 4
const startZoom = .8
type View = typeof flatOverview

/** The opening camera: the player's capital and its suburbs, close enough to read the streets. */
function homeView(nation: string | null | undefined): View {
  const capital = nation ? (map.capitals as Record<string, number[]>)[nation] : undefined
  const [x, y] = capital ?? [map.width / 2, map.height / 2]
  return limitView({ zoom: capital ? startZoom : minZoom * 1.6, x: centerX - x * (capital ? startZoom : minZoom * 1.6), y: centerY - y * (capital ? startZoom : minZoom * 1.6) })
}

type Layers = { traffic: boolean; military: boolean; labels: boolean }
const defaultLayers: Layers = { traffic: true, military: true, labels: true }
function storedLayers(): Layers {
  try {
    return { ...defaultLayers, ...JSON.parse(localStorage.getItem('gambit:map-layers') ?? '{}') }
  } catch {
    return defaultLayers
  }
}

function limitView(view: View) {
  return {
    zoom: view.zoom,
    x: Math.max(centerX + 120 - map.width * view.zoom, Math.min(centerX - 120, view.x)),
    y: Math.max(centerY + 100 - map.height * view.zoom, Math.min(centerY - 100, view.y)),
  }
}

const modeLabels = { political: 'Political', relations: 'Relations', military: 'Military', unrest: 'Unrest', regions: 'Regions', biomes: 'Biomes' }
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

// The card is about 18rem wide and up to 15rem tall: near the right or bottom edge of the
// map it opens on the other side of the pointer so it is never cut off.
function cardPlace(x: number, y: number, box?: { w: number; h: number }): CSSProperties {
  const rem = typeof window === 'undefined' ? 16 : parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
  const w = 18 * rem, h = 15 * rem
  const place: CSSProperties = {}
  if (box && x + 18 + w > box.w) place.right = Math.max(4, box.w - x + 18)
  else place.left = x + 18
  if (box && y + 18 + h > box.h) place.bottom = Math.max(4, box.h - y + 18)
  else place.top = y + 18
  return place
}

function ProvinceCard({ state, id, x, y, box }: { state: GameState; id: string; x: number; y: number; box?: { w: number; h: number } }) {
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
    <div className="province-card" style={{ ...nationStyle(owner), ...cardPlace(x, y, box) } as CSSProperties} role="tooltip">
      <header>
        {flag && <img src={flag} alt="" />}
        <div>
          <strong>{nation.name}</strong>
          <span>{county?.name ?? id.toUpperCase()} · {terrainOf[id]?.label}</span>
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
  const [view, setView] = useState(() => homeView(state.seat.nation))
  const [citySelection, setCitySelection] = useState<string | null>(null)
  const [mode, setMode] = useState<MapMode>('political')
  const warCtl = useWar(state)
  const warTargets = warCtl.attackMode ? attackable(state, warCtl.war) : null
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null)
  const relations = mode === 'relations' && Boolean(state.seat.nation)
  const shownMode: MapMode = mode === 'relations' && !relations ? 'political' : mode
  const drag = useRef<{ id: number; x: number; y: number; view: View; moved: boolean } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const markerScale = markerScaleFor(view.zoom)
  const suppressClick = useRef(false)
  const windowRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const lifeRef = useRef<SVGSVGElement>(null)
  const [stage, setStage] = useState({ w: 1240, h: 860 })
  const [layers, setLayers] = useState(storedLayers)
  const overview = view.zoom < .45

  function toggleLayer(key: keyof Layers) {
    setLayers((current) => {
      const next = { ...current, [key]: !current[key] }
      try { localStorage.setItem('gambit:map-layers', JSON.stringify(next)) } catch { /* private mode */ }
      return next
    })
  }

  // The CSS sea under the map follows the camera: the stage size turns world units into pixels.
  useLayoutEffect(() => {
    const element = stageRef.current
    if (!element) return
    const measure = () => setStage({ w: element.clientWidth || 1240, h: element.clientHeight || 860 })
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  // Reduced motion: hold every vehicle where it stands instead of hiding public life.
  useEffect(() => {
    const svg = lifeRef.current
    if (!svg) return
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const apply = () => (query.matches ? svg.pauseAnimations() : svg.unpauseAnimations())
    apply()
    query.addEventListener('change', apply)
    return () => query.removeEventListener('change', apply)
  }, [])

  useEffect(() => {
    if (!historyFocus) return
    setCitySelection(null)
    const center = historyFocus.province
      ? map.provinces.find(({ id }) => id === historyFocus.province)?.center
      : historyFocus.nation && (map.capitals as Record<string, number[]>)[historyFocus.nation]
    if (!center) return
    const zoom = 1.1
    setMode('political')
    setHover(null)
    setView(limitView({ zoom, x: centerX - center[0] * zoom, y: centerY - center[1] * zoom }))
  }, [historyFocus])

  const crisisId = state.crisis?.id
  useEffect(() => {
    if (crisisId !== 'one_berth') return
    setCitySelection(null)
    const zoom = .75
    setMode('political')
    setView(limitView({ zoom, x: centerX - kessarPort[0] * zoom, y: centerY - kessarPort[1] * zoom }))
  }, [crisisId])

  function selectCity(province: string) {
    setCitySelection(province)
    setHover(null)
    onSelect(state.provinces[province])
  }

  function zoom(factor: number, anchor: [number, number] = [centerX, centerY]) {
    setView((current) => {
      const next = Math.max(minZoom, Math.min(maxZoom, current.zoom * factor))
      const ratio = next / current.zoom
      return limitView({
        zoom: next,
        x: anchor[0] + (current.x - anchor[0]) * ratio,
        y: anchor[1] + (current.y - anchor[1]) * ratio,
      })
    })
  }

  // Wheel and trackpad zoom around the pointer. A native listener so the page does not scroll.
  useEffect(() => {
    const svg = svgRef.current
    const target = stageRef.current
    if (!svg || !target) return
    function onWheel(event: WheelEvent) {
      event.preventDefault()
      const rect = svg!.getBoundingClientRect()
      const scale = Math.max(rect.width / VB.w, rect.height / VB.h)
      const x = VB.x + (event.clientX - rect.left - (rect.width - VB.w * scale) / 2) / scale
      const y = VB.y + (event.clientY - rect.top - (rect.height - VB.h * scale) / 2) / scale
      zoom(Math.exp(-Math.max(-60, Math.min(60, event.deltaY)) * .004), [x, y])
    }
    target.addEventListener('wheel', onWheel, { passive: false })
    return () => target.removeEventListener('wheel', onWheel)
  }, [])

  function startDrag(event: PointerEvent<SVGSVGElement>) {
    if (event.button !== 0 || !event.isPrimary) return
    suppressClick.current = false
    drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, view, moved: false }
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

  const detail = overview ? 'overview' : 'streets'
  const layerStyle = { '--m': markerScale } as CSSProperties
  const px = Math.max(stage.w / VB.w, stage.h / VB.h)
  const seaTile = Math.max(24, 900 * view.zoom * px)
  const visible = { w: stage.w / px, h: stage.h / px }
  const frame = {
    x: (VB.x + (VB.w - visible.w) / 2 - view.x) / view.zoom, y: (VB.y + (VB.h - visible.h) / 2 - view.y) / view.zoom,
    w: visible.w / view.zoom, h: visible.h / view.zoom,
  }
  const seaStyle = {
    '--sea-tile': `${seaTile.toFixed(1)}px`,
    '--sea-x': `${(((view.x - VB.x) * px + (stage.w - VB.w * px) / 2) % seaTile).toFixed(1)}px`,
    '--sea-y': `${(((view.y - VB.y) * px + (stage.h - VB.h * px) / 2) % seaTile).toFixed(1)}px`,
  } as CSSProperties

  return (
    <div className="map-window" ref={windowRef} onPointerLeave={() => setHover(null)}>
      <div className="map-stage" ref={stageRef}>
      <div className="map-sea" aria-hidden="true" style={seaStyle} />
      <svg ref={svgRef} className="political-map" data-zoomed={view.zoom > minZoom} viewBox={`${VB.x} ${VB.y} ${VB.w} ${VB.h}`}
        style={layerStyle} data-map-mode={shownMode} data-detail={detail}
        preserveAspectRatio="xMidYMid slice"
        aria-label={`${modeLabels[shownMode]} map`} onPointerDown={startDrag}
        tabIndex={0} onKeyDown={(event) => {
          const offset = { ArrowLeft: [55, 0], ArrowRight: [-55, 0], ArrowUp: [0, 55], ArrowDown: [0, -55] }[event.key]
          if (offset) {
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
        </defs>
        <MarkerScale.Provider value={markerScale}>
        <g data-map-camera transform={`translate(${view.x} ${view.y}) scale(${view.zoom})`}>
          <Sea x={-1600 * WORLD} y={-1300 * WORLD} width={map.width + 3200 * WORLD} height={map.height + 2600 * WORLD} />
          <path d={coastPath} className="coast-halo" />
          <path d={coastPath} className="coast-shelf" />
          <path d={coastPath} className="coast-reef" />
          <g clipPath="url(#land)">
            <path d={coastPath} className="coast-land" />
            {map.provinces.map(({ id, path }) => {
              const owner = state.provinces[id]
              const nation = state.nations[owner]
              return (
                <path key={id} d={path} className="province" style={{ ...provinceStyle(state, owner, shownMode), '--biome-color': terrainOf[id]?.color } as CSSProperties}
                  data-province={id} data-biome={terrainOf[id]?.id} data-climate={polar.has(id) ? 'polar' : undefined} data-biome-view={shownMode === 'biomes'} data-county={countyOf.get(id)?.name} data-owner={owner} data-home={owner === state.seat.nation} data-selected={Boolean(nation && owner === selected)}
                  data-hover={hover?.id === id}
                  onPointerMove={(event) => hoverProvince(id, event)}
                  onPointerLeave={() => setHover(null)}
                  data-war-target={Boolean(warTargets?.has(id))}
                  onClick={() => {
                    if (warTargets?.has(id)) void warCtl.attack(id)
                    else if (nation) onSelect(owner)
                  }}
                  aria-label={`${nation?.name ?? 'Unclaimed'} · ${id.toUpperCase()}`} />
              )
            })}
            <Biomes />
            <GroundCover />
            <Relief />
            <TerrainFeatures />
            <Rivers />
            <Mountains />
            <UrbanFabric />
            <TransportStatic state={state} />
            <Facilities state={state} />
            {shownMode === 'regions' && <g className="county-borders map-decoration">
              {countyEdges.map(({ between, path }) => <path key={between.join('|')} d={path} />)}
            </g>}
            <NationalBorders state={state} />
          </g>
          <SeaIce />
          <Lakes />
          <Harbours state={state} />
          <path d={coastPath} className="coastline map-decoration" />
        </g>
        </MarkerScale.Provider>
      </svg>
      <svg ref={lifeRef} className="map-layer map-life" viewBox={`${VB.x} ${VB.y} ${VB.w} ${VB.h}`} preserveAspectRatio="xMidYMid slice"
        style={layerStyle} data-map-mode={shownMode} data-detail={detail} aria-hidden="true">
        <MarkerScale.Provider value={markerScale}>
        <g data-life-camera transform={`translate(${view.x} ${view.y}) scale(${view.zoom})`}>
          <WaterMotion />
          {layers.traffic && <PublicLife state={state} overview={overview} />}
          {layers.military && <Military state={state} overview={overview} />}
          <WarFronts state={state} />
        </g>
        </MarkerScale.Provider>
      </svg>
      <svg className="map-layer map-markers" viewBox={`${VB.x} ${VB.y} ${VB.w} ${VB.h}`} preserveAspectRatio="xMidYMid slice"
        style={layerStyle} data-map-mode={shownMode} data-detail={detail} data-labels={layers.labels}>
        <MarkerScale.Provider value={markerScale}>
        <g data-marker-camera transform={`translate(${view.x} ${view.y}) scale(${view.zoom})`}>
          <text className="water-label map-decoration" x={400 * WORLD} y={373 * WORLD}>North Sea</text>
          <text className="water-label map-decoration" x={1603 * WORLD} y={743 * WORLD}>Meridian Ocean</text>
          <text className="water-label map-decoration" x={250 * WORLD} y={387 * WORLD}>Northern Passage</text>
          <text className="water-label map-decoration" x={915 * WORLD} y={825 * WORLD}>Kessar Strait</text>
          <text className="water-label map-decoration" x={156 * WORLD} y={954 * WORLD}>Western Ocean</text>
          {shownMode === 'regions' ? (
            <g className="county-labels map-decoration">
              {counties.map((county) => {
                const centers = map.provinces.filter(({ id }) => county.provinces.includes(id)).map(({ center }) => center)
                const x = centers.reduce((sum, center) => sum + center[0], 0) / centers.length
                const y = centers.reduce((sum, center) => sum + center[1], 0) / centers.length
                return <text key={county.name} x={x} y={y + 18}>{county.name}</text>
              })}
            </g>
          ) : <TerritoryLabels state={state} selected={selected} zoom={view.zoom} />}
          <MapOverlays state={state} onSelect={onSelect} />
          <NavalFleets state={state} />
          <CrisisFocus state={state} />
          {layers.labels && <SiteLabels state={state} />}
          <CapitalMarkers state={state} />
          <UnitCounters state={state} />
          <WarMapLayer state={state} controls={warCtl} showAll={shownMode === 'military'} />
          <LeaderMedallions state={state} selected={selected} onSelect={onSelect} />
          <CityMarkers state={state} onCity={selectCity} />
          <RelationPops state={state} />
          <DecisionMotion state={state} online={online} />
        </g>
        </MarkerScale.Provider>
      </svg>
      <div className="map-vignette" aria-hidden="true" />
      </div>
      {hover && <ProvinceCard state={state} id={hover.id} x={hover.x} y={hover.y} box={windowRef.current ? { w: windowRef.current.clientWidth, h: windowRef.current.clientHeight } : undefined} />}
      <WarRoomPanel state={state} selected={selected} controls={warCtl} />
      <div className="map-hud-top">
        {citySelection && <FreightSummary state={state} province={citySelection} onClose={() => setCitySelection(null)} />}
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
            {shownMode === 'biomes' ? (
              Object.values(infrastructure.biomes).map((biome) => (
                <span key={biome.label} style={{ '--legend-color': biome.color } as CSSProperties}>{biome.label}</span>
              ))
            ) : shownMode === 'military' || shownMode === 'unrest' ? (
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
          <div className="map-controls">
          <Minimap state={state} frame={frame} onJump={(x, y) => setView((current) =>
            limitView({ ...current, x: centerX - x * current.zoom, y: centerY - y * current.zoom }))} />
          <div className="map-layers" role="group" aria-label="Map layers">
            {([['traffic', 'Traffic'], ['military', 'Military'], ['labels', 'Labels']] as const).map(([key, label]) => (
              <button key={key} type="button" aria-pressed={layers[key]} onClick={() => toggleLayer(key)}>{label}</button>
            ))}
          </div>
          <div className="map-zoom" role="group" aria-label="Map zoom">
            <button onClick={() => zoom(1 / 1.6)} disabled={view.zoom <= minZoom} aria-label="Zoom out">−</button>
            <button onClick={() => { setCitySelection(null); setView(flatOverview) }} aria-label="Fit campaign map">Fit map</button>
            <button onClick={() => zoom(1.6)} disabled={view.zoom >= maxZoom} aria-label="Zoom in">+</button>
          </div>
          </div>
        </div>
        <OrdersBar state={state} selected={selected} />
      </div>
    </div>
  )
}
