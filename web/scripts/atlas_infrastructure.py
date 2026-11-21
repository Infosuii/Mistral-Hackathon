"""Author the terrain-aware roads, rivers, airports and city plans for the campaign atlas.

Coordinates arrive already scaled to the generated world (see SCALE in generate-atlas.py).
The authored river courses and biome bands are written at 1x and scaled here. Everything
is seeded, so regenerating without source changes reproduces the same files.

Output (data/infrastructure.json):
  biomes, regions       biome definitions and each province's biome
  rivers                [{"points", "width"}] smoothed courses, drawn and bridged as-is
  roads                 province-to-province links; "length" is centre to centre for the
                        engine's travel time, "points" stop at each town's ring road
  junctions             [x, y, angle, kind] interchanges where a road meets a town
  settlements           per province: streets, building lots, parks, an airport site,
                        industrial facility sites and the surrounding farm fields
"""

import json
import math
import random
from pathlib import Path

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union
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

# Lot footprints (frontage, depth) and the spacing between neighbours along a street.
LOT = {"house": (5.4, 4.8, 2.4), "commercial": (8.5, 7.5, 2.2), "tower": (8, 8, 3.5),
       "industrial": (14, 10, 3), "civic": (12, 9, 4)}
# Field crop tones by biome (indexes the renderer's six crop colours).
CROPS = {"farmland": [0, 1, 2, 3, 4, 5, 0, 1], "marsh": [1, 2, 5, 2], "dryland": [0, 3, 3, 4], "woodland": [1, 2, 5]}
STREET_HALF = {"arterial": 2.6, "street": 1.7}


def biome(point, river, scale):
    """Biome bands are authored at 1x."""
    x, y = point[0] / scale, point[1] / scale
    if river.distance(Point(point)) < 24 * scale:
        return "marsh"
    if y < 325 and x < 590:
        return "taiga" if (x + y * .6) % 180 > 35 else "highlands"
    if 565 < x < 1100 and y < 565:
        return "highlands" if y < 380 else "woodland"
    if y > 775 and x > 590:
        return "dryland"
    return "woodland" if math.sin(x / 118) + math.cos(y / 109) > .28 else "farmland"


def rounded(point, digits=1):
    return [round(v, digits) for v in point]


def chaikin(points, rounds=3):
    for _ in range(rounds):
        out = [points[0]]
        for a, b in zip(points, points[1:]):
            out += [(a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25), (a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75)]
        out.append(points[-1])
        points = out
    return points


