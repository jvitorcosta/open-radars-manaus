"""The README's map (docs/map.svg): Manaus from OpenStreetMap, one sign per verified point and a legend.

GitHub's ```geojson map draws every pin the same, so this one is drawn here. The base map (river, green
areas, roads, street and neighbourhood names) comes from OpenStreetMap once (base_markup) and then lives
inside the SVG: rebuilding the points and the legend (build) reads it back from the file, so it needs no
network and gives the same bytes for the same rows.
"""
import math
import re

# Urban Manaus, west to east from Ponta Negra to the Zona Leste, north to south from the Tarumã to the river.
WEST, EAST, NORTH, SOUTH = -60.100, -59.880, -2.975, -3.150
WIDTH = 800
COS = math.cos(math.radians((NORTH + SOUTH) / 2))
HEIGHT = round(WIDTH * (NORTH - SOUTH) / ((EAST - WEST) * COS))
ROAD_CLASSES = ("tertiary", "secondary", "primary", "trunk", "motorway")   # drawn in this order, big on top
LABELLED = ("motorway", "trunk", "primary")
SIMPLIFY_PX = 1.5        # drop a vertex closer than this to the last one kept
MIN_AREA_PX = 6          # drop water and green rings smaller than this
STREET_LABELS = 16
LABEL_STEP_PX = 6       # coarser line used to find gentle stretches for names
LABEL_GAP_PX = 10       # pieces of one avenue this close are joined for its name
LEGEND = (12, HEIGHT - 176, 312, HEIGHT - 34)   # x0, y0, x1, y1: bottom left, over the Rio Negro
RIVER_LABEL = (-3.1345, -59.904, "Rio Negro")
ABBREVIATIONS = (("Avenida ", "Av. "), ("Estrada ", "Estr. "), ("Rua ", "R. "), ("Alameda ", "Al. "),
                 ("Professor ", "Prof. "), ("Governador ", "Gov. "), ("Presidente ", "Pres. "),
                 ("Doutor ", "Dr. "), ("Coronel ", "Cel. "), ("Desembargador ", "Des. "),
                 ("Ministro ", "Min. "), ("Arquiteto ", "Arq. "), ("Engenheiro ", "Eng. "))

KIND_NAMES = {"speed": "Medidor de velocidade / Speed camera",
              "bump": "Lombada eletrônica / Speed bump",
              "redlight": "Avanço de sinal / Red light"}

STYLE = """<style>
.bg{fill:#f2efe9}.water{fill:#aad3df}.green{fill:#cde6c0}.aero{fill:#e4e0d8}
.road{fill:none;stroke-linecap:round;stroke-linejoin:round}
.r-motorway,.r-trunk{stroke:#f0a35e;stroke-width:2.6}.r-primary{stroke:#f6c47e;stroke-width:2}
.r-secondary{stroke:#fbe2ae;stroke-width:1.4}.r-tertiary{stroke:#fff;stroke-width:0.9}
.st,.sub,.river{paint-order:stroke;stroke:#f2efe9;stroke-width:3px;stroke-linejoin:round;text-anchor:middle}
.st{font:600 10px sans-serif;fill:#4f4a42}.sub{font:9px sans-serif;letter-spacing:.06em;fill:#8c857a}
.river{font:italic 13px serif;fill:#4f7f99;stroke:#aad3df}
.card{fill:#fff;fill-opacity:.94;stroke:#d9d3c7}.t{font:12px sans-serif;fill:#2b2b2b}
.h{font:bold 14px sans-serif;fill:#1f1f1f}.s{font:11px sans-serif;fill:#5c5c5c}.note{paint-order:stroke;stroke:#f2efe9;stroke-width:3px}
.ring{fill:#fff;stroke:#c62828}.lim{font:bold 8px sans-serif;fill:#1f1f1f;text-anchor:middle}
.tri{fill:#f2a900;stroke:#fff}.box{fill:#263238}.lamp{fill:#e53935}.off{fill:#546e7a}.dir{fill:#263238}
@media (prefers-color-scheme:dark){.bg{fill:#1a1f26}.water{fill:#1d3a4c}.green{fill:#1f3025}.aero{fill:#262b33}
.r-motorway,.r-trunk{stroke:#a4703c}.r-primary{stroke:#86663c}.r-secondary{stroke:#584b37}.r-tertiary{stroke:#363e48}
.st,.sub,.note{stroke:#1a1f26}.st{fill:#d6d0c4}.sub{fill:#8a929c}.river{fill:#8fbcd4;stroke:#1d3a4c}
.card{fill:#0d1117;stroke:#30363d}.t{fill:#e6edf3}.h{fill:#f0f6fc}.s{fill:#9da7b3}
.box{fill:#cfd8dc}.off{fill:#90a4ae}.dir{fill:#e6edf3}}
</style>"""


