// Procedural terrain for the political map: relief shading, mountains, forests and the
// sea graticule. Everything is generated from fixed seeds, so the map never changes
// between renders. Purely decorative: no pointer events.
import map from '../atlas.json'
import infrastructure from '../../../data/infrastructure.json'

type Biome = keyof typeof infrastructure.biomes
const region: Record<string, string> = infrastructure.regions
export const terrainOf = Object.fromEntries(Object.entries(region).map(([province, id]) =>
  [province, { id, ...infrastructure.biomes[id as Biome] }]))
export const coastPath = map.coast

function rng(seed: number) {
  let state = seed >>> 0
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0
    return state / 2 ** 32
  }
}

export function TerrainDefs() {
  return (
    <>
      <filter id="relief" x="0" y="0" width={map.width} height={map.height} filterUnits="userSpaceOnUse">
        <feTurbulence type="fractalNoise" baseFrequency=".016 .026" numOctaves="4" seed="7" result="noise" />
        <feDiffuseLighting in="noise" surfaceScale="6" diffuseConstant="1.05" lightingColor="#fff" result="light">
          <feDistantLight azimuth="312" elevation="29" />
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
        <stop offset="0%" stopColor="#415b68" />
        <stop offset="57%" stopColor="#334a5c" />
        <stop offset="100%" stopColor="#1b3042" />
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
      <path fill="#cedbd1" opacity=".55" d="M0 0H1740V280C1480 248 1291 186 1100 224S780 184 603 257 234 283 0 233Z" />
      <path fill="#638155" d="M0 506C352 414 522 519 638 430S862 303 961 205L1073 187C950 315 948 535 765 618S205 713 0 663Z" />
      <path fill="#997d58" d="M116 710C335 585 437 774 605 715S906 742 1030 665 1350 686 1740 616V1060H0Z" />
      <path fill="#3f6445" d="M1015 432C1175 415 1340 281 1740 323V530C1559 598 1492 550 1365 635S1125 648 1015 621Z" />
      <path fill="#c2b395" opacity=".65" d="M518 382C660 360 717 271 836 240S960 195 1094 134L1160 202C1011 279 889 296 788 358S629 438 578 490Z" />
      <path fill="#567269" d="M187 587C298 515 404 536 430 585S485 749 590 779L546 827C362 798 404 662 300 661L193 694Z" />
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
      {map.provinces.map(({ id, center: [cx, cy], path }) => {
        const biome = terrainOf[id]?.id
        const random = rng(Number(id.slice(1)) * 104729)
        const Glyph = biome === 'taiga' || biome === 'woodland' ? Tree : biome === 'highlands' ? Mountain
          : biome === 'marsh' ? Wetland : biome === 'farmland' ? Field : Hill
        return <g key={id}>
          <clipPath id={`biome-${id}`}><path d={path} clipRule="evenodd" /></clipPath>
          <g clipPath={`url(#biome-${id})`} data-terrain={biome} opacity={biome === 'highlands' ? .53 : .68}>
            {Array.from({length: 20}, (_, i) => {
              const angle = random() * Math.PI * 2
              const distance = 31 + random() * 96
              return <Glyph key={i} x={cx + Math.cos(angle) * distance} y={cy + Math.sin(angle) * distance}
                s={.29 + random() * .43} />
            })}
          </g>
        </g>
      })}
    </g>
  )
}

export function Rivers() {
  return <g className="rivers map-decoration">
    {infrastructure.rivers.map((river, index) => <path key={index}
      d={`M${river.map((point) => point.join(',')).join(' L')}`}
      className={river.length < 5 ? 'tributary' : undefined} />)}
  </g>
}
