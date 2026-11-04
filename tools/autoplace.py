"""Turn an IMMU address into a guessed point on the right carriageway, with a heading.

A crossing ('Avenida A/Rua B') is placed where the two roads meet in OpenStreetMap, a few metres
before the junction on the lane of its sentido; any other address is geocoded and snapped to its road.

Ported from car-cyberdeck's tools/cameras.py (MIT, same author). The guess only seeds the review
map: a human drags the pin and confirms it before anything reaches radars.csv.
"""
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse

from sources import BBOX, OVERPASS_URLS, _STOP, http_req, plain

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
VIEWBOX = "-60.15,-2.90,-59.80,-3.25"   # left,top,right,bottom
CENTRE = (-3.1019, -60.0250)            # Manaus, when nothing else is known
SETBACK_M = 15                          # a crossing's radar watches the stop line, just before the junction
NEAR_M = 40                             # two roads this close count as meeting (a roundabout, a split node in OSM)
ROADS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "roads.json")
ROADS_MAX_AGE = 30 * 86400              # the named roads of Manaus, downloaded once and kept this long

_last_geocode = [0.0]


def street_of(address):
    """The street part of an IMMU address: 'Avenida X, nº 9 – Bairro, sentido Leste' -> 'Avenida X'."""
    addr = re.split(r",?\s*sentido\s", address, flags=re.I)[0]
    parts = [p.strip() for p in re.split(r"\s+[–—-]\s+", addr)]
    return parts[0].split(",")[0].split("/")[0]


def geocode(item):
    """First guess for an address-only item (Nominatim: at most 1 request/s). None when not found."""
    wait = 1.1 - (time.time() - _last_geocode[0])
    if wait > 0:
        time.sleep(wait)
    _last_geocode[0] = time.time()
    addr = re.split(r",?\s*sentido\s", item["address"], flags=re.I)[0]
    parts = [p.strip() for p in re.split(r"\s+[–—-]\s+", addr)]
    street = street_of(item["address"])
    district = parts[-1].split(",")[0] if len(parts) > 1 else ""
    q = "%s, %s, Manaus, Amazonas, Brazil" % (street, district) if district else "%s, Manaus, Amazonas, Brazil" % street
    url = NOMINATIM_URL + "?" + urllib.parse.urlencode({"q": q, "format": "json", "limit": 1, "countrycodes": "br",
                                                        "viewbox": VIEWBOX, "bounded": 1})
    try:
        _, body = http_req(url)
        res = json.loads(body)
        if res:
            return float(res[0]["lat"]), float(res[0]["lon"])
    except (urllib.error.URLError, ValueError, OSError, KeyError, TypeError, IndexError):
        pass     # also an unexpected JSON shape, e.g. {"error": ...}
    return None


def _spelt(w):
    """One spelling for old and new forms: 'Cyrillo' and 'Cirilo' are the same word."""
    return re.sub(r"(.)\1+", r"\1", w.replace("y", "i"))


def _name_words(name):
    return {_spelt(w) for w in re.findall(r"[a-z0-9]+", plain(name)) if w not in _STOP}


def _all_words(name):
    return {_spelt(w) for w in re.findall(r"[a-z0-9]+", plain(name))}


def _ways_named(ways, name):
    """The ways named like name; those that carry every word of it (the 'Avenida' too) when there are any,
    so 'Avenida João Valério' does not also take 'Beco João Valério'."""
    found = [w for w in ways if _named(w, name)]
    want = _all_words(name)
    exact = [w for w in found if want <= _all_words(w.get("tags", {}).get("name", ""))]
    return exact or found


def _named(el, street):
    """Does a way's name share at least 2 words with the street (its only word, for a one-word street)?"""
    want = _name_words(street)
    need = min(2, len(want))
    return bool(need) and len(want & _name_words(el.get("tags", {}).get("name", ""))) >= need


def _overpass(q, timeout=70):
    last = None
    for attempt in range(2):    # the public instances answer 502 or stall now and then: retry, try the mirror
        for url in OVERPASS_URLS:
            try:
                _, body = http_req(url, data=urllib.parse.urlencode({"data": q}).encode(), timeout=timeout)
                return json.loads(body).get("elements", [])
            except (urllib.error.URLError, OSError, ValueError) as e:
                last = e
    raise last


