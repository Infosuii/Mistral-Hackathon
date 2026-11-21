// The motion layer: everything that moves on the campaign map. It sits in its own SVG over
// the static world so animation never forces the 10,000-building city layer to repaint.
//
// Public life is passive and follows the rules the engine already enforces: freighters and
// ferries sail between trading partners, trains run only on active rail services, trucks
// only on haulage roads, airliners only on scheduled air services. Military life scales
// with each nation's army; war fronts appear wherever two belligerents share a border.
import { memo, type CSSProperties, type ReactNode } from 'react'
import map from '../atlas.json'
import infrastructure from '../../../data/infrastructure.json'
import rail from '../../../data/rail.json'
import sea from '../../../data/sea_routes.json'
import type { GameState } from '../state'
import { nationStyle } from '../theme'
import { facilityPlacements, harbours, pace, roads, STACKS } from './Infrastructure'
import { useMarkerScale } from './scale'
import {
  Airliner, ArmyTruck, Car, Fighter, Helicopter, Jeep, LightPlane, Locomotive, Tank, Truck, Vessel, Wagon,
} from './sprites'
import { coastPath } from './Terrain'
import './life.css'

type Pt = number[]
const seaRoutes = sea.routes as Record<string, Pt[]>
const capitals = map.capitals as Record<string, Pt>
const centers = new Map(map.provinces.map(({ id, center }) => [id, center as Pt]))

const f1 = (n: number) => Math.round(n * 10) / 10
const frozenRivers = new Set(infrastructure.climate.frozen_rivers)
const frozenLakes = new Set((map as unknown as { frozenLakes?: number[] }).frozenLakes ?? [])
const polyline = (points: Pt[]) => `M${points.map(([x, y]) => `${f1(x)},${f1(y)}`).join('L')}`
const lengthOf = (points: Pt[]) => points.slice(1).reduce((sum, p, i) => sum + Math.hypot(p[0] - points[i][0], p[1] - points[i][1]), 0)
/** Out and back along the same line, so a sprite with rotate="auto" faces the way it travels. */
const roundTrip = (points: Pt[]) => [...points, ...[...points].reverse().slice(1)]

function prefix(points: Pt[], limit: number) {
  const out = [points[0]]
  let left = limit
  for (let i = 1; i < points.length; i++) {
    const [a, b] = [points[i - 1], points[i]]
    const d = Math.hypot(b[0] - a[0], b[1] - a[1])
    if (d >= left) {
      out.push([a[0] + (b[0] - a[0]) * left / d, a[1] + (b[1] - a[1]) * left / d])
      return out
    }
    out.push(b)
    left -= d
  }
  return out
}

function curve(from: Pt, to: Pt, bow: number, steps = 16): Pt[] {
  const angle = Math.atan2(to[1] - from[1], to[0] - from[0])
  const length = Math.hypot(to[0] - from[0], to[1] - from[1])
  const c = [(from[0] + to[0]) / 2 + Math.sin(angle) * bow * length, (from[1] + to[1]) / 2 - Math.cos(angle) * bow * length]
  return Array.from({ length: steps + 1 }, (_, i) => {
    const t = i / steps
    return [(1 - t) ** 2 * from[0] + 2 * (1 - t) * t * c[0] + t * t * to[0], (1 - t) ** 2 * from[1] + 2 * (1 - t) * t * c[1] + t * t * to[1]]
  })
}

function ellipse(cx: number, cy: number, rx: number, ry: number, turn = 0, steps = 28): Pt[] {
  return Array.from({ length: steps + 1 }, (_, i) => {
    const t = i / steps * Math.PI * 2
    const x = Math.cos(t) * rx, y = Math.sin(t) * ry
    return [cx + x * Math.cos(turn) - y * Math.sin(turn), cy + x * Math.sin(turn) + y * Math.cos(turn)]
  })
}

