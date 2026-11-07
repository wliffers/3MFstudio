"""Tests fuer threemf_geom: Newell-Normale, Triangulation, planare UV."""

from __future__ import annotations

import math
import time

import pytest

import threemf_geom
from threemf_geom import GeometryError, newell_normal, planar_uv, triangulate


# --------------------------------------------------------------------------
# Hilfen
# --------------------------------------------------------------------------

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _len(a):
    return math.sqrt(_dot(a, a))


def ring_area(points):
    """Flaeche eines ebenen 3D-Rings (Betrag des Newell-Vektors / 2)."""
    sx = sy = sz = 0.0
    n = len(points)
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        sx += (a[1] - b[1]) * (a[2] + b[2])
        sy += (a[2] - b[2]) * (a[0] + b[0])
        sz += (a[0] - b[0]) * (a[1] + b[1])
    return 0.5 * math.sqrt(sx * sx + sy * sy + sz * sz)


def tri_area(verts, tri):
    a, b, c = (verts[i] for i in tri)
    return 0.5 * _len(_cross(_sub(b, a), _sub(c, a)))


def total_area(verts, tris):
    return sum(tri_area(verts, t) for t in tris)


def assert_orientation(verts, tris, normal):
    """Jedes Dreieck zeigt in Richtung der gegebenen Normale."""
    for t in tris:
        a, b, c = (verts[i] for i in t)
        n = _cross(_sub(b, a), _sub(c, a))
        assert _dot(n, normal) > 0.0, f"Dreieck {t} falsch herum"


def circle(n, r=5.0, z=0.0, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(2 * math.pi * i / n),
             cy + r * math.sin(2 * math.pi * i / n), z) for i in range(n)]


def rect(x0, y0, x1, y1, z=0.0):
    return [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]


def cw(points):
    return list(reversed(points))


# --------------------------------------------------------------------------
# newell_normal
# --------------------------------------------------------------------------

def test_newell_square_ccw_points_up():
    n = newell_normal(rect(0, 0, 2, 2))
    assert n == pytest.approx((0.0, 0.0, 1.0))


def test_newell_square_cw_points_down():
    n = newell_normal(cw(rect(0, 0, 2, 2)))
    assert n == pytest.approx((0.0, 0.0, -1.0))


def test_newell_is_unit_length_for_tilted_face():
    pts = [(0, 0, 0), (4, 0, 0), (4, 3, 3), (0, 3, 3)]
    n = newell_normal(pts)
    assert _len(n) == pytest.approx(1.0)
    assert _dot(n, (1, 0, 0)) == pytest.approx(0.0)


def test_newell_degenerate_line_gives_zero_vector():
    assert newell_normal([(0, 0, 0), (1, 0, 0), (2, 0, 0)]) == (0.0, 0.0, 0.0)


def test_newell_too_few_points_gives_zero_vector():
    assert newell_normal([(0, 0, 0), (1, 0, 0)]) == (0.0, 0.0, 0.0)
    assert newell_normal([]) == (0.0, 0.0, 0.0)


# --------------------------------------------------------------------------
# triangulate: Grundformen
# --------------------------------------------------------------------------

def test_convex_quad_two_triangles():
    pts = rect(0, 0, 3, 2)
    verts, tris = triangulate(pts)
    assert len(verts) == 4
    assert len(tris) == 2
    assert total_area(verts, tris) == pytest.approx(6.0)
    assert_orientation(verts, tris, (0, 0, 1))


def test_triangle_stays_one_triangle():
    verts, tris = triangulate([(0, 0, 0), (1, 0, 0), (0, 1, 0)])
    assert len(tris) == 1
    assert total_area(verts, tris) == pytest.approx(0.5)


