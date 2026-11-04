"""Where Manaus radars are reported (IMMU page, the IMMU survey, OpenStreetMap) and how to tell
whether a reported one is already in the list.

Ported from car-cyberdeck's tools/cameras.py (MIT, same author). An item is a dict
{kind, address, sentido, heading, label, limit, source, lat, lon}; IMMU items have no coordinates.
IMMU items also carry {street, cross}: the road the radar is on and, at a crossing, the other road.
"""
import csv
import html.parser
import json
import math
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

IMMU_URL = "https://immu.manaus.am.gov.br/index.php?r=site%2Finforadar"
OVERPASS_URLS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")
BBOX = "-3.25,-60.15,-2.90,-59.80"  # south,west,north,east
USER_AGENT = "open-radars-manaus/1.0 (+https://github.com/jvitorcosta/open-radars-manaus)"
# The points IMMU announced in the press but not (yet) on its page, typed in from the announcements.
LISTS = tuple(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lists", f)
              for f in ("immu-2026-02.csv", "immu-2026-07.csv"))

MATCH_M = 50.0
HEADING_TOL = 60    # degrees: IMMU gives a cardinal direction, the real bearing can differ

# --- matching ------------------------------------------------------------------------------------

_STOP = {"av", "avenida", "rua", "r", "de", "da", "do", "das", "dos", "e", "em", "frente", "n", "no", "a", "o",
         "prof", "professor", "cel", "coronel", "tv", "travessa", "dr", "doutor", "gov", "governador",
         "gen", "general"}


def haversine_m(la1, lo1, la2, lo2):
    p1, p2 = math.radians(la1), math.radians(la2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(a))