def xy(lat, lon):
    return round((lon - WEST) / (EAST - WEST) * WIDTH, 1), round((NORTH - lat) / (NORTH - SOUTH) * HEIGHT, 1)


def _thin(pts, step=SIMPLIFY_PX):
    """The points without those closer than step to the last one kept; the line's two ends stay."""
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= step:
            out.append(p)
    if len(pts) > 1 and out[-1] != pts[-1]:
        out[-1] = pts[-1]
    return out


def _in_view(x, y, margin=0):
    return -margin <= x <= WIDTH + margin and -margin <= y <= HEIGHT + margin


def _d(pts, close=False):
    return "M" + " L".join("%g %g" % p for p in pts) + ("Z" if close else "")


# --- areas: the river, lakes, green areas -----------------------------------------------------------


def rings(ways):
    """Closed rings from a multipolygon's member ways, joined end to end (a ring left open stays open)."""
    return join([[(g["lat"], g["lon"]) for g in w] for w in ways])


def join(chains, gap=0.0):
    """Lines joined where one ends at (or within gap of) another's end, until each closes or meets no other."""
    chains = [list(c) for c in chains if len(c) > 1]

    def near(a, b):
        return a == b or (gap and math.hypot(a[0] - b[0], a[1] - b[1]) <= gap)

    out = []
    while chains:
        ring = chains.pop()
        grown = True
        while ring[0] != ring[-1] and grown:
            grown = False
            for i, c in enumerate(chains):
                if near(c[0], ring[-1]):
                    ring += c[1:]
                elif near(c[-1], ring[-1]):
                    ring += c[-2::-1]
                elif near(c[-1], ring[0]):
                    ring = c[:-1] + ring
                elif near(c[0], ring[0]):
                    ring = c[:0:-1] + ring
                else:
                    continue
                chains.pop(i)
                grown = True
                break
        out.append(ring)
    return out


def clip(pts, margin=4):
    """A polygon (pixel points) clipped to the view plus a margin (Sutherland-Hodgman)."""
    lo_x, lo_y, hi_x, hi_y = -margin, -margin, WIDTH + margin, HEIGHT + margin
    edges = ((lambda p: p[0] >= lo_x, lambda a, b: _cut(a, b, 0, lo_x)),
             (lambda p: p[0] <= hi_x, lambda a, b: _cut(a, b, 0, hi_x)),
             (lambda p: p[1] >= lo_y, lambda a, b: _cut(a, b, 1, lo_y)),
             (lambda p: p[1] <= hi_y, lambda a, b: _cut(a, b, 1, hi_y)))
    for inside, cut in edges:
        if not pts:
            break
        src, pts = pts, []
        prev = src[-1]
        for cur in src:
            if inside(cur):
                if not inside(prev):
                    pts.append(cut(prev, cur))
                pts.append(cur)
            elif inside(prev):
                pts.append(cut(prev, cur))
            prev = cur
    return pts


def _cut(a, b, axis, value):
    t = (value - a[axis]) / (b[axis] - a[axis])
    p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
    return (round(p[0], 1), round(p[1], 1))