def test_concave_l_shape_four_triangles_area_preserved():
    l_shape = [(0, 0, 0), (3, 0, 0), (3, 1, 0), (1, 1, 0), (1, 3, 0), (0, 3, 0)]
    verts, tris = triangulate(l_shape)
    assert len(verts) == 6
    assert len(tris) == 4
    assert total_area(verts, tris) == pytest.approx(5.0)
    assert_orientation(verts, tris, (0, 0, 1))
    # kein Dreieck liegt im ausgesparten Quadrat (1..3, 1..3)
    for t in tris:
        cx = sum(verts[i][0] for i in t) / 3.0
        cy = sum(verts[i][1] for i in t) / 3.0
        assert not (cx > 1.0 and cy > 1.0)


def test_polygon_with_rectangular_hole():
    outer = rect(0, 0, 4, 4)
    hole = rect(1, 1, 2, 3)
    verts, tris = triangulate(outer, [hole])
    assert len(verts) == 8
    assert len(tris) == 8
    assert total_area(verts, tris) == pytest.approx(16.0 - 2.0)
    assert_orientation(verts, tris, (0, 0, 1))
    for t in tris:
        cx = sum(verts[i][0] for i in t) / 3.0
        cy = sum(verts[i][1] for i in t) / 3.0
        assert not (1.0 < cx < 2.0 and 1.0 < cy < 3.0), "Dreieck im Loch"


def test_hole_orientation_does_not_matter():
    outer = rect(0, 0, 4, 4)
    hole = rect(1, 1, 2, 3)
    v1, t1 = triangulate(outer, [hole])
    v2, t2 = triangulate(outer, [cw(hole)])
    assert total_area(v1, t1) == pytest.approx(total_area(v2, t2))
    assert total_area(v2, t2) == pytest.approx(14.0)


def test_vertical_wall_face_in_xz_plane():
    # Wand in der XZ-Ebene (y = 0), Tuerloch
    wall = [(0, 0, 0), (5, 0, 0), (5, 0, 2.5), (0, 0, 2.5)]
    door = [(1, 0, 0.0), (2, 0, 0.0), (2, 0, 2.0), (1, 0, 2.0)]
    verts, tris = triangulate(wall, [door])
    assert total_area(verts, tris) == pytest.approx(12.5 - 2.0)
    assert_orientation(verts, tris, newell_normal(wall))
    # alle Eckpunkte bleiben in der Ebene
    assert all(v[1] == 0.0 for v in verts)


def test_clockwise_input_follows_newell_normal_of_outer():
    pts = cw(rect(0, 0, 2, 3))
    normal = newell_normal(pts)
    assert normal == pytest.approx((0.0, 0.0, -1.0))
    verts, tris = triangulate(pts)
    assert total_area(verts, tris) == pytest.approx(6.0)
    assert_orientation(verts, tris, normal)


def test_clockwise_concave_input_follows_newell_normal():
    l_shape = [(0, 0, 0), (3, 0, 0), (3, 1, 0), (1, 1, 0), (1, 3, 0), (0, 3, 0)]
    pts = cw(l_shape)
    verts, tris = triangulate(pts)
    assert len(tris) == 4
    assert total_area(verts, tris) == pytest.approx(5.0)
    assert_orientation(verts, tris, (0, 0, -1))


def test_tilted_plane_with_hole_area():
    # Rechteck 4 x 5 in einer geneigten Ebene, Loch 1 x 1
    def lift(x, y):
        return (x, y * 0.6, y * 0.8)  # Laenge in y bleibt (0.6^2+0.8^2=1)
    outer = [lift(0, 0), lift(4, 0), lift(4, 5), lift(0, 5)]
    hole = [lift(1, 1), lift(2, 1), lift(2, 2), lift(1, 2)]
    verts, tris = triangulate(outer, [hole])
    assert total_area(verts, tris) == pytest.approx(20.0 - 1.0)
    assert_orientation(verts, tris, newell_normal(outer))


# --------------------------------------------------------------------------
# triangulate: Bereinigung
# --------------------------------------------------------------------------

