"""Abnahme mit den Beispielen des Anwenders (input/examples, 2026-11-07): Lesen und Hin-und-zurueck muessen stimmen.

Je Datei:
- Lesen: Zahl der Koerper, Filament je Koerper, Farbe je Filament, uebergangene Hilfskoerper, Bemalung, Groesse.
- Hin und zurueck: jeden Koerper seinem Filament zuordnen (wie nach dem Import in Allplan), schreiben, wieder
  lesen - Koerper je Filament, Volumen je Filament und Gesamtgroesse bleiben gleich.

Die Erwartungen stehen hier ausgeschrieben; sie stammen aus Bambus eigener Zusatzdatei der Beispiele
(model_settings.config, project_settings.config) und nicht aus unserem Leser. Dateien ohne Farben sind
Formtests. Dass Bambu Studio die geschriebenen Dateien genauso liest, prueft test_examples_bambu.py.
"""

from collections import Counter
from pathlib import Path

import pytest

import threemf_model as model
from shapes import box
from threemf_reader import read_file, read_3mf
from threemf_session import Body, Session
from threemf_writer import write_3mf

EXAMPLES = Path(__file__).resolve().parents[1] / "input" / "examples"
# Die Beispieldateien sind Fremdmaterial und liegen nicht im veroeffentlichten Repo: ohne den Ordner wird
# hier uebersprungen (= nicht geprueft), nicht gescheitert.
pytestmark = pytest.mark.skipif(not EXAMPLES.is_dir(), reason="input/examples fehlt - Beispiele nicht geprueft")

