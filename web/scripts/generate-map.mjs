import { writeFileSync } from 'node:fs'
import { Delaunay } from 'd3-delaunay'

const bounds = [0, 0, 1000, 680]
const coast = [
  [72, 244], [52, 194], [91, 175], [106, 142], [169, 155], [221, 114],
  [269, 128], [284, 100], [353, 82], [388, 103], [438, 92], [466, 118],
  [485, 157], [498, 179], [525, 151], [543, 120], [582, 136], [620, 103],
  [683, 116], [723, 95], [754, 122], [790, 124], [841, 153], [845, 181],
  [901, 168], [917, 206], [950, 221], [931, 263], [958, 298], [930, 338],
  [946, 365], [923, 400], [887, 413], [877, 456], [828, 475], [804, 531],
  [755, 567], [712, 562], [703, 529], [722, 489], [691, 453], [661, 443],
  [633, 461], [608, 498], [583, 515], [598, 551], [573, 594], [516, 604],
  [482, 574], [438, 590], [408, 573], [369, 577], [347, 549], [309, 559],
  [290, 537], [239, 549], [204, 526], [158, 535], [109, 507], [118, 471],
  [94, 454], [108, 413], [80, 391], [95, 355], [68, 330], [85, 295],
]

// Match the starting owners in contracts/examples/state.json. Keep this seed
// order stable because each index identifies a province in the engine state.
const regions = {
  valdoria: [[244, 365], [142, 378], [164, 463], [233, 486], [309, 470], [351, 393], [313, 331], [188, 315]],
  ostrava: [[776, 232], [864, 183], [896, 246], [878, 309], [799, 316], [713, 275], [666, 207], [755, 156], [644, 141]],
  zarnia: [[774, 432], [706, 346], [710, 415], [815, 380], [878, 397], [783, 502], [571, 207], [540, 271], [572, 347], [619, 405]],
  kessaria: [[549, 465], [388, 482], [441, 532], [518, 550], [465, 414]],
  nordhaven: [[337, 174], [125, 227], [200, 207], [230, 158], [275, 241], [366, 253], [419, 196], [426, 133]],
}
const seeds = Object.values(regions).flat()

// Subdivide the coast with seeded offsets to give the chart small inlets and headlands.
let seed = 7
function random() {
  seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
  return seed / 2 ** 32
}
const shoreline = coast.flatMap(([x, y], index) => {
  const [nextX, nextY] = coast[(index + 1) % coast.length]
  const dx = nextX - x
  const dy = nextY - y
  const length = Math.hypot(dx, dy)
  return [[x, y], ...[0.25, 0.5, 0.75].map((fraction) => {
    const offset = (random() - 0.5) * 12
    return [
      Math.round(x + dx * fraction - dy * offset / length),
      Math.round(y + dy * fraction + dx * offset / length),
    ]
  })]
})

const voronoi = Delaunay.from(seeds).voronoi(bounds)

const borderEdges = new Map()
const provinces = seeds.map((center, index) => {
  const id = `p${String(index + 1).padStart(2, '0')}`
  const vertices = voronoi.cellPolygon(index).map((point) => point.map((value) => Number(value.toFixed(1))).join(','))
  for (let n = 1; n < vertices.length; n += 1) {
    const edge = [vertices[n - 1], vertices[n]].sort().join('L')
    const owners = borderEdges.get(edge) ?? []
    owners.push(id)
    borderEdges.set(edge, owners)
  }
  return { id, center, path: `M${vertices.slice(0, -1).join('L')}Z` }
})
const borders = []
for (const [edge, ids] of borderEdges) {
  if (ids.length === 2) borders.push({ between: ids, path: `M${edge}` })
}
const capitals = Object.fromEntries(Object.entries(regions).map(([nation, points]) => [nation, points[0]]))
const map = { width: bounds[2], height: bounds[3], coast: `M${shoreline.join('L')}Z`, capitals }
// One province or border per line keeps geometry diffs easy to scan.
function entries(items) {
  return items.map((item) => `    ${JSON.stringify(item)}`).join(',\n')
}
writeFileSync(new URL('../src/map.json', import.meta.url), `${JSON.stringify(map, null, 2).slice(0, -2)},\n  "provinces": [\n${entries(provinces)}\n  ],\n  "borders": [\n${entries(borders)}\n  ]\n}\n`)
