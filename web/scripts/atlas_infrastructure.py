"""Author the terrain-aware roads and continuous urban fabric for the campaign atlas."""

import json
import math
import random
from pathlib import Path

from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely.prepared import prep


RIVERS = [
    [(750,306),(710,368),(681,444),(611,520),(548,595),(469,654),(407,682),(367,714),(293,756),(203,754),(108,727)],
    [(316,587),(369,618),(404,684)], [(779,436),(722,438),(648,479)],
    [(381,159),(365,206),(396,244),(418,257),(454,288),(485,326)],
    [(381,159),(309,164),(271,173),(244,196),(186,209),(92,211)],
    [(1423,211),(1399,300),(1344,355),(1270,460),(1212,488),(1176,572),(1170,715),(1218,817),(1259,916)],
    [(1530,400),(1432,428),(1270,460)], [(1104,323),(1151,373),(1228,397)], [(987,664),(1074,686),(1170,715)],
    [(876,540),(849,583),(850,621),(890,660),(883,712),(871,758),(922,808)],
]

BIOMES = {
    "taiga": {"label":"Boreal forest","color":"#435a49","speed":.77},
    "highlands": {"label":"Rocky highlands","color":"#6b6858","speed":.63},
    "woodland": {"label":"Temperate woodland","color":"#506747","speed":.81},
    "farmland": {"label":"Agricultural plain","color":"#858459","speed":1},
    "marsh": {"label":"River floodplain","color":"#627963","speed":.69},
    "dryland": {"label":"Dry coastal scrub","color":"#8d795b","speed":.89},
}


def biome(point, river):
    x, y = point
    if river.distance(Point(point)) < 24:
        return "marsh"
    if y < 325 and x < 590:
        return "taiga" if (x + y * .6) % 180 > 35 else "highlands"
    if 565 < x < 1100 and y < 565:
        return "highlands" if y < 380 else "woodland"
    if y > 775 and x > 590:
        return "dryland"
    return "woodland" if math.sin(x / 118) + math.cos(y / 109) > .28 else "farmland"


def rounded(point):
    return [round(v, 1) for v in point]


def urban_network(data, centers, cells, adjacency, owners, cities, land, track_points):
    rivers = [LineString(points) for points in RIVERS]
    river = unary_union(rivers)
    biomes = {p: biome(point, river) for p, point in centers.items()}
    roads = []
    for a, neighbors in adjacency.items():
        for b in neighbors:
            if b <= a:
                continue
            try:
                points = track_points([a, b])
            except StopIteration:
                continue  # a narrow boundary can have no two-segment road corridor
            line = LineString(points)
            crossing = line.intersection(river)
            bridges = []
            for point in ([crossing] if crossing.geom_type == "Point" else getattr(crossing, "geoms", [])):
                if point.geom_type != "Point" or point.is_empty:
                    continue
                d = line.project(point)
                if 4 < d < line.length - 4:
                    start, end = line.interpolate(d - 7), line.interpolate(d + 7)
                    bridges.append([rounded(start.coords[0]), rounded(end.coords[0])])
            main = (a in cities and b in cities) or owners[a] != owners[b]
            terrain = min(BIOMES[biomes[a]]["speed"], BIOMES[biomes[b]]["speed"])
            roads.append({"id": f"{a}|{b}", "a": a, "b": b, "points": points, "bridges": bridges,
                          "kind": "motorway" if main else "road", "speed": terrain,
                          "length": round(line.length)})

    usable = prep(land.buffer(-2).difference(river.buffer(5)))
    settlements = []
    for i, (province, center) in enumerate(centers.items()):
        city = cities.get(province)
        terrain = biomes[province]
        rng = random.Random(i * 379 + 51)
        x, y = center
        radius = 55 if city and city["capital"] else 39 if city else 19
        if terrain in ("highlands", "taiga"):
            radius *= .85
        # Curved local streets track water and connect their built-up neighbourhoods.
        streets, lots = [], []
        usable_streets = []
        for angle in (.1, .92, 1.68, 2.45):
            dx, dy = math.cos(angle), math.sin(angle)
            for branch in (-1, 1):
                coordinates = [(x + branch * dx * radius*.2, y + branch * dy * radius*.2),
                               (x + branch * dx * radius*.58 - dy * radius*.14, y + branch * dy * radius*.58 + dx * radius*.14),
                               (x + branch * dx * radius, y + branch * dy * radius)]
                line = LineString(coordinates)
                if usable.covers(line):
                    streets.append([rounded(p) for p in coordinates])
                    usable_streets.append(line)
        attempts = 320 if city and city["capital"] else 205 if city else 68
        for _ in range(attempts):
            angle = rng.random() * math.tau
            r = (rng.random() ** .68) * radius
            px, py = x + math.cos(angle)*r, y + math.sin(angle)*r*.78
            point = Point(px, py)
            if not usable.contains(point) or not cells[province].contains(point):
                continue
            if usable_streets and min(street.distance(point) for street in usable_streets) < 2.6:
                continue
            if terrain == "woodland" and r > radius*.7 and rng.random() < .35:
                continue
            kind = "tower" if city and city["capital"] and r < radius*.48 else (
                "industrial" if city and city["resource"] in ("oil", "chips") and px > x else
                "commercial" if city and r < radius*.62 else "house")
            width, depth = ((3.3, 3.8) if kind == "tower" else (4.6, 3.2) if kind == "industrial" else (2.5, 2.2))
            if any((old[0]-px)**2 + (old[1]-py)**2 < (width*.76+old[2]*.58)**2 for old in lots):
                continue
            lots.append([round(px,1),round(py,1),width,depth,kind,rng.randrange(5)])
        settlements.append({"id":province,"center":center,"streets":streets,"lots":lots,"radius":round(radius,1)})

    (Path(data) / "infrastructure.json").write_text(json.dumps({
        "biomes":BIOMES,"regions":biomes,"rivers":RIVERS,"roads":roads,"settlements":settlements,
    }, separators=(",", ":")) + "\n", encoding="utf-8")