/** One sprite travelling a path forever. offset staggers sprites sharing a path. */
function Mover({ path, seconds, offset = 0, rotate = 'auto', children, className = 'mover', style }: {
  path: string; seconds: number; offset?: number; rotate?: string; children: ReactNode; className?: string; style?: CSSProperties
}) {
  return <g className={className} style={style}>
    <animateMotion path={path} dur={`${f1(seconds)}s`} begin={`${-f1(((offset % seconds) + seconds) % seconds)}s`}
      rotate={rotate} calcMode="linear" repeatCount="indefinite" />
    {children}
  </g>
}

/** A train: locomotive and wagons each following the same track a fixed gap apart. */
function Train({ points, seconds, offset, passenger, cars }: { points: Pt[]; seconds: number; offset: number; passenger: boolean; cars: number }) {
  const loop = roundTrip(points)
  const path = polyline(loop)
  const gap = 13.5 / (lengthOf(loop) / seconds)
  return <g className="train">
    {Array.from({ length: cars + 1 }, (_, i) => (
      <Mover key={i} path={path} seconds={seconds} offset={offset - i * gap}>
        {i === 0 ? <Locomotive passenger={passenger} /> : <Wagon kind={passenger ? 3 : (i + Math.round(offset)) % 5} />}
      </Mover>
    ))}
  </g>
}

// --- water -------------------------------------------------------------------------------

export const WaterMotion = memo(function WaterMotion() {
  return <g className="water-motion" aria-hidden="true">
    <path className="coast-foam" d={coastPath} />
    {infrastructure.rivers.map((river, i) => frozenRivers.has(i) ? null : (
      <path key={i} className="river-flow" d={polyline(river.points)} style={{ strokeWidth: river.width * .25, animationDelay: `${-i * 1.7}s` }} />
    ))}
    {(map as unknown as { lakes?: string[] }).lakes?.map((lake, i) => frozenLakes.has(i) ? null : (
      <path key={i} className="lake-ripple" d={lake} style={{ animationDelay: `${-i * 2.3}s` }} />
    ))}
  </g>
})

// --- harbours and lakes -------------------------------------------------------------------

/** Each port's own traffic, in the harbour's frame (the pier runs along +x): a cargo ship
 *  that waits at its berth, sails out to sea and comes back, and two warships rocking at
 *  their moorings. These used to be painted still into the static harbour drawing. */
function HarbourTraffic({ state }: { state: GameState }) {
  return <g className="harbour-traffic">
    {harbours.map(({ nation, province, x, y, angle }, i) => {
      const owner = state.provinces[province] ?? nation
      if (!state.nations[owner]) return null
      const out: Pt[] = [[32, -29], [96, -29], [180, -62], [300, -70], [420, -40]]
      const loop = roundTrip(out)
      const seconds = 44
      const begin = `${-f1((i * 11) % seconds)}s`
      return <g key={nation} transform={`translate(${f1(x)} ${f1(y)}) rotate(${f1(angle)})`} style={nationStyle(owner)}>
        <g className="mover">
          {/* wait at the berth, sail out, turn, sail back, wait again */}
          <animateMotion path={polyline(loop)} dur={`${seconds}s`} begin={begin} rotate="auto" calcMode="linear"
            keyPoints="0;0;0.5;1;1" keyTimes="0;0.18;0.5;0.82;1" repeatCount="indefinite" />
          <Vessel kind="cargo" />
        </g>
        <Mover path="M30,17 L31.4,18.2 L30,19.2 L28.8,18 Z" seconds={6.5} offset={i} rotate="180"><Vessel kind="frigate" /></Mover>
        <Mover path="M28,39 L29.2,40.4 L28,41.4 L26.8,40.2 Z" seconds={7.5} offset={i * 2} rotate="0"><Vessel kind="destroyer" /></Mover>
      </g>
    })}
  </g>
}

