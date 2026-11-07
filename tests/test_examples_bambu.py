"""Gegenprobe mit dem echten Bambu Studio: liest es die zurueckgeschriebenen Beispiele so, wie wir sie schreiben?

Je Beispiel: lesen -> zuordnen wie nach dem Import -> schreiben -> Bambu Studio baut daraus ueber seine
Kommandozeile ein Projekt mit den Originalfarben (threemf_bambu, ohne Fenster). Geprueft wird Bambus Ergebnis:
Filament je Teil und die Farbliste. Ohne Bambu Studio werden die Tests uebersprungen - das heisst "nicht
geprueft", nie "in Ordnung". Dauer: etwa 1-5 s je Datei.
"""

import json
import os
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import pytest

import threemf_bambu as bambu
from threemf_reader import read_file
from threemf_session import Body, Session
from threemf_writer import write_3mf

PROGRAM = os.environ.get("BAMBU_STUDIO_EXE", r"C:\Program Files\Bambu Studio\bambu-studio.exe")
EXAMPLES = Path(__file__).resolve().parents[1] / "input" / "examples"
NAMES = sorted(path.name for path in EXAMPLES.glob("*.3mf"))

pytestmark = pytest.mark.skipif(not os.path.isfile(PROGRAM), reason="Bambu Studio nicht installiert - nicht geprueft")


def _bambu_filaments(project: str) -> Counter:
    """Filament je Teil, wie Bambu es in sein Projekt schreibt; ein Teil ohne eigene Angabe erbt vom Objekt."""
    with zipfile.ZipFile(project) as archive:
        config = ET.fromstring(archive.read("Metadata/model_settings.config"))
    found = Counter()
    for obj in config.findall("object"):
        own = {m.get("key"): m.get("value") for m in obj.findall("metadata")}
        for part in obj.findall("part"):
            meta = {m.get("key"): m.get("value") for m in part.findall("metadata")}
            value = meta.get("extruder") or own.get("extruder") or "1"
            found[int(value) if value != "0" else int(own.get("extruder") or 1)] += 1
    return found


@pytest.mark.parametrize("name", NAMES)
def test_bambu_reads_our_file_with_every_filament_and_colour(name, tmp_path):
    parts = read_file(str(EXAMPLES / name)).parts
    session = Session()
    for index, part in enumerate(parts):
        session.assign(part.filament, [Body(f"k{index}", part.name, 1, (0, 0, 0), part)])
    written = tmp_path / "zurueck.3mf"
    write_3mf(str(written), session.parts())
    colours = {part.filament: part.colour for part in parts}
    project = tmp_path / "projekt.3mf"
    assert bambu.coloured_project(PROGRAM, str(written), colours, str(project)) == ""
    assert _bambu_filaments(str(project)) == Counter(part.filament for part in parts)
    with zipfile.ZipFile(project) as archive:
        settings = json.loads(archive.read("Metadata/project_settings.config"))
    assert settings["filament_colour"] == bambu.colour_list(colours)


def test_bambu_takes_the_chosen_type_of_each_filament(tmp_path):
    """Gewaehlte Sorte je Filament -> Bambus Projekt traegt Material, Profil und Kennung (gemessen 2026-11-07)."""
    from shapes import box
    from threemf_session import Choice
    written = tmp_path / "sorten.3mf"
    write_3mf(str(written), [box(0, 0, 0, 20, 20, 20, "A", 1), box(30, 0, 0, 20, 20, 20, "B", 2),
                             box(60, 0, 0, 20, 20, 20, "C", 3)])
    choices = {1: Choice("#00AE42", "Grün", "Bambu Lab", "PETG HF", "PETG", "GFG02"),
               2: Choice("#0078BF", "Marineblau", "Bambu Lab", "PLA Matte", "PLA", "GFA01"),
               3: Choice("#FF6A13", "Orange", "Polymaker", "PolyLite ASA", "ASA")}
    colours = {number: choice.hex for number, choice in choices.items()}
    project = tmp_path / "projekt.3mf"
    # ohne Bambu-Einstellungen (appdata leer): Drucker bleibt offen, Filamente in der A1-Fassung
    assert bambu.coloured_project(PROGRAM, str(written), colours, str(project), choices=choices,
                                  appdata=str(tmp_path)) == ""
    with zipfile.ZipFile(project) as archive:
        settings = json.loads(archive.read("Metadata/project_settings.config"))
    assert settings["filament_colour"] == ["#00AE42", "#0078BF", "#FF6A13"]
    assert settings["filament_type"] == ["PETG", "PLA", "ASA"]
    assert settings["filament_settings_id"] == ["Bambu PETG HF @BBL A1", "Bambu PLA Matte @BBL A1", "Generic ASA @BBL A1"]
    assert settings["filament_ids"][:2] == ["GFG02", "GFA01"]
    assert not settings.get("printer_model")                      # offen: Bambu Studio nimmt seinen aktuellen Drucker


def test_bambu_project_carries_the_printer_set_in_bambu_studio(tmp_path):
    """Mit Bambus echten Einstellungen traegt das Projekt dessen Drucker und dazu passende Profile (2026-11-07)."""
    from shapes import box
    from threemf_session import Choice
    machine, process, _slots = bambu.printer_for(PROGRAM)
    if not machine:
        pytest.skip("in Bambu Studio ist kein Drucker eingestellt - nicht geprueft")
    written = tmp_path / "drucker.3mf"
    write_3mf(str(written), [box(0, 0, 0, 20, 20, 20, "A", 1), box(30, 0, 0, 20, 20, 20, "B", 2)])
    choices = {2: Choice("#00AE42", "Gruen", "Bambu Lab", "PETG HF", "PETG", "GFG02")}
    project = tmp_path / "projekt.3mf"
    assert bambu.coloured_project(PROGRAM, str(written), {1: "#FFFFFF", 2: "#00AE42"}, str(project),
                                  choices=choices) == ""
    with zipfile.ZipFile(project) as archive:
        settings = json.loads(archive.read("Metadata/project_settings.config"))
    assert settings["printer_settings_id"] == machine and settings["print_settings_id"] == process
    assert settings["filament_type"][1] == "PETG"
    folder = os.path.join(bambu.profile_root(PROGRAM), "filament")
    for name in settings["filament_settings_id"]:
        assert machine in bambu.resolve_profile(folder, name)["compatible_printers"]