_roads = []


def road_network():
    """Every named road in Manaus with node ids and geometry, from build/roads.json while it is fresh.
    One download (about 15 MB) instead of a query per crossing, which the public servers time out on."""
    if not _roads:
        try:
            if time.time() - os.path.getmtime(ROADS_PATH) < ROADS_MAX_AGE:
                with open(ROADS_PATH, encoding="utf-8") as f:
                    cached = json.load(f)
                if isinstance(cached, list):
                    _roads.extend(cached)
        except (OSError, ValueError):
            pass
    if not _roads:
        q = '[out:json][timeout:180];way["highway"]["name"](%s);out body geom;' % BBOX
        _roads.extend(el for el in _overpass(q, timeout=200) if el.get("type") == "way")
        os.makedirs(os.path.dirname(ROADS_PATH), exist_ok=True)
        with open(ROADS_PATH, "w", encoding="utf-8") as f:
            json.dump(_roads, f)
    return _roads


def fetch_crossing_ways(street, cross):
    """The roads of Manaus named like the street or the cross road, with node ids and geometry."""
    return [w for w in road_network() if _named(w, street) or _named(w, cross)]


def at_crossing(ways, street, cross, want_heading, setback_m=SETBACK_M):
    """(lat, lon, heading) on the street, setback_m before the junction with the cross road, on the lane that
    runs the way of want_heading (the first junction reached, on a split road); the junction itself with no
    heading when want_heading is None. None when the two roads never meet."""
    on = _ways_named(ways, street)
    crossing = [w for w in _ways_named(ways, cross) if w not in on]
    other = {n for w in crossing for n in w.get("nodes", [])}
    shared = [(w, k) for w in on for k, n in enumerate(w.get("nodes", [])) if n in other]
    if not shared:
        shared = _nearly_meet(on, crossing)
    if not shared:
        return None
    if want_heading is None:
        pts = {w["nodes"][k]: w["geometry"][k] for w, k in shared}
        lat = sum(g["lat"] for g in pts.values()) / len(pts)
        lon = sum(g["lon"] for g in pts.values()) / len(pts)
        return round(lat, 6), round(lon, 6), None
    lat0, lon0 = shared[0][0]["geometry"][shared[0][1]]["lat"], shared[0][0]["geometry"][shared[0][1]]["lon"]
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110574
    for tol in (45, 80):   # IMMU's sentido is a compass point; a road may run well off it
        cands = _approaches(shared, want_heading, tol, setback_m, lat0, lon0, kx, ky)
        if cands:
            break
    else:
        return None
    _, _, lat, lon, h = min(cands)
    return round(lat, 6), round(lon, 6), round(h) % 360


def _approaches(shared, want_heading, tol, setback_m, lat0, lon0, kx, ky):
    """(how far along the sentido the junction is, angle off the sentido, lat, lon, heading) for each way in
    to a junction node that runs within tol degrees of want_heading."""
    sw, cw = math.sin(math.radians(want_heading)), math.cos(math.radians(want_heading))
    cands = []
    for w, k in shared:
        g, ow = w["geometry"], str(w.get("tags", {}).get("oneway", "")).lower()
        before = []                                   # the node a car comes from, by the way's direction
        if k > 0 and ow != "-1":
            before.append(g[k - 1])
        if k + 1 < len(g) and ow not in ("yes", "true", "1"):
            before.append(g[k + 1])
        x, y = (g[k]["lon"] - lon0) * kx, (g[k]["lat"] - lat0) * ky
        for b in before:
            dx, dy = (g[k]["lon"] - b["lon"]) * kx, (g[k]["lat"] - b["lat"]) * ky
            seg = math.hypot(dx, dy)
            if not seg:
                continue
            h = math.degrees(math.atan2(dx, dy)) % 360
            if _angle(h, want_heading) > tol:
                continue
            t = min(setback_m, seg) / seg
            cands.append((round(x * sw + y * cw, 1), _angle(h, want_heading),
                          g[k]["lat"] - t * dy / ky, g[k]["lon"] - t * dx / kx, h))
    return cands