# Datei: (Filament -> Zahl der Koerper, Farbe je benutztem Filament, Hilfskoerper, bemalt, Groesse in mm)
EXPECTED = {
    "3D+Printer+Test.3mf": ({6: 13}, {6: "#161616"}, 0, 0, (96.0, 50.0, 28.68)),
    "3D+PUZZLE.3mf": ({1: 37}, {1: "#FEC600"}, 0, 0, (496.86, 203.0, 10.0)),
    "3D_Printer_test.3mf": ({1: 1}, {1: "#808080"}, 0, 0, (100.0, 100.0, 60.52)),
    "3Layers4ColorsPlate1.3mf": ({3: 3, 1: 2, 2: 2, 4: 2},
                                 {1: "#0086D6", 2: "#FCE300", 3: "#FFFFFF", 4: "#EC008C"}, 0, 0, (100.0, 100.0, 0.36)),
    "8_Colors_AMS_Test.3mf": ({n: 1 for n in range(1, 9)},
                              {1: "#3F8E43", 2: "#6F5034", 3: "#847D48", 4: "#00B1B7", 5: "#008080", 6: "#804040",
                               7: "#00AE42", 8: "#0086D6"}, 0, 0, (50.0, 50.0, 50.0)),
    "Amazing+Luulia.3mf": ({1: 1}, {1: "#FFFFFF"}, 0, 1, (35.23, 35.23, 26.42)),
    "AMS+eight+color+test+swatch+BODS.3mf": ({6: 2, 8: 3, 2: 3, 4: 4, 1: 2, 3: 2, 5: 2, 7: 2},
                                             {1: "#161616", 2: "#FFFFFF", 3: "#F72323", 4: "#46A8F9", 5: "#A03CF7",
                                              6: "#057748", 7: "#FFF144", 8: "#0ACC38"}, 0, 0, (43.81, 43.81, 0.6)),
    "AMS+test+16+colors.3mf": ({n: 1 for n in range(1, 17)},
                               {1: "#FFFFFF", 2: "#FFFF00", 3: "#FF9933", 4: "#FD6102", 5: "#F930F3", 6: "#FF0000",
                                7: "#00FFFF", 8: "#004B7C", 9: "#2323F7", 10: "#735DF9", 11: "#38CC0A", 12: "#487705",
                                13: "#E3CE77", 14: "#804040", 15: "#898989", 16: "#161616"}, 0, 0, (152.4, 152.4, 1.0)),
    "MIUT.3mf": ({1: 1}, {1: "#008000"}, 0, 0, (180.0, 180.0, 3.0)),
    "Puzzle1.3mf": ({1: 1}, {1: "#AE96D4"}, 0, 0, (99.7, 99.7, 3.85)),
    "pyramid_lattice_11_layers_cell10mm_width1.0mm_no_tray.3mf": ({1: 1}, {1: "#F98C36"}, 0, 0, (101.0, 87.6, 82.65)),
    "Stella_Octangula_Fractal_Level_1_P1S_04Nozzle_SILK_PLA_17g_1Hr_19Min.3mf": ({1: 1}, {1: "#000000"}, 0, 0,
                                                                                (35.0, 35.0, 35.0)),
    # ohne die zwei Einstellungs-Wuerfel (modifier_part), die ueber das Modell hinausragen
    "torture+test!.3mf": ({1: 5}, {1: "#FF6A13"}, 2, 0, (50.5, 50.0, 51.94)),
    # zweite Lieferung des Anwenders (2026-11-07 mittags)
    "All+in+One+Calibration+Cube.3mf": ({1: 4}, {1: "#808080"}, 0, 0, (40.0, 40.0, 40.0)),
    "Ball_of_Mirrored_Dodecahedra_P1S_04_Nozzle_131g_7h43m,_SILK_PLA.3mf": ({1: 1}, {1: "#FFFFFF"}, 0, 0,
                                                                            (100.0, 105.15, 111.84)),
    "Bambu+Cube+Color-Version.3mf": ({1: 1}, {1: "#FFFFFF"}, 0, 1, (30.0, 30.0, 30.0)),
    "Benchy+gone+crazy.3mf": ({1: 1}, {1: "#C12E1F"}, 0, 1, (60.74, 32.64, 48.0)),
    "Floral+Design+Molding.3mf": ({3: 1}, {3: "#E8DBB7"}, 0, 0, (90.4, 90.61, 5.6)),
    "Infill+Test+Map+V2.3mf": ({3: 66, 1: 1, 2: 236}, {3: "#0ACC38", 1: "#161616", 2: "#FFFFFF"}, 0, 0,
                               (165.0, 165.0, 9.0)),
    "ksr+FDMTest.3mf": ({1: 1}, {1: "#8E9089"}, 0, 1, (75.0, 70.0, 92.0)),
    "Nick+Stress+test+v2 (1).3mf": ({1: 1}, {1: "#FFFFFF"}, 0, 0, (100.0, 100.0, 61.0)),
    "Nick+Stress+test+v2.3mf": ({1: 1}, {1: "#FFFFFF"}, 0, 0, (100.0, 100.0, 61.0)),
    "Original_3DBenchy_3Dprintconcept.3mf": ({1: 1}, {1: "#E05028"}, 0, 0, (60.0, 31.0, 48.0)),
    "Shape+Toy+2+All.3mf": ({1: 9}, {1: "#FF6A13"}, 0, 0, (495.06, 208.91, 49.5)),
    "六边拉桥.3mf": ({5: 1}, {5: "#38CC0A"}, 0, 0, (102.31, 88.63, 12.8)),
    "四色小船+-+副本.3mf": ({1: 1}, {1: "#FFFFFF"}, 0, 1, (31.0, 60.0, 48.0)),
    "圆形搭桥+-+D90.3mf": ({1: 1}, {1: "#FF0000"}, 0, 0, (90.0, 90.0, 10.2)),
}

NAMES = sorted(EXPECTED)
UNREPAIRABLE = {"Nick+Stress+test+v2.3mf", "Nick+Stress+test+v2 (1).3mf"}


def test_every_example_has_an_expectation_and_the_other_way_round():
    assert sorted(path.name for path in EXAMPLES.glob("*.3mf")) == NAMES


@pytest.fixture(scope="module")
def results():
    return {name: read_file(str(EXAMPLES / name)) for name in NAMES}


