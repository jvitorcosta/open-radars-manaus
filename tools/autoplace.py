"""Turn an IMMU address into a guessed point on the right carriageway, with a heading.

Ported from car-cyberdeck's tools/cameras.py (MIT, same author). The guess only seeds the review
map: a human drags the pin and confirms it before anything reaches radars.csv.
"""
import json
import math
import re
import time
import urllib.error
import urllib.parse

from sources import OVERPASS_URLS, _STOP, http_req, plain

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
VIEWBOX = "-60.15,-2.90,-59.80,-3.25"   # left,top,right,bottom
CENTRE = (-3.1019, -60.0250)            # Manaus, when nothing else is known

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


def _name_words(name):
    return {w for w in re.findall(r"[a-z0-9]+", plain(name)) if w not in _STOP}


def fetch_ways(lat, lon, street, radius_m=300):
    """Named roads within radius_m of the point whose name shares at least 2 words with the street
    (or all of them, for a one-word street)."""
    q = '[out:json][timeout:25];way(around:%d,%s,%s)["highway"]["name"];out tags geom;' % (radius_m, lat, lon)
    last = None
    for url in OVERPASS_URLS:
        try:
            _, body = http_req(url, data=urllib.parse.urlencode({"data": q}).encode(), timeout=70)
            elements = json.loads(body).get("elements", [])
            break
        except (urllib.error.URLError, OSError, ValueError) as e:
            last = e
    else:
        raise last
    want = _name_words(street)
    need = min(2, len(want))
    if not need:
        return []
    return [el for el in elements if el.get("type") == "way" and "geometry" in el
            and len(want & _name_words(el.get("tags", {}).get("name", ""))) >= need]


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
    spot, heading = geocode(item), None
    if spot:
        try:
            ways = fetch_ways(spot[0], spot[1], street_of(item["address"]))
            found = snap(spot[0], spot[1], ways, item.get("heading"))
            if found:
                spot, heading = (found[0], found[1]), found[2]
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
    out["lat"], out["lon"] = spot or CENTRE
    out["heading"], out["guess"] = heading, True
    return out
