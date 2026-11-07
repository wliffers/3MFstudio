"""Der Weg der Farben nach Bambu Studio ohne Bambu: Befehl, Farbliste, Rueckfall. Der echte Lauf: test_examples_bambu.py."""

import json
import os
import types

import threemf_bambu as bambu
from shapes import box
from threemf_session import Body, Choice, Session, names_from_parts


def test_only_bambu_studio_gets_the_coloured_project():
    assert bambu.is_bambu(r"C:\Program Files\Bambu Studio\bambu-studio.exe")
    assert not bambu.is_bambu(r"C:\Program Files\OrcaSlicer\orca-slicer.exe")
    assert not bambu.is_bambu("")


def test_colour_list_has_one_colour_per_filament_and_fills_gaps():
    assert bambu.colour_list({1: "#FF0000", 3: "#0000FF"}) == ["#FF0000", bambu.DEFAULT_COLOUR, "#0000FF"]
    assert bambu.colour_list({}) == [bambu.DEFAULT_COLOUR]


def test_command_loads_one_filament_profile_per_colour_without_slicing():
    profiles = {"machine": "m", "process": "p", "filament": {"PLA": "f1", "PETG": "f2"}}
    command = bambu.project_command("bambu-studio.exe", profiles, ["PLA", "PETG"], ["#FF0000", "#00FF00"], "in.3mf",
                                    "aus")
    assert command[command.index("--load-filaments") + 1] == "f1;f2"
    assert command[command.index("--filament-colour") + 1] == "#FF0000;#00FF00"
    assert "--slice" not in command and command[-1] == "in.3mf"


def test_without_bambu_nothing_runs_and_the_reason_is_given(tmp_path):
    calls = []
    assert bambu.coloured_project(str(tmp_path / "orca.exe"), "x.3mf", {1: "#FF0000"}, "y.3mf",
                                  run=lambda *a, **k: calls.append(a)) == "kein Bambu Studio"
    assert calls == []


def test_a_failing_bambu_run_leaves_no_project(tmp_path, monkeypatch):
    program = tmp_path / "bambu-studio.exe"
    program.write_bytes(b"MZ")
    monkeypatch.setattr(bambu, "write_profiles", lambda _program, _target, names, machine="", process="": {
        "filament": {name: "f" for name in names}})
    target = tmp_path / "projekt.3mf"
    reason = bambu.coloured_project(str(program), "x.3mf", {1: "#FF0000"}, str(target), appdata=str(tmp_path),
                                    run=lambda *a, **k: types.SimpleNamespace(returncode=3))
    assert reason == "Bambu Studio meldet 3" and not target.exists()


def test_filament_colours_are_the_most_frequent_body_colour():
    session = Session()
    session.assign(1, [Body("a", "a", 6, (255, 0, 0), box(0, 0, 0, 1, 1, 1)),
                       Body("b", "b", 6, (255, 0, 0), box(2, 0, 0, 1, 1, 1)),
                       Body("c", "c", 7, (0, 0, 255), box(4, 0, 0, 1, 1, 1))])
    session.assign(3, [Body("d", "d", 4, (0, 255, 0), box(6, 0, 0, 1, 1, 1))])
    assert session.filament_colours() == {1: "#FF0000", 3: "#00FF00"}


def test_names_of_our_own_files_come_back():
    parts = [box(0, 0, 0, 1, 1, 1, "Grundkörper", 1), box(0, 0, 0, 1, 1, 1, "Text 1", 2),
             box(0, 0, 0, 1, 1, 1, "Text 2", 2), box(0, 0, 0, 1, 1, 1, "Filament 3", 3),
             box(0, 0, 0, 1, 1, 1, "Sockel", 4), box(0, 0, 0, 1, 1, 1, "Deckel", 4)]
    assert names_from_parts(parts) == {1: "Grundkörper", 2: "Text"}