@pytest.mark.parametrize("name", NAMES)
def test_reading_gives_the_bodies_filaments_and_colours_bambu_shows(results, name):
    filaments, colours, helpers, painted, size = EXPECTED[name]
    result = results[name]
    assert Counter(part.filament for part in result.parts) == Counter(filaments)
    assert {part.filament: part.colour for part in result.parts} == colours
    assert (result.skipped_helpers, result.painted_parts) == (helpers, painted)
    assert model.size(result.parts) == pytest.approx(size, abs=0.01)
    assert all(part.triangles and part.vertices for part in result.parts)


def _volumes(parts) -> dict[int, float]:
    totals: dict[int, float] = {}
    for part in parts:
        totals[part.filament] = totals.get(part.filament, 0.0) + abs(model.signed_volume(part))
    return totals


@pytest.mark.parametrize("name", NAMES)
def test_import_then_export_keeps_bodies_filaments_volumes_and_size(results, name, tmp_path):
    parts = results[name].parts
    session = Session()
    for index, part in enumerate(parts):
        session.assign(part.filament, [Body(f"k{index}", part.name, 1, (0, 0, 0), part)])
    target = tmp_path / "zurueck.3mf"
    write_3mf(str(target), session.parts())
    back = read_3mf(str(target))
    assert Counter(part.filament for part in back) == Counter(part.filament for part in parts)
    before, after = _volumes(parts), _volumes(back)
    assert after.keys() == before.keys()
    for filament, volume in before.items():
        assert after[filament] == pytest.approx(volume, rel=1e-4), f"Filament {filament}"
    assert model.size(back) == pytest.approx(model.size(parts), abs=0.01)


def test_separate_puzzle_pieces_stay_separate_objects(results):
    groups = model.grouped_for_objects(results["3D+PUZZLE.3mf"].parts)
    assert len(groups) > 1


def _sliver_count(part) -> int:
    return sum(model._sliver_middle(tuple(part.vertices[i] for i in t), model.SLIVER_TOLERANCE_MM) is not None
               for t in part.triangles)


def test_zero_area_triangles_go_without_opening_the_mesh_or_changing_the_volume(results):
    # 8_Colors_AMS_Test: Dreiecke mit drei Ecken auf einer Linie - Allplan lehnte diese Koerper ab (live 2026-11-07)
    parts = [model.merge_vertices(p) for p in results["8_Colors_AMS_Test.3mf"].parts]
    assert sum(_sliver_count(p) for p in parts) > 0
    for part in parts:
        clean = model.drop_slivers(part)
        assert _sliver_count(clean) == 0
        assert model.is_closed(clean)
        assert abs(model.signed_volume(clean)) == pytest.approx(abs(model.signed_volume(part)), rel=1e-9)


@pytest.mark.parametrize("name", NAMES)
def test_repair_for_allplan_closes_every_piece_and_keeps_the_volume(results, name):
    # Allplan nimmt nur geschlossene Netze ohne Beruehrkanten an (live 2026-11-07: torture test, Gitterpyramide)
    pieces = [shell for part in results[name].parts for shell in model.repaired_shells(part)]
    if name in UNREPAIRABLE:
        # Kanten mit 1, 3, 5 oder 11 Dreiecken und verkehrt liegende Dreiecke: nach Allplans Regeln nicht zu
        # schliessen - kommt als Flaechenkoerper an. Wird es repariert, diese Ausnahme streichen.
        assert not all(model.is_closed(piece) for piece in pieces)
        return
    assert all(model.is_closed(piece) for piece in pieces)
    if name.startswith("Stella"):
        return                       # sieben Sterne durchdringen sich - getrennt zaehlt der gemeinsame Raum doppelt
    before = sum(abs(model.signed_volume(model.merge_vertices(part))) for part in results[name].parts)
    after = sum(abs(model.signed_volume(piece)) for piece in pieces)
    assert after == pytest.approx(before, rel=1e-3)