const lakeLoops: Pt[][] = ((map as unknown as { lakes?: string[] }).lakes ?? []).flatMap((lake, i) => {
  if (frozenLakes.has(i)) return []
  const pts = (lake.match(/-?\d+(\.\d+)?/g)?.map(Number) ?? []).reduce<Pt[]>((acc, n, k, all) => (k % 2 ? acc : [...acc, [n, all[k + 1]]]), [])
  if (pts.length < 3) return []
  const cx = pts.reduce((sum, p) => sum + p[0], 0) / pts.length
  const cy = pts.reduce((sum, p) => sum + p[1], 0) / pts.length
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1])
  const rx = (Math.max(...xs) - Math.min(...xs)) / 2, ry = (Math.max(...ys) - Math.min(...ys)) / 2
  if (Math.min(rx, ry) < 24) return []
  return [ellipse(cx, cy, rx * .38, ry * .38, 0, 24)]
})

/** Fishing boats circling the inland lakes (not the frozen ones). */
const LakeBoats = memo(function LakeBoats() {
  return <g className="lake-boats">
    {lakeLoops.map((loop, i) => (
      <Mover key={i} path={polyline(loop)} seconds={lengthOf(loop) / 7} offset={i * 9}>
        <Vessel kind="fishing" />
      </Mover>
    ))}
  </g>
})

// --- public life --------------------------------------------------------------------------

function laneFrom(nation: string, key: string, limit: number): Pt[] {
  const route = seaRoutes[key]
  const ordered = key.split('|')[0] === nation ? route : [...route].reverse()
  return prefix(ordered, limit)
}

function routesOf(nation: string) {
  return Object.keys(seaRoutes).filter((key) => key.split('|').includes(nation))
}

const atWar = (state: GameState, a: string, b: string) =>
  state.links.some((l) => l.type === 'war' && ((l.a === a && l.b === b) || (l.a === b && l.b === a)))

function Shipping({ state, scale }: { state: GameState; scale: number }) {
  const ships: ReactNode[] = []
  for (const { nation, province } of harbours) {
    const owner = state.provinces[province] ?? nation
    if (!state.nations[owner]) continue
    routesOf(nation).slice(0, 3).forEach((key, i) => {
      const other = key.split('|').find((n) => n !== nation)!
      if (atWar(state, nation, other)) return
      const lane = laneFrom(nation, key, 1500 + i * 400)
      const loop = roundTrip(lane)
      const seconds = lengthOf(loop) / 11
      ships.push(<Mover key={`f${nation}${i}`} path={polyline(loop)} seconds={seconds} offset={i * 13 + nation.length * 5}
        style={nationStyle(owner)}><g transform={`scale(${scale})`}><Vessel kind="fishing" /></g></Mover>)
      if (i < 2) ships.push(<Mover key={`c${nation}${i}`} path={polyline(loop)} seconds={seconds * 1.4} offset={i * 29 + 40}
        style={nationStyle(owner)}><g transform={`scale(${scale})`}><Vessel kind={i ? 'tanker' : 'cargo'} /></g></Mover>)
    })
  }
  // Long-haul freighters and ferries sail only between trading partners at peace.
  for (const link of state.links) {
    if (link.type !== 'trade' || atWar(state, link.a, link.b)) continue
    const key = [link.a, link.b].sort().join('|')
    const route = seaRoutes[key]
    if (!route) continue
    const loop = roundTrip(route)
    const seconds = lengthOf(loop) / 22
    ships.push(<Mover key={`t${key}`} path={polyline(loop)} seconds={seconds} offset={key.length * 7}
      style={nationStyle(link.a)}><g transform={`scale(${scale})`}><Vessel kind="cargo" /></g></Mover>)
    ships.push(<Mover key={`r${key}`} path={polyline(loop)} seconds={seconds * .8} offset={seconds * .45}
      style={nationStyle(link.b)}><g transform={`scale(${scale})`}><Vessel kind={lengthOf(route) < 6000 ? 'ferry' : 'tanker'} /></g></Mover>)
  }
  return <g className="shipping">{ships}</g>
}