def test_duplicate_and_collinear_points_removed():
    pts = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 0, 0), (2, 2, 0), (1, 2, 0),
           (0, 2, 0), (0, 1, 0), (0, 0, 0)]  # Mittelpunkte, Doppelpunkt, Schlusspunkt
    verts, tris = triangulate(pts)
    assert len(verts) == 4
    assert len(tris) == 2
    assert total_area(verts, tris) == pytest.approx(4.0)


def test_vertices_reference_original_coordinates():
    pts = rect(0, 0, 2, 2)
    verts, tris = triangulate(pts)
    assert sorted(verts) == sorted(pts)
    assert all(0 <= i < len(verts) for t in tris for i in t)


def test_too_few_points_raises():
    with pytest.raises(GeometryError):
        triangulate([(0, 0, 0), (1, 0, 0)])


def test_too_few_points_after_cleanup_raises():
    with pytest.raises(GeometryError):
        triangulate([(0, 0, 0), (0, 0, 0), (1, 0, 0), (1, 0, 0)])


def test_zero_area_collinear_raises():
    with pytest.raises(GeometryError):
        triangulate([(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)])


def test_geometry_error_is_value_error():
    assert issubclass(GeometryError, ValueError)


def test_error_text_has_no_forbidden_word():
    with pytest.raises(GeometryError) as ei:
        triangulate([(0, 0, 0), (1, 0, 0)])
    assert "traceback" not in str(ei.value).lower()


def test_hole_outside_outer_raises():
    with pytest.raises(GeometryError):
        triangulate(rect(0, 0, 2, 2), [rect(5, 5, 6, 6)])


def test_degenerate_hole_is_ignored():
    outer = rect(0, 0, 2, 2)
    verts, tris = triangulate(outer, [[(0.5, 0.5, 0), (1, 0.5, 0), (1.5, 0.5, 0)]])
    assert total_area(verts, tris) == pytest.approx(4.0)


# --------------------------------------------------------------------------
# triangulate: Robustheit und Groesse
# --------------------------------------------------------------------------

def test_many_vertices_circle_300():
    pts = circle(300)
    t0 = time.perf_counter()
    verts, tris = triangulate(pts)
    elapsed = time.perf_counter() - t0
    assert len(tris) == 298
    assert total_area(verts, tris) == pytest.approx(ring_area(pts))
    assert_orientation(verts, tris, (0, 0, 1))
    assert elapsed < 5.0


def test_many_vertices_comb_concave():
    # Kamm mit 60 Zinken (Sockel y 0..1, Zinken bis y = 3): stark konkav
    n = 60
    w = 1.5 * (n - 1) + 0.5
    pts = [(0.0, 0.0, 0.0), (w, 0.0, 0.0)]
    for k in reversed(range(n)):
        xl = 1.5 * k
        xr = xl + 0.5
        if k < n - 1:
            pts.append((xr, 1.0, 0.0))
        pts.append((xr, 3.0, 0.0))
        pts.append((xl, 3.0, 0.0))
        if k > 0:
            pts.append((xl, 1.0, 0.0))
    verts, tris = triangulate(pts)
    assert len(tris) == len(verts) - 2
    assert total_area(verts, tris) == pytest.approx(w * 1.0 + n * 0.5 * 2.0)
    assert_orientation(verts, tris, newell_normal(pts))


def test_circle_with_three_holes():
    outer = circle(120, r=10.0)
    holes = [circle(24, r=1.5, cx=-4.0, cy=1.0),
             circle(24, r=1.5, cx=0.0, cy=-2.0),
             circle(24, r=1.5, cx=4.5, cy=2.0)]
    verts, tris = triangulate(outer, holes)
    expected = ring_area(outer) - sum(ring_area(h) for h in holes)
    assert total_area(verts, tris) == pytest.approx(expected)
    assert len(verts) == 120 + 72
    assert_orientation(verts, tris, (0, 0, 1))


