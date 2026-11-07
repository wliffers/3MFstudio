"""Farbliste: mitgelieferter Stand, Bambus eigene Liste, Reihenfolge der Hersteller, Bauskript."""

import gzip
import json
import os
import sys

import threemf_filaments as filaments

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import build_filaments  # noqa: E402


def _bambu_file(folder, entries):
    path = folder / "BambuStudio" / "system" / "BBL" / "filament" / filaments.BAMBU_COLOUR_FILE
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"data": entries, "total": len(entries)}), encoding="utf-8")
    return path


def _bundled(tmp_path, brands):
    path = tmp_path / "liste.json.gz"
    path.write_bytes(gzip.compress(json.dumps({"version": "2026.11.07", "brands": brands}).encode("utf-8")))
    return str(path)


def test_the_shipped_list_is_there_and_bambu_lab_comes_first(tmp_path, monkeypatch):
    monkeypatch.setattr(filaments, "DEFAULT_BAMBU_PROGRAM_DIR", str(tmp_path / "kein_bambu"))
    catalogue = filaments.catalogue("de", appdata="", bundled=filaments.BUNDLED_FILE, program="")
    brands = catalogue.brands()
    assert len(brands) > 100 and catalogue.count() > 10000
    assert brands[0] == filaments.BAMBU_BRAND
    assert brands[1:] == sorted(brands[1:], key=str.casefold)
    basic = catalogue.line(filaments.BAMBU_BRAND, "PLA Basic")
    assert basic is not None and basic.material == "PLA" and len(basic.swatches) > 10
    assert all(swatch.hex.startswith("#") and len(swatch.hex) == 7 for swatch in basic.swatches)


def test_the_licence_of_the_shipped_list_goes_with_it():
    licence = os.path.join(os.path.dirname(filaments.BUNDLED_FILE), "LICENSE_OpenFilamentDatabase.txt")
    with open(licence, encoding="utf-8") as handle:
        text = handle.read()
    assert "Permission is hereby granted" in text and "Open Filament" in text


def test_bambu_studio_replaces_the_bambu_lab_entries_with_names_in_the_users_language(tmp_path, monkeypatch):
    monkeypatch.setattr(filaments, "DEFAULT_BAMBU_PROGRAM_DIR", str(tmp_path / "kein_bambu"))
    bundled = _bundled(tmp_path, [["Bambu Lab", [["PLA Basic", "PLA", [["Jade White", "#FFFFFF"]]]]],
                                  ["eSUN", [["PLA+", "PLA", [["Fire Red", "#C0392B"]]]]]])
    _bambu_file(tmp_path, [
        {"fila_id": "GFA00", "fila_type": "PLA Basic", "fila_color": ["#FFFFFFFF"],
         "fila_color_name": {"en": "Jade White", "de": "Jadeweiß"}},
        {"fila_id": "GFA00", "fila_type": "PLA Basic", "fila_color": ["#9CDBD9FF", "#FFFFFFFF"],
         "fila_color_name": {"en": "Arctic Whisper", "de": ""}},
        {"fila_id": "GFG02", "fila_type": "PETG HF", "fila_color": ["#00AE42FF"], "fila_color_name": {"en": "Green"}},
        {"fila_id": "GFX", "fila_type": "", "fila_color": ["#000000FF"], "fila_color_name": {"en": "ohne Sorte"}},
    ])
    catalogue = filaments.catalogue("de", program="", materials={"GFG02": "PETG"}, bundled=bundled,
                                    appdata=str(tmp_path))
    assert catalogue.bambu_file and catalogue.brands() == ["Bambu Lab", "eSUN"]
    basic = catalogue.line("Bambu Lab", "PLA Basic")
    assert basic.code == "GFA00"
    assert [(s.name, s.hex, s.more) for s in basic.swatches] == [("Arctic Whisper", "#9CDBD9", ("#FFFFFF",)),
                                                                  ("Jadeweiß", "#FFFFFF", ())]
    assert catalogue.line("Bambu Lab", "PETG HF").material == "PETG"
    assert catalogue.line("eSUN", "PLA+").swatches[0].hex == "#C0392B"


def test_without_bambu_studio_and_without_the_shipped_list_nothing_breaks(tmp_path, monkeypatch):
    monkeypatch.setattr(filaments, "DEFAULT_BAMBU_PROGRAM_DIR", str(tmp_path / "kein_bambu"))
    catalogue = filaments.catalogue("de", program="", bundled=str(tmp_path / "fehlt.json.gz"), appdata=str(tmp_path))
    assert catalogue.brands() == [] and catalogue.count() == 0 and catalogue.bambu_file == ""


def test_colour_values_are_normalised():
    assert filaments.normal_hex("#00ae42ff") == "#00AE42"
    assert filaments.normal_hex("00AE42") == "#00AE42"
    assert filaments.normal_hex("#00AE4") == "" and filaments.normal_hex("grün") == ""


def test_the_build_script_keeps_only_current_colours_and_merges_double_lines():
    data = {"version": "1", "brands": [{"id": "b%d" % index, "name": "Marke %d" % index}
                                        for index in range(build_filaments.MIN_BRANDS)],
            "filaments": [{"id": "f1", "brand_id": "b1", "name": "PLA", "material": "PLA"},
                          {"id": "f2", "brand_id": "b1", "name": "PLA", "material": "PLA"},
                          {"id": "f3", "brand_id": "b2", "name": "Alt", "material": "PLA", "discontinued": True}],
            "variants": [{"filament_id": "f1", "name": "Rot", "color_hex": "#ff0000"},
                         {"filament_id": "f2", "name": "Blau", "color_hex": "0000FF", "color_hexes": ["#0000FF", "#FFFFFF"]},
                         {"filament_id": "f1", "name": "Weg", "color_hex": "#123456", "discontinued": True},
                         {"filament_id": "f3", "name": "Grün", "color_hex": "#00FF00"}]}
    reduced = build_filaments.reduce(data)
    assert reduced["brands"] == [["Marke 1", [["PLA", "PLA", [["Blau", "#0000FF", "#FFFFFF"], ["Rot", "#FF0000"]]]]]]