def _area(pts):
    return abs(sum(pts[i - 1][0] * p[1] - p[0] * pts[i - 1][1] for i, p in enumerate(pts))) / 2


def areas_markup(features, cls):
    """One evenodd <path> per feature; a feature is a list of rings of {"lat", "lon"} points."""
    out = []
    for feature in features:
        parts = []
        for ring in feature:
            pts = _thin(clip([xy(lat, lon) for lat, lon in ring]))
            if len(pts) >= 3 and _area(pts) >= MIN_AREA_PX:
                parts.append(_d(pts, close=True))
        if parts:
            out.append('<path class="%s" fill-rule="evenodd" d="%s"/>' % (cls, "".join(parts)))
    return out


def osm_areas(elements):
    """Overpass ways and relations (out geom) as features: lists of (lat, lon) rings."""
    features = []
    for e in elements:
        if e["type"] == "way":
            g = [(p["lat"], p["lon"]) for p in e.get("geometry") or []]
            if len(g) > 3 and g[0] == g[-1]:
                features.append([g])
        elif e["type"] == "relation":
            members = [m["geometry"] for m in e.get("members", []) if m.get("type") == "way" and m.get("geometry")]
            features.append(rings(members))
    return features


# --- roads and labels -------------------------------------------------------------------------------


def _road_lines(ways):
    """(class, name, pixel points) for each road way drawn at this scale and at least partly in view."""
    out = []
    for w in ways:
        kind = w.get("tags", {}).get("highway")
        if kind not in ROAD_CLASSES:
            continue
        pts = _thin([xy(g["lat"], g["lon"]) for g in w.get("geometry") or []])
        if len(pts) >= 2 and any(_in_view(x, y) for x, y in pts):
            out.append((kind, w["tags"].get("name", ""), pts))
    return out


def short_name(name):
    for long, short in ABBREVIATIONS:
        name = name.replace(long, short)
    return name


def _turn(a, b, c):
    t1 = math.atan2(b[1] - a[1], b[0] - a[0])
    t2 = math.atan2(c[1] - b[1], c[0] - b[0])
    return abs((t2 - t1 + math.pi) % (2 * math.pi) - math.pi)


def _smooth(pts, k=3):
    """A line with each point averaged with its k neighbours on each side (ends kept): text reads better
    on a curve without the road's small wiggles."""
    if len(pts) <= 2 * k:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        lo, hi = max(0, i - k), min(len(pts), i + k + 1)
        out.append((sum(p[0] for p in pts[lo:hi]) / (hi - lo), sum(p[1] for p in pts[lo:hi]) / (hi - lo)))
    return out + [pts[-1]]


def _split_sharp(pts, max_turn=1.0):
    """A line cut at its sharp corners (where joined pieces double back, or the road turns a corner)."""
    pieces, start = [], 0
    for i in range(1, len(pts) - 1):
        if _turn(pts[i - 1], pts[i], pts[i + 1]) > max_turn:
            pieces.append(pts[start:i + 1])
            start = i
    return pieces + [pts[start:]]


def _stretches(pts, need, max_turn=1.0):
    """Every stretch of a line at least need long that turns at most max_turn in total: (turning, points)."""
    out = []
    for i in range(len(pts) - 1):
        length, j = 0.0, i
        while j + 1 < len(pts) and length < need:
            length += math.hypot(pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1])
            j += 1
        if length < need:
            break
        turning = sum(_turn(pts[k - 1], pts[k], pts[k + 1]) for k in range(i + 1, j))
        if turning <= max_turn:
            out.append((turning, pts[i:j + 1]))
    return out