def test_grid_of_holes_3x3():
    outer = rect(0, 0, 10, 10)
    holes = [rect(1 + 3 * i, 1 + 3 * j, 2 + 3 * i, 2 + 3 * j)
             for i in range(3) for j in range(3)]
    verts, tris = triangulate(outer, holes)
    assert total_area(verts, tris) == pytest.approx(100.0 - 9.0)
    assert_orientation(verts, tris, (0, 0, 1))


def test_hole_vertex_on_same_height_as_outer_vertex():
    # Strahl vom rechtesten Lochpunkt trifft genau einen Eckpunkt (y = 1)
    outer = [(0, 0, 0), (6, 0, 0), (6, 1, 0), (4, 1, 0), (4, 5, 0), (0, 5, 0)]
    # rechtester Lochpunkt (2, 1) liegt auf der Hoehe des Aussenecks (4, 1)
    hole = [(1, 0.25, 0), (2, 1, 0), (1, 1, 0)]
    verts, tris = triangulate(outer, [hole])
    assert total_area(verts, tris) == pytest.approx(ring_area(outer) - 0.375)
    assert_orientation(verts, tris, (0, 0, 1))


def test_bridge_blocked_by_reflex_vertex():
    # Konkave Aussenform: der direkte Sichtstrahl wird durch eine Ecke verdeckt
    outer = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (6, 10, 0), (6, 4, 0),
             (5, 4, 0), (5, 10, 0), (0, 10, 0)]
    hole = rect(1, 1, 3, 3)
    verts, tris = triangulate(outer, [hole])
    assert total_area(verts, tris) == pytest.approx(ring_area(outer) - 4.0)
    assert_orientation(verts, tris, (0, 0, 1))


def test_random_star_polygons_with_holes_seeded():
    """Zufaellige sternfoermige Umrisse mit Kreisloechern, im Raum gekippt."""
    import random
    rng = random.Random(2)
    checked = 0
    for _ in range(400):
        n = rng.randint(12, 80)
        angs = sorted(rng.uniform(0, 2 * math.pi) for _ in range(n))
        gaps = [(angs[(i + 1) % n] - angs[i]) % (2 * math.pi) for i in range(n)]
        if max(gaps) > 1.0:
            continue
        outer = [(math.cos(a) * r, math.sin(a) * r, 0.0)
                 for a in angs for r in [rng.uniform(8, 10)]]
        holes, centers = [], []
        for _ in range(rng.randint(0, 5)):
            cx, cy, r = rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(0.2, 0.9)
            if all(math.hypot(cx - a, cy - b) > r + rr + 0.1 for a, b, rr in centers):
                centers.append((cx, cy, r))
                m = rng.randint(3, 12)
                h = [(cx + r * math.cos(2 * math.pi * i / m),
                      cy + r * math.sin(2 * math.pi * i / m), 0.0) for i in range(m)]
                if rng.random() < 0.5:
                    h.reverse()
                holes.append(h)
        th = rng.uniform(0, math.pi)
        c, s = math.cos(th), math.sin(th)

        def rot(p):
            return (p[0], p[1] * c - p[2] * s, p[1] * s + p[2] * c)
        outer = [rot(p) for p in outer]
        holes = [[rot(p) for p in h] for h in holes]
        verts, tris = triangulate(outer, holes)
        expected = ring_area(outer) - sum(ring_area(h) for h in holes)
        assert total_area(verts, tris) == pytest.approx(expected, rel=1e-6)
        assert_orientation(verts, tris, newell_normal(outer))
        assert len(tris) == len(verts) + 2 * len(holes) - 2
        checked += 1
    assert checked > 100


# --------------------------------------------------------------------------
# planar_uv
# --------------------------------------------------------------------------

def test_uv_floor_uses_xy_scaled():
    pts = [(0, 0, 3), (2, 0, 3), (2, 4, 3), (0, 4, 3)]
    uv = planar_uv(pts, (0, 0, 1), 2.0, 4.0)
    assert uv == [pytest.approx((0.0, 0.0)), pytest.approx((1.0, 0.0)),
                  pytest.approx((1.0, -1.0)), pytest.approx((0.0, -1.0))]