def _profiles(tmp_path, *names):
    folder = tmp_path / "resources" / "profiles" / "BBL" / "filament"
    folder.mkdir(parents=True)
    for name in names:
        (folder / (name + ".json")).write_text("{}", encoding="utf-8")
    return folder


def test_the_profile_follows_the_chosen_type_and_falls_back_step_by_step(tmp_path):
    folder = _profiles(tmp_path, "Bambu PETG HF @BBL A1", "Bambu PLA Matte @BBL A1", "Generic ASA @BBL A1",
                       "Generic PETG @BBL A1", bambu.FALLBACK_FILAMENT)
    bases = {"GFG02": ("Bambu PETG HF", "PETG")}
    pick = lambda **values: Choice("#000000", **values)
    assert bambu.filament_profile(str(folder), pick(code="GFG02"), bases) == "Bambu PETG HF @BBL A1"
    assert bambu.filament_profile(str(folder), pick(brand="Bambu Lab", line="PLA Matte")) == "Bambu PLA Matte @BBL A1"
    assert bambu.filament_profile(str(folder), pick(brand="Polymaker", line="PolyLite ASA", material="ASA"))         == "Generic ASA @BBL A1"
    assert bambu.filament_profile(str(folder), pick(material="PETG-CF")) == "Generic PETG @BBL A1"
    assert bambu.filament_profile(str(folder), pick(material="PEEK")) == bambu.FALLBACK_FILAMENT
    assert bambu.filament_profile(str(folder), None) == bambu.FALLBACK_FILAMENT


def test_base_profiles_link_the_bambu_id_to_profile_name_and_material(tmp_path):
    folder = tmp_path / "filament"
    folder.mkdir()
    (folder / "fdm_filament_pet.json").write_text('{"filament_type": ["PETG"]}', encoding="utf-8")
    (folder / "Bambu PETG HF @base.json").write_text('{"inherits": "fdm_filament_pet", "filament_id": "GFG02"}',
                                                     encoding="utf-8")
    (folder / "Kaputt @base.json").write_text("{", encoding="utf-8")
    assert bambu.base_profiles(str(folder)) == {"GFG02": ("Bambu PETG HF", "PETG")}
    assert bambu.base_profiles(str(tmp_path / "fehlt")) == {}


def test_one_profile_per_filament_unchosen_ones_stay_pla_basic(tmp_path):
    program = tmp_path / "bambu-studio.exe"
    _profiles(tmp_path, "Bambu PLA Matte @BBL A1", bambu.FALLBACK_FILAMENT)
    choices = {2: Choice("#0078BF", "Marineblau", "Bambu Lab", "PLA Matte", "PLA")}
    assert bambu.profile_list(str(program), 3, choices) == [bambu.FALLBACK_FILAMENT, "Bambu PLA Matte @BBL A1", bambu.FALLBACK_FILAMENT]


def test_the_command_leaves_the_printer_open_without_machine_and_process():
    command = bambu.project_command("bambu-studio.exe", {"filament": {"PLA": "f1"}}, ["PLA"], ["#FF0000"], "in.3mf",
                                    "aus")
    assert "--load-settings" not in command and command[command.index("--load-filaments") + 1] == "f1"


def _bambu_config(tmp_path, machine="Bambu Lab X2D 0.4 nozzle", process="0.20mm Standard @BBL X2D", filaments=()):
    folder = tmp_path / "BambuStudio"
    folder.mkdir(exist_ok=True)
    text = json.dumps({"presets": {"machine": machine, "process": process, "filaments": list(filaments)}})
    (folder / "BambuStudio.conf").write_text(text + "\n# MD5 checksum 00\n", encoding="utf-8")
    return str(tmp_path)


