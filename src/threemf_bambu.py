"""Farben und Sorten nach Bambu Studio - ueber dessen Kommandozeile, ohne Fenster. Reines Python, kein Allplan.

Eine fremde 3MF-Datei bringt in Bambu nur Form, Teilnamen und Filamentnummer mit; Farben und Sorten verwirft
Bambu (G1, spike_g1/ERGEBNIS.md). Bambu Studio selbst kann aber aus unserer Datei ein eigenes Projekt bauen,
mit Farbe und Sorte je Filament - gemessen 2026-11-07 mit Bambu Studio 02.09.01.70: 16 Farben in 1,5 s, jede
Farbe und jede Filamentnummer wie geschrieben (tests/test_examples_bambu.py).

Das ist eine ZUGABE: ohne Bambu Studio (oder wenn es scheitert) bleibt die gewoehnliche Datei, nichts bricht.
Bambus Profile liegen in der Installation nur als Teilstuecke vor (inherits/include); die Kommandozeile
verlangt vollstaendige Dateien, deshalb werden sie hier zusammengesetzt.

Drucker (Wunsch 2026-11-07): das Projekt nimmt den Drucker, der in Bambu Studio gerade eingestellt ist
(BambuStudio.conf, Schluessel presets.machine), und dazu dessen Druckprofil und die Filamentprofile, die
laut ihrem Feld `compatible_printers` zu ihm passen. Ist kein Drucker zu finden, bleibt er im Projekt OFFEN
(gemessen: ohne --load-settings traegt das Projekt Sorten und Farben, printer_model leer) - Bambu Studio
nimmt dann seinen aktuellen. Je Filament laedt das Projekt das Profil der gewaehlten Sorte
(`filament_profile`): Bambus Profil ueber die Filament-Kennung, sonst "Generic <Material>", ohne Wahl das
Filament, das in Bambu in diesem Fach steckt, sonst PLA Basic.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile

LOG = logging.getLogger("threemfstudio.part")

CONFIG_FOLDER = "BambuStudio"               # Bambus Einstellungen je Windows-Benutzer unter %APPDATA%
CONFIG_FILE = "BambuStudio.conf"            # JSON, dahinter eine Pruefsummenzeile ("# MD5 checksum ...")
USER_PRESETS = "user"                       # eigene (geaenderte) Profile des Anwenders: user/<Konto>/<Art>/
PROCESS_STEM = "0.20mm Standard"            # Bambus Standard-Druckprofil, gibt es fuer jeden Drucker
PLA_STEM = "Bambu PLA Basic"
FALLBACK_SUFFIX = " @BBL A1"                # Filamentprofile, wenn der Drucker offen bleibt (A1-Fassung)
FALLBACK_FILAMENT = PLA_STEM + FALLBACK_SUFFIX
BASE_SUFFIX = " @base"
INHERIT_DEPTH = 4                           # so weit folgt system_machine einem eigenen Profil zu seinem Vorbild
TIMEOUT_S = 120
DEFAULT_COLOUR = "#808080"
PROJECT_NAME = "projekt.3mf"


def is_bambu(program: str) -> bool:
    return os.path.basename(program).lower().startswith("bambu-studio")


def profile_root(program: str) -> str:
    return os.path.join(os.path.dirname(program), "resources", "profiles", "BBL")


def resolve_profile(folder: str, name: str, seen: tuple[str, ...] = ()) -> dict:
    """Profil samt aller Eltern (inherits) und Bausteine (include) zu einer vollstaendigen Datei."""
    if name in seen:
        raise ValueError(f"Bambu-Profil verweist im Kreis auf sich selbst: {name}")
    with open(os.path.join(folder, name + ".json"), encoding="utf-8") as handle:
        data = json.load(handle)
    merged: dict = {}
    for parent in [data.get("inherits")] + list(data.get("include", [])):
        if parent:
            merged.update(resolve_profile(folder, parent, seen + (name,)))
    merged.update(data)
    merged.pop("include", None)
    return merged


# ---------------------------------------------------------------------------------------------- Bambus Einstellungen

def config_path(appdata: str | None = None) -> str:
    base = appdata if appdata is not None else os.environ.get("APPDATA", "")
    return os.path.join(base, CONFIG_FOLDER, CONFIG_FILE)


def current_presets(appdata: str | None = None) -> dict:
    """Drucker, Druckprofil und Filamente, die in Bambu Studio gerade eingestellt sind.

    Rueckgabe {"machine": Name, "process": Name, "filaments": [Name je Fach]}; leer, wenn die Datei fehlt oder
    unlesbar ist. Hinter dem JSON steht Bambus Pruefsumme, deshalb raw_decode statt json.load."""
    path = config_path(appdata)
    try:
        with open(path, encoding="utf-8") as handle:
            data, _end = json.JSONDecoder().raw_decode(handle.read().lstrip())
    except (OSError, ValueError) as exc:
        LOG.info("Bambu-Einstellungen nicht lesbar (%s): %s", path, exc)
        return {}
    presets = data.get("presets") if isinstance(data, dict) else None
    if not isinstance(presets, dict):
        return {}
    filaments = presets.get("filaments")
    return {"machine": str(presets.get("machine") or ""),
            "process": str(presets.get("process") or ""),
            "filaments": [str(name) for name in filaments] if isinstance(filaments, list) else []}


def user_roots(appdata: str | None = None) -> list[str]:
    """Die Ordner mit eigenen Profilen des Anwenders (user/<Konto>/)."""
    base = os.path.join(os.path.dirname(config_path(appdata)), USER_PRESETS)
    try:
        return sorted(os.path.join(base, name) for name in os.listdir(base)
                      if os.path.isdir(os.path.join(base, name)))
    except OSError:
        return []


def system_machine(root: str, name: str, appdata: str | None = None, depth: int = INHERIT_DEPTH) -> str:
    """Bambus Systemprofil zu diesem Druckernamen: der Name selbst, wenn es ihn als Datei gibt; bei einem
    eigenen Profil des Anwenders das Systemprofil, von dem es erbt; "" wenn nichts passt."""
    if not name:
        return ""
    if os.path.isfile(os.path.join(root, "machine", name + ".json")):
        return name
    for user_root in user_roots(appdata):
        path = os.path.join(user_root, "machine", name + ".json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                parent = str(json.load(handle).get("inherits") or "")
        except (OSError, ValueError) as exc:
            LOG.info("Eigenes Bambu-Druckerprofil %s nicht lesbar: %s", path, exc)
            return ""
        return system_machine(root, parent, appdata, depth - 1) if depth > 0 else ""
    LOG.info("Bambu-Drucker %s hat kein Profil in %s", name, root)
    return ""


def compatible(folder: str, stem: str, machine: str) -> str:
    """Das Profil "<stem> @..." aus diesem Ordner, das laut compatible_printers zu diesem Drucker passt.

    Bevorzugt die Fassung mit Duesenangabe ("... 0.4 nozzle"), sonst die erste passende; "" wenn keine passt.
    Ein unlesbares Profil wird uebergangen."""
    try:
        names = [name[:-len(".json")] for name in os.listdir(folder)
                 if name.startswith(stem + " @") and name.endswith(".json")]
    except OSError as exc:
        LOG.warning("Bambu-Profile nicht lesbar (%s): %s", folder, exc)
        return ""
    for name in sorted(names, key=lambda candidate: (" nozzle" not in candidate, candidate)):
        try:
            printers = resolve_profile(folder, name).get("compatible_printers") or []
        except (OSError, ValueError) as exc:
            LOG.info("Bambu-Profil %s uebergangen: %s", name, exc)
            continue
        if machine in printers:
            return name
    return ""


def process_for(root: str, machine: str, preferred: str = "") -> str:
    """Das Druckprofil zum Drucker: das in Bambu eingestellte, wenn es ein Systemprofil fuer diesen Drucker
    ist, sonst "0.20mm Standard" fuer ihn; "" wenn es keins gibt."""
    folder = os.path.join(root, "process")
    if preferred and os.path.isfile(os.path.join(folder, preferred + ".json")):
        try:
            if machine in (resolve_profile(folder, preferred).get("compatible_printers") or []):
                return preferred
        except (OSError, ValueError) as exc:
            LOG.info("Bambu-Druckprofil %s uebergangen: %s", preferred, exc)
    return compatible(folder, PROCESS_STEM, machine)


def printer_for(program: str, appdata: str | None = None) -> tuple[str, str, list[str]]:
    """Was das Projekt ueber den Drucker weiss: (Druckerprofil, Druckprofil, Filament je Fach) aus Bambus
    Einstellungen; Drucker und Druckprofil leer, wenn der Drucker offen bleiben muss."""
    presets = current_presets(appdata)
    root = profile_root(program)
    machine = system_machine(root, presets.get("machine", ""), appdata)
    process = process_for(root, machine, presets.get("process", "")) if machine else ""
    if machine and not process:
        LOG.info("Kein Druckprofil fuer %s - der Drucker bleibt im Projekt offen", machine)
        machine = ""
    return machine, process, presets.get("filaments", [])


def current_machine(program: str, appdata: str | None = None) -> str:
    """Nur der Drucker, fuer die Anzeige im Fenster: "" wenn er offen bleiben wird."""
    return system_machine(profile_root(program), current_presets(appdata).get("machine", ""), appdata)


# ---------------------------------------------------------------------------------------------- Filamentprofile

def base_profiles(folder: str) -> dict[str, tuple[str, str]]:
    """Bambus Grundprofile ("<Name> @base") -> {Filament-Kennung: (Name ohne " @base", Material)}.

    Ueber die Kennung (GFA00 ...) haengt Bambus Farbliste an ihrem Profil; das Material ("PLA", "PETG-CF")
    steht im Profil oder in seinen Eltern. Ein unlesbares Profil wird uebergangen (Protokoll)."""
    found: dict[str, tuple[str, str]] = {}
    try:
        names = sorted(name for name in os.listdir(folder) if name.endswith(BASE_SUFFIX + ".json"))
    except OSError as exc:
        LOG.warning("Bambu-Profile nicht lesbar (%s): %s", folder, exc)
        return found
    for name in names:
        stem = name[:-len(".json")]
        try:
            data = resolve_profile(folder, stem)
        except (OSError, ValueError) as exc:
            LOG.info("Bambu-Profil %s uebergangen: %s", stem, exc)
            continue
        code = str(data.get("filament_id") or "").strip()
        kind = data.get("filament_type")
        kind = kind[0] if isinstance(kind, list) and kind else kind
        if code:
            found[code] = (stem[:-len(BASE_SUFFIX)], str(kind or "").strip())
    return found


def _variant(folder: str, stem: str, machine: str) -> str:
    """Die Fassung eines Filamentprofils fuer den Drucker; ohne Drucker die A1-Fassung, wenn es sie gibt."""
    if machine:
        return compatible(folder, stem, machine)
    name = stem + FALLBACK_SUFFIX
    return name if os.path.isfile(os.path.join(folder, name + ".json")) else ""


def filament_profile(folder: str, choice=None, bases: dict[str, tuple[str, str]] | None = None,
                     machine: str = "", default: str = "") -> str:
    """Das Bambu-Filamentprofil fuer eine gewaehlte Sorte (Felder code/brand/line/material, oder None).

    Reihenfolge: Bambus Profil ueber die Kennung, "Bambu <Sorte>", "Generic <Material>" (auch ohne Zusatz
    hinter "-": PETG-CF -> PETG) - jeweils in der Fassung fuer den Drucker. Ohne Wahl `default` (das Filament
    in Bambus Fach), wenn es das Profil gibt, sonst PLA Basic. Genommen wird nur, was als Datei da ist."""
    stems = []
    if choice is not None:
        code, brand = getattr(choice, "code", ""), getattr(choice, "brand", "")
        line, material = getattr(choice, "line", ""), getattr(choice, "material", "")
        if code and bases and code in bases:
            stems.append(bases[code][0])
        if brand == "Bambu Lab" and line:
            stems.append("Bambu " + line)
        if material:
            stems.append("Generic " + material)
            stems.append("Generic " + material.split("-")[0])
        for stem in stems:
            name = _variant(folder, stem, machine)
            if name:
                return name
    if default and os.path.isfile(os.path.join(folder, default + ".json")):
        return default
    return _variant(folder, PLA_STEM, machine) or FALLBACK_FILAMENT


def profile_list(program: str, slots: int, choices: dict | None = None, machine: str = "",
                 defaults: list[str] | tuple[str, ...] = ()) -> list[str]:
    """Filamentprofil je Filament 1..slots. `defaults` sind Bambus Faecher (Fach 1 zuerst)."""
    folder = os.path.join(profile_root(program), "filament")
    chosen = {number: choice for number, choice in (choices or {}).items() if choice is not None}
    bases = base_profiles(folder) if any(getattr(choice, "code", "") for choice in chosen.values()) else {}
    return [filament_profile(folder, chosen.get(number), bases, machine,
                             defaults[number - 1] if number <= len(defaults) else "")
            for number in range(1, slots + 1)]


# ---------------------------------------------------------------------------------------------- Projekt bauen

def write_profiles(program: str, target: str, filaments: list[str] | None = None, machine: str = "",
                   process: str = "") -> dict:
    """Vollstaendige Profile in den Arbeitsordner: Drucker und Druckprofil (nur wenn benannt) und je
    verschiedenem Filamentprofil eine Datei. Rueckgabe: {"machine": Pfad, "process": Pfad,
    "filament": {Profilname: Pfad}} - Drucker und Druckprofil fehlen, wenn der Drucker offen bleibt."""
    root = profile_root(program)
    paths: dict = {"filament": {}}
    for kind, name in (("machine", machine), ("process", process)):
        if not name:
            continue
        paths[kind] = os.path.join(target, kind + ".json")
        with open(paths[kind], "w", encoding="utf-8") as handle:
            json.dump(resolve_profile(os.path.join(root, kind), name), handle, ensure_ascii=False)
    for index, name in enumerate(dict.fromkeys(filaments or [FALLBACK_FILAMENT])):
        path = os.path.join(target, "filament_%d.json" % (index + 1))
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(resolve_profile(os.path.join(root, "filament"), name), handle, ensure_ascii=False)
        paths["filament"][name] = path
    return paths


def colour_list(colours: dict[int, str]) -> list[str]:
    """Farbe je Filament 1..hoechste Nummer; Luecken bekommen Grau (Bambu braucht je Filament eine Farbe)."""
    highest = max(colours) if colours else 1
    return [colours.get(number) or DEFAULT_COLOUR for number in range(1, highest + 1)]


def project_command(program: str, profiles: dict, filaments: list[str], colours: list[str], source: str,
                    out_dir: str) -> list[str]:
    """Bambus Kommandozeile: Drucker und Druckprofil (wenn bekannt), je Filament sein Profil und seine Farbe,
    kein Slicen, nur das Projekt."""
    command = [program]
    if profiles.get("machine") and profiles.get("process"):
        command += ["--load-settings", profiles["machine"] + ";" + profiles["process"]]
    return command + ["--load-filaments", ";".join(profiles["filament"][name] for name in filaments),
                      "--filament-colour", ";".join(colours),
                      "--outputdir", out_dir, "--export-3mf", PROJECT_NAME, source]


def coloured_project(program: str, source: str, colours: dict[int, str], target: str, run=None,
                     choices: dict | None = None, appdata: str | None = None) -> str:
    """Laesst Bambu Studio aus `source` ein Projekt mit diesen Filamentfarben bauen und legt es als `target` ab.

    `target` darf `source` sein - Bambu hat die Datei dann schon gelesen, bevor sie ersetzt wird; scheitert
    Bambu, bleibt `source` unangetastet. `choices` ist die gewaehlte Sorte je Filament (threemf_session.Choice
    oder None). Rueckgabe: leer bei Erfolg, sonst der Grund (fuer das Protokoll - der Anwender behaelt dann
    die gewoehnliche Datei). `run` ersetzt subprocess.run, `appdata` den Ort von Bambus Einstellungen (Test).
    """
    if not is_bambu(program) or not os.path.isfile(program):
        return "kein Bambu Studio"
    work = tempfile.mkdtemp(prefix="3mfstudio_")
    try:
        tones = colour_list(colours)
        machine, process, defaults = printer_for(program, appdata)
        filaments = profile_list(program, len(tones), choices, machine, defaults)
        LOG.info("Bambu-Projekt: Drucker %s, Druckprofil %s, Filamente %s", machine or "offen", process or "-",
                 filaments)
        profiles = write_profiles(program, work, filaments, machine, process)
        command = project_command(program, profiles, filaments, tones, source, work)
        code = (run or subprocess.run)(command, cwd=work, timeout=TIMEOUT_S, check=False).returncode
        built = os.path.join(work, PROJECT_NAME)
        if code != 0 or not os.path.isfile(built):
            return f"Bambu Studio meldet {code}"
        shutil.copyfile(built, target)              # ueberschreibt auch source; Laufwerke duerfen verschieden sein
        return ""
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        LOG.warning("Bambu-Projekt gescheitert: %s", exc)
        return str(exc)
    finally:
        shutil.rmtree(work, ignore_errors=True)