def _clear(x, y, w, placed, keep_out):
    if not (w / 2 + 6 <= x <= WIDTH - w / 2 - 6 and 12 <= y <= HEIGHT - 20):
        return False
    x0, y0, x1, y1 = LEGEND
    if x0 - w / 2 - 4 <= x <= x1 + w / 2 + 4 and y0 - 10 <= y <= y1 + 10:
        return False
    if any(math.hypot(x - px, y - py) < (w + pw) / 2 * 0.75 + 14 for px, py, pw in placed):
        return False
    return all(math.hypot(x - kx, y - ky) > 26 for kx, ky in keep_out)


def street_labels(lines, keep_out=()):
    """Names written along the biggest roads (SVG textPath), on the gentlest stretch long enough for the
    name, never upside down, and clear of each other, the legend and the points."""
    total = {}
    for kind, name, pts in lines:
        if name and kind in LABELLED:
            total[name] = total.get(name, 0) + sum(
                math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    out, placed = [], []
    for name in sorted(total, key=lambda n: (-total[n], n)):
        text = short_name(name)
        w = len(text) * 5.6
        options = []
        # an avenue is mapped in many pieces, with small gaps at junctions and roundabouts
        for pts in join((pts for _k, n, pts in lines if n == name), LABEL_GAP_PX):
            for piece in _split_sharp(_thin(pts, LABEL_STEP_PX)):
                options += _stretches(_smooth(piece), w + 12, 1.2)
        for _turning, pts in sorted(options, key=lambda o: o[0]):
            if not all(_clear(x, y, 10, placed, keep_out) for x, y in pts):   # the whole curve, not its middle
                continue
            if pts[-1][0] < pts[0][0]:
                pts = pts[::-1]          # read left to right
            out.append('<path id="st%d" fill="none" d="%s"/><text class="st" dy="3.5">'
                       '<textPath href="#st%d" startOffset="50%%">%s</textPath></text>'
                       % (len(out), _d(pts), len(out), _esc(text)))
            placed += [(x, y, 10) for x, y in pts[::2]]
            break
        if len(out) >= STREET_LABELS:
            break
    return out, placed


def suburb_labels(places, placed, keep_out=()):
    """Neighbourhood names where they don't crowd the street names or the points."""
    out = []
    for p in sorted(places, key=lambda p: p["name"]):
        x, y = xy(p["lat"], p["lon"])
        text = p["name"].upper()
        w = len(text) * 5.4
        if _clear(x, y, w, placed, keep_out):
            out.append('<text class="sub" x="%.1f" y="%.1f">%s</text>' % (x, y + 3, _esc(text)))
            placed.append((x, y, w))
    return out


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def base_markup(roads, water=(), green=(), aero=(), places=(), keep_out=()):
    """The base map: areas, roads, then labels. roads are Overpass highway ways with geometry; water,
    green and aero Overpass ways and relations (out geom); places {"name", "lat", "lon"} neighbourhoods;
    keep_out pixel points the labels stay clear of (the verified points)."""
    out = areas_markup(osm_areas(green), "green") + areas_markup(osm_areas(aero), "aero")
    out += areas_markup(osm_areas(water), "water")
    lines = _road_lines(roads)
    for kind in ROAD_CLASSES:
        ds = [_d(pts) for k, _n, pts in lines if k == kind]
        if ds:
            out.append('<path class="road r-%s" d="%s"/>' % (kind, " ".join(ds)))
    labels, placed = street_labels(lines, keep_out)
    out += labels
    out += suburb_labels(places, placed, keep_out)
    rx, ry = xy(RIVER_LABEL[0], RIVER_LABEL[1])
    out.append('<text class="river" x="%.1f" y="%.1f">%s</text>' % (rx, ry, RIVER_LABEL[2]))
    return "\n".join(out)


def base_of(svg):
    """The base map markup inside an existing map, or None when it has none."""
    m = re.search(r'<g id="base">\n(.*?)\n</g>\n<g id="points">', svg, re.S)
    return m.group(1) if m else None


# --- points and legend ------------------------------------------------------------------------------


def icon(kind, x, y, limit, size=1.5):
    """The point's sign: a speed-limit ring (with the limit), a warning triangle, or a traffic light."""
    if kind == "speed":
        text = str(limit) if limit else ""
        return ('<circle class="ring" cx="%g" cy="%g" r="%g" stroke-width="%g"/>'
                '<text class="lim" x="%g" y="%g">%s</text>'
                % (x, y, 7 * size, 2.2 * size, x, y + 2.8 * size, text))
    if kind == "bump":
        r = 8 * size
        return ('<path class="tri" stroke-width="%g" d="M%g %g L%g %g L%g %gZ"/>'
                % (1.2 * size, x, y - r, x + r * 0.9, y + r * 0.6, x - r * 0.9, y + r * 0.6))
    w, h = 6 * size, 13 * size
    return ('<rect class="box" x="%g" y="%g" width="%g" height="%g" rx="%g"/>'
            '<circle class="lamp" cx="%g" cy="%g" r="%g"/><circle class="off" cx="%g" cy="%g" r="%g"/>'
            % (x - w / 2, y - h / 2, w, h, 2 * size, x, y - h / 4, 1.8 * size, x, y + h / 4, 1.8 * size))


def arrow(x, y, heading):
    """A small wedge just outside the icon, pointing the enforced direction (0 = north, clockwise)."""
    a = math.radians(heading)
    def at(r, da):
        return x + r * math.sin(a + da), y - r * math.cos(a + da)
    tip, left, right = at(20, 0), at(13.5, 0.42), at(13.5, -0.42)
    return '<path class="dir" d="M%.1f %.1f L%.1f %.1f L%.1f %.1fZ"/>' % (tip + left + right)


def build(rows, base, listed):
    """The whole SVG: the base map, then the points (arrow under icon), then the legend.
    listed is how many addresses the transcribed official lists hold (tools/lists)."""
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
             'role="img" aria-label="Mapa dos pontos verificados em Manaus">' % (WIDTH, HEIGHT, WIDTH, HEIGHT),
             STYLE, '<rect class="bg" width="%d" height="%d"/>' % (WIDTH, HEIGHT),
             '<g id="base">\n%s\n</g>' % base, '<g id="points">']
    for r in sorted(rows, key=lambda r: r["id"]):
        x, y = xy(r["lat"], r["lon"])
        parts.append('<g><title>%s · %s · %s</title>%s%s</g>'
                     % (r["id"], _esc(r["label"]), "%s km/h" % r["limit"] if r["limit"] else r["kind"],
                        arrow(x, y, r["heading"]), icon(r["kind"], x, y, r["limit"])))
    parts.append("</g>")
    counts = {k: sum(1 for r in rows if r["kind"] == k) for k in KIND_NAMES}
    latest = max((r["checked"] for r in rows), default="—")
    x0, top, x1, y1 = LEGEND
    parts.append('<g id="legend"><rect class="card" x="%d" y="%d" width="%d" height="%d" rx="8"/>'
                 '<text class="h" x="24" y="%d">Pontos verificados: %d</text>'
                 '<text class="s" x="24" y="%d">Última verificação / last checked: %s</text>'
                 % (x0, top, x1 - x0, y1 - top, top + 22, len(rows), top + 39, latest))
    for i, (kind, name) in enumerate(KIND_NAMES.items()):
        y = top + 62 + i * 22
        parts.append('%s<text class="t" x="44" y="%d">%s: %d</text>'
                     % (icon(kind, 30, y - 4, 60 if kind == "speed" else None, 1.0), y, name, counts[kind]))
    parts.append('<text class="s" x="24" y="%d">%d endereços das listas da IMMU em verificação</text></g>'
                 % (top + 132, listed))
    parts.append('<text class="s note" x="%d" y="%d" text-anchor="end">'
                 '© OpenStreetMap contributors · seta = sentido fiscalizado / arrow = enforced direction</text>'
                 % (WIDTH - 10, HEIGHT - 10))
    parts.append("</svg>\n")
    return "\n".join(parts)