def _system_profiles(tmp_path):
    """Eine kleine Bambu-Installation: X2D- und A1-Drucker, Druckprofile, Filamente mit compatible_printers."""
    root = tmp_path / "resources" / "profiles" / "BBL"
    files = {
        "machine/Bambu Lab X2D 0.4 nozzle": {"printer_model": "Bambu Lab X2D"},
        "machine/Bambu Lab A1 0.4 nozzle": {"printer_model": "Bambu Lab A1"},
        "process/0.20mm Standard @BBL X2D": {"compatible_printers": ["Bambu Lab X2D 0.4 nozzle"]},
        "process/0.08mm Fein @BBL X2D": {"compatible_printers": ["Bambu Lab X2D 0.4 nozzle"]},
        "process/0.20mm Standard @BBL A1": {"compatible_printers": ["Bambu Lab A1 0.4 nozzle"]},
        "filament/fdm_pla": {"filament_type": ["PLA"], "compatible_printers": []},
        "filament/Bambu PLA Basic @BBL X2D": {"inherits": "fdm_pla", "compatible_printers": ["Bambu Lab X2D 0.6 nozzle"]},
        "filament/Bambu PLA Basic @BBL X2D 0.4 nozzle": {"inherits": "fdm_pla",
                                                         "compatible_printers": ["Bambu Lab X2D 0.4 nozzle"]},
        "filament/Bambu PLA Basic @BBL A1": {"inherits": "fdm_pla", "compatible_printers": ["Bambu Lab A1 0.4 nozzle"]},
        "filament/Bambu PETG HF @BBL X2D 0.4 nozzle": {"compatible_printers": ["Bambu Lab X2D 0.4 nozzle"]},
        "filament/Bambu PETG HF @BBL A1": {"compatible_printers": ["Bambu Lab A1 0.4 nozzle"]},
        "filament/Generic ASA @BBL X2D 0.4 nozzle": {"compatible_printers": ["Bambu Lab X2D 0.4 nozzle"]},
        "filament/Bambu PETG Basic @BBL X2D 0.4 nozzle": {"compatible_printers": ["Bambu Lab X2D 0.4 nozzle"]},
    }
    for name, data in files.items():
        path = root / (name + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    program = tmp_path / "bambu-studio.exe"
    program.write_bytes(b"MZ")
    return str(program), str(root)


def test_bambus_settings_name_printer_process_and_filaments(tmp_path):
    appdata = _bambu_config(tmp_path, filaments=["Bambu PETG Basic @BBL X2D 0.4 nozzle"])
    assert bambu.current_presets(appdata) == {"machine": "Bambu Lab X2D 0.4 nozzle",
                                              "process": "0.20mm Standard @BBL X2D",
                                              "filaments": ["Bambu PETG Basic @BBL X2D 0.4 nozzle"]}
    assert bambu.current_presets(str(tmp_path / "leer")) == {}
    (tmp_path / "BambuStudio" / "BambuStudio.conf").write_text("{kaputt", encoding="utf-8")
    assert bambu.current_presets(appdata) == {}


def test_compatible_profile_is_found_by_its_printer_list_nozzle_variant_first(tmp_path):
    _program, root = _system_profiles(tmp_path)
    filament = os.path.join(root, "filament")
    assert bambu.compatible(filament, "Bambu PLA Basic", "Bambu Lab X2D 0.4 nozzle") == "Bambu PLA Basic @BBL X2D 0.4 nozzle"
    assert bambu.compatible(filament, "Bambu PLA Basic", "Bambu Lab X2D 0.6 nozzle") == "Bambu PLA Basic @BBL X2D"
    assert bambu.compatible(filament, "Bambu PLA Basic", "Bambu Lab P1S 0.4 nozzle") == ""
    assert bambu.compatible(filament, "Bambu PLA", "Bambu Lab X2D 0.4 nozzle") == ""     # kein Praefix-Treffer
    assert bambu.process_for(root, "Bambu Lab X2D 0.4 nozzle", "0.08mm Fein @BBL X2D") == "0.08mm Fein @BBL X2D"
    assert bambu.process_for(root, "Bambu Lab X2D 0.4 nozzle", "0.20mm Standard @BBL A1") == "0.20mm Standard @BBL X2D"
    assert bambu.process_for(root, "Bambu Lab P1S 0.4 nozzle") == ""


def test_the_printer_comes_from_bambus_settings_or_stays_open(tmp_path):
    program, root = _system_profiles(tmp_path)
    appdata = _bambu_config(tmp_path, filaments=["Bambu PETG Basic @BBL X2D 0.4 nozzle", "fehlt"])
    assert bambu.printer_for(program, appdata) == ("Bambu Lab X2D 0.4 nozzle", "0.20mm Standard @BBL X2D",
                                                   ["Bambu PETG Basic @BBL X2D 0.4 nozzle", "fehlt"])
    assert bambu.current_machine(program, appdata) == "Bambu Lab X2D 0.4 nozzle"
    own = tmp_path / "BambuStudio" / "user" / "123" / "machine"           # eigenes Profil erbt vom Systemprofil
    own.mkdir(parents=True)
    (own / "Mein X2D.json").write_text('{"inherits": "Bambu Lab X2D 0.4 nozzle"}', encoding="utf-8")
    assert bambu.printer_for(program, _bambu_config(tmp_path, machine="Mein X2D"))[0] == "Bambu Lab X2D 0.4 nozzle"
    assert bambu.printer_for(program, _bambu_config(tmp_path, machine="Bambu Lab P1S 0.4 nozzle"))[:2] == ("", "")
    assert bambu.printer_for(program, str(tmp_path / "nichts")) == ("", "", [])
    assert bambu.system_machine(root, "", appdata) == ""


def test_filament_profiles_follow_the_printer_and_bambus_slots(tmp_path):
    program, _root = _system_profiles(tmp_path)
    machine = "Bambu Lab X2D 0.4 nozzle"
    choices = {1: Choice("#00AE42", "Gruen", "Bambu Lab", "PETG HF", "PETG", "GFG02"),
               3: Choice("#FF6A13", "Orange", "Polymaker", "PolyLite ASA", "ASA")}
    slots = ["Bambu PETG Basic @BBL X2D 0.4 nozzle", "Bambu PETG Basic @BBL X2D 0.4 nozzle", "x", "x"]
    assert bambu.profile_list(program, 4, choices, machine, slots) == [
        "Bambu PETG HF @BBL X2D 0.4 nozzle",         # gewaehlte Sorte schlaegt Bambus Fach
        "Bambu PETG Basic @BBL X2D 0.4 nozzle",      # ohne Wahl: was in Bambus Fach steckt
        "Generic ASA @BBL X2D 0.4 nozzle",
        "Bambu PLA Basic @BBL X2D 0.4 nozzle"]       # Fach unbekannt: PLA Basic fuer den Drucker
    assert bambu.profile_list(program, 2, choices, "", []) == ["Bambu PETG HF @BBL A1", bambu.FALLBACK_FILAMENT]
    paths = bambu.write_profiles(program, str(tmp_path), ["Bambu PLA Basic @BBL A1"])
    assert set(paths) == {"filament"}                                      # Drucker offen: kein machine/process
    paths = bambu.write_profiles(program, str(tmp_path), ["Bambu PLA Basic @BBL A1"], machine,
                                 "0.20mm Standard @BBL X2D")
    with open(paths["machine"], encoding="utf-8") as handle:
        assert json.load(handle)["printer_model"] == "Bambu Lab X2D"


def test_the_project_may_replace_its_own_source(tmp_path):
    program, _root = _system_profiles(tmp_path)
    source = tmp_path / "datei.3mf"
    source.write_bytes(b"neutral")
    seen = []

    def fake_run(command, cwd, timeout, check):
        seen.append(command)
        with open(os.path.join(cwd, bambu.PROJECT_NAME), "wb") as handle:
            handle.write(b"projekt")
        return types.SimpleNamespace(returncode=0)

    reason = bambu.coloured_project(program, str(source), {1: "#FF0000"}, str(source), run=fake_run,
                                    appdata=_bambu_config(tmp_path))
    assert reason == "" and source.read_bytes() == b"projekt"
    assert seen[0][-1] == str(source) and "--load-settings" in seen[0]