def pieces(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "LineString":
        return [geometry]
    return [g for g in getattr(geometry, "geoms", []) if g.geom_type == "LineString"]


def thin(line, tolerance=.6):
    return [rounded(p) for p in line.simplify(tolerance).coords]


def rect(x, y, w, d, angle):
    c, s = math.cos(angle), math.sin(angle)
    return Polygon([(x + c * u - s * v, y + s * u + c * v) for u, v in ((-w/2, -d/2), (w/2, -d/2), (w/2, d/2), (-w/2, d/2))])


def curved_road(points, corridor, rng):
    """Bend a straight corridor gently so motorways sweep instead of ruling straight lines."""
    if len(points) != 2:
        return chaikin([tuple(p) for p in points], 3)
    (x0, y0), (x1, y1) = points
    length = math.dist(points[0], points[1])
    for bend in (.09, -.07, .05, 0):
        sign = 1 if rng.random() < .5 else -1
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        ox, oy = -(y1 - y0) / length * bend * sign * length, (x1 - x0) / length * bend * sign * length
        trial = chaikin([(x0, y0), (x0 * .7 + x1 * .3 + ox * .7, y0 * .7 + y1 * .3 + oy * .7),
                         (mx + ox, my + oy), (x0 * .3 + x1 * .7 + ox * .7, y0 * .3 + y1 * .7 + oy * .7), (x1, y1)], 3)
        if corridor.covers(LineString(trial)):
            return trial
    return [tuple(points[0]), tuple(points[1])]


def bridges_for(line, water):
    """Each river crossing becomes a deck that starts and ends on dry ground."""
    spans = []
    for part in pieces(line.intersection(water)):
        a = line.project(Point(part.coords[0]))
        b = line.project(Point(part.coords[-1]))
        a, b = min(a, b) - 3, max(a, b) + 3
        if a > 0 and b < line.length:
            spans.append(thin(substring(line, a, b), .2))
    return spans


def urban_network(data, centers, cells, adjacency, owners, cities, land, track_points, rail_links, scale):
    rivers = []
    for course in RIVERS:
        points = [(x * scale, y * scale) for x, y in chaikin(course, 3)]
        rivers.append({"points": [rounded(p) for p in points], "width": 13 if len(course) > 4 else 8})
    river_lines = [LineString(r["points"]) for r in rivers]
    river = unary_union(river_lines)
    water = unary_union([line.buffer(r["width"] / 2 + 1.5) for line, r in zip(river_lines, rivers)])
    biomes = {p: biome(point, river, scale) for p, point in centers.items()}

    def radius_of(province):
        city = cities.get(province)
        r = 245 if city and city["capital"] else 180 if city else 92
        nearest = min((math.dist(centers[province], centers[q]) for q in adjacency[province]), default=1e9)
        return min(r, nearest * .46) * (.82 if biomes[province] in ("highlands", "taiga") else 1)

    # Rail runs a little to one side of the road corridor between the same stations, with
    # gentle curves; it keeps to land and falls back to the surveyed line if it cannot.
    for link in rail_links:
        line = LineString(link["points"])
        corridor = unary_union([cells[p] for p in link["via"]]).buffer(.3 * scale)
        moved = line.offset_curve(16)
        if moved.geom_type == "LineString" and len(moved.coords) > 1:
            interior = list(moved.coords)
            middle = interior[1:-1] or [interior[len(interior) // 2]]
            trial = chaikin([tuple(link["points"][0]), *middle, tuple(link["points"][-1])], 2)
            if corridor.covers(LineString(trial)):
                link["points"] = [rounded(p) for p in LineString(trial).simplify(.5).coords]
        link["bridges"] = bridges_for(LineString(link["points"]), water)

    intercity = set()
    for link in rail_links:
        intercity |= {"|".join(sorted(pair)) for pair in zip(link["via"], link["via"][1:])}

    roads, junctions, no_build = [], [], []
    for a, neighbors in adjacency.items():
        for b in neighbors:
            if b <= a:
                continue
            try:
                points = track_points([a, b])
            except StopIteration:
                continue  # a narrow boundary can have no two-segment road corridor
            corridor = cells[a].union(cells[b]).buffer(.3 * scale)
            rng = random.Random(f"{a}|{b}")
            full = LineString(curved_road(points, corridor, rng))
            ra, rb = radius_of(a) * .5, radius_of(b) * .5
            if full.length <= ra + rb + 20:
                continue
            line = substring(full, ra, full.length - rb)
            kind = "motorway" if f"{a}|{b}" in intercity else "road"
            terrain = min(BIOMES[biomes[a]]["speed"], BIOMES[biomes[b]]["speed"])
            for end, toward in ((line.coords[0], line.coords[1]), (line.coords[-1], line.coords[-2])):
                angle = math.degrees(math.atan2(toward[1] - end[1], toward[0] - end[0]))
                junctions.append([*rounded(end), round(angle), "interchange" if kind == "motorway" else "roundabout"])
            roads.append({"id": f"{a}|{b}", "a": a, "b": b, "points": thin(line), "bridges": bridges_for(line, water),
                          "kind": kind, "speed": terrain, "length": round(full.length)})
            no_build.append(line.buffer(9 if kind == "motorway" else 6))
    for link in rail_links:
        no_build.append(LineString(link["points"]).buffer(4))
    blocked = prep(unary_union(no_build))

    settlements = []
    for i, (province, center) in enumerate(centers.items()):
        # A town may spread into the next province when the same nation holds it.
        home = unary_union([cells[q] for q in [province, *adjacency[province]] if owners[q] == owners[province]])
        settlements.append(settlement(province, center, cells[province], home, cities.get(province), biomes[province],
                                      radius_of(province), land, river, water, blocked, random.Random(i * 379 + 51)))

    (Path(data) / "infrastructure.json").write_text(json.dumps({
        "scale": scale, "biomes": BIOMES, "regions": biomes, "rivers": rivers, "roads": roads,
        "junctions": junctions, "settlements": settlements,
    }, separators=(",", ":")) + "\n", encoding="utf-8")


def settlement(province, center, cell, home, city, terrain, radius, land, river, water, blocked, rng):
    x, y = center
    capital = bool(city and city["capital"])
    # Floodplain towns keep back from the river behind levee parks; others build to the bank.
    clearance = 34 if terrain == "marsh" else 12
    usable = land.buffer(-5).intersection(home.buffer(-3)).difference(river.buffer(clearance))
    room = prep(usable)
    theta = rng.random() * math.pi
    squash = .66 if terrain in ("highlands", "taiga") else .9  # valley towns stretch along one axis

    def warp(px, py):
        """Local plan coordinates (circle) to the map: rotated and squashed by terrain."""
        u, v = px, py * squash
        return x + u * math.cos(theta) - v * math.sin(theta), y + u * math.sin(theta) + v * math.cos(theta)

    def plan_line(points):
        return LineString([warp(px, py) for px, py in points])

    streets = []  # (tier, LineString)

    def add(tier, line):
        for part in pieces(line.intersection(usable)):
            if part.length > 10:
                streets.append((tier, part))

    R = radius
    town = city is None
    # Ring road and radial avenues: the skeleton every district hangs off.
    ring_r = R * .5
    add("arterial", plan_line([(ring_r * math.cos(t / 40 * math.tau), ring_r * math.sin(t / 40 * math.tau)) for t in range(41)]))
    spokes = 4 if town else 8 if capital else 6
    angles = [k * math.tau / spokes + rng.uniform(-.18, .18) for k in range(spokes)]
    for k, a in enumerate(angles):
        bend = rng.uniform(-.25, .25)
        add("arterial", plan_line([(r * math.cos(a + bend * r / R), r * math.sin(a + bend * r / R))
                                   for r in [0, R * .25, R * .5, R * .75, R * 1.02]]))
    # Downtown grid inside the ring; its blocks are filled whole further down.
    step = 26 if capital else 30
    blocks = []
    if not town:
        count = int(ring_r // step)
        for k in range(-count, count + 1):
            off = k * step
            half = math.sqrt(max(0, (ring_r * .97) ** 2 - off ** 2))
            if half > 8:
                add("street", plan_line([(-half, off), (half, off)]))
                add("street", plan_line([(off, -half), (off, half)]))
        for i in range(-count, count):
            for j in range(-count, count):
                cx, cy = (i + .5) * step, (j + .5) * step
                if math.hypot(abs(cx) + step / 2, abs(cy) + step / 2) < ring_r * .97:
                    blocks.append((cx, cy))
    else:  # a market town: a crossroads high street through the centre
        add("street", plan_line([(-ring_r, 0), (ring_r, 0)]))
        add("street", plan_line([(0, -ring_r), (0, ring_r)]))
    # Curving suburban crescents, back to back, with loop closes between the avenues.
    spacing = 19
    bands = [r / R for r in [ring_r + spacing * (n + 1) for n in range(int((R - ring_r) // spacing))]]
    industrial_sector = rng.random() * math.tau
    for k, a in enumerate(angles):
        b = angles[(k + 1) % spokes] + (math.tau if k + 1 == spokes else 0)
        middle = (a + b) / 2
        works = not town and abs((middle - industrial_sector + math.pi) % math.tau - math.pi) < .6
        for j, band in enumerate(bands):
            if works and j % 2:
                continue  # sheds need deeper plots: every other crescent in the works district
            wobble = rng.uniform(.04, .09)
            phase = rng.random() * math.tau
            arc = [(R * band * (1 + wobble * math.sin(phase + t * 3.1)) * math.cos(a + (b - a) * t),
                    R * band * (1 + wobble * math.sin(phase + t * 3.1)) * math.sin(a + (b - a) * t))
                   for t in [s / 18 for s in range(1, 18)]]
            add("street", plan_line(arc))
            if j < len(bands) - 1 and rng.random() < .3:
                # A cul-de-sac loop joining this crescent to the next, like a planned close.
                mid = a + (b - a) * rng.uniform(.3, .7)
                r0, r1 = R * band, R * bands[j + 1]
                loop = [((r0 + (r1 - r0) * t) * math.cos(mid + .05 * math.sin(t * math.pi)),
                         (r0 + (r1 - r0) * t) * math.sin(mid + .05 * math.sin(t * math.pi))) for t in (0, .5, 1)]
                add("street", plan_line(loop))

    street_union = unary_union([line.buffer(STREET_HALF[tier] + .6) for tier, line in streets]) if streets else Point(x, y).buffer(0)
    street_block = prep(street_union)

    # Parks: a central square and one green inside the suburbs.
    parks = []
    for r_park, rn in ((R * .1, 0), (R * .13, rng.uniform(.6, .85))):
        if town and rn == 0:
            continue
        a = rng.random() * math.tau
        px, py = warp(R * rn * math.cos(a), R * rn * math.sin(a))
        if room.contains(Point(px, py)):
            parks.append([round(px, 1), round(py, 1), round(r_park, 1)])
    park_block = prep(unary_union([Point(px, py).buffer(r) for px, py, r in parks])) if parks else None

    # Airport: a runway just outside town on open, dry, level ground.
    airport = None
    runway = 92 if terrain not in ("highlands", "taiga") else 74
    for distance in (1.35, 1.6, 1.9, 1.15, 2.2):
        for k in range(16):
            a = theta + k * math.tau / 16
            ax, ay = x + math.cos(a) * R * distance, y + math.sin(a) * R * distance
            for heading in (a + math.pi / 2, a, a + math.pi / 4, a - math.pi / 4):
                field = rect(ax, ay, runway + 10, 34, heading)
                if room.contains(field) and not blocked.intersects(field) and not water.intersects(field):
                    airport = {"at": rounded((ax, ay)), "angle": round(math.degrees(heading), 1), "length": runway}
                    access = LineString([(ax, ay), (x + math.cos(a) * R * .5, y + math.sin(a) * R * .5)])
                    add("arterial", access)
                    break
            if airport:
                break
        if airport:
            break
    airport_block = prep(rect(*airport["at"], runway + 16, 40, math.radians(airport["angle"]))) if airport else None

    # Facility sites for the engine's other buildings: industrial estates at the town edge.
    sites = []
    for k in range(40):
        if len(sites) == 4:
            break
        a = theta + math.pi + k * 2.4
        sx, sy = warp(R * 1.08 * math.cos(a), R * 1.08 * math.sin(a))
        spot = Point(sx, sy).buffer(16)
        if room.contains(spot) and not blocked.intersects(spot) and \
                not (airport_block and airport_block.intersects(spot)) and all(math.dist((sx, sy), s) > 34 for s in sites):
            sites.append(rounded((sx, sy)))
    site_block = prep(unary_union([Point(s).buffer(20) for s in sites])) if sites else None

    lots, placed = [], {}

    def free(poly, px, py, reach):
        cx, cy = int(px // 16), int(py // 16)
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for other in placed.get((gx, gy), []):
                    if other.distance(Point(px, py)) < reach and other.intersects(poly):
                        return False
        return True

    def zone(px, py):
        rn = math.dist((px, py), (x, y)) / R
        heading = math.atan2(py - y, px - x)
        if not town and abs((heading - industrial_sector + math.pi) % math.tau - math.pi) < .6 and rn > .45:
            return "industrial"
        if capital and rn < .3:
            return "tower"
        if not town and rn < .5:
            return "commercial"
        return "civic" if rng.random() < .025 else "house"

    def place(poly, px, py, w, d, kind, angle):
        if not room.contains(poly) or street_block.intersects(poly) or blocked.intersects(poly):
            return False
        if (park_block and park_block.intersects(poly)) or (airport_block and airport_block.intersects(poly)) \
                or (site_block and site_block.intersects(poly)):
            return False
        if not free(poly, px, py, max(w, d) + 14):
            return False
        placed.setdefault((int(px // 16), int(py // 16)), []).append(poly)
        lots.append([round(px, 1), round(py, 1), round(w, 1), round(d, 1), kind, rng.randrange(5), round(math.degrees(angle))])
        return True

    # Downtown blocks: towers and offices filling each block, split into two to four plots.
    inner = step - 2 * (STREET_HALF["street"] + 1.2)
    for cx, cy in blocks:
        rn = math.hypot(cx, cy) / R
        kind = "tower" if capital and rn < .3 else "commercial"
        split = 2 if kind == "tower" or rng.random() < .6 else 1
        sub = inner / split
        for u in range(split):
            for v in range(split):
                bx = cx - inner / 2 + sub * (u + .5)
                by = cy - inner / 2 + sub * (v + .5)
                px, py = warp(bx, by)
                w, d = sub - 1.6, sub * squash - 1.6
                place(rect(px, py, w, d, theta), px, py, w, d, "civic" if rng.random() < .03 else kind, theta)

    for tier, line in sorted(streets, key=lambda item: item[0] != "arterial"):
        distance = 4.0
        while distance < line.length - 4:
            p0, p1 = line.interpolate(distance - .5), line.interpolate(distance + .5)
            angle = math.atan2(p1.y - p0.y, p1.x - p0.x)
            mid = line.interpolate(distance)
            kind = zone(mid.x, mid.y)
            w, d, gap = LOT[kind]
            for side in (-1, 1):
                if terrain == "woodland" and rng.random() < .12:
                    continue  # woodland towns keep stands of trees between houses
                offset = STREET_HALF[tier] + .9 + d / 2
                px, py = mid.x - math.sin(angle) * offset * side, mid.y + math.cos(angle) * offset * side
                place(rect(px, py, w, d, angle), px, py, w, d, kind, angle)
            distance += w + gap

    # Farm fields: a patchwork of strip plots on agricultural, floodplain and scrub land.
    # Farmland is cultivated almost everywhere; woodland only in clearings.
    fields = []
    coverage = {"farmland": .8, "marsh": .45, "dryland": .3, "woodland": .16}.get(terrain, 0)
    if coverage:
        heading = rng.random() * math.pi
        u, v = (math.cos(heading), math.sin(heading)), (-math.sin(heading), math.cos(heading))
        town_zone = Point(x, y).buffer(R * 1.1)
        own = prep(cell)
        farm_room = prep(land.buffer(-5).intersection(cell.buffer(-4)).difference(river.buffer(clearance)))
        span = max(cell.bounds[2] - cell.bounds[0], cell.bounds[3] - cell.bounds[1])
        w, d, gap = 38, 17, 3
        for i in range(-int(span / (w + gap)), int(span / (w + gap)) + 1):
            for j in range(-int(span / (d + gap)), int(span / (d + gap)) + 1):
                if rng.random() > coverage:
                    continue
                stretch = rng.choice((1, 1, 1, .5))  # occasional half plots break up the pattern
                fx = x + u[0] * i * (w + gap) + v[0] * j * (d + gap)
                fy = y + u[1] * i * (w + gap) + v[1] * j * (d + gap)
                poly = rect(fx, fy, w * stretch, d, heading)
                if farm_room.contains(poly) and own.contains(poly) and not blocked.intersects(poly) \
                        and not town_zone.intersects(poly) and not (airport_block and airport_block.intersects(poly)) \
                        and not (site_block and site_block.intersects(poly)):
                    fields.append([round(fx, 1), round(fy, 1), round(w * stretch, 1), d,
                                   round(math.degrees(heading), 1), rng.choice(CROPS[terrain])])

    # Forest stands and peaks on open ground: clear of the town, fields, roads and water.
    # Trees cluster in stands; highland peaks run in loose ridges.
    flora = []
    density = {"taiga": 300, "woodland": 210, "marsh": 60, "highlands": 70, "farmland": 30, "dryland": 40}[terrain]
    open_ground = prep(land.buffer(-4).intersection(cell.buffer(-4)).difference(water))
    field_block = prep(unary_union([rect(fx, fy, fw, fd, math.radians(fa)) for fx, fy, fw, fd, fa, _ in fields])) if fields else None
    town_clear = Point(x, y).buffer(R * 1.06)
    x0, y0, x1, y1 = cell.bounds
    stands = [(rng.uniform(x0, x1), rng.uniform(y0, y1)) for _ in range(max(3, density // 22))]
    attempts = 0
    while len(flora) < density and attempts < density * 8:
        attempts += 1
        sx, sy = stands[attempts % len(stands)]
        spread = 55 if terrain != "highlands" else 90
        px, py = sx + rng.gauss(0, spread), sy + rng.gauss(0, spread * .7)
        point = Point(px, py)
        if not open_ground.contains(point) or town_clear.contains(point) or blocked.contains(point):
            continue
        if field_block and field_block.contains(point):
            continue
        if airport_block and airport_block.contains(point):
            continue
        roll = rng.random()
        if terrain == "highlands":
            kind = 2 if roll < .6 else 1
        elif terrain == "taiga":
            kind = 1 if roll < .85 else 0
        elif terrain == "woodland":
            kind = 3 if roll < .22 else 0
        elif terrain == "marsh":
            kind = 4 if roll < .55 else 0
        elif terrain == "dryland":
            kind = 5 if roll < .7 else 0
        else:
            kind = 0
        size = rng.uniform(9, 16) if kind == 2 else rng.uniform(1.6, 2.6) if kind in (4, 5) else rng.uniform(2.6, 4.4)
        flora.append([round(px, 1), round(py, 1), round(size, 1), kind])

    # Ground cover: broad soft patches of meadow, heath, scrub or sand that break up each
    # province's base colour. Tone indexes into the renderer's palette for the biome.
    patches = []
    for _ in range(26):
        px, py = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if open_ground.contains(Point(px, py)):
            patches.append([round(px), round(py), round(rng.uniform(40, 130)), rng.randrange(3)])

    return {
        "id": province, "center": center, "radius": round(R, 1),
        "streets": [[0 if tier == "arterial" else 1, thin(line)] for tier, line in streets],
        "lots": lots, "parks": parks, "airport": airport, "sites": sites, "fields": fields,
        "flora": flora,  # [x, y, size, kind]: 0 broadleaf, 1 conifer, 2 peak, 3 autumn tree, 4 reeds, 5 shrub
        "patches": patches,  # [x, y, radius, tone]
    }
