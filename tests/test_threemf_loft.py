"""Glatte Koerper aus Hoehenschnitten (threemf_loft) und dichte Netze fuer den Export (threemf_model.sealed)."""

import math

from shapes import box
from threemf_loft import aligned_profiles, loft_plan, master_profile, profile_points, step_heights, surface_area
from threemf_model import Part, combined, is_closed, moved, open_edge_count, sealed, signed_volume


def cylinder(radius=10.0, height=20.0, sides=64, z0=0.0, name="Zylinder"):
    """Geschlossenes Prisma mit `sides` Ecken - fuer das Netz "gerundet"."""
    ring = [(radius * math.cos(2 * math.pi * k / sides), radius * math.sin(2 * math.pi * k / sides)) for k in range(sides)]
    vertices = [(x, y, z0) for x, y in ring] + [(x, y, z0 + height) for x, y in ring] + [(0, 0, z0), (0, 0, z0 + height)]
    bottom, top = 2 * sides, 2 * sides + 1
    triangles = []
    for k in range(sides):
        n = (k + 1) % sides
        triangles += [(k, n, sides + n), (k, sides + n, sides + k), (bottom, n, k), (top, sides + k, sides + n)]
    return Part(name, 1, tuple(vertices), tuple(triangles))


# ------------------------------------------------------------------------------------- Plan

def test_a_round_part_gets_one_zone_with_eighteen_outlines_and_exact_caps():
    part = cylinder()
    plan = loft_plan(part)
    assert plan is not None and len(plan.zones) == 1 and len(plan.zones[0]) == 18
    assert {round(p[2], 9) for p in plan.zones[0][0]} == {0.0}
    assert {round(p[2], 9) for p in plan.zones[0][-1]} == {20.0}
    assert abs(plan.volume - abs(signed_volume(part))) < 1e-9
    assert abs(plan.area - surface_area(part)) < 1e-9


def test_a_flat_part_is_left_to_the_normal_way():
    assert loft_plan(box(0, 0, 0, 10, 20, 30)) is None


def test_a_part_with_two_islands_or_a_hole_is_not_a_section_part():
    two = combined([cylinder(), moved([cylinder()], (30.0, 0.0, 0.0))[0]])
    assert loft_plan(two) is None


def test_a_step_splits_the_part_into_two_zones():
    """Breiter Sockel, schmaler Zapfen darauf (Shape Toy): an der Stufe wird geteilt."""
    base = cylinder(radius=20.0, height=5.0)
    peg = cylinder(radius=5.0, height=15.0, z0=5.0)
    # Sockeldeckel und Zapfenboden liegen auf derselben Hoehe - als ein geschlossenes Netz zusammengesetzt:
    part = _stacked(base, peg)
    assert step_heights(part, 0.0, 20.0) == [5.0]
    plan = loft_plan(part)
    assert plan is not None and len(plan.zones) == 2
    assert loft_plan(part, split_steps=False) is not None


def _stacked(base: Part, peg: Part) -> Part:
    """Sockel + Zapfen als EIN geschlossener Koerper: der Sockeldeckel bekommt ein Loch fuer den Zapfen."""
    sides = 64
    vertices = list(base.vertices[:2 * sides]) + list(peg.vertices[:2 * sides]) + [(0, 0, 0), (0, 0, 20.0)]
    peg_off, bottom, top = 2 * sides, 4 * sides, 4 * sides + 1
    triangles = []
    for k in range(sides):
        n = (k + 1) % sides
        triangles += [(k, n, sides + n), (k, sides + n, sides + k), (bottom, n, k)]                  # Sockel
        triangles += [(sides + k, sides + n, peg_off + n), (sides + k, peg_off + n, peg_off + k)]     # Ring
        triangles += [(peg_off + k, peg_off + n, peg_off + sides + n), (peg_off + k, peg_off + sides + n,
                                                                         peg_off + sides + k)]       # Zapfen
        triangles.append((top, peg_off + sides + k, peg_off + sides + n))
    part = Part("Stufe", 1, tuple(vertices), tuple(triangles))
    assert is_closed(part)
    return part


# ------------------------------------------------------------------------------------- Profile

