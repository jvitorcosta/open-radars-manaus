"""Host tests for tools/mapsvg.py (no network). Run: python -m pytest -q"""
import mapsvg

ROADS = '<path class="road" stroke-width="1.8" d="M0 0 L10 10"/>'


def row(n=1, kind="speed", lat=-3.06, lon=-60.0, heading=90, limit=60, checked="2026-11-08"):
    return {"id": "mao-%04d" % n, "kind": kind, "lat": lat, "lon": lon, "heading": heading, "limit": limit,
            "label": "Av. X · Y", "source": "car", "checked": checked}


def test_xy_maps_the_corners():
    assert mapsvg.xy(mapsvg.NORTH, mapsvg.WEST) == (0, 0)
    assert mapsvg.xy(mapsvg.SOUTH, mapsvg.EAST) == (mapsvg.WIDTH, mapsvg.HEIGHT)


def test_roads_markup_keeps_drawn_classes_and_skips_the_rest():
    ways = [{"tags": {"highway": "primary"}, "geometry": [{"lat": -3.05, "lon": -60.05}, {"lat": -3.06, "lon": -60.0}]},
            {"tags": {"highway": "residential"}, "geometry": [{"lat": -3.05, "lon": -60.05}, {"lat": -3.06, "lon": -60.0}]},
            {"tags": {"highway": "trunk"}, "geometry": [{"lat": -2.0, "lon": -61.0}, {"lat": -2.1, "lon": -61.1}]}]
    out = mapsvg.roads_markup(ways)
    assert out.count("<path") == 1 and 'stroke-width="1.8"' in out    # residential and off-map trunk left out


def test_build_round_trips_its_roads_and_is_stable():
    svg = mapsvg.build([row()], ROADS, 37)
    assert mapsvg.roads_of(svg) == ROADS
    assert mapsvg.build([row()], mapsvg.roads_of(svg), 37) == svg
    assert mapsvg.roads_of("<svg></svg>") is None


def test_build_draws_one_sign_per_point_with_its_limit_and_the_legend():
    svg = mapsvg.build([row(1), row(2, kind="redlight", limit=None), row(3, kind="bump", limit=None,
                                                                      checked="2026-11-09")], ROADS, 37)
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
