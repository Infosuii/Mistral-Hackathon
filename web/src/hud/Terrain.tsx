// Procedural terrain for the political map: relief shading, mountains, forests and the
// sea graticule. Everything is generated from fixed seeds, so the map never changes
// between renders. Purely decorative: no pointer events.
import { memo } from 'react'
import map from '../atlas.json'
import infrastructure from '../../../data/infrastructure.json'
import { WORLD } from './scale'

type Biome = keyof typeof infrastructure.biomes
const region: Record<string, string> = infrastructure.regions
const climate = infrastructure.climate as { polar: string[]; frozen_rivers: number[]; ice: number[][] }
export const polar = new Set(climate.polar)
const frozenLakes = new Set((map as unknown as { frozenLakes?: number[] }).frozenLakes ?? [])
const frozenRivers = new Set(climate.frozen_rivers)
export const terrainOf = Object.fromEntries(Object.entries(region).map(([province, id]) =>
  [province, { id, ...infrastructure.biomes[id as Biome] }]))
export const coastPath = map.coast


export function TerrainDefs() {
  return (
    <>
      <filter id="relief" x="0" y="0" width={map.width / WORLD} height={map.height / WORLD} filterUnits="userSpaceOnUse">
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
      <pattern id="sea-swell" width="91" height="72" patternUnits="userSpaceOnUse" patternTransform={`scale(${WORLD * .6})`}>
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
/** Graticule lines over open water. The water itself is the animated CSS layer under the map. */
export const Sea = memo(function Sea({ x, y, width, height }: { x: number; y: number; width: number; height: number }) {
  const lines = []
  const grid = 80 * WORLD
  for (let gx = Math.floor(x / grid) * grid; gx < x + width; gx += grid) {
    lines.push(<path key={`m${gx}`} d={`M${gx},${y} Q${gx + (gx - 500 * WORLD) * 0.06},${y + height / 2} ${gx},${y + height}`} />)
  }
  for (let gy = Math.floor(y / grid) * grid; gy < y + height; gy += grid) {
    lines.push(<path key={`p${gy}`} d={`M${x},${gy} Q${x + width / 2},${gy + (gy - 340 * WORLD) * 0.08} ${x + width},${gy}`} />)
  }
  return (
    <g className="map-decoration">
      <g className="graticule">{lines}</g>
    </g>
  )
})

/** Freshwater lakes: a sandy, reedy shore, shallows, then deeper water toward the middle. */
export const Lakes = memo(function Lakes() {
  const lakes = (map as unknown as { lakes?: string[] }).lakes ?? []
  return <g className="lakes map-decoration">
    {lakes.map((d, i) => <g key={i} data-lake={i} data-frozen={frozenLakes.has(i)}>
      <path className="lake-shore" d={d} />
      <path className="lake-water" d={d} />
      <path className="lake-shallows" d={d} />
    </g>)}
  </g>
})

/** Ground cover: soft patches of meadow, heath, scrub or sand under the forests and fields. */
const patchTones: Record<string, string[]> = {
  farmland: ['#9aa35a', '#b3a865', '#7f9a4f'], woodland: ['#5f8a4c', '#83945a', '#4b7442'],
  taiga: ['#4c705a', '#6c8466', '#3d5f4c'], marsh: ['#5f8c76', '#7da07a', '#4f7b6a'],
  highlands: ['#9a8d6e', '#7f7a63', '#b2a585'], dryland: ['#c4a86e', '#b69560', '#d2bb84'],
}
const regions = infrastructure.regions as Record<string, string>
export const GroundCover = memo(function GroundCover() {
  const paths: Record<string, string> = {}
  for (const settlement of infrastructure.settlements) {
    const tones = polar.has(settlement.id) ? ['#eef3f0', '#d2dfde', '#bccdca'] : patchTones[regions[settlement.id]] ?? patchTones.farmland
    for (const [x, y, r, tone] of settlement.patches) {
      const colour = tones[tone]
      paths[colour] = (paths[colour] ?? '') + `M${x - r},${y}a${r},${r * .7} 0 1,0 ${2 * r},0a${r},${r * .7} 0 1,0 ${-2 * r},0`
    }
  }
  return <g className="ground-cover map-decoration">
    {Object.entries(paths).map(([colour, d]) => <path key={colour} d={d} fill={colour} />)}
  </g>
})

// Relief shading laid over the nation colours (inside the land clip).
export const Biomes = memo(function Biomes() {
  return (
    <g className="terrain-biomes map-decoration" transform={`scale(${WORLD})`}>
      <path fill="#cedbd1" opacity=".55" d="M0 0H1740V280C1480 248 1291 186 1100 224S780 184 603 257 234 283 0 233Z" />
      <path fill="#638155" d="M0 506C352 414 522 519 638 430S862 303 961 205L1073 187C950 315 948 535 765 618S205 713 0 663Z" />
      <path fill="#997d58" d="M116 710C335 585 437 774 605 715S906 742 1030 665 1350 686 1740 616V1060H0Z" />
      <path fill="#3f6445" d="M1015 432C1175 415 1340 281 1740 323V530C1559 598 1492 550 1365 635S1125 648 1015 621Z" />
      <path fill="#c2b395" opacity=".65" d="M518 382C660 360 717 271 836 240S960 195 1094 134L1160 202C1011 279 889 296 788 358S629 438 578 490Z" />
      <path fill="#567269" d="M187 587C298 515 404 536 430 585S485 749 590 779L546 827C362 798 404 662 300 661L193 694Z" />
    </g>
  )
})

export const Relief = memo(function Relief() {
  return (
    <g transform={`scale(${WORLD})`}>
      <rect className="relief map-decoration" x="0" y="0" width={map.width / WORLD} height={map.height / WORLD} filter="url(#relief)" />
    </g>
  )
})

const f1 = (n: number) => Math.round(n * 10) / 10
const circle = (cx: number, cy: number, rr: number) =>
  `M${f1(cx - rr)},${f1(cy)}a${f1(rr)},${f1(rr)} 0 1,0 ${f1(2 * rr)},0a${f1(rr)},${f1(rr)} 0 1,0 ${f1(-2 * rr)},0`
const flora = (() => {
  let shade = '', canopy = '', light = '', pines = '', pineLight = '', rock = '', rockLight = '', snow = ''
  let autumn = '', autumnLight = '', reeds = '', shrubs = '', pineSnow = '', frost = ''
  for (const settlement of infrastructure.settlements) {
    const cold = polar.has(settlement.id)
    for (const [x, y, r, kind] of settlement.flora) {
      if (kind === 2) {
        rock += `M${f1(x - r)},${f1(y + r * .5)}L${f1(x)},${f1(y - r * .8)}L${f1(x + r)},${f1(y + r * .5)}Z`
        rockLight += `M${f1(x - r)},${f1(y + r * .5)}L${f1(x)},${f1(y - r * .8)}L${f1(x - r * .1)},${f1(y + r * .5)}Z`
        snow += `M${f1(x - r * .3)},${f1(y - r * .36)}L${f1(x)},${f1(y - r * .8)}L${f1(x + r * .3)},${f1(y - r * .36)}L${f1(x + r * .08)},${f1(y - r * .44)}L${f1(x - r * .06)},${f1(y - r * .3)}Z`
      } else if (kind === 1) {
        shade += `M${f1(x + r * .5)},${f1(y - r * 1.2)}L${f1(x + r * 1.6)},${f1(y + r * 1.3)}L${f1(x - r * .4)},${f1(y + r * 1.3)}Z`
        pines += `M${f1(x)},${f1(y - r * 1.9)}L${f1(x + r)},${f1(y + r)}L${f1(x - r)},${f1(y + r)}Z`
        pineLight += `M${f1(x)},${f1(y - r * 1.9)}L${f1(x)},${f1(y + r)}L${f1(x - r)},${f1(y + r)}Z`
        if (cold) pineSnow += `M${f1(x)},${f1(y - r * 1.9)}L${f1(x + r * .5)},${f1(y - r * .45)}L${f1(x)},${f1(y - r * .75)}L${f1(x - r * .55)},${f1(y - r * .4)}Z`
      } else if (kind === 4) {
        reeds += `M${f1(x - r)},${f1(y)}l${f1(r * .3)},${f1(-r * 1.8)}M${f1(x)},${f1(y)}v${f1(-r * 2.2)}M${f1(x + r)},${f1(y)}l${f1(-r * .3)},${f1(-r * 1.8)}`
      } else if (kind === 5) {
        shrubs += circle(x, y, r)
      } else {
        shade += circle(x + r * .5, y + r * .4, r)
        if (kind === 3) {
          autumn += circle(x, y, r)
          autumnLight += circle(x - r * .3, y - r * .35, r * .5)
        } else if (cold) {
          frost += circle(x, y, r)
        } else {
          canopy += circle(x, y, r)
          light += circle(x - r * .3, y - r * .35, r * .5)
        }
      }
    }
  }
  return { shade, canopy, light, pines, pineLight, rock, rockLight, snow, autumn, autumnLight, reeds, shrubs, pineSnow, frost }
})()

/** Forest stands and highland peaks, placed by the atlas generator clear of towns and fields. */
export const TerrainFeatures = memo(function TerrainFeatures() {
  return (
    <g className="terrain-features map-decoration">
      <path d={flora.rock} fill="#55554b" />
      <path d={flora.rockLight} fill="#8d8b7c" />
      <path d={flora.snow} fill="#e4e5dc" />
      <path d={flora.shade} fill="#142a20" opacity=".35" />
      <path d={flora.shrubs} fill="#7d7a46" />
      <path d={flora.canopy} fill="#356b3f" />
      <path d={flora.light} fill="#75a05a" />
      <path d={flora.autumn} fill="#b5652f" />
      <path d={flora.autumnLight} fill="#e0a548" />
      <path d={flora.reeds} fill="none" stroke="#a8a35e" strokeWidth=".8" strokeLinecap="round" />
      <path d={flora.frost} fill="#a9bdb4" />
      <path d={flora.pines} fill="#24503f" />
      <path d={flora.pineLight} fill="#3f7a5c" />
      <path d={flora.pineSnow} fill="#f1f5f2" />
    </g>
  )
})

type Pt = [number, number]
const poly = (points: Pt[]) => `M${points.map(([px, py]) => `${f1(px)},${f1(py)}`).join('L')}Z`
const along = (a: Pt, b: Pt, t: number): Pt => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]

/** Mountain ranges: shaded peaks with a lit western face, a shadowed eastern face, scree at the
 *  foot and snowcaps on the high or polar summits. Drawn back to front so ridges overlap. */
const ranges = (() => {
  let scree = '', lit = '', shadow = '', snow = '', snowShade = '', strata = ''
  const peaks = infrastructure.settlements.flatMap((settlement) =>
    (settlement.peaks as number[][]).map((peak) => [...peak, polar.has(settlement.id) ? 1 : 0]))
    .sort((a, b) => a[1] - b[1])
  for (const [x, y, size, snowy, cold] of peaks) {
    const h = size * .74
    const apex: Pt = [x + size * .04, y - h]
    const left: Pt = [x - size * .5, y], right: Pt = [x + size * .5, y], foot: Pt = [x + size * .1, y]
    const shoulderL: Pt = [x - size * .24, y - h * .52], shoulderR: Pt = [x + size * .27, y - h * .47]
    scree += `M${f1(x - size * .62)},${f1(y)}a${f1(size * .62)},${f1(size * .13)} 0 1,0 ${f1(size * 1.24)},0a${f1(size * .62)},${f1(size * .13)} 0 1,0 ${f1(-size * 1.24)},0`
    lit += poly([left, shoulderL, apex, foot])
    shadow += poly([apex, shoulderR, right, foot])
    strata += `M${f1(x - size * .12)},${f1(y - h * .32)}l${f1(-size * .14)},${f1(h * .2)}M${f1(x + size * .2)},${f1(y - h * .26)}l${f1(size * .1)},${f1(h * .18)}`
    if (snowy) {
      const depth = cold ? .62 : .4
      const capL = along(apex, shoulderL, depth * 1.4 > 1 ? 1 : depth * 1.4)
      const capR = along(apex, shoulderR, depth * 1.3 > 1 ? 1 : depth * 1.3)
      const ridge = along(apex, foot, depth * .8)
      snow += poly([apex, capL, [capL[0] + size * .07, capL[1] - h * .06], [ridge[0] - size * .04, ridge[1] + h * .03], ridge])
      snowShade += poly([apex, ridge, [ridge[0] + size * .05, ridge[1] - h * .02], capR])
    }
  }
  return { scree, lit, shadow, snow, snowShade, strata }
})()

const ridgeBands = infrastructure.settlements.flatMap((settlement) =>
  ((settlement as { ridges?: [number, number[][]][] }).ridges ?? []).map(([width, points], i) => ({
    key: `${settlement.id}:${i}`, width, cold: polar.has(settlement.id),
    d: `M${points.map((point) => point.join(',')).join('L')}`,
  })))

export const Mountains = memo(function Mountains() {
  return <g className="mountain-ranges map-decoration">
    {ridgeBands.map(({ key, width, cold, d }) => <g key={key} data-ridge={key}>
      <path d={d} fill="none" stroke={cold ? '#aebbbb' : '#86785d'} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" opacity=".6" />
      <path d={d} fill="none" stroke={cold ? '#93a2a5' : '#6b5f4b'} strokeWidth={width * .5} strokeLinecap="round" strokeLinejoin="round" opacity=".45" />
    </g>)}
    <path d={ranges.scree} fill="#2c2a22" opacity=".28" />
    <path d={ranges.lit} fill="#ae9f80" />
    <path d={ranges.shadow} fill="#675d4d" />
    <path d={ranges.strata} fill="none" stroke="#4f483c" strokeWidth="1.1" strokeLinecap="round" opacity=".55" />
    <path d={ranges.snow} fill="#f2f5f2" />
    <path d={ranges.snowShade} fill="#c3d0d6" />
  </g>
})

/** Pack ice drifting off the polar coast: irregular floes with a shadow on the water. */
const floes = (() => {
  let ice = '', under = ''
  for (const [x, y, r, turn] of climate.ice) {
    const points: Pt[] = Array.from({ length: 6 }, (_, k) => {
      const a = (turn + k * 60 + ((turn * (k + 3)) % 23) - 11) * Math.PI / 180
      const reach = r * (.68 + ((turn * (k + 7)) % 31) / 100)
      return [x + Math.cos(a) * reach, y + Math.sin(a) * reach]
    })
    ice += poly(points)
    under += poly(points.map(([px, py]) => [px + r * .18, py + r * .22] as Pt))
  }
  return { ice, under }
})()

export const SeaIce = memo(function SeaIce() {
  return <g className="sea-ice map-decoration">
    <path d={floes.under} fill="#1d4152" opacity=".35" />
    <path d={floes.ice} fill="#e8f1f2" stroke="#a7c4cd" strokeWidth=".9" strokeLinejoin="round" />
  </g>
})

export const Rivers = memo(function Rivers() {
  return <g className="rivers map-decoration">
    {infrastructure.rivers.map((river, index) => {
      const d = `M${river.points.map((point) => point.join(',')).join(' L')}`
      return <g key={index} data-river-width={river.width} data-frozen={frozenRivers.has(index)}>
        <path className="river-bank" d={d} style={{ strokeWidth: river.width + 7 }} />
        <path className="river-water" d={d} style={{ strokeWidth: river.width }} />
      </g>
    })}
  </g>
})
