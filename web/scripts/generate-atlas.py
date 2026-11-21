"""Generate the campaign atlas and navigable routes from the authored province map.

Run after npm run generate:map in web. The generator uses Shapely, which the game
server itself does not need. Province IDs and opening owners remain stable.
"""

from itertools import combinations, product
import heapq
import json
import math
from pathlib import Path
import re

from shapely import affinity, voronoi_polygons
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.ops import unary_union

from atlas_infrastructure import urban_network

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "web" / "src" / "map.json"
DATA = ROOT / "data"
WIDTH, HEIGHT = 1740, 1060
# Original coastline outlines in atlas coordinates. The inner sea divides the
# northern island from the mainland while the south coast has a sheltered gulf.
MAINLAND = [
    (108, 657), (92, 567), (126, 530), (113, 467), (170, 430),
    (236, 425), (279, 387), (375, 415), (452, 385), (496, 322),
    (557, 313), (580, 247), (629, 239), (659, 186), (732, 195),
    (789, 122), (850, 105), (907, 133), (989, 98), (1087, 102),
    (1141, 68), (1214, 93), (1277, 65), (1385, 83), (1440, 51),
    (1521, 79), (1573, 157), (1550, 222), (1587, 291), (1561, 416),
    (1585, 482), (1554, 570), (1580, 672), (1549, 741), (1563, 837),
    (1515, 909), (1437, 923), (1397, 880), (1344, 899), (1265, 874),
    (1170, 892), (1108, 860), (1049, 873), (1011, 843), (966, 842),
    (927, 803), (876, 799), (841, 841), (854, 875), (815, 923),
    (734, 934), (671, 900), (579, 942), (528, 922), (439, 940),
    (347, 917), (314, 877), (241, 877), (193, 843), (219, 793),
    (162, 772), (137, 715),
]
ISLAND = [
    (55, 247), (70, 200), (52, 173), (88, 132), (126, 136),
    (147, 91), (199, 101), (220, 63), (282, 68), (313, 42),
    (366, 62), (413, 51), (450, 74), (489, 64), (533, 94),
    (541, 135), (570, 148), (558, 204), (583, 229), (560, 278),
    (574, 311), (524, 333), (486, 321), (445, 344), (417, 317),
    (371, 329), (327, 305), (291, 333), (242, 350), (218, 317),
    (159, 329), (123, 286), (71, 287),
]
ISLETS = [
    [(604, 126), (618, 107), (645, 106), (655, 126), (635, 145), (609, 144)],
    [(127, 362), (141, 349), (163, 357), (159, 377), (139, 385)],
    [(912, 886), (930, 870), (949, 878), (953, 902), (925, 909)],
]
LAKES = [(469, 654, 24, 12), (381, 159, 24, 13), (1270, 460, 32, 16), (1170, 715, 21, 13)]
PORTS = {
    "valdoria": ("p03", (185, 815)), "nordhaven": ("p34", (90, 310)),
    "ostrava": ("p10", (1620, 283)), "kessaria": ("p31", (886, 866)),
    "zarnia": ("p23", (1230, 938)),
}


def coastline(points):
    # Deterministic smaller bends between the large geographic features.
    expanded = []
    for a, b in zip(points, points[1:] + points[:1]):
        expanded.append(a)
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        for step in range(1, math.ceil(length / 14)):
            t = step / math.ceil(length / 14)
            bend = 4 * math.sin(a[0] * .09 + a[1] * .04 + step * 1.8)
            expanded.append((a[0] + dx * t - bend * dy / length, a[1] + dy * t + bend * dx / length))
    return Polygon(expanded).buffer(4).buffer(-4)


