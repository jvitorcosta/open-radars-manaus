"""The README's static map (docs/map.svg): Manaus' main roads, one icon per verified point and a legend.

GitHub's ```geojson map draws every pin the same, so this one is drawn here. The roads come from
OpenStreetMap once (roads_markup) and then live inside the SVG: rebuilding the points and the legend
(build) reads them back from the file, so it needs no network and gives the same bytes for the same rows.
"""
import math
import re

# Urban Manaus, west to east from Ponta Negra to the Zona Leste, north to south from the Tarumã to the river.
WEST, EAST, NORTH, SOUTH = -60.100, -59.880, -2.975, -3.150
WIDTH = 800
COS = math.cos(math.radians((NORTH + SOUTH) / 2))
HEIGHT = round(WIDTH * (NORTH - SOUTH) / ((EAST - WEST) * COS))
ROAD_WIDTHS = {"motorway": 2.4, "trunk": 2.4, "primary": 1.8, "secondary": 1.2, "tertiary": 0.6}
SIMPLIFY_PX = 1.5   # drop a road vertex closer than this to the last one kept

KIND_NAMES = {"speed": "Medidor de velocidade / Speed camera",
              "bump": "Lombada eletrônica / Speed bump",
              "redlight": "Avanço de sinal / Red light"}

STYLE = """<style>
.bg{fill:#f7f5f0}.road{fill:none;stroke:#cfc8bb;stroke-linecap:round;stroke-linejoin:round}
.card{fill:#fff;fill-opacity:.92;stroke:#d9d3c7}.t{font:12px sans-serif;fill:#2b2b2b}
.h{font:bold 14px sans-serif;fill:#1f1f1f}.s{font:11px sans-serif;fill:#5c5c5c}
.ring{fill:#fff;stroke:#c62828}.lim{font:bold 8px sans-serif;fill:#1f1f1f;text-anchor:middle}
.tri{fill:#f2a900;stroke:#fff}.box{fill:#263238}.lamp{fill:#e53935}.off{fill:#546e7a}.dir{fill:#263238}
@media (prefers-color-scheme:dark){.bg{fill:#161b22}.road{stroke:#3b4450}.card{fill:#0d1117;stroke:#30363d}
.t{fill:#e6edf3}.h{fill:#f0f6fc}.s{fill:#9da7b3}.box{fill:#cfd8dc}.off{fill:#90a4ae}.dir{fill:#e6edf3}}
</style>"""


def xy(lat, lon):
    return round((lon - WEST) / (EAST - WEST) * WIDTH, 1), round((NORTH - lat) / (NORTH - SOUTH) * HEIGHT, 1)


def roads_markup(ways):
    """The <path> elements for the roads worth drawing at this scale, from Overpass ways with geometry."""
    out = []
    for kind in ("tertiary", "secondary", "primary", "trunk", "motorway"):   # bigger roads drawn on top
        for w in ways:
            if w.get("tags", {}).get("highway") != kind:
                continue
            pts, last = [], None
            for g in w.get("geometry") or []:
                p = xy(g["lat"], g["lon"])
                if last is None or math.hypot(p[0] - last[0], p[1] - last[1]) >= SIMPLIFY_PX:
                    pts.append(p)
                    last = p
            if len(pts) < 2 or all(not (0 <= x <= WIDTH and 0 <= y <= HEIGHT) for x, y in pts):
                continue
            d = "M" + " L".join("%g %g" % p for p in pts)
            out.append('<path class="road" stroke-width="%g" d="%s"/>' % (ROAD_WIDTHS[kind], d))
    return "\n".join(out)


def roads_of(svg):
    """The road markup inside an existing map, or None when it has none."""
    m = re.search(r'<g id="roads">\n(.*?)\n?</g>', svg, re.S)
    return m.group(1) if m else None


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


def build(rows, roads, listed):
    """The whole SVG: roads, then the points (arrow under icon), then the legend.
    listed is how many addresses the transcribed official lists hold (tools/lists)."""
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
             'role="img" aria-label="Mapa dos pontos verificados em Manaus">' % (WIDTH, HEIGHT, WIDTH, HEIGHT),
             STYLE, '<rect class="bg" width="%d" height="%d"/>' % (WIDTH, HEIGHT),
             '<g id="roads">\n%s\n</g>' % roads, '<g id="points">']
    for r in sorted(rows, key=lambda r: r["id"]):
        x, y = xy(r["lat"], r["lon"])
        parts.append('<g><title>%s · %s · %s</title>%s%s</g>'
                     % (r["id"], r["label"], "%s km/h" % r["limit"] if r["limit"] else r["kind"],
                        arrow(x, y, r["heading"]), icon(r["kind"], x, y, r["limit"])))
    parts.append("</g>")
    counts = {k: sum(1 for r in rows if r["kind"] == k) for k in KIND_NAMES}
    latest = max((r["checked"] for r in rows), default="—")
    top = HEIGHT - 176   # bottom left: the Rio Negro, where no road runs
    parts.append('<g id="legend"><rect class="card" x="12" y="%d" width="300" height="142" rx="8"/>'
                 '<text class="h" x="24" y="%d">Pontos verificados: %d</text>'
                 '<text class="s" x="24" y="%d">Última verificação / last checked: %s</text>'
                 % (top, top + 22, len(rows), top + 39, latest))
    for i, (kind, name) in enumerate(KIND_NAMES.items()):
        y = top + 62 + i * 22
        parts.append('%s<text class="t" x="44" y="%d">%s: %d</text>'
                     % (icon(kind, 30, y - 4, 60 if kind == "speed" else None, 1.0), y, name, counts[kind]))
    parts.append('<text class="s" x="24" y="%d">%d endereços das listas da IMMU em verificação</text></g>'
                 % (top + 132, listed))
    parts.append('<text class="s" x="%d" y="%d" text-anchor="end">'
                 '© OpenStreetMap contributors · seta = sentido fiscalizado / arrow = enforced direction</text>'
                 % (WIDTH - 10, HEIGHT - 10))
    parts.append("</svg>\n")
    return "\n".join(parts)
