import { useLayoutEffect, useRef } from 'react'
import coast from '../../../data/sea_routes.json'
import type { GameState } from '../state'
import { nationStyle } from '../theme'
import { ShipSilhouette } from './DecisionMotion'
import { useMarkerScale } from './scale'

const routes: Record<string, number[][]> = coast.routes

function FleetMarker({ route, progress, nation, label, blockading }: {
  route: number[][]
  progress: number
  nation: string
  label: string
  blockading: boolean
}) {
  const path = useRef<SVGPathElement>(null)
  const ship = useRef<SVGGElement>(null)
  const position = useRef<number | null>(null)
  const m = useMarkerScale()
  const d = `M${route.map((point) => point.join(',')).join(' L')}`

  useLayoutEffect(() => {
    const track = path.current
    const marker = ship.current
    if (!track || !marker) return
    const length = track.getTotalLength()
    const from = position.current ?? (blockading ? progress : 0)
    const move = (fraction: number) => {
      const { x, y } = track.getPointAtLength(fraction * length)
      const behind = track.getPointAtLength(Math.max(0, fraction * length - 3 * m))
      const ahead = track.getPointAtLength(Math.min(length, fraction * length + 3 * m))
      const angle = Math.atan2(ahead.y - behind.y, ahead.x - behind.x) * 180 / Math.PI
      marker.setAttribute('transform', `translate(${x} ${y}) scale(${m})`)
      marker.querySelector('[data-vessel]')?.setAttribute('transform',
        `rotate(${angle + (progress < from ? 0 : 180)}) scale(1.1)`)
      position.current = fraction
    }
    if (from === progress || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      move(progress)
      return
    }
    move(from)
    const started = performance.now()
    let frame = 0
    function animate(now: number) {
      const t = Math.min(1, (now - started) / 1800)
      const eased = 1 - (1 - t) ** 2
      move(from + (progress - from) * eased)
      if (t < 1) frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [d, progress, blockading, m])

  return (
    <g className="naval-fleet" style={nationStyle(nation)} data-fleet={nation} data-blockading={blockading}>
      <title>{label}</title>
      <path ref={path} className="fleet-lane" d={d} />
      <g ref={ship} className="fleet-marker">
        {blockading && <circle className="fleet-blockade" r="27" />}
        <g data-vessel><ShipSilhouette kind="patrol" /></g>
        <text y="-25">{label}</text>
      </g>
    </g>
  )
}

export function NavalFleets({ state }: { state: GameState }) {
  return (
    <g className="naval-layer map-decoration">
      {Object.entries(state.fleets ?? {}).map(([nation, fleet]) => {
        const pair = [nation, fleet.target].sort()
        const path = routes[pair.join('|')]
        if (!path || !state.nations[nation] || !state.nations[fleet.target]) return null
        const outbound = pair[0] === nation ? path : [...path].reverse()
        const blockading = !fleet.returning && state.turn >= fleet.arrival_turn
        const status = fleet.returning ? 'Returning' : blockading ? 'Blockading' : 'Fleet en route'
        const progress = fleet.returning ? .35 : blockading ? 1 : .6
        return <FleetMarker key={`${nation}:${fleet.target}`} nation={nation} route={outbound}
          blockading={blockading} progress={progress}
          label={`${status} · ${state.nations[fleet.returning ? nation : fleet.target].name}`} />
      })}
    </g>
  )
}
