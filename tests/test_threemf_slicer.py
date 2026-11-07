"""Der Weg zum Slicer ohne Allplan und ohne Slicer: Einstellung speichern/laden, Programm pruefen, oeffnen.

Gestartet wird hier nichts - `start` und `launch` sind Attrappen. Dass Windows die Datei wirklich in Bambu Studio
oeffnet, belegt nur der Klick in Allplan.
"""

import json

import threemf_slicer as slicer


def written(tmp_path, name="modell.3mf"):
    path = tmp_path / name
    path.write_bytes(b"PK")
    return str(path)


def test_settings_default_to_windows_when_the_file_is_missing_or_broken(tmp_path):
    assert slicer.load(str(tmp_path / "fehlt.json")) == dict(slicer.DEFAULTS)
    broken = tmp_path / "kaputt.json"
    broken.write_text("{ nicht json", encoding="utf-8")
    assert slicer.load(str(broken)) == dict(slicer.DEFAULTS)
    odd = tmp_path / "falsch.json"
    odd.write_text(json.dumps({"slicer": 7}), encoding="utf-8")
    assert slicer.load(str(odd)) == dict(slicer.DEFAULTS)


def test_settings_survive_save_and_load_and_leave_no_half_file(tmp_path):
    path = str(tmp_path / "3MFStudio" / "einstellungen.json")
    slicer.save({"slicer": r"C:\Programme\Orca Slicer\orca-slicer.exe"}, path)
    assert slicer.load(path) == dict(slicer.DEFAULTS, slicer=r"C:\Programme\Orca Slicer\orca-slicer.exe")
    assert [entry.name for entry in (tmp_path / "3MFStudio").iterdir()] == ["einstellungen.json"]


def test_settings_live_per_windows_user():
    assert slicer.settings_path(r"C:\Users\x\AppData\Roaming").endswith(r"Roaming\3MFStudio\einstellungen.json")


def test_only_an_existing_program_is_accepted(tmp_path):
    program = tmp_path / "slicer.exe"
    program.write_bytes(b"MZ")
    assert slicer.check_program(str(program)) == ""
    assert "(.exe)" in slicer.check_program(str(tmp_path / "liesmich.txt"))
    assert "gibt es nicht" in slicer.check_program(str(tmp_path / "weg.exe"))


def test_labels_and_tips():
    assert slicer.program_label("") == "Windows-Standard für 3MF-Dateien"
    assert slicer.program_label(r"C:\Program Files\Bambu Studio\bambu-studio.exe") == "bambu-studio"
    assert "Zuerst" in slicer.open_tip("", "")
    assert "modell.3mf" in slicer.open_tip(r"C:\Druck\modell.3mf", "")
    assert "orca-slicer" in slicer.open_tip(r"C:\Druck\modell.3mf", r"C:\x\orca-slicer.exe")


def test_without_a_written_file_nothing_starts(tmp_path):
    started = []
    assert slicer.open_in_slicer("", "", started.append, started.append) == "Noch keine 3MF-Datei geschrieben."
    gone = str(tmp_path / "weg.3mf")
    assert slicer.open_in_slicer(gone, "", started.append, started.append).startswith("Die Datei gibt es nicht mehr")
    assert started == []


def test_without_a_chosen_program_windows_opens_the_file(tmp_path):
    path, started = written(tmp_path), []
    assert slicer.open_in_slicer(path, "", started.append) == ""
    assert started == [path]


def test_without_any_slicer_on_the_pc_there_is_a_message_not_an_error(tmp_path):
    path = written(tmp_path)

    def no_program(_path):
        raise OSError(1155, "Keine Anwendung zugeordnet")
    message = slicer.open_in_slicer(path, "", no_program)
    assert "kein Programm eingerichtet" in message and path in message


def test_a_chosen_program_gets_the_file_as_argument_without_a_shell(tmp_path):
    path = written(tmp_path)
    program = tmp_path / "slicer.exe"
    program.write_bytes(b"MZ")
    calls = []
    assert slicer.open_in_slicer(path, str(program), launch=lambda args, **options: calls.append((args, options))) == ""
    assert calls == [([str(program), path], {"close_fds": True})]


def test_a_chosen_program_that_vanished_says_where_to_fix_it(tmp_path):
    path = written(tmp_path)
    message = slicer.open_in_slicer(path, str(tmp_path / "weg.exe"), launch=lambda *a, **k: None)
    assert "gibt es nicht" in message and "Windows-Standard" in message


def test_module_has_no_allplan_import():
    source = open(slicer.__file__, encoding="utf-8").read()
    assert "NemAll_Python" not in source
