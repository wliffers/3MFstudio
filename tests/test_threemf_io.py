"""Schreiber, Leser und Netz-Modell - ohne Allplan."""

import os
import xml.etree.ElementTree as ET
import zipfile

import pytest

import threemf_model as model
from shapes import box
from threemf_model import Part, ThreeMfError
from threemf_reader import read_3mf
from threemf_writer import write_3mf

BAMBU_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "bambu_02_09_01_70_zwei_teile.3mf")
CORE = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"


def extent(part, axis):
    values = [vertex[axis] for vertex in part.vertices]
    return max(values) - min(values)


# ---------------------------------------------------------------------- Netz-Modell

def test_volume_sign_tells_inside_from_outside():
    assert model.signed_volume(box(0, 0, 0, 20, 20, 20)) == pytest.approx(8000.0)
    assert model.signed_volume(box(0, 0, 0, 20, 20, 20, inward=True)) == pytest.approx(-8000.0)


def test_orient_outward_turns_an_allplan_body_and_leaves_a_good_one():
    turned = model.orient_outward(box(0, 0, 0, 40, 20, 10, inward=True))
    assert model.signed_volume(turned) == pytest.approx(8000.0)
    good = box(0, 0, 0, 40, 20, 10)
    assert model.orient_outward(good) is good


def test_closed_mesh_is_recognised_and_an_open_one_too():
    cube = box(0, 0, 0, 1, 1, 1)
    assert model.is_closed(cube)
    assert not model.is_closed(Part("offen", 1, cube.vertices, cube.triangles[:-1]))


def test_merge_vertices_joins_equal_points_and_drops_degenerate_triangles():
    cube = box(0, 0, 0, 1, 1, 1)
    doubled = Part("doppelt", 1, cube.vertices + cube.vertices,
                   tuple((a + 8, b + 8, c) for a, b, c in cube.triangles) + ((0, 8, 1),))
    merged = model.merge_vertices(doubled)
    assert len(merged.vertices) == 8
    assert len(merged.triangles) == 12
    assert model.is_closed(merged)


def test_scaled_reduces_and_rejects_nonsense():
    small = model.scaled([box(0, 0, 0, 1000, 1000, 1000)], 100)[0]
    assert model.size([small]) == pytest.approx((10.0, 10.0, 10.0))
    with pytest.raises(ValueError):
        model.scaled([box(0, 0, 0, 1, 1, 1)], 0)


def test_placed_on_plate_stands_on_zero_in_the_plate_centre():
    low, high = model.bounding_box(model.placed_on_plate([box(500000, 500000, 37, 40, 20, 10)]))
    assert low[2] == pytest.approx(0.0)
    assert ((low[0] + high[0]) / 2, (low[1] + high[1]) / 2) == pytest.approx((128.0, 128.0))


def test_build_volume_check():
    assert model.fits_build_volume([box(0, 0, 0, 256, 256, 256)])
    assert not model.fits_build_volume([box(0, 0, 0, 256.1, 10, 10)])


def test_overlap_order_puts_the_small_body_last_and_keeps_ties_in_input_order():
    base, inlay = box(0, 0, 0, 40, 20, 10, "Grundkoerper"), box(10, 7, 5, 20, 6, 5, "Einlage", inward=True)
    twin_a, twin_b = box(0, 0, 0, 5, 5, 5, "A"), box(9, 0, 0, 5, 5, 5, "B")
    assert [p.name for p in model.ordered_for_overlap([inlay, base])] == ["Grundkoerper", "Einlage"]
    assert [p.name for p in model.ordered_for_overlap([twin_a, twin_b])] == ["A", "B"]
    assert [p.name for p in model.ordered_for_overlap([twin_b, twin_a])] == ["B", "A"]


# ---------------------------------------------------------------------- Schreiber

def test_written_file_comes_back_unchanged(tmp_path):
    parts = [box(0, 0, 0, 40, 20, 10, "Grundkörper", 1), box(10, 7, 5, 20, 6, 5, "Text", 2)]
    target = tmp_path / "modell.3mf"
    write_3mf(str(target), parts)
    back = read_3mf(str(target))
    assert [(p.name, p.filament) for p in back] == [("Grundkörper", 1), ("Text", 2)]
    for original, read in zip(parts, back):
        assert read.triangles == original.triangles
        assert len(read.vertices) == len(original.vertices)
        for got, want in zip(read.vertices, original.vertices):
            assert got == pytest.approx(want)


def _extruders(config) -> list[list[str]]:
    return [[m.get("value") for part in obj.findall("part") for m in part.findall("metadata") if m.get("key") == "extruder"]
            for obj in config.findall("object")]


def test_bodies_inside_each_other_are_one_object_with_a_part_per_body_and_no_colour_or_project_data(tmp_path):
    target = tmp_path / "modell.3mf"
    write_3mf(str(target), [box(0, 0, 0, 4, 4, 4, "A", 1), box(1, 1, 1, 1, 1, 5, "B", 3)])
    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())
        root = ET.fromstring(archive.read("3D/3dmodel.model"))
        config = ET.fromstring(archive.read("Metadata/model_settings.config"))
        text = archive.read("3D/3dmodel.model").decode("utf-8")
    assert names == {"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model", "Metadata/model_settings.config"}
    assert [item.get("objectid") for item in root.iterfind(f"{CORE}build/{CORE}item")] == ["3"]
    assert _extruders(config) == [["1", "3"]]
    assert "basematerials" not in text and "colorgroup" not in text
    assert ">BambuStudio-" not in text