def plain(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def _words(label):
    return {w for w in re.findall(r"[a-z0-9]+", plain(label)) if w not in _STOP}


def _district(label):
    """Words after the '·' of a label ('Av. Torquato Tapajós · Da Paz' -> {'paz'}); empty when there is none."""
    return _words(label.split("·", 1)[1]) if "·" in label else set()


def matches(item, row):
    """Same radar? Within 50 m when both have coordinates, else by the words of the label (numbers
    and a known direction must agree: 'Seripa 7' is not 'Seripa 8')."""
    if item.get("kind") != row.get("kind"):
        return False
    if item.get("lat") is not None and row.get("lat") is not None:
        if haversine_m(item["lat"], item["lon"], row["lat"], row["lon"]) <= MATCH_M:
            # one crossing, two directions: two radars
            return not _opposed(item.get("heading"), row.get("heading"))
        if item.get("source") == "osm":      # an OSM node has no words worth comparing
            return False
    a, b = _words(item.get("label", "")), _words(row.get("label", ""))
    if not a or not b:
        return False
    if {w for w in a if w.isdigit()} != {w for w in b if w.isdigit()}:
        return False
    if _opposed(item.get("heading"), row.get("heading")):
        return False
    da, db = _district(item.get("label", "")), _district(row.get("label", ""))
    if da and db and not (da <= db or db <= da):   # same street, other district: another radar
        return False
    shared = len(a & b)
    return shared >= 2 and shared / min(len(a), len(b)) >= 0.6


def _opposed(a, b):
    """Both headings known and more than HEADING_TOL apart (a real bearing, 255, vs IMMU's cardinal, 270, is not)."""
    if a is None or b is None:
        return False
    d = abs(a - b) % 360
    return min(d, 360 - d) > HEADING_TOL


def diff(items, rows):
    """(new items not in the list, list rows no longer reported). Car and community rows are never 'gone'."""
    new = [i for i in items if not any(matches(i, r) for r in rows)]
    gone = [r for r in rows if r["source"] not in ("car", "community") and not any(matches(i, r) for i in items)]
    return new, gone


# --- sources -------------------------------------------------------------------------------------

_SENTIDO = {"norte": 0, "leste": 90, "sul": 180, "oeste": 270}
_KIND_BY_HEADING = (("radares de velocidade", "speed"), ("lombadas", "bump"), ("radares de avanco", "redlight"))


class _ImmuParser(html.parser.HTMLParser):
    """Collects the <li> rows of the <ol> that follows each heading (found by its text, in a <b>)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.kind = None
        self.in_b = self.in_li = False
        self.buf = []
        self.items = []

    def handle_starttag(self, tag, attrs):
        if tag == "b":
            self.in_b, self.buf = True, []
        elif tag == "li" and self.kind:
            self.in_li, self.buf = True, []

    def handle_endtag(self, tag):
        if tag == "b" and self.in_b:
            self.in_b = False
            text = plain(" ".join("".join(self.buf).split()))
            for key, kind in _KIND_BY_HEADING:
                if text.startswith(key):
                    self.kind = kind
        elif tag == "li" and self.in_li:
            self.in_li = False
            text = " ".join("".join(self.buf).split())
            if text:
                self.items.append((self.kind, text))
        elif tag == "ol":
            self.kind = None

    def handle_data(self, data):
        if self.in_b or self.in_li:
            self.buf.append(data)


def _abbrev(s):
    for a, b in (("Avenida ", "Av. "), ("Professor ", "Prof. "), ("Coronel ", "Cel. "), ("Jornalista ", "Jorn. "),
                 ("Travessa ", "Tv. "), ("Doutor ", "Dr. "), ("Governador ", "Gov. "), ("General ", "Gen. ")):
        s = s.replace(a, b)
    return s


def immu_label(address):
    """'Avenida Professor Nilton Lins, nº 900, Jardim Via Veneto – Flores, sentido Leste' -> 'Av. Prof. Nilton Lins 900 · Flores'."""
    addr = re.sub(r",?\s*sentido\s+.*$", "", address.strip().rstrip("."), flags=re.I)
    parts = [p.strip() for p in re.split(r"\s+[–—-]\s+", addr)]
    street, num = parts[0], ""
    m = re.search(r",\s*n[ºo°]\s*([\d.]+)", street)
    if m:
        num = " " + m.group(1).replace(".", "")
    street = street.split(",")[0]
    district = parts[-1].split(",")[0] if len(parts) > 1 else ""
    label = _abbrev(street) + num + (" · " + district if district else "")
    return re.sub(r"\s+", " ", re.sub(r'[,"]', " ", label)).strip()


def crossing_of(address):
    """(street, cross) of an address: 'Avenida A/Avenida B – Bairro, sentido Sul' -> ('Avenida A', 'Avenida B');
    cross is '' when the address is not a crossing."""
    addr = re.split(r",?\s*sentido\s", address, flags=re.I)[0]
    street = re.split(r"\s+[–—-]\s+", addr)[0].split(",")[0]
    a, _, b = street.partition("/")
    return a.strip(), b.strip()


def sentido_of(address):
    m = re.search(r"sentido\s+(.+?)\.?$", address.strip(), flags=re.I)
    return m.group(1).strip() if m else ""


def heading_of(sentido):
    return _SENTIDO.get(plain(sentido).strip())


def parse_immu(page):
    """The three lists of the IMMU page as items {kind, address, sentido, heading, label, limit, source}."""
    p = _ImmuParser()
    p.feed(page)
    items = []
    for kind, text in p.items:
        sentido = sentido_of(text)
        street, cross = crossing_of(text)
        items.append({"kind": kind, "address": text, "sentido": sentido, "heading": heading_of(sentido),
                      "label": immu_label(text), "limit": None, "source": "immu", "lat": None, "lon": None,
                      "street": street, "cross": cross})
    return _distinct_labels(items)


def _distinct_labels(items):
    """Two radars on one street and district would share a label: tell them apart by their sentido."""
    seen = {}
    for it in items:
        seen.setdefault(it["label"], []).append(it)
    for group in seen.values():
        if len(group) > 1:
            for it in group:
                it["label"] += " " + (it["sentido"].split()[0] if it["sentido"] else "?")
    return items


def announced_items(paths=LISTS):
    """The points of IMMU's announcements (tools/lists/*.csv: kind,street,cross,district,sentido,limit,note)."""
    items = []
    for path in paths:
        with open(path, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                where = r["street"] + ("/" + r["cross"] if r["cross"] else "")
                address = where + (", " + r["note"] if r["note"] else "") + " – " + r["district"]
                if r["sentido"]:
                    address += ", sentido " + r["sentido"]
                label = _abbrev(r["street"]) + ("/" + _abbrev(r["cross"]) if r["cross"] else "") + " · " + r["district"]
                items.append({"kind": r["kind"], "address": address, "sentido": r["sentido"],
                              "heading": heading_of(r["sentido"]), "label": label,
                              "limit": int(r["limit"]) if r["limit"] else None, "source": "immu",
                              "lat": None, "lon": None, "street": r["street"], "cross": r["cross"]})
    return _distinct_labels(items)


# The 7 "Levantamentos Técnicos" on the IMMU page (Av. do Turismo); the limit (60) is from their PDFs.
_SURVEY = (
    ("Av. do Turismo, oposto a empresa Vida Film nº 12568 - Tarumã-açu, sentido oeste", "Av. do Turismo · Vida Film"),
    ("Av. do Turismo/Av. Thales Loureiro - Ponta Negra, sentido complexo turístico Ponta Negra", "Av. do Turismo · Thales Loureiro"),
    ("Av. do Turismo, em frente a 123ª IEADAM - Tarumã, sentido norte", "Av. do Turismo · IEADAM"),
    ("Av. do Turismo, 3727 - Ponta Negra, sentido complexo turístico Ponta Negra", "Av. do Turismo 3727"),
    ("Av. do Turismo, oposto ao Cond Viver Tarumã - Tarumã-Açu, sentido oeste", "Av. do Turismo · Viver Tarumã"),
    ("Av. do Turismo, oposto Cond. Mediterrâneo I - Tarumã, sentido aeroporto Eduardo Gomes", "Av. do Turismo · Mediterrâneo"),
    ("Av. do Turismo, em frente ao Cond Viva Vida Tarumã - Tarumã, sentido leste", "Av. do Turismo · Viva Vida"),
)


def survey_items():
    out = []
    for address, label in _SURVEY:
        s = sentido_of(address)
        street, cross = crossing_of(address)
        out.append({"kind": "speed", "address": address, "sentido": s, "heading": heading_of(s), "label": label,
                    "limit": 60, "source": "survey", "lat": None, "lon": None, "street": street, "cross": cross})
    return out


def parse_overpass(data):
    items = []
    for el in data.get("elements", []):
        if el.get("type") != "node":
            continue
        tags = el.get("tags", {})
        ms = re.match(r"\d+", tags.get("maxspeed", ""))
        d = tags.get("direction", "")
        items.append({"kind": "speed", "address": "", "sentido": "", "heading": int(d) % 360 if d.isdigit() else None,
                      "label": tags.get("name") or "OSM %d" % el["id"], "limit": int(ms.group(0)) if ms else None,
                      "source": "osm", "lat": float(el["lat"]), "lon": float(el["lon"])})
    return items


# --- network -------------------------------------------------------------------------------------


def http_req(url, data=None, headers=None, timeout=30):
    h = {"User-Agent": USER_AGENT}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def fetch_immu():
    _, body = http_req(IMMU_URL)
    return parse_immu(body.decode("utf-8", "replace")) + survey_items() + announced_items()


def fetch_osm():
    q = '[out:json][timeout:25];node["highway"="speed_camera"](%s);out;' % BBOX
    last = None
    for attempt in range(2):    # the public instances answer 502 or stall now and then: retry, try the mirror
        for url in OVERPASS_URLS:
            try:
                _, body = http_req(url, data=urllib.parse.urlencode({"data": q}).encode(), timeout=70)
                return parse_overpass(json.loads(body))
            except (urllib.error.URLError, OSError, ValueError) as e:
                last = e
        time.sleep(2)
    raise last