function Trains({ state, overview }: { state: GameState; overview: boolean }) {
  const active = new Set(state.rail_services ?? [])
  return <g className="trains">
    {rail.routes.filter(({ id }) => active.has(id)).map(({ id, points }, i) => {
      const seconds = lengthOf(roundTrip(points)) / 26
      return <g key={id} data-train={id} style={nationStyle(state.provinces[id.split('|')[0]])}>
        <Train points={points} seconds={seconds} offset={i * 11} passenger={i % 3 === 0} cars={overview ? 1 : 4} />
      </g>
    })}
  </g>
}

function RoadTraffic({ state }: { state: GameState }) {
  const hauling = new Set(state.road_services ?? [])
  return <g className="road-traffic-layer">
    {roads.filter(({ id }) => hauling.has(id)).flatMap(({ id, points, speed, kind }, index) => {
      const loop = roundTrip(points)
      const seconds = lengthOf(loop) / (speed * pace(kind) * 30)
      return [0, 1, 2].map((k) => (
        <Mover key={`${id}:${k}`} className="mover road-traffic" path={polyline(loop)} seconds={seconds} offset={index * 3.7 + k * seconds / 3}>
          <g transform="translate(0 2.2)">{k === 2 ? <Car tone={index} /> : <Truck tone={index + k} />}</g>
        </Mover>
      ))
    })}
  </g>
}

/** Commuter cars on each town's ring road and avenues. */
const cityRoutes = infrastructure.settlements.flatMap((settlement, s) => settlement.streets
  .filter(([tier]) => tier === 0)
  .map(([, points]) => points as Pt[])
  .filter((points) => lengthOf(points) > 90)
  .sort((a, b) => lengthOf(b) - lengthOf(a))
  .slice(0, settlement.radius > 120 ? 3 : 1)
  .map((points, i) => ({ id: `${settlement.id}:${i}`, points, seed: s * 7 + i })))

const CityTraffic = memo(function CityTraffic() {
  return <g className="city-traffic">
    {cityRoutes.flatMap(({ id, points, seed }) => {
      const loop = roundTrip(points)
      const seconds = lengthOf(loop) / 16
      return [<Mover key={id} path={polyline(loop)} seconds={seconds} offset={seed * 2.3}>
        <g transform="translate(0 1.4)"><Car tone={seed} /></g>
      </Mover>]
    })}
  </g>
})

function CivilAviation({ state, scale }: { state: GameState; scale: number }) {
  const fields = facilityPlacements(state).filter((site) => site.kind === 'airfield')
  const where = new Map(fields.map((site) => [site.province, site]))
  const flights = (state.air_services ?? []).flatMap((id, i) => {
    const [a, b] = id.split('|').map((p) => where.get(p))
    if (!a || !b) return []
    const path = curve([a.x, a.y], [b.x, b.y], .14, 24)
    const loop = roundTrip(path)
    return [<g key={id} className="air-service" data-air-service={id} style={nationStyle(a.owner)}>
      <path className="air-lane" d={polyline(path)} />
      <Mover path={polyline(loop)} seconds={lengthOf(loop) / 90} offset={i * 9}>
        <g transform={`scale(${scale * 1.1})`}><Airliner /></g>
      </Mover>
    </g>]
  })
  // Light aircraft fly the circuit at every airfield: take off, downwind, base, land.
  const circuits = fields.map(({ province, owner, x, y, angle, length }, i) => {
    const t = angle * Math.PI / 180
    const local = [[-length / 2, 0], [length / 2 + 60, 0], [length / 2 + 150, -110], [-length / 2 - 150, -110], [-length / 2 - 60, 0], [-length / 2, 0]]
    const points = local.map(([u, v]) => [x + u * Math.cos(t) - v * Math.sin(t), y + u * Math.sin(t) + v * Math.cos(t)])
    return <Mover key={province} path={polyline(points)} seconds={lengthOf(points) / 34} offset={i * 5} style={nationStyle(owner)}>
      <g transform={`scale(${Math.max(1, scale * .8)})`}><LightPlane /></g>
    </Mover>
  })
  // High-altitude overflights between capitals of nations at peace.
  const ids = Object.keys(state.nations)
  const overflights = ids.flatMap((a, i) => ids.slice(i + 1).map((b) => [a, b])).filter(([a, b]) => !atWar(state, a, b))
    .slice(0, 5).map(([a, b], i) => {
      const path = curve(capitals[a], capitals[b], i % 2 ? .1 : -.1, 20)
      const loop = roundTrip(path)
      return <Mover key={`${a}${b}`} className="mover overflight" path={polyline(loop)} seconds={lengthOf(loop) / 120} offset={i * 17}>
        <g transform={`scale(${scale * 1.4})`}><Airliner /></g>
      </Mover>
    })
  return <g className="civil-aviation">{flights}{circuits}{overflights}</g>
}