def test_uv_ceiling_with_downward_normal_also_uses_xy():
    uv = planar_uv([(1, 2, 3)], (0, 0, -1), 1.0, 1.0)
    assert uv[0] == pytest.approx((1.0, -2.0))


def test_uv_wall_v_is_minus_z_and_u_along_horizontal_tangent():
    # glTF: v waechst im Bild nach unten -> v = -z, damit das Bild aufrecht steht
    # Wand in der XZ-Ebene, Normale -Y -> Tangente +X
    n = (0.0, -1.0, 0.0)
    pts = [(0, 0, 0), (3, 0, 0), (3, 0, 2.5), (0, 0, 2.5)]
    uv = planar_uv(pts, n, 1.5, 0.5)
    assert uv[0] == pytest.approx((0.0, 0.0))
    assert uv[1] == pytest.approx((2.0, 0.0))
    assert uv[2] == pytest.approx((2.0, -5.0))
    assert uv[3] == pytest.approx((0.0, -5.0))


def test_uv_wall_along_y_axis_uses_y_for_u():
    # Wand in der YZ-Ebene, Normale +X -> Tangente = cross(z, x) = +Y
    uv = planar_uv([(7, 2, 1)], (1.0, 0.0, 0.0), 1.0, 1.0)
    assert uv[0] == pytest.approx((2.0, -1.0))


def test_uv_diagonal_wall_is_metric():
    # 45-Grad-Wand: u laeuft entlang der Wandrichtung, Laenge in Metern
    n = (math.sqrt(0.5), -math.sqrt(0.5), 0.0)
    a, b = (0.0, 0.0, 0.0), (2.0, 2.0, 0.0)
    uv = planar_uv([a, b], n, 1.0, 1.0)
    assert uv[1][0] - uv[0][0] == pytest.approx(math.hypot(2.0, 2.0))


def test_uv_continuity_two_adjacent_faces_same_plane():
    n = (0.0, -1.0, 0.0)
    face1 = [(0, 0, 0), (2, 0, 0), (2, 0, 3), (0, 0, 3)]
    face2 = [(2, 0, 0), (5, 0, 0), (5, 0, 3), (2, 0, 3)]
    uv1 = planar_uv(face1, n, 1.2, 1.2)
    uv2 = planar_uv(face2, n, 1.2, 1.2)
    assert uv1[1] == pytest.approx(uv2[0])
    assert uv1[2] == pytest.approx(uv2[3])


def test_uv_continuity_two_adjacent_floor_faces():
    n = (0.0, 0.0, 1.0)
    f1 = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)]
    f2 = [(2, 0, 0), (4, 0, 0), (4, 2, 0), (2, 2, 0)]
    uv1 = planar_uv(f1, n, 0.8, 0.8)
    uv2 = planar_uv(f2, n, 0.8, 0.8)
    assert uv1[1] == pytest.approx(uv2[0])
    assert uv1[2] == pytest.approx(uv2[3])


def test_uv_threshold_for_flat_roof():
    # Dachneigung ~30 Grad: |nz| = cos(30) = 0.866 >= 0.7071 -> Draufsicht
    nz = math.cos(math.radians(30))
    ny = -math.sin(math.radians(30))
    uv = planar_uv([(1, 2, 3)], (0.0, ny, nz), 1.0, 1.0)
    assert uv[0] == pytest.approx((1.0, -2.0))
    # steil (60 Grad): nz = 0.5 -> Wandprojektion, v = -z
    nz = math.cos(math.radians(60))
    ny = -math.sin(math.radians(60))
    uv = planar_uv([(1, 2, 3)], (0.0, ny, nz), 1.0, 1.0)
    assert uv[0][1] == pytest.approx(-3.0)


def _extent(values):
    return max(values) - min(values)


