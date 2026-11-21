"""Generate the campaign atlas and navigable routes from the authored province map.

Run after npm run generate:map in web. The generator uses Shapely, which the game
server itself does not need. Province IDs and opening owners remain stable.
"""

from collections import defaultdict
from itertools import combinations, product
import heapq
import json
import math
from pathlib import Path
import re

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "web" / "src" / "map.json"
DATA = ROOT / "data"
WIDTH, HEIGHT = 1760, 1000
LANDMASSES = {
    "valdoria": (120, 230), "kessaria": (120, 230),
    "nordhaven": (55, 20),
    "ostrava": (690, 245), "zarnia": (690, 245),
}
LAKES = (("valdoria", (329, 387), 18, 10), ("nordhaven", (332, 163), 14, 8),
         ("ostrava", (767, 294), 23, 12), ("zarnia", (766, 441), 13, 8))
PORTS = {
    "valdoria": ("p03", (80, 500)), "nordhaven": ("p34", (20, 200)),
    "ostrava": ("p10", (880, 140)), "kessaria": ("p31", (520, 640)),
    "zarnia": ("p23", (760, 600)),
}


def vertices(path):
    return [tuple(map(float, item.split(","))) for item in re.findall(r"-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?", path)]


def shift(point, nation):
    dx, dy = LANDMASSES[nation]
    return (point[0] + dx, point[1] + dy)


def path_for(geometry):
    def ring(coords):
        return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in list(coords)[:-1]) + "Z"

    if geometry.geom_type == "Polygon":
        return ring(geometry.exterior.coords) + "".join(ring(hole.coords) for hole in geometry.interiors)
    return "".join(path_for(child) for child in geometry.geoms if child.area > 0)


def write_data(path, main, lists=()):
    body = json.dumps(main, indent=2)[:-2]
    for name, entries in lists:
        rows = ",\n".join("    " + json.dumps(entry, separators=(",", ":")) for entry in entries)
        body += f',\n  "{name}": [\n{rows}\n  ]'
    path.write_text(body + "\n}\n", encoding="utf-8")


def sea_routes(land, port_coords):
    blocked = land.buffer(13)
    step = 24
    water = {(x, y) for x in range(0, WIDTH + 1, step) for y in range(0, HEIGHT + 1, step)
             if not blocked.intersects(Point(x, y))}
    directions = [(dx, dy, math.hypot(dx, dy)) for dx, dy in product((-step, 0, step), repeat=2) if dx or dy]

    def visible(a, b):
        return not blocked.intersects(LineString([a, b]))

    anchors = {}
    for nation, point in port_coords.items():
        anchors[nation] = next(candidate for candidate in sorted(water, key=lambda v: (math.dist(v, point), v))
                               if visible(point, candidate))

    def route(source, target):
        start, end = anchors[source], anchors[target]
        costs, parents, queue = {start: 0}, {}, [(0.0, start)]
        while queue:
            distance, p = heapq.heappop(queue)
            if p == end:
                break
            if distance != costs[p]:
                continue
            for dx, dy, weight in directions:
                q = (p[0] + dx, p[1] + dy)
                cost = distance + weight
                if q in water and cost < costs.get(q, math.inf) and visible(p, q):
                    costs[q], parents[q] = cost, p
                    heapq.heappush(queue, (cost, q))
        trail = [end]
        while trail[-1] != start:
            trail.append(parents[trail[-1]])
        trail = [port_coords[source], *reversed(trail), port_coords[target]]
        simplified = [trail[0]]
        cursor = 0
        while cursor < len(trail) - 1:
            cursor = next(i for i in range(len(trail) - 1, cursor, -1) if visible(simplified[-1], trail[i]))
            simplified.append(trail[cursor])
        return simplified

    return {f"{a}|{b}": route(a, b) for a, b in combinations(sorted(port_coords), 2)}


def generate():
    base = json.loads(SOURCE.read_text())
    countries = json.loads((DATA / "nations.json").read_text())
    owners = countries["provinces"]
    seed_coast = Polygon(vertices(base["coast"])).buffer(2).buffer(-2)
    zones = defaultdict(list)
    for entry in base["provinces"]:
        offset = LANDMASSES[owners[entry["id"]]]
        zones[offset].append(Polygon(vertices(entry["path"])).intersection(seed_coast))
    water = defaultdict(list)
    for nation, center, rx, ry in LAKES:
        lake = affinity.scale(Point(center).buffer(1, quad_segs=8), rx, ry, origin=center)
        water[LANDMASSES[nation]].append(lake)
    shapes = {
        offset: unary_union(items).buffer(-3).buffer(3).difference(unary_union(water[offset]))
        for offset, items in zones.items()
    }
    continents = [affinity.translate(shape, *offset) for offset, shape in shapes.items()]
    shores = unary_union(continents)

    provinces = []
    for entry in base["provinces"]:
        nation = owners[entry["id"]]
        offset = LANDMASSES[nation]
        geometry = Polygon(vertices(entry["path"])).intersection(shapes[offset])
        provinces.append({"id": entry["id"], "center": shift(entry["center"], nation),
                          "path": path_for(affinity.translate(geometry, *offset))})

    borders = []
    adjacency = {province: [] for province in owners}
    for edge in base["borders"]:
        a, b = edge["between"]
        offset = LANDMASSES[owners[a]]
        if offset != LANDMASSES[owners[b]]:
            continue
        line = LineString(vertices(edge["path"])).intersection(shapes[offset])
        if line.is_empty:
            continue
        pieces = [line] if line.geom_type == "LineString" else [part for part in line.geoms if part.geom_type == "LineString"]
        path = "".join("M" + "L".join(f"{x + offset[0]:.1f},{y + offset[1]:.1f}" for x, y in piece.coords)
                       for piece in pieces if piece.length > 0)
        if path:
            adjacency[a].append(b)
            adjacency[b].append(a)
            borders.append({"between": [a, b], "path": path})

    write_data(SOURCE.with_name("atlas.json"), {
        "width": WIDTH, "height": HEIGHT, "coast": path_for(shores),
        "capitalOffsets": LANDMASSES,
        "capitals": {nation: shift(point, nation) for nation, point in base["capitals"].items()},
    }, (("provinces", provinces), ("borders", borders)))
    write_data(DATA / "atlas_adjacency.json", {p: sorted(q) for p, q in adjacency.items()})

    ports = {nation: {"province": province, "position": shift(point, nation)}
             for nation, (province, point) in PORTS.items()}
    routes = sea_routes(shores, {nation: port["position"] for nation, port in ports.items()})
    write_data(DATA / "sea_routes.json", {"ports": ports, "routes": routes})


if __name__ == "__main__":
    generate()
