import { memo, type MouseEvent } from 'react'
import map from '../atlas.json'
import type { GameState } from '../state'
import { nationStyle } from '../theme'

const Territories = memo(function Territories({ owners }: { owners: string }) {
  const owner = JSON.parse(owners) as Record<string, string>
  return <>{map.provinces.map(({ id, path }) => <path key={id} d={path} className="minimap-province" style={nationStyle(owner[id])} />)}</>
})

/** The whole campaign at a glance: territories, wars and the camera's viewport. Click to move. */
export function Minimap({ state, frame, onJump }: {
  state: GameState
  frame: { x: number; y: number; w: number; h: number }
  onJump: (x: number, y: number) => void
}) {
  const capitals = map.capitals as Record<string, number[]>
  function jump(event: MouseEvent<SVGSVGElement>) {
    const box = event.currentTarget.getBoundingClientRect()
    onJump((event.clientX - box.left) / box.width * map.width, (event.clientY - box.top) / box.height * map.height)
  }
  return <svg className="minimap" viewBox={`0 0 ${map.width} ${map.height}`} onClick={jump} role="img"
    aria-label="Minimap. Click to move the camera.">
    <rect width={map.width} height={map.height} className="minimap-sea" />
    <Territories owners={JSON.stringify(state.provinces)} />
    {(map as unknown as { lakes?: string[] }).lakes?.map((d, i) => <path key={i} d={d} className="minimap-sea" />)}
    {state.links.filter((l) => l.type === 'war').map(({ a, b }) => capitals[a] && capitals[b] && (
      <path key={a + b} className="minimap-war" d={`M${capitals[a].join(',')}L${capitals[b].join(',')}`} />
    ))}
    <rect className="minimap-frame" x={frame.x} y={frame.y} width={frame.w} height={frame.h} />
  </svg>
}