export function PublicLife({ state, overview }: { state: GameState; overview: boolean }) {
  const m = useMarkerScale()
  const scale = Math.max(1, m * .45)
  return <g className="public-life" aria-hidden="true">
    <HarbourTraffic state={state} />
    <LakeBoats />
    <Shipping state={state} scale={scale} />
    {!overview && <CityTraffic />}
    {!overview && <RoadTraffic state={state} />}
    <Trains state={state} overview={overview} />
    <CivilAviation state={state} scale={scale} />
  </g>
}

// --- military ----------------------------------------------------------------------------

function Smoke({ x, y, heavy = false }: { x: number; y: number; heavy?: boolean }) {
  return <g className={heavy ? 'smoke heavy' : 'smoke'} transform={`translate(${x} ${y})`}>
    {[0, 1, 2, 3].map((i) => <circle key={i} r={heavy ? 5 : 3.2} style={{ animationDelay: `${-i * .9}s` }} />)}
  </g>
}

export function Military({ state, overview }: { state: GameState; overview: boolean }) {
  const m = useMarkerScale()
  const scale = Math.max(1, m * .45)
  const sites = facilityPlacements(state)
  const units: ReactNode[] = []
  sites.forEach(({ province, kind, owner, x, y }, i) => {
    const nation = state.nations[owner]
    if (!nation) return
    const style = nationStyle(owner)
    if (kind === 'army_base') {
      const loop = ellipse(x, y, 62, 44)
      const path = polyline(loop)
      const tanks = Math.max(1, Math.min(4, Math.round(nation.stats.army / 22)))
      const roster = [...Array.from({ length: tanks }, () => 'tank'), 'truck', 'jeep', 'truck']
      roster.forEach((unit, k) => units.push(
        <Mover key={`p${province}${k}`} path={path} seconds={34} offset={k * 34 / roster.length} style={style}>
          {unit === 'tank' ? <Tank /> : unit === 'jeep' ? <Jeep /> : <ArmyTruck />}
        </Mover>))
      units.push(<Mover key={`h${province}`} path={polyline(ellipse(x, y, 120, 80, .4))} seconds={18} offset={i * 3} style={style}>
        <g transform={`scale(${scale * 1.15})`}><Helicopter /></g>
      </Mover>)
      // Convoys run the nation's own roads out of the base province.
      if (!overview) {
        roads.filter((road) => (road.a === province || road.b === province) && state.provinces[road.a] === owner
          && state.provinces[road.b] === owner).slice(0, 2).forEach((road, r) => {
          const loop = roundTrip(road.points)
          const seconds = lengthOf(loop) / 9
          ;['jeep', 'tank', 'truck', 'truck'].forEach((unit, k) => units.push(
            <Mover key={`c${province}${r}${k}`} path={polyline(loop)} seconds={seconds} offset={r * 40 - k * 1.6} style={style}>
              <g transform="translate(0 -2.4)">{unit === 'tank' ? <Tank /> : unit === 'jeep' ? <Jeep /> : <ArmyTruck />}</g>
            </Mover>))
        })
      }
    }
    if (kind === 'airfield') {
      [0, 1].forEach((k) => units.push(
        <Mover key={`j${province}${k}`} path={polyline(ellipse(x, y, 320, 170, k ? 1.1 : -.3))} seconds={20 + k * 4}
          offset={k * 6 + i} style={style}><g transform={`scale(${scale * 1.2})`}><Fighter /></g></Mover>))
    }
    for (const [dx, dy] of STACKS[kind] ?? []) units.push(<Smoke key={`s${province}${kind}${dx}`} x={x + dx} y={y + dy} />)
  })
  // Combat air patrol over each capital and warships patrolling out of each port.
  for (const [id, nation] of Object.entries(state.nations)) {
    const capital = capitals[id]
    if (!capital) continue
    const pairs = nation.stats.army > 45 ? 2 : 1
    for (let k = 0; k < pairs; k++) {
      units.push(<Mover key={`cap${id}${k}`} path={polyline(ellipse(capital[0], capital[1], 900, 560, k * .9))} seconds={46}
        offset={k * 20} style={nationStyle(id)}><g transform={`scale(${scale * 1.2})`}><Fighter /></g></Mover>)
      units.push(<Mover key={`cap${id}${k}w`} path={polyline(ellipse(capital[0], capital[1], 900, 560, k * .9))} seconds={46}
        offset={k * 20 - .7} style={nationStyle(id)}><g transform={`translate(0 14) scale(${scale * 1.2})`}><Fighter /></g></Mover>)
    }
  }
  for (const { nation, province } of harbours) {
    const owner = state.provinces[province] ?? nation
    const army = state.nations[owner]?.stats.army ?? 0
    const keys = routesOf(nation)
    for (let k = 0; k < Math.min(3, 1 + Math.floor(army / 35)); k++) {
      const loop = roundTrip(laneFrom(nation, keys[k % keys.length], 2400 + k * 500))
      units.push(<Mover key={`n${nation}${k}`} path={polyline(loop)} seconds={lengthOf(loop) / 14} offset={k * 31 + 11}
        style={nationStyle(owner)}><g transform={`scale(${scale})`}><Vessel kind={k % 2 ? 'destroyer' : 'frigate'} /></g></Mover>)
    }
  }
  return <g className="military-life" aria-hidden="true">{units}</g>
}