def test_bodies_with_a_gap_become_separate_objects_and_touching_ones_stay_together(tmp_path):
    target = tmp_path / "puzzle.3mf"
    # A und B liegen aufeinander (Schichten) - C hat Abstand
    parts = [box(0, 0, 0, 1, 1, 1, "A", 1), box(0, 0, 1, 1, 1, 1, "B", 2), box(5, 0, 0, 1, 1, 1, "C", 2)]
    write_3mf(str(target), parts)
    with zipfile.ZipFile(target) as archive:
        root = ET.fromstring(archive.read("3D/3dmodel.model"))
        config = ET.fromstring(archive.read("Metadata/model_settings.config"))
    assert [item.get("objectid") for item in root.iterfind(f"{CORE}build/{CORE}item")] == ["4", "5"]
    assert _extruders(config) == [["1", "2"], ["2"]]
    assert [(p.name, p.filament) for p in read_3mf(str(target))] == [("A", 1), ("B", 2), ("C", 2)]


def test_names_with_special_characters_survive(tmp_path):
    name = 'Schild "Eingang" & <Maß>'
    target = tmp_path / "namen.3mf"
    write_3mf(str(target), [box(0, 0, 0, 1, 1, 1, name, 2)], object_name='Modell "A" & B')
    assert read_3mf(str(target))[0].name == name


def test_writer_refuses_what_cannot_be_printed(tmp_path):
    target = str(tmp_path / "x.3mf")
    cube = box(0, 0, 0, 1, 1, 1)
    with pytest.raises(ThreeMfError):
        write_3mf(target, [])
    with pytest.raises(ThreeMfError):
        write_3mf(target, [Part("leer", 1, cube.vertices, ())])
    with pytest.raises(ThreeMfError):
        write_3mf(target, [Part("ohne Filament", 0, cube.vertices, cube.triangles)])
    with pytest.raises(ThreeMfError):
        write_3mf(target, [Part("kaputt", 1, cube.vertices[:4], cube.triangles)])
    assert os.listdir(tmp_path) == []


def test_writer_replaces_an_existing_file_and_leaves_no_temporary_file(tmp_path):
    target = tmp_path / "modell.3mf"
    target.write_text("alt")
    write_3mf(str(target), [box(0, 0, 0, 1, 1, 1)])
    assert os.listdir(tmp_path) == ["modell.3mf"]
    assert zipfile.is_zipfile(target)


# ---------------------------------------------------------------------- Leser

def test_reads_a_project_file_written_by_bambu_studio():
    parts = read_3mf(BAMBU_FILE)
    assert [(p.name, p.filament) for p in parts] == [("Grundkörper", 1), ("Text", 2)]
    for part in parts:
        assert [extent(part, axis) for axis in range(3)] == pytest.approx([20.0, 20.0, 20.0])
        assert model.signed_volume(part) == pytest.approx(8000.0)
    left = min(v[0] for v in parts[0].vertices)
    right = min(v[0] for v in parts[1].vertices)
    assert right - left == pytest.approx(30.0)


def _archive(tmp_path, model_xml, name="fremd.3mf"):
    target = tmp_path / name
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("3D/3dmodel.model", model_xml)
    return str(target)


TETRAHEDRON = ('<vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/>'
               '<vertex x="0" y="0" z="1"/></vertices><triangles><triangle v1="0" v2="2" v3="1"/>'
               '<triangle v1="0" v2="1" v3="3"/><triangle v1="1" v2="2" v3="3"/><triangle v1="2" v2="0" v3="3"/></triangles>')
NS = 'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"'


def test_reads_a_plain_standard_file_and_converts_inches(tmp_path):
    path = _archive(tmp_path, f'<model unit="inch" {NS}><resources><object id="1" name="Keil" type="model">'
                              f'<mesh>{TETRAHEDRON}</mesh></object></resources>'
                              '<build><item objectid="1"/></build></model>')
    part = read_3mf(path)[0]
    assert (part.name, part.filament) == ("Keil", 1)
    assert extent(part, 0) == pytest.approx(25.4)


def test_placement_of_components_and_items_is_applied(tmp_path):
    path = _archive(tmp_path, f'<model unit="millimeter" {NS}><resources>'
                              f'<object id="1" type="model"><mesh>{TETRAHEDRON}</mesh></object>'
                              '<object id="2" type="model"><components>'
                              '<component objectid="1" transform="2 0 0 0 2 0 0 0 2 10 0 0"/></components></object>'
                              '</resources><build><item objectid="2" transform="1 0 0 0 1 0 0 0 1 0 100 0"/></build></model>')
    part = read_3mf(path)[0]
    assert min(v[0] for v in part.vertices) == pytest.approx(10.0)
    assert min(v[1] for v in part.vertices) == pytest.approx(100.0)
    assert extent(part, 2) == pytest.approx(2.0)
    assert part.name == "Teil 1"


def test_mirrored_placement_keeps_the_outside_outside(tmp_path):
    path = _archive(tmp_path, f'<model {NS}><resources><object id="1" type="model"><mesh>{TETRAHEDRON}</mesh></object>'
                              '</resources><build><item objectid="1" transform="-1 0 0 0 1 0 0 0 1 0 0 0"/></build></model>')
    assert model.signed_volume(read_3mf(path)[0]) > 0.0


def test_reader_explains_broken_files(tmp_path):
    no_zip = tmp_path / "kein.3mf"
    no_zip.write_text("kein Archiv")
    with pytest.raises(ThreeMfError):
        read_3mf(str(no_zip))
    with pytest.raises(ThreeMfError):
        read_3mf(_archive(tmp_path, f'<model {NS}><resources/><build/></model>', "leer.3mf"))
    with pytest.raises(ThreeMfError):
        read_3mf(_archive(tmp_path, f'<model {NS}><resources/><build><item objectid="7"/></build></model>', "verweis.3mf"))
