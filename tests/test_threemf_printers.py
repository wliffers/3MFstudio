"""Druckerliste und Druckplatte: Lage, Bauraum-Kanten, eigene Masse, Einstellungen - ohne Allplan."""

import pytest

import threemf_printers as printers
import threemf_slicer as slicer
import threemf_window as window
from threemf_model import ThreeMfError

A1 = printers.Printer("Bambu Lab A1", "Bambu Lab", 256.0, 256.0, 256.0)


def test_the_shipped_list_has_bambu_lab_first_and_the_a1():
    found = printers.load()
    assert len(found) > 80
    assert found[0].brand == "Bambu Lab"
    brands = [printer.brand for printer in found if printer.brand != "Bambu Lab"]
    assert brands == sorted(brands, key=str.casefold)
    assert printers.find(found, "Bambu Lab A1") == A1
    assert printers.find(found, "Bambu Lab A1 mini").width == 180.0
    assert printers.find(found, "gibt es nicht") is None


def test_the_plate_is_1_mm_thick_with_its_top_at_zero_and_centred():
    corner, size = printers.plate_box(A1)
    assert corner == (-128.0, -128.0, -1.0) and size == (256.0, 256.0, 1.0)
    assert corner[2] + size[2] == 0.0                              # Oberseite genau auf Z = 0


def test_the_build_volume_is_twelve_edges_from_zero_to_the_build_height():
    lines = printers.volume_lines(printers.Printer("H2D", "Bambu Lab", 350.0, 320.0, 325.0))
    assert len(lines) == 6
    bottom, top = lines[0], lines[1]
    assert len(bottom) == 5 and bottom[0] == bottom[-1] and {point[2] for point in bottom} == {0.0}
    assert {point[2] for point in top} == {325.0}
    assert {(x, y) for x, y, _z in bottom} == {(-175.0, -160.0), (175.0, -160.0), (175.0, 160.0), (-175.0, 160.0)}
    edges = sum(len(line) - 1 for line in lines)
    assert edges == 12


def test_custom_sizes_accept_commas_and_refuse_nonsense():
    assert printers.custom("200,5", "180", 150) == printers.Printer("", "", 200.5, 180.0, 150.0)
    with pytest.raises(ThreeMfError):
        printers.custom("abc", "180", "150")
    with pytest.raises(ThreeMfError):
        printers.custom("0", "180", "150")
    with pytest.raises(ThreeMfError):
        printers.custom("200", "180", "99999")


def test_the_plate_choice_is_kept_in_the_settings(tmp_path):
    path = str(tmp_path / "einstellungen.json")
    settings = slicer.load(path)
    assert settings["drucker"] == "Bambu Lab A1" and settings["bauraum"] is True
    settings.update(drucker="", bauraum=False, eigene_masse=[300.0, 300.0, 400.0])
    slicer.save(settings, path)
    again = slicer.load(path)
    assert (again["drucker"], again["bauraum"], again["eigene_masse"]) == ("", False, [300.0, 300.0, 400.0])


def test_the_settings_panel_has_the_build_plate():
    xaml = window.build_xaml()
    for name in ("PlatePrinter", "PlateCustom", "PlateWidth", "PlateDepth", "PlateHeight", "PlateVolume", "PlatePlace",
                 "UniversalCheck", "FileKind"):
        assert 'x:Name="%s"' % name in xaml