FLOOR_RECT = [(0, 0, 0), (4, 0, 0), (4, 2, 0), (0, 2, 0)]            # 4 m in x, 2 m in y
WALL_RECT = [(0, 0, 0), (4, 0, 0), (4, 0, 2), (0, 0, 2)]             # 4 m lang, 2 m hoch, Normale -Y


def test_uv_rotation_zero_and_offset_zero_are_bit_identical():
    n_floor, n_wall = (0, 0, 1), (0.3, -0.8, 0.0)
    pts = [(0.1, 0.7, 0.3), (2.9, -1.3, 4.1), (-3.3, 5.5, 0.0)]
    for n in (n_floor, n_wall):
        old_style = planar_uv(pts, n, 1.7, 0.45)
        assert planar_uv(pts, n, 1.7, 0.45, 0.0, (0.0, 0.0)) == old_style
        assert planar_uv(pts, n, 1.7, 0.45, rotation=0.0, offset=(0.0, 0.0)) == old_style
    # Die unveraenderte Formel (bitgenau, kein Rundungsunterschied)
    assert planar_uv(pts, n_floor, 1.7, 0.45) == [(p[0] / 1.7, -p[1] / 0.45) for p in pts]


def test_uv_rotation_90_swaps_extents_on_2_to_1_tile_floor():
    # Kachel 2 m x 1 m; Flaeche 4 m x 2 m
    plain = planar_uv(FLOOR_RECT, (0, 0, 1), 2.0, 1.0)
    assert _extent([u for u, _ in plain]) == pytest.approx(2.0)      # 4 m / 2 m
    assert _extent([v for _, v in plain]) == pytest.approx(2.0)      # 2 m / 1 m
    turned = planar_uv(FLOOR_RECT, (0, 0, 1), 2.0, 1.0, math.pi / 2)
    # Nach 90 Grad laeuft u entlang y (2 m / 2 m) und v entlang x (4 m / 1 m): keine Verzerrung
    assert _extent([u for u, _ in turned]) == pytest.approx(1.0)
    assert _extent([v for _, v in turned]) == pytest.approx(4.0)


def test_uv_rotation_90_swaps_extents_on_2_to_1_tile_wall():
    plain = planar_uv(WALL_RECT, (0.0, -1.0, 0.0), 2.0, 1.0)
    assert _extent([u for u, _ in plain]) == pytest.approx(2.0)
    assert _extent([v for _, v in plain]) == pytest.approx(2.0)
    turned = planar_uv(WALL_RECT, (0.0, -1.0, 0.0), 2.0, 1.0, math.pi / 2)
    assert _extent([u for u, _ in turned]) == pytest.approx(1.0)      # 2 m Hoehe / 2 m
    assert _extent([v for _, v in turned]) == pytest.approx(4.0)      # 4 m Laenge / 1 m


def test_uv_rotation_is_metric_not_distorting_on_non_square_tile():
    # Unter Drehung bleibt der Abstand zweier Punkte in Kachel-Einheiten das Bild des Meterabstands:
    # ein Meter entlang x ist bei Drehung 90 Grad genau ein Meter entlang v (Kachel 3 m x 0.5 m)
    uv = planar_uv([(0, 0, 0), (1, 0, 0)], (0, 0, 1), 3.0, 0.5, math.pi / 2)
    assert (uv[1][0] - uv[0][0]) == pytest.approx(0.0, abs=1e-12)
    assert (uv[1][1] - uv[0][1]) == pytest.approx(-1.0 / 0.5)         # t' = -sin * s


def test_uv_rotation_sign_counterclockwise_like_khr_texture_transform():
    # Quadratische Kachel: gleiche Matrix wie KHR_texture_transform (u' = c*u + s*v, v' = -s*u + c*v)
    base = planar_uv([(1.0, 0.5, 0.0)], (0, 0, 1), 1.0, 1.0)[0]
    angle = 0.6
    turned = planar_uv([(1.0, 0.5, 0.0)], (0, 0, 1), 1.0, 1.0, angle)[0]
    assert turned[0] == pytest.approx(math.cos(angle) * base[0] + math.sin(angle) * base[1])
    assert turned[1] == pytest.approx(-math.sin(angle) * base[0] + math.cos(angle) * base[1])