def position(point, owner):
    x, y = point
    if owner == "nordhaven":
        return (round((x - 65) * 1.16 + 101), round((y - 90) * 1.53 + 108))
    return (round(x * 1.43 + 119), round(y * 1.32 + 112))


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
    entries = base["provinces"]
    land = {"main": coastline(MAINLAND), "island": coastline(ISLAND)}
    lakes = [affinity.scale(Point(x, y).buffer(1, quad_segs=12), rx, ry, origin=(x, y))
             for x, y, rx, ry in LAKES]
    for zone in land:
        land[zone] = land[zone].difference(unary_union(lakes))
    shores = unary_union([*land.values(), *(coastline(points) for points in ISLETS)])
    cells, centers = {}, {}
    for zone, shore in land.items():
        region = [p for p in entries if (owners[p["id"]] == "nordhaven") == (zone == "island")]
        points = [position(p["center"], owners[p["id"]]) for p in region]
        raw = voronoi_polygons(MultiPoint(points), extend_to=Polygon([(-320,-320),(1920,-320),(1920,1280),(-320,1280)]),
                               ordered=True)
        for entry, point, cell in zip(region, points, raw.geoms, strict=True):
            clipped = cell.intersection(shore)
            assert not clipped.is_empty, entry["id"]
            center = Point(point)
            if not clipped.contains(center):
                center = clipped.representative_point()
            cells[entry["id"]] = clipped
            centers[entry["id"]] = [round(center.x, 1), round(center.y, 1)]

    provinces = [{"id": p["id"], "center": centers[p["id"]], "path": path_for(cells[p["id"]])} for p in entries]
    borders = []
    adjacency = {province: [] for province in owners}
    for a, b in combinations(cells, 2):
        line = cells[a].boundary.intersection(cells[b].boundary)
        if line.length < 1:
            continue
        pieces = [line] if line.geom_type == "LineString" else [part for part in line.geoms if part.geom_type == "LineString"]
        path = "".join("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in piece.coords)
                       for piece in pieces if piece.length > 0)
        if path:
            adjacency[a].append(b)
            adjacency[b].append(a)
            borders.append({"between": [a, b], "path": path})

    capital_provinces = {owner: next(p for p, n in owners.items() if n == owner) for owner in PORTS}
    ratio = round(shores.area / (WIDTH * HEIGHT), 3)
    print(f"Atlas land coverage: {ratio:.1%}")
    assert .57 <= ratio <= .63
    write_data(SOURCE.with_name("atlas.json"), {
        "width": WIDTH, "height": HEIGHT, "coast": path_for(shores),
        "landFraction": ratio,
        "capitals": {nation: centers[p] for nation, p in capital_provinces.items()},
    }, (("provinces", provinces), ("borders", borders)))
    write_data(DATA / "atlas_adjacency.json", {p: sorted(q) for p, q in adjacency.items()})

    ports = {nation: {"province": province, "position": point} for nation, (province, point) in PORTS.items()}
    routes = sea_routes(shores, {nation: port["position"] for nation, port in ports.items()})
    write_data(DATA / "sea_routes.json", {"ports": ports, "routes": routes})

    counties = json.loads((DATA / "counties.json").read_text())
    cities = {}
    for county in counties:
        p = next((p for p in county["provinces"] if p in capital_provinces.values()), county["provinces"][0])
        cities[p] = {"name": county["name"], "resource": county["resource"], "output": county["output"],
                     "capital": p in capital_provinces.values()}
    # City routes follow province adjacencies. Keep only the shortest connections
    # that join another station, plus one cross-border link per adjacent pair.
    def shortest(start):
        queue, distances, paths = [(0., start)], {start: 0.}, {start: [start]}
        while queue:
            distance, p = heapq.heappop(queue)
            if distance != distances[p]:
                continue
            for q in adjacency[p]:
                cost = distance + math.dist(centers[p], centers[q])
                if cost < distances.get(q, math.inf):
                    distances[q] = cost
                    paths[q] = [*paths[p], q]
                    heapq.heappush(queue, (cost, q))
        return distances, paths

    def track_points(via):
        out = [centers[via[0]]]
        for a, b in zip(via, via[1:]):
            start, end = centers[a], centers[b]
            corridor = cells[a].union(cells[b]).buffer(.3)
            if not corridor.covers(LineString([start, end])):
                x0, y0, x1, y1 = corridor.bounds
                candidates = [(x, y) for x in range(math.ceil(x0), math.floor(x1), 5)
                              for y in range(math.ceil(y0), math.floor(y1), 5)]
                candidates.sort(key=lambda point: math.dist(start, point) + math.dist(end, point))
                waypoint = next(point for point in candidates if corridor.covers(LineString([start, point, end])))
                out.append(waypoint)
            out.append(end)
        return out

    links = []
    for a in cities:
        distances, paths = shortest(a)
        for b in sorted((b for b in cities if b != a and b in distances), key=distances.get)[:3]:
            key = "|".join(sorted([a, b]))
            if not any(link["id"] == key for link in links):
                links.append({"id": key, "from": a, "to": b, "via": paths[b], "points": track_points(paths[b])})
    write_data(DATA / "rail.json", {"cities": cities}, (("routes", links),))
    urban_network(DATA, centers, cells, adjacency, owners, cities, shores, track_points)


if __name__ == "__main__":
    generate()
