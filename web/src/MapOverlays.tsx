import map from './atlas.json'
import type { GameState } from './state'

const capitals: Record<string, number[]> = map.capitals
const centers = new Map(map.provinces.map(({ id, center }) => [id, center]))

function Connection({ type, a, b }: GameState['links'][number]) {
  const from = capitals[a]
  const to = capitals[b]
  if (!from || !to) return null
  // Bow each route away from the straight line so an alliance and trade route can coexist.
  const bend = type === 'alliance' ? -0.18 : 0.18
  const x = (from[0] + to[0]) / 2 - (to[1] - from[1]) * bend
  const y = (from[1] + to[1]) / 2 + (to[0] - from[0]) * bend
  return <path className={`map-link ${type}`} data-link={type} d={`M${from.join(',')} Q${x},${y} ${to.join(',')}`} />
}

export function MapOverlays({ state, onSelect }: { state: GameState; onSelect: (id: string) => void }) {
  const wars = new Set(state.links.filter(({ type }) => type === 'war').map(({ a, b }) => [a, b].sort().join('|')))
  const fronts = map.borders.filter(({ between: [a, b] }) => (
    wars.has([state.provinces[a], state.provinces[b]].sort().join('|'))
  ))

  // Keep the latest event per location when a turn contains several in one province.
  const events = new Map(state.events.filter(({ turn }) => turn === state.turn)
    .map((event) => [event.province ?? event.nation, event]))

  return (
    <>
      <g className="map-decoration" clipPath="url(#land)">
        {fronts.map(({ between, path }) => <path key={between.join('|')} className="map-link war-front" data-link="war" d={path} />)}
      </g>
      <g className="map-decoration">
        {state.links.filter(({ type }) => type === 'trade' || type === 'alliance').map((link) => (
          <Connection key={`${link.type}|${link.a}|${link.b}`} {...link} />
        ))}
      </g>
      {[...events].map(([key, event]) => {
        const center = (event.province && centers.get(event.province)) || (event.nation && capitals[event.nation])
        if (!center) return null
        const [x, y] = center
        const nation = (event.province && state.provinces[event.province]) || event.nation
        const label = event.type.replaceAll('_', ' ')
        return (
          <g key={key} className="map-event" data-event={event.type}
            transform={`translate(${x} ${y + 15})`}
            onClick={() => nation && state.nations[nation] && onSelect(nation)}>
            <title>{label}{event.province && ` · ${event.province.toUpperCase()}`}</title>
            <circle r="9" />
            <text y="5">!</text>
          </g>
        )
      })}
    </>
  )
}