// --- war ----------------------------------------------------------------------------------

function parsePath(path: string): Pt[] {
  const numbers = path.match(/-?\d+(\.\d+)?/g)?.map(Number) ?? []
  const points: Pt[] = []
  for (let i = 0; i + 1 < numbers.length; i += 2) points.push([numbers[i], numbers[i + 1]])
  return points
}

function Blast({ x, y, period, delay, size = 6 }: { x: number; y: number; period: number; delay: number; size?: number }) {
  const begin = `${-f1(delay)}s`
  return <g transform={`translate(${f1(x)} ${f1(y)})`} className="blast">
    <circle className="blast-fire" r="0">
      <animate attributeName="r" values={`0;${size};${size * 1.3};${size * 1.3}`} keyTimes="0;.06;.22;1" dur={`${period}s`} begin={begin} repeatCount="indefinite" />
      <animate attributeName="opacity" values="0;1;0;0" keyTimes="0;.04;.24;1" dur={`${period}s`} begin={begin} repeatCount="indefinite" />
    </circle>
    <circle className="blast-core" r="0">
      <animate attributeName="r" values={`0;${size * .5};0;0`} keyTimes="0;.04;.12;1" dur={`${period}s`} begin={begin} repeatCount="indefinite" />
    </circle>
  </g>
}

function Flash({ x, y, period, delay }: { x: number; y: number; period: number; delay: number }) {
  return <circle className="muzzle" cx={f1(x)} cy={f1(y)} r="3.4" opacity="0">
    <animate attributeName="opacity" values="0;1;0;0" keyTimes="0;.04;.12;1" dur={`${period}s`} begin={`${-f1(delay)}s`} repeatCount="indefinite" />
  </circle>
}