def test_bodies_that_touch_along_an_edge_get_their_own_points():
    # zwei Wuerfel, die sich nur entlang einer Kante beruehren: dort treffen sich vier Dreiecke
    touching = model.combined([box(0, 0, 0, 1, 1, 1), box(1, 1, 0, 1, 1, 1)])
    merged = model.merge_vertices(touching)
    assert not model.is_closed(merged)
    split = model.split_nonmanifold(merged)
    assert model.is_closed(split) and len(split.vertices) == len(merged.vertices) + 2
    assert [model.is_closed(shell) for shell in model.split_shells(split)] == [True, True]


def test_a_missing_triangle_is_filled_and_inner_faces_vanish():
    cube = model.merge_vertices(box(0, 0, 0, 2, 2, 2))
    holed = model.replace(cube, triangles=cube.triangles[1:])
    assert not model.is_closed(holed)
    assert model.is_closed(model.fill_holes(holed))
    inner = model.replace(cube, triangles=cube.triangles + (cube.triangles[0], tuple(reversed(cube.triangles[0]))))
    assert model.drop_duplicate_faces(inner).triangles == cube.triangles


def test_face_edges_in_any_order_become_outer_ring_and_hole():
    outer = [(0, 0, 0), (4, 0, 0), (4, 4, 0), (0, 4, 0)]
    hole = [(1, 1, 0), (1, 3, 0), (3, 3, 0), (3, 1, 0)]
    segments = [(ring[i], ring[(i + 1) % 4]) for ring in (outer, hole) for i in range(4)]
    shuffled = [segments[i] for i in (5, 0, 7, 2, 1, 6, 3, 4)]   # wie Allplan sie bei Puzzle-Umrissen liefert
    rings = model.chain_rings(shuffled, 1e-3)
    assert sorted(len(ring) for ring in rings) == [4, 4]
    assert {frozenset(ring) for ring in rings} == {frozenset(outer), frozenset(hole)}


def test_rings_become_outer_with_holes_and_an_island_in_a_hole_stays_its_own_piece():
    outer = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]                 # gegen den Uhrzeigersinn
    hole = [(2, 2, 0), (2, 8, 0), (8, 8, 0), (8, 2, 0)]                     # im Uhrzeigersinn
    island = [(4, 4, 0), (6, 4, 0), (6, 6, 0), (4, 6, 0)]
    regions = model.face_regions([island, hole, outer])
    assert sorted((len(o), len(h)) for o, h in regions) == [(4, 0), (4, 1)]
    assert next(h for o, h in regions if o == outer) == [hole]


def test_a_hole_touching_the_outline_is_spliced_in_and_triangulates():
    import threemf_geom
    outer = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0), (0, 5, 0)]
    hole = [(0, 5, 0), (3, 6, 0), (3, 4, 0)]                                # beruehrt den Rand bei (0, 5)
    spliced, rest = model.splice_touching_holes(outer, [hole], 1e-3)
    assert rest == [] and len(spliced) == len(outer) + len(hole)
    points, triangles = threemf_geom.triangulate(spliced, rest)
    area = sum(abs((points[b][0] - points[a][0]) * (points[c][1] - points[a][1])
                   - (points[b][1] - points[a][1]) * (points[c][0] - points[a][0])) / 2 for a, b, c in triangles)
    assert area == pytest.approx(100.0 - 3.0)


def test_filament_colours_find_a_close_allplan_colour():
    palette = {1: (0, 0, 0), 4: (0, 255, 0), 6: (255, 0, 0), 7: (0, 0, 255), 16: (45, 45, 45), 9: (240, 240, 180)}
    assert model.nearest_colour(model.hex_rgb("#F72323"), palette) == 6
    assert model.nearest_colour(model.hex_rgb("#161616"), palette) in (1, 16)
    assert model.nearest_colour(model.hex_rgb("#0ACC38"), palette) == 4
    assert model.hex_rgb("kaputt") is None
