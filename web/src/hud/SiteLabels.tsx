import { useLayoutEffect, useRef } from 'react'
import counties from '../../../data/counties.json'
import rail from '../../../data/rail.json'
import type { GameState } from '../state'
import { nationStyle } from '../theme'
import { facilityPlacements, harbours, kindNames } from './Infrastructure'
import { useMarkerScale } from './scale'

const county = new Map(counties.flatMap((c) => c.provinces.map((id) => [id, c.name] as const)))
const cities = rail.cities as Record<string, { name: string }>
const placeName = (province: string) => cities[province]?.name ?? county.get(province) ?? province.toUpperCase()

function Tag({ x, y, icon, text, kind, owner, m, dy = 0 }: {
  x: number; y: number; icon: string; text: string; kind: string; owner: string; m: number; dy?: number
}) {
  const width = text.length * 6.1 + 24
  return <g className="site-label" data-site-label={kind} transform={`translate(${x} ${y}) scale(${m}) translate(0 ${dy})`} style={nationStyle(owner)}>
    <rect x={-width / 2} y="-9" width={width} height="15" rx="7.5" />
    <path className="site-icon" d={icon} transform={`translate(${-width / 2 + 9} -1.5)`} />
    <text x={-width / 2 + 18} y="2.5">{text}</text>
  </g>
}

const ICONS = {
  port: 'M0-5v9M-3-2h6M-4 2q4 4 8 0',
  airport: 'M-5 0h10M0-1-3-5h1.6L2-1M0 1-3 5h1.6L2 1M4-1l1.5 1L4 1',
  army_base: 'M-4-4h8v4l-4 4-4-4Z',
  arms_factory: 'M-5 4V-1l3-2v2l3-2v2l3-2V4Z',
  factory: 'M-5 4V-1l3-2v2l3-2v2l3-2V4Z',
  chip_works: 'M-3-3h6v6h-6ZM-5-1h2M3-1h2M-5 1h2M3 1h2',
  farm: 'M-4 4V-1l4-3 4 3V4Z',
  freight_yard: 'M-5 2h10M-4-2h8v3h-8Z',
}

/** Names for every port, airport and engine building; minor sites only when zoomed in. */
export function SiteLabels({ state }: { state: GameState }) {
  const m = useMarkerScale()
  const ref = useRef<SVGGElement>(null)
  // Declutter: ports always show; an airport or works tag that would print over a town's
  // name or an earlier tag hides until you zoom in far enough for it to fit.
  useLayoutEffect(() => {
    const group = ref.current
    if (!group) return
    const run = () => {
      const towns = [...(group.closest('svg')?.querySelectorAll('.city-marker text') ?? [])].map((t) => t.getBoundingClientRect())
      const kept: DOMRect[] = []
      const tags = [...group.querySelectorAll<SVGGElement>('.site-label')]
        .sort((a, b) => Number(b.dataset.siteLabel === 'port') - Number(a.dataset.siteLabel === 'port'))
      for (const tag of tags) {
        tag.style.display = ''
        const r = tag.getBoundingClientRect()
        const hits = (o: DOMRect) => r.left < o.right && o.left < r.right && r.top < o.bottom && o.top < r.bottom
        if (tag.dataset.siteLabel !== 'port' && (towns.some(hits) || kept.some(hits))) tag.style.display = 'none'
        else kept.push(r)
      }
    }
    run()
    const late = window.setTimeout(run, 400)
    return () => window.clearTimeout(late)
  })
  return <g ref={ref} className="site-labels">
    {harbours.map(({ nation, province, x, y }) => {
      const owner = state.provinces[province] ?? nation
      return <Tag key={nation} x={x} y={y} dy={-30} icon={ICONS.port} text={`Port of ${placeName(province)}`} kind="port" owner={owner} m={m} />
    })}
    {facilityPlacements(state).map(({ province, kind, owner, x, y }) => kind === 'airfield'
      ? <Tag key={`${province}${kind}`} x={x} y={y} dy={-24} icon={ICONS.airport} text={`${placeName(province)} Airport`} kind="airport" owner={owner} m={m} />
      : <Tag key={`${province}${kind}`} x={x} y={y} dy={-36} icon={ICONS[kind as keyof typeof ICONS] ?? ICONS.factory}
          text={`${kindNames[kind]?.name ?? kind} · ${placeName(province)}`} kind={kind} owner={owner} m={m} />)}
  </g>
}
