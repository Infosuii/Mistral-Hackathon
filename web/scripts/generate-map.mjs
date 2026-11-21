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

// The order defines stable IDs shared with the engine. Append new seeds at the end.
const regions = {
  valdoria: [[244, 365], [142, 378], [164, 463], [233, 486], [309, 470], [351, 393], [313, 331], [188, 315]],
  ostrava: [[776, 232], [864, 183], [896, 246], [878, 309], [799, 316], [713, 275], [666, 207], [755, 156]],
  nordhaven: [[337, 174], [125, 227], [200, 207], [230, 158], [275, 241], [366, 253], [419, 196], [426, 133]],
  kessaria: [[549, 465], [385, 487], [442, 536], [513, 548], [459, 450], [469, 368], [564, 349], [616, 407]],
  zarnia: [[774, 432], [706, 346], [710, 415], [815, 380], [878, 397], [783, 502], [571, 207], [540, 271]],
}
const seeds = [
  regions.valdoria[0],
  ...regions.ostrava,
  ...regions.valdoria.slice(1),
  ...regions.nordhaven,
  ...regions.kessaria,
  ...regions.zarnia,
]

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
const provinces = seeds.map((_, index) => ({
  id: `p${String(index + 1).padStart(2, '0')}`,
  path: voronoi.renderCell(index).replace(/-?\d+\.\d+/g, (number) => Number(number).toFixed(1)),
}))
const capitals = Object.fromEntries(Object.entries(regions).map(([nation, points]) => [nation, points[0]]))
const map = { width: bounds[2], height: bounds[3], coast: `M${shoreline.join('L')}Z`, capitals }
// A province per line keeps handoffs and diffs easy to scan.
const lines = JSON.stringify(map, null, 2).slice(0, -2)
const provinceLines = provinces.map((province) => `    ${JSON.stringify(province)}`).join(',\n')
writeFileSync(new URL('../src/map.json', import.meta.url), `${lines},\n  "provinces": [\n${provinceLines}\n  ]\n}\n`)