function Shell({ from, to, period, delay }: { from: Pt; to: Pt; period: number; delay: number }) {
  const path = curve(from, to, .3, 12)
  const begin = `${-f1(delay)}s`
  return <g>
    <circle className="shell" r="1.8">
      <animateMotion path={polyline(path)} keyPoints="0;1;1" keyTimes="0;.5;1" calcMode="linear" dur={`${period}s`} begin={begin} repeatCount="indefinite" />
      <animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.49;.5;1" dur={`${period}s`} begin={begin} repeatCount="indefinite" />
    </circle>
    <Blast x={to[0]} y={to[1]} period={period} delay={delay - period * .5} size={6} />
  </g>
}

/** Where two belligerents meet: armour advances from its garrisons, trades fire across the line,
 *  artillery lands behind it and jets fly strikes from their airfields. */
export function WarFronts({ state }: { state: GameState }) {
  const m = useMarkerScale()
  const scale = Math.max(1, m * .45)
  const wars = state.links.filter((link) => link.type === 'war')
  if (!wars.length) return null
  const sites = facilityPlacements(state)
  return <g className="war-fronts" aria-hidden="true">
    {wars.flatMap(({ a, b }) => {
      const edges = map.borders.filter(({ between: [p, q] }) => {
        const pair = [state.provinces[p], state.provinces[q]]
        return pair.includes(a) && pair.includes(b) && pair[0] !== pair[1]
      })
      const chosen = edges.filter((_, i) => i % Math.max(1, Math.ceil(edges.length / 4)) === 0).slice(0, 4)
      const fronts = chosen.map(({ between, path }, e) => {
        const points = parsePath(path)
        const mid = points[Math.floor(points.length / 2)]
        const side = (nation: string) => {
          const province = between.find((p) => state.provinces[p] === nation)!
          const c = centers.get(province)!
          const length = Math.hypot(c[0] - mid[0], c[1] - mid[1]) || 1
          return { nation, d: [(c[0] - mid[0]) / length, (c[1] - mid[1]) / length] }
        }
        return <g key={`${a}${b}${e}`} className="front" data-front={`${a}|${b}`}>
          <ellipse cx={mid[0]} cy={mid[1]} rx="60" ry="40" className="scorch" />
          {[side(a), side(b)].map(({ nation, d }, s) => {
            const n = [-d[1], d[0]]
            const facing = Math.atan2(-d[1], -d[0]) * 180 / Math.PI
            const base = sites.find((site) => site.owner === nation && site.kind === 'army_base')
            const staging = [mid[0] + d[0] * 70, mid[1] + d[1] * 70]
            const from = base ? [base.x - staging[0], base.y - staging[1]] : [d[0] * 400, d[1] * 400]
            const enemy = (k: number) => [mid[0] - d[0] * (40 + k * 12) + n[0] * (k - 1) * 26, mid[1] - d[1] * (40 + k * 12) + n[1] * (k - 1) * 26]
            return <g key={nation} className="front-side" style={{ ...nationStyle(nation), '--fx': `${f1(from[0])}px`, '--fy': `${f1(from[1])}px` } as CSSProperties}>
              {[-1, 0, 1].map((k) => {
                const back = [staging[0] + n[0] * k * 24, staging[1] + n[1] * k * 24]
                const fore = [mid[0] + d[0] * 26 + n[0] * k * 24, mid[1] + d[1] * 26 + n[1] * k * 24]
                return <g key={k}>
                  <Mover path={polyline([back, fore, back])} seconds={7 + k} offset={e * 2 + s * 3 + k} rotate={String(f1(facing))}>
                    <g transform="scale(1.25)"><Tank /></g>
                  </Mover>
                  <Flash x={fore[0] - d[0] * 11} y={fore[1] - d[1] * 11} period={1.9 + (k + 1) * .4} delay={e + s * .7 + k * .5} />
                </g>
              })}
              <Mover path={polyline([[staging[0] + d[0] * 40 - n[0] * 50, staging[1] + d[1] * 40 - n[1] * 50],
                [staging[0] + d[0] * 40 + n[0] * 50, staging[1] + d[1] * 40 + n[1] * 50]].concat([[staging[0] + d[0] * 40 - n[0] * 50, staging[1] + d[1] * 40 - n[1] * 50]]))}
                seconds={9} offset={e * 3 + s}><ArmyTruck /></Mover>
              {[0, 1, 2].map((k) => <Shell key={k} from={[mid[0] + d[0] * 180 + n[0] * (k - 1) * 40, mid[1] + d[1] * 180 + n[1] * (k - 1) * 40]}
                to={enemy(k)} period={2.6 + k * .5} delay={e * 1.3 + s * 1.1 + k * .8} />)}
            </g>
          })}
          <path className="tracer" d={polyline([[mid[0] + side(a).d[0] * 20, mid[1] + side(a).d[1] * 20], [mid[0] + side(b).d[0] * 20, mid[1] + side(b).d[1] * 20]])} />
          <Smoke x={mid[0] + 18} y={mid[1] - 6} heavy />
          <Smoke x={mid[0] - 30} y={mid[1] + 14} heavy />
        </g>
      })
      // Strike sorties from each side's airfields to the first front.
      const target = fronts.length ? parsePath(chosen[0].path)[Math.floor(parsePath(chosen[0].path).length / 2)] : null
      const strikes = target ? [a, b].flatMap((nation, s) => sites.filter((site) => site.owner === nation && site.kind === 'airfield')
        .slice(0, 1).map((field) => {
          const out = curve([field.x, field.y], target, s ? .12 : -.12, 16)
          const loop = roundTrip(out)
          const seconds = lengthOf(loop) / 110
          return <g key={`strike${nation}`} style={nationStyle(nation)}>
            {[0, 1].map((k) => <Mover key={k} path={polyline(loop)} seconds={seconds} offset={s * 4 - k * .5}>
              <g transform={`translate(0 ${k * 12}) scale(${scale * 1.3})`}><Fighter /></g>
            </Mover>)}
            <Blast x={target[0] + (s ? 30 : -30)} y={target[1] + 10} period={seconds} delay={s * 4 - seconds * .5} size={9} />
          </g>
        })) : []
      // A naval engagement at the middle of the sea lane when both sides have a port.
      const lane = seaRoutes[[a, b].sort().join('|')]
      let naval: ReactNode = null
      if (lane && state.provinces[(sea.ports as Record<string, { province: string }>)[a]?.province] === a
        && state.provinces[(sea.ports as Record<string, { province: string }>)[b]?.province] === b) {
        const mid = prefix(lane, lengthOf(lane) / 2).at(-1)!
        naval = <g key="naval" className="naval-clash">
          {[a, b].map((nation, s) => {
            const sign = s ? 1 : -1
            const path = polyline([[mid[0] + sign * 90, mid[1] - 40], [mid[0] + sign * 70, mid[1] + 40], [mid[0] + sign * 90, mid[1] - 40]])
            return <g key={nation} style={nationStyle(nation)}>
              <Mover path={path} seconds={14} offset={s * 5}><g transform={`scale(${scale})`}><Vessel kind="destroyer" /></g></Mover>
              <Flash x={mid[0] + sign * 70} y={mid[1]} period={2.2} delay={s} />
            </g>
          })}
          <Blast x={mid[0] - 30} y={mid[1] + 12} period={3.1} delay={.4} size={5} />
          <Blast x={mid[0] + 24} y={mid[1] - 18} period={2.7} delay={1.6} size={5} />
        </g>
      }
      return [<g key={`${a}|${b}`} data-war={`${a}|${b}`}>{fronts}{strikes}{naval}</g>]
    })}
  </g>
}