def test_profile_points_are_evenly_spaced_counter_clockwise_and_start_right_of_the_centre():
    ring = tuple(reversed(loft_plan(cylinder()).zones[0][5]))       # im Uhrzeigersinn uebergeben
    points = profile_points(ring, 1.0)
    assert len(points) == round(sum(math.dist(ring[i - 1], ring[i]) for i in range(len(ring))))
    assert points[0][0] > 9.9 and abs(points[0][1]) < 0.6
    twice_area = sum(points[i - 1][0] * points[i][1] - points[i][0] * points[i - 1][1] for i in range(len(points)))
    assert twice_area > 0


def test_aligned_profiles_lie_on_top_of_each_other_and_equal_sections_collapse():
    plan = loft_plan(cylinder())
    profiles = aligned_profiles(plan.zones[0], 1.0)
    assert profiles is not None and profiles.corners == ()
    # ein gerader Zylinder: alle Schnitte gleich -> nur unterster und oberster bleiben
    assert len(profiles.points) == 2
    for low, high in zip(*profiles.points):
        assert abs(low[0] - high[0]) < 1e-4 and abs(low[1] - high[1]) < 1e-4


def test_sharp_corners_stay_exact_and_straight_edges_keep_only_their_ends():
    square = ((0.0, 0.0, 1.0), (5.0, 0.0, 1.0), (10.0, 0.0, 1.0), (10.0, 10.0, 1.0), (0.0, 10.0, 1.0))
    points, corners, straight = master_profile(square, 1.0)
    assert len(corners) == 4 and all(straight)
    assert sorted((round(points[i][0]), round(points[i][1])) for i in corners) == [(0, 0), (0, 10), (10, 0), (10, 10)]
    assert len(points) == 4


# ------------------------------------------------------------------------------------- dicht

def test_sealed_closes_a_seam_where_one_side_has_an_extra_point():
    """Wie Allplans Naht an einer runden Flaeche: links ein Punkt mehr auf der Kante als rechts (T-Stoss)."""
    cube = box(0, 0, 0, 10, 10, 10)
    vertices = list(cube.vertices) + [(5.0, 0.0, 0.0)]          # Punkt 8 mitten auf der Kante 0-1
    triangles = [t for t in cube.triangles if t != (0, 2, 1)] + [(0, 2, 8), (8, 2, 1)]
    cracked = Part("Naht", 1, tuple(vertices), tuple(triangles))
    assert open_edge_count(cracked) > 0
    tight = sealed(cracked)
    assert is_closed(tight) and open_edge_count(tight) == 0
    assert abs(signed_volume(tight) - 1000.0) < 1e-6


def test_sealed_fills_a_thin_slit_and_the_volume_no_longer_depends_on_the_position():
    cube = box(0, 0, 0, 10, 10, 10)
    # die Bodenflaeche als zwei Streifen, dazwischen ein 0,05 mm breiter Spalt (zwei Raender, die nicht passen)
    vertices = list(cube.vertices) + [(5.0, 0.0, 0.0), (5.0, 10.0, 0.0), (5.05, 0.0, 0.0), (5.05, 10.0, 0.0)]
    triangles = [t for t in cube.triangles if t not in ((0, 2, 1), (0, 3, 2))]
    triangles += [(0, 9, 8), (0, 3, 9), (10, 2, 1), (10, 11, 2)]
    # die Seitenflaechen bekommen die neuen Punkte auf ihrer Unterkante, sonst waere der Spalt nach aussen offen
    triangles = [t for t in triangles if t not in ((0, 1, 5), (2, 3, 7))]
    triangles += [(0, 8, 5), (8, 10, 5), (10, 1, 5), (2, 11, 7), (11, 9, 7), (9, 3, 7)]
    slit = Part("Spalt", 1, tuple(vertices), tuple(triangles))
    assert open_edge_count(slit) > 0
    tight = sealed(slit)
    assert open_edge_count(tight) == 0
    far = moved([tight], (2800.0, -2600.0, 0.0))[0]
    assert abs(signed_volume(tight) - signed_volume(far)) < 1e-3
    assert abs(signed_volume(tight) - 1000.0) < 1e-3


def test_sealed_leaves_a_closed_body_alone_and_a_wide_hole_open():
    cube = box(0, 0, 0, 10, 10, 10)
    assert sealed(cube).triangles == cube.triangles
    tube = cylinder()
    top = 2 * 64 + 1
    lid_missing = Part("offen", 1, tube.vertices, tuple(t for t in tube.triangles if top not in t))
    assert open_edge_count(sealed(lid_missing)) == 64
