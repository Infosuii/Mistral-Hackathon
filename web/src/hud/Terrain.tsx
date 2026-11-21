// Procedural terrain for the political map: relief shading, mountains, forests and the
// sea graticule. Everything is generated from fixed seeds, so the map never changes
// between renders. Purely decorative: no pointer events.
import map from '../map.json'

export type TerrainKind = 'mountains' | 'forest' | 'hills' | 'plains' | 'coast'

function rng(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0
    return s / 2 ** 32
  }
}

// One terrain kind per province, fixed by its id. Provinces near the coast lean to
// plains and coast; inland ones to hills, forests and mountains.
const coastPoints = map.coast.match(/\d+(\.\d+)?,\d+(\.\d+)?/g)!.map((p) => p.split(',').map(Number))
function distanceToCoast([x, y]: number[]) {
  return Math.min(...coastPoints.map(([cx, cy]) => Math.hypot(cx - x, cy - y)))
}

export const terrainOf: Record<string, TerrainKind> = Object.fromEntries(map.provinces.map(({ id, center }) => {
  const r = rng(Number(id.slice(1)) * 7919)()
  const inland = distanceToCoast(center)
  if (inland < 45) return [id, r < 0.6 ? 'coast' : 'plains']
  if (inland > 110) return [id, r < 0.55 ? 'mountains' : 'forest']
  return [id, r < 0.3 ? 'hills' : r < 0.65 ? 'forest' : 'plains']
}))

export const terrainLabel: Record<TerrainKind, string> = {
  mountains: 'Mountains', forest: 'Forest', hills: 'Hills', plains: 'Plains', coast: 'Coastal lowland',
}

export function TerrainDefs() {
  return (
    <>
      <filter id="relief" x="0" y="0" width="100%" height="100%" filterUnits="userSpaceOnUse">
        <feTurbulence type="fractalNoise" baseFrequency=".011" numOctaves="5" seed="7" result="noise" />
        <feDiffuseLighting in="noise" surfaceScale="5.5" diffuseConstant="1.05" lightingColor="#fff" result="light">
          <feDistantLight azimuth="315" elevation="38" />
        </feDiffuseLighting>
        <feColorMatrix in="light" type="saturate" values="0" />
      </filter>
      <filter id="unit-shadow" x="-30%" y="-30%" width="160%" height="160%">
        <feDropShadow dx="0" dy="1.5" stdDeviation="1.4" floodColor="#000" floodOpacity=".65" />
      </filter>
      <filter id="label-glow" x="-10%" y="-40%" width="120%" height="180%">
        <feGaussianBlur stdDeviation="2.2" />
      </filter>
      <pattern id="sea-swell" width="46" height="18" patternUnits="userSpaceOnUse">
        <path d="M0 9 q11.5 -5 23 0 t23 0" fill="none" stroke="var(--sea-line)" strokeWidth=".8" />
      </pattern>
      <pattern id="war-hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="4" height="10" fill="var(--war)" opacity=".35" />
      </pattern>
      <radialGradient id="sea-depth" cx="50%" cy="48%" r="70%">
        <stop offset="0%" stopColor="var(--sea-shallow)" />
        <stop offset="55%" stopColor="var(--sea)" />
        <stop offset="100%" stopColor="var(--sea-deep)" />
      </radialGradient>
      <radialGradient id="vignette" cx="50%" cy="50%" r="75%">
        <stop offset="60%" stopColor="#000" stopOpacity="0" />
        <stop offset="100%" stopColor="#000" stopOpacity=".55" />
      </radialGradient>
    </>
  )
}

// The open sea around the continent, with a lat/long graticule.
export function Sea({ x, y, width, height }: { x: number; y: number; width: number; height: number }) {
  const lines = []
  for (let gx = Math.floor(x / 80) * 80; gx < x + width; gx += 80) {
    lines.push(<path key={`m${gx}`} d={`M${gx},${y} Q${gx + (gx - 500) * 0.06},${y + height / 2} ${gx},${y + height}`} />)
  }
  for (let gy = Math.floor(y / 80) * 80; gy < y + height; gy += 80) {
    lines.push(<path key={`p${gy}`} d={`M${x},${gy} Q${x + width / 2},${gy + (gy - 340) * 0.08} ${x + width},${gy}`} />)
  }
  return (
    <g className="map-decoration">
      <rect x={x} y={y} width={width} height={height} fill="url(#sea-depth)" />
      <rect x={x} y={y} width={width} height={height} fill="url(#sea-swell)" opacity=".5" />
      <g className="graticule">{lines}</g>
    </g>
  )
}

// Relief shading laid over the nation colours (inside the land clip).
export function Relief() {
  return (
    <rect className="relief map-decoration" x="0" y="0" width={map.width} height={map.height} filter="url(#relief)" />
  )
}

function Mountain({ x, y, s }: { x: number; y: number; s: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path className="glyph-shade" d="M-9,5 L-1,-7 L3,-1 L6,-4 L12,5 Z" />
      <path className="glyph-light" d="M-1,-7 L-3.5,-2.5 L-1,-3.5 L1,-1.5 L3,-1 Z" />
    </g>
  )
}

function Tree({ x, y, s }: { x: number; y: number; s: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path className="glyph-shade" d="M0,-7 L5,2 L1.2,2 L1.2,5 L-1.2,5 L-1.2,2 L-5,2 Z" />
    </g>
  )
}

function Hill({ x, y, s }: { x: number; y: number; s: number }) {
  return <path className="glyph-line" transform={`translate(${x} ${y}) scale(${s})`} d="M-8,3 Q0,-7 8,3" />
}

// Small terrain glyphs scattered around each province centre.
export function TerrainFeatures() {
  return (
    <g className="terrain-features map-decoration">
      {map.provinces.map(({ id, center: [cx, cy] }) => {
        const kind = terrainOf[id]
        if (kind === 'plains' || kind === 'coast') return null
        const r = rng(Number(id.slice(1)) * 104729)
        const count = kind === 'forest' ? 9 : kind === 'mountains' ? 6 : 4
        const glyphs = []
        for (let i = 0; i < count; i += 1) {
          const a = r() * Math.PI * 2
          const d = 10 + r() * 26
          const x = cx + Math.cos(a) * d
          const y = cy + Math.sin(a) * d * 0.75 + 10
          const s = 0.75 + r() * 0.6
          const Glyph = kind === 'forest' ? Tree : kind === 'mountains' ? Mountain : Hill
          glyphs.push(<Glyph key={i} x={x} y={y} s={s} />)
        }
        return <g key={id} data-terrain={kind}>{glyphs}</g>
      })}
    </g>
  )
}
