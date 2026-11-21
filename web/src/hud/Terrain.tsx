// Procedural terrain for the political map: relief shading, mountains, forests and the
// sea graticule. Everything is generated from fixed seeds, so the map never changes
// between renders. Purely decorative: no pointer events.
import map from '../atlas.json'

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
const coastPoints = map.coast.match(/-?\d+(\.\d+)?,-?\d+(\.\d+)?/g)!.map((p) => p.split(',').map(Number))
export const coastPath = map.coast

const islands = [
  'M765,330 q-9,-15 6,-23 q12,-4 21,6 q8,8 -5,16 q-7,8 -22,1Z',
  'M740,351 q-9,-7 -4,-13 q8,-6 14,1 q7,5 0,12 q-6,3 -10,0Z',
  'M956,802 q-15,-8 -7,-25 q13,-14 30,-10 q12,3 11,15 q-3,8 -12,11 q-11,12 -22,9Z',
  'M1005,818 q-8,-5 -2,-12 q7,-5 15,0 q4,5 -1,9 q-6,5 -12,3Z',
]

export function OffshoreIslands() {
  return (
    <g className="offshore-islands map-decoration">
      {islands.map((path) => <path key={path} d={path} />)}
    </g>
  )
}

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
        <feTurbulence type="fractalNoise" baseFrequency=".009" numOctaves="3" seed="7" result="noise" />
        <feDiffuseLighting in="noise" surfaceScale="3.5" diffuseConstant="1.05" lightingColor="#fff" result="light">
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
      <pattern id="sea-swell" width="91" height="72" patternUnits="userSpaceOnUse">
        <path d="M9 14 h14 m-7 4 h12 M64 43 h15 m-6 4 h10 M28 61 h9" fill="none" stroke="var(--sea-line)" strokeWidth="1" />
      </pattern>
      <pattern id="war-hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="4" height="10" fill="var(--war)" opacity=".35" />
      </pattern>
      <radialGradient id="sea-depth" cx="50%" cy="48%" r="70%">
        <stop offset="0%" stopColor="#24576c" />
        <stop offset="57%" stopColor="#153a54" />
        <stop offset="100%" stopColor="#091f35" />
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
      <rect x={x} y={y} width={width} height={height} fill="url(#sea-swell)" opacity=".42" />
      <g className="graticule">{lines}</g>
    </g>
  )
}

// Relief shading laid over the nation colours (inside the land clip).
export function Biomes() {
  return (
    <g className="terrain-biomes map-decoration">
      <g transform="translate(55 20)">
        <path fill="#d5ebdb" d="M0 20h500v175q-79 54-174 5t-163 16Q74 199 0 235Z" />
        <path fill="#50775a" d="M41 205q93-88 172-23t119 9q67-28 110 26v160H51Z" />
      </g>
      <g transform="translate(120 230)">
        <path fill="#326642" d="M33 275q111-72 212-31t151 56q33 56-50 80q-173 58-313-14Z" />
        <path fill="#e2bb73" d="M229 566q89-72 199-75t172-85v223H228Z" />
        <path fill="#b8a475" d="M89 456q131-47 234-28t114 56v86H91Z" />
      </g>
      <g transform="translate(690 245)">
        <path fill="#d0bb99" d="M507 50h441v273q-96 28-160-17t-155-8q-64 13-126-37Z" />
        <path fill="#2c5c38" d="M503 312q91-43 174 29t168 15q81-46 114 1v220H503Z" />
      </g>
    </g>
  )
}

export function Relief() {
  return (
    <rect className="relief map-decoration" x="0" y="0" width={map.width} height={map.height} filter="url(#relief)" />
  )
}

function Mountain({ x, y, s }: { x: number; y: number; s: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path fill="#344b47" d="M-10 6v-2h2v-3h2v-3h2v-3h2v-3h3v3h2v3h2v3h2v-2h2v2h2v3h2v2Z" />
      <path fill="#879688" d="M-9 4h2V1h2v-3h2v-3h2v8h-2v3h-6Z" />
      <path fill="#e0e3d3" d="M-2-8h3v3h2v3h-3v-1h-2v1h-2v-3h2Z" />
    </g>
  )
}

function Tree({ x, y, s }: { x: number; y: number; s: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path fill="#4b4332" d="M-1 2h2v4h-2Z" />
      <path fill="#244538" d="M-1-8h2v2h2v3h2v3h2v3H-6V0h2v-3h2v-3h1Z" />
      <path fill="#759258" d="M-1-7h2v3h2v2H1v3h-4v-2h1v-3h1Z" />
    </g>
  )
}

function Hill({ x, y, s }: { x: number; y: number; s: number }) {
  return <path className="glyph-line" transform={`translate(${x} ${y}) scale(${s})`} d="M-8,3 Q0,-7 8,3" />
}

function Field({ x, y, s }: { x: number; y: number; s: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path fill="#8c8950" d="M-7-2h12l3 5H-5Z" />
      <path stroke="#d6c48c" strokeWidth=".8" d="m-5-1 2 3m1-3 2 3m1-3 2 3m1-3 2 3" />
    </g>
  )
}

function Wetland({ x, y, s }: { x: number; y: number; s: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path fill="#57837a" d="M-6 1h4v-2h8v2h2v3H-6Z" />
      <path stroke="#b6b481" strokeWidth=".85" d="M-4 2v-4m2 3-1-3m7 2v-4m2 4 1-3" />
    </g>
  )
}

// Detail is sparse in fields and denser in forest belts and ridges.
export function TerrainFeatures() {
  return (
    <g className="terrain-features map-decoration">
      {map.provinces.map(({ id, center: [cx, cy] }) => {
        const kind = terrainOf[id]
        const r = rng(Number(id.slice(1)) * 104729)
        const count = kind === 'forest' ? 12 : kind === 'mountains' ? 8 : 5
        const glyphs = []
        for (let i = 0; i < count; i += 1) {
          const a = r() * Math.PI * 2
          const d = 10 + r() * 26
          const x = cx + Math.cos(a) * d
          const y = cy + Math.sin(a) * d * 0.75 + 10
          const s = 0.75 + r() * 0.6
          const Glyph = kind === 'forest' ? Tree : kind === 'mountains' ? Mountain
            : kind === 'plains' ? Field : kind === 'coast' ? Wetland : Hill
          glyphs.push(<Glyph key={i} x={x} y={y} s={s} />)
        }
        return <g key={id} data-terrain={kind}>{glyphs}</g>
      })}
    </g>
  )
}

export function Rivers() {
  return (
    <g className="rivers map-decoration">
      <g transform="translate(120 230)">
        <path d="M250 296q41 30 39 56t40 35q-13 20 22 37t39 70q-17 26-18 63" />
        <path className="tributary" d="M187 358q28 18 58 10t59 8" />
      </g>
      <g transform="translate(55 20)">
        <path d="M332 163q-42 32-82 20t-63 24q-26 14-45 8t-81 6" />
        <path className="tributary" d="M222 147q7 34 37 38" />
      </g>
      <g transform="translate(690 245)">
        <path d="M755 143q18 44 1 76t11 75q-24 47-4 84t3 63q16 36-6 62t-11 68" />
        <path className="tributary" d="M591 351q47-27 89-2t74 8M865 276q-39 18-95 18" />
      </g>
    </g>
  )
}