def _nearly_meet(on, crossing, near_m=NEAR_M):
    """Where the roads come within near_m of each other without a shared node: the street's nodes nearest
    the cross road (up to 10 m further than the closest one)."""
    pts = [g for w in crossing for g in w.get("geometry", [])]
    if not pts:
        return []
    ky, kx = 110574, 111320 * math.cos(math.radians(pts[0]["lat"]))
    dist = [(min(math.hypot((g["lon"] - p["lon"]) * kx, (g["lat"] - p["lat"]) * ky) for p in pts), w, k)
            for w in on for k, g in enumerate(w.get("geometry", []))]
    if not dist:
        return []
    d0 = min(d for d, _, _ in dist)
    return [(w, k) for d, w, k in dist if d <= min(d0 + 10, near_m)]


def fetch_ways(lat, lon, street, radius_m=300):
    """Named roads passing within radius_m of the point whose name shares at least 2 words with the street
    (or all of them, for a one-word street)."""
    kx, ky = 111320 * math.cos(math.radians(lat)), 110574

    def near(w):
        pts = [((g["lon"] - lon) * kx, (g["lat"] - lat) * ky) for g in w.get("geometry", [])]
        return any(_seg_dist(a, b) <= radius_m for a, b in zip(pts, pts[1:])) or any(
            math.hypot(*p) <= radius_m for p in pts[:1])

    return [w for w in road_network() if "geometry" in w and _named(w, street) and near(w)]


def _seg_dist(a, b):
    """Distance from the origin to the segment a-b (metres, flat)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    seg2 = dx * dx + dy * dy
    t = 0.0 if not seg2 else max(0.0, min(1.0, -(a[0] * dx + a[1] * dy) / seg2))
    return math.hypot(a[0] + t * dx, a[1] + t * dy)


def _angle(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def snap(lat, lon, ways, want_heading):
    """(lat, lon, heading) of the nearest point on a way that runs the way of want_heading, or None.
    With no wanted heading the nearest point wins and the heading is only given for a one-way road."""
    kx, ky = 111320 * math.cos(math.radians(lat)), 110574
    best = None   # (dist, x, y, heading)
    for way in ways:
        ow = str(way.get("tags", {}).get("oneway", "")).lower()
        pts = [((g["lon"] - lon) * kx, (g["lat"] - lat) * ky) for g in way.get("geometry", [])]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            if not seg2:
                continue
            t = max(0.0, min(1.0, -(ax * dx + ay * dy) / seg2))   # the point is the origin
            fx, fy = ax + t * dx, ay + t * dy
            dist = math.hypot(fx, fy)
            bearing = math.degrees(math.atan2(dx, dy)) % 360
            if ow in ("yes", "true", "1"):
                hs = [bearing]
            elif ow == "-1":
                hs = [(bearing + 180) % 360]
            else:
                hs = [bearing, (bearing + 180) % 360]
            for h in hs:
                if want_heading is not None and _angle(h, want_heading) > 90:
                    continue
                if best is None or dist < best[0]:
                    best = (dist, fx, fy, h if want_heading is not None or len(hs) == 1 else None)
    if best is None:
        return None
    _, fx, fy, h = best
    return round(lat + fy / ky, 6), round(lon + fx / kx, 6), None if h is None else round(h) % 360


def autoplace(item):
    """The item with lat, lon, heading and guess=True filled; never raises on network trouble."""
    out = dict(item)
    spot, heading, how = None, None, "crossing"
    if item.get("cross"):
        try:
            found = at_crossing(fetch_crossing_ways(item["street"], item["cross"]), item["street"], item["cross"],
                                item.get("heading"))
            if found:
                spot, heading = (found[0], found[1]), found[2]
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
    if spot is None:
        spot, heading = _snapped(item)
        how = "street" if spot else "none"
    out["lat"], out["lon"] = spot or CENTRE
    out["heading"], out["guess"], out["how"] = heading, True, how
    return out


def _snapped(item):
    """The geocoded spot snapped onto its road: ((lat, lon) or None, heading or None)."""
    spot, heading = geocode(item), None
    if spot:
        try:
            ways = fetch_ways(spot[0], spot[1], street_of(item["address"]))
            found = snap(spot[0], spot[1], ways, item.get("heading"))
            if found:
                spot, heading = (found[0], found[1]), found[2]
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
    return spot, heading