def test_uv_rotation_around_world_origin_of_projection():
    # Der Ursprung bleibt fest, auch bei gedrehter Wand
    n = (0.0, -1.0, 0.0)
    assert planar_uv([(0, 0, 0)], n, 2.0, 1.0, 1.1)[0] == pytest.approx((0.0, 0.0))
    # Punkt (2, 0) auf dem Boden, 180 Grad -> (-2, 0)
    uv = planar_uv([(2.0, 0.0, 0.0)], (0, 0, 1), 1.0, 1.0, math.pi)[0]
    assert uv == pytest.approx((-2.0, 0.0), abs=1e-12)


def test_uv_rotation_keeps_continuity_across_adjacent_faces():
    n = (0.0, -1.0, 0.0)
    face1 = [(0, 0, 0), (2, 0, 0), (2, 0, 3), (0, 0, 3)]
    face2 = [(2, 0, 0), (5, 0, 0), (5, 0, 3), (2, 0, 3)]
    uv1 = planar_uv(face1, n, 1.2, 0.7, 0.9, (0.1, 0.2))
    uv2 = planar_uv(face2, n, 1.2, 0.7, 0.9, (0.1, 0.2))
    assert uv1[1] == pytest.approx(uv2[0])
    assert uv1[2] == pytest.approx(uv2[3])


def test_uv_offset_added_in_tile_fractions_after_division():
    pts = [(2, 4, 0), (0, 0, 0)]
    plain = planar_uv(pts, (0, 0, 1), 2.0, 4.0)
    moved = planar_uv(pts, (0, 0, 1), 2.0, 4.0, offset=(0.25, -0.5))
    for a, b in zip(plain, moved):
        assert b == pytest.approx((a[0] + 0.25, a[1] - 0.5))
    wall_plain = planar_uv(WALL_RECT, (0.0, -1.0, 0.0), 2.0, 1.0)
    wall_moved = planar_uv(WALL_RECT, (0.0, -1.0, 0.0), 2.0, 1.0, offset=(0.1, 0.2))
    for a, b in zip(wall_plain, wall_moved):
        assert b == pytest.approx((a[0] + 0.1, a[1] + 0.2))


def test_uv_offset_is_not_rotated_nor_scaled():
    pts = [(1.0, 1.0, 0.0)]
    turned = planar_uv(pts, (0, 0, 1), 4.0, 0.5, 0.7)[0]
    both = planar_uv(pts, (0, 0, 1), 4.0, 0.5, 0.7, (0.3, 0.4))[0]
    assert both == pytest.approx((turned[0] + 0.3, turned[1] + 0.4))


@pytest.mark.parametrize("kwargs", [
    {"rotation": float("nan")},
    {"rotation": float("inf")},
    {"offset": (float("nan"), 0.0)},
    {"offset": (0.0, float("inf"))},
    {"offset": (0.0,)},
    {"offset": 1.0},
    {"rotation": "schief"},
])
def test_uv_invalid_rotation_or_offset_raises(kwargs):
    with pytest.raises(GeometryError):
        planar_uv([(0, 0, 0)], (0, 0, 1), 1.0, 1.0, **kwargs)


def test_uv_scale_must_be_positive():
    with pytest.raises(GeometryError):
        planar_uv([(0, 0, 0)], (0, 0, 1), 0.0, 1.0)
    with pytest.raises(GeometryError):
        planar_uv([(0, 0, 0)], (0, 0, 1), 1.0, -2.0)


def test_uv_zero_normal_raises():
    with pytest.raises(GeometryError):
        planar_uv([(0, 0, 0)], (0, 0, 0), 1.0, 1.0)


def test_module_has_no_allplan_import():
    src = open(threemf_geom.__file__, encoding="utf-8").read()
    assert "NemAll_Python" not in src
