"""Host tests for tools/mapsvg.py (no network). Run: python -m pytest -q"""
import mapsvg

BASE = '<path class="road r-primary" d="M0 0 L10 10"/>'


def row(n=1, kind="speed", lat=-3.06, lon=-60.0, heading=90, limit=60, checked="2026-11-08"):
    return {"id": "mao-%04d" % n, "kind": kind, "lat": lat, "lon": lon, "heading": heading, "limit": limit,
            "label": "Av. X · Y", "source": "car", "checked": checked}


def test_xy_maps_the_corners():
    assert mapsvg.xy(mapsvg.NORTH, mapsvg.WEST) == (0, 0)
    assert mapsvg.xy(mapsvg.SOUTH, mapsvg.EAST) == (mapsvg.WIDTH, mapsvg.HEIGHT)


def way(kind, *pts, name=""):
    return {"tags": {"highway": kind, "name": name}, "geometry": [{"lat": la, "lon": lo} for la, lo in pts]}


def test_base_markup_draws_classes_in_order_and_skips_the_rest():
    ways = [way("primary", (-3.05, -60.05), (-3.06, -60.0)), way("residential", (-3.05, -60.05), (-3.06, -60.0)),
            way("trunk", (-2.0, -61.0), (-2.1, -61.1)), way("secondary", (-3.07, -60.05), (-3.08, -60.0))]
    out = mapsvg.base_markup(ways)
    assert 'class="road r-primary"' in out and 'class="road r-secondary"' in out
    assert "r-residential" not in out and "r-trunk" not in out       # not drawn / off the map
    assert out.index("r-secondary") < out.index("r-primary")          # big roads on top
    assert 'class="river"' in out


def test_base_markup_draws_water_green_and_neighbourhoods():
    lake = {"type": "way", "geometry": [{"lat": la, "lon": lo} for la, lo in
                                        ((-3.05, -60.05), (-3.05, -60.0), (-3.09, -60.0), (-3.05, -60.05))]}
    out = mapsvg.base_markup([], water=[lake], green=[lake], places=[{"name": "Flores", "lat": -3.07, "lon": -60.0}])
    assert '<path class="water"' in out and '<path class="green"' in out
    assert out.index('class="green"') < out.index('class="water"')     # water drawn over green
    assert ">FLORES</text>" in out


def test_join_links_pieces_end_to_end_and_across_small_gaps():
    a, b, c = [(0, 0), (10, 0)], [(20, 0), (10, 0)], [(23, 0), (30, 0)]
    joined = mapsvg.join([a, b])
    assert len(joined) == 1 and sorted(joined[0]) == [(0, 0), (10, 0), (20, 0)]
    assert len(mapsvg.join([a, b, c])) == 2
    assert len(mapsvg.join([a, b, c], gap=5)) == 1


def test_clip_keeps_a_polygon_inside_the_view():
    pts = mapsvg.clip([(-100, -100), (100, -100), (100, 100), (-100, 100)])
    assert pts and all(-4 <= x <= mapsvg.WIDTH + 4 and -4 <= y <= mapsvg.HEIGHT + 4 for x, y in pts)
    assert mapsvg.clip([(-50, -50), (-40, -50), (-40, -40)]) == []      # all outside


def test_street_labels_follow_the_road_left_to_right_and_skip_the_points():
    road = [way("primary", (-3.06, -59.96), (-3.06, -60.06), name="Avenida Teste")]   # drawn east to west
    out = mapsvg.base_markup(road)
    assert '<textPath href="#st0" startOffset="50%">Av. Teste</textPath>' in out
    d = out.split('<path id="st0" fill="none" d="M')[1].split('"')[0]
    xs = [float(p.split()[0]) for p in d.split(" L")]
    assert xs[0] < xs[-1]                                                # reads left to right
    near = [mapsvg.xy(-3.06, -59.96 - i / 100) for i in range(11)]     # a point every ~36 px
    assert "textPath" not in mapsvg.base_markup(road, keep_out=near)     # every stretch passes a point


def test_short_name_abbreviates():
    assert mapsvg.short_name("Avenida Professor Nilton Lins") == "Av. Prof. Nilton Lins"


def test_build_round_trips_its_base_and_is_stable():
    svg = mapsvg.build([row()], BASE, 37)
    assert mapsvg.base_of(svg) == BASE
    assert mapsvg.build([row()], mapsvg.base_of(svg), 37) == svg
    assert mapsvg.base_of("<svg></svg>") is None


def test_build_draws_one_sign_per_point_with_its_limit_and_the_legend():
    svg = mapsvg.build([row(1), row(2, kind="redlight", limit=None), row(3, kind="bump", limit=None,
                                                                      checked="2026-11-09")], BASE, 37)
    points = svg.split('<g id="points">')[1].split("</g>\n</g>")[0]
    assert points.count("<title>") == 3
    assert '<text class="lim"' in points and ">60</text>" in points
    assert "Pontos verificados: 3" in svg
    assert "Última verificação / last checked: 2026-11-09" in svg
    assert "Medidor de velocidade / Speed camera: 1" in svg and "Avanço de sinal / Red light: 1" in svg
    assert "37 endereços das listas da IMMU em verificação" in svg
    assert "© OpenStreetMap contributors" in svg


def test_arrow_points_the_heading():
    north = mapsvg.arrow(100, 100, 0)
    east = mapsvg.arrow(100, 100, 90)
    assert north.startswith('<path class="dir" d="M100.0 80.0')
    assert east.startswith('<path class="dir" d="M120.0 100.0')
