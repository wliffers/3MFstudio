"""3MFStudio in eine Allplan-Installation kopieren.

Das Hauptskript 3MFStudio.py und dreizehn Hilfsmodule (threemf_*.py) samt Farb- und Druckerliste und Lizenztext landen in EINEM Part-Ordner unter
PythonPartsScripts; die Palette unter Library/3MFStudio.
Das Hauptskript laedt seine Hilfsmodule beim Modul-Load per importlib.reload neu (brain 2026-08-15);
nach einem Deploy Allplan trotzdem neu starten, wenn das Hauptskript schon geladen war (brain 2026-08-13).
Liegt daneben die Kopie des Plugin-Managers (PythonPartsScripts/<DEVELOPER_SLUG>/3MFStudio, aus dem .allep),
bekommt sie dieselben Skripte - Allplan startet das Part aus dem Ordner, dessen Palette angeklickt wird.

    python deploy.py            # nach Usr von Allplan 2027 (Standard)
    python deploy.py --check    # nur pruefen, nichts kopieren
    python deploy.py --force    # trotz laufendem Allplan

Die .pyp unter src/ behaelt den flachen Skriptnamen, damit der Head-less-Loop sie aus src/
laden kann; beim Kopieren wird <Name> auf den Unterordner umgeschrieben.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")

DEFAULT_VERSION = "2027"

PART_FOLDER = "3MFStudio"
MAIN_SCRIPT = "3MFStudio.py"
PYP_FILE = "3MFStudio.pyp"
LIBRARY_FOLDER = "3MFStudio"
DEVELOPER_SLUG = "willi_liffers"   # Unterordner, den der Plugin-Manager fuer das .allep anlegt (build_allep.py)

SCRIPTS = [
    MAIN_SCRIPT,
    "threemf_text.py",
    "threemf_geom.py",
    "threemf_model.py",
    "threemf_loft.py",
    "threemf_writer.py",
    "threemf_reader.py",
    "threemf_session.py",
    "threemf_allplan.py",
    "threemf_window.py",
    "threemf_slicer.py",
    "threemf_bambu.py",
    "threemf_filaments.py",
    "threemf_filaments.json.gz",               # Farbliste (build_filaments.py), Open Filament Database, MIT
    "LICENSE_OpenFilamentDatabase.txt",        # Lizenztext der Farbliste - muss mitgehen
    "threemf_printers.py",
    "threemf_printers.json",                   # Druckerliste (build_printers.py) - liegt ganz im PythonPart
]

#: Altlasten frueherer Deploys, die am Ziel entfernt werden (noch keine).
OBSOLETE = []

PACKAGE_INIT = '''\
"""Part-Package fuer Allplan - von deploy.py geschrieben, hier nicht editieren.

Macht den Ordner zu einem ECHTEN Package und re-exportiert das Part-Modul,
damit das Part auch laeuft, wenn Allplan nach dem flachen Skriptnamen fragt.
"""

# Der Modulname beginnt mit einer Ziffer - "from .3MFStudio import *" waere kein gueltiges Python.
import importlib as _importlib

_part = _importlib.import_module(".3MFStudio", __name__)
globals().update({name: value for name, value in vars(_part).items() if not name.startswith("_")})
'''


def usr_path(version):
    """Benutzerordner einer Allplan-Version."""

    return os.path.join(os.path.expanduser("~"), "Documents", "Nemetschek",
                        "Allplan", version, "Usr", "Local")


def _allplan_is_running():
    """Ein Deploy in eine laufende Sitzung kann still verloren gehen."""

    try:
        output = subprocess.run(["tasklist", "/NH", "/FO", "CSV"],
                                capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return False

    return any(line.lower().startswith('"allplan_') for line in output.splitlines())


def _install_pyp(library_dir):
    """Palette kopieren und ihren <Script><Name> auf den Unterordner zeigen lassen."""

    source = os.path.join(SRC, PYP_FILE)
    flat_tag = "<Name>%s</Name>" % MAIN_SCRIPT
    nested_tag = "<Name>%s\\%s</Name>" % (PART_FOLDER, MAIN_SCRIPT)

    with open(source, "r", encoding="utf-8") as handle:
        content = handle.read()

    if nested_tag not in content:
        if flat_tag not in content:
            raise SystemExit("Skriptpfad nicht patchbar: weder %s noch %s in %s"
                             % (flat_tag, nested_tag, source))

        content = content.replace(flat_tag, nested_tag, 1)

    os.makedirs(library_dir, exist_ok=True)

    with open(os.path.join(library_dir, PYP_FILE), "w", encoding="utf-8", newline="") as handle:
        handle.write(content)

    print("  %s  (Skriptpfad -> %s\\%s)" % (PYP_FILE, PART_FOLDER, MAIN_SCRIPT))

    # Allplans eigene Kopie der Palette - bleibt sie liegen, gewinnt sie.
    cache = os.path.join(library_dir, "___pyp__")

    if os.path.isfile(cache):
        os.remove(cache)
        print("  ___pyp__-Cache entfernt")


def _shadowing_scripts(scripts_dir):
    """Flache Altdateien, die den Part-Ordner verdecken wuerden."""

    return [name for name in SCRIPTS + OBSOLETE
            if os.path.isfile(os.path.join(scripts_dir, name))]


def _same_file(source, target):
    """Gleicher Inhalt? (Zeitstempel reichen nicht - copy2 setzt sie, der Plugin-Manager nicht.)"""

    if not os.path.isfile(target):
        return False

    with open(source, "rb") as first, open(target, "rb") as second:
        return first.read() == second.read()


def plugin_dir(scripts_dir):
    """Die Kopie, die der Plugin-Manager aus dem .allep angelegt hat; None, wenn es keine gibt.

    Allplan startet das Part aus dem Ordner, dessen Palette der Anwender anklickt - hat er das .allep
    installiert, ist das diese Kopie, nicht PART_FOLDER (gemessen 2026-11-07: Modul willi_liffers.3MFStudio).
    """

    folder = os.path.join(scripts_dir, DEVELOPER_SLUG, PART_FOLDER)

    return folder if os.path.isfile(os.path.join(folder, MAIN_SCRIPT)) else None


def _refresh_plugin_copy(folder):
    """Dieselben Skripte auch in die Plugin-Kopie legen - sonst laeuft dort der alte Stand weiter."""

    print("\nPlugin-Kopie -> %s" % folder)

    for name in SCRIPTS:
        shutil.copy2(os.path.join(SRC, name), os.path.join(folder, name))

    print("  %d Dateien erneuert (die __init__.py des Plugins bleibt)" % len(SCRIPTS))
    cache = os.path.join(folder, "__pycache__")

    if os.path.isdir(cache):
        shutil.rmtree(cache)
        print("  __pycache__ entfernt")

    print("  Hinweis: der Plugin-Manager zeigt weiter die Paketnummer des installierten .allep.")


def deploy(target_path, force=False):
    scripts_dir = os.path.join(target_path, "PythonPartsScripts")
    part_dir = os.path.join(scripts_dir, PART_FOLDER)
    library_dir = os.path.join(target_path, "Library", LIBRARY_FOLDER)

    if not os.path.isdir(scripts_dir):
        raise SystemExit("PythonPartsScripts nicht gefunden: %s" % scripts_dir)

    if not force and _allplan_is_running():
        raise SystemExit("Allplan laeuft - mit --force trotzdem deployen.")

    print("Ziel: %s" % target_path)
    print("\nSkripte -> %s" % part_dir)
    os.makedirs(part_dir, exist_ok=True)

    for name in SCRIPTS:
        source = os.path.join(SRC, name)

        if not os.path.isfile(source):
            raise SystemExit("Quelldatei fehlt: %s" % source)

        shutil.copy2(source, os.path.join(part_dir, name))
        print("  %s" % name)

    for name in OBSOLETE:
        stale = os.path.join(part_dir, name)

        if os.path.isfile(stale):
            os.remove(stale)
            print("  Altdatei entfernt: %s" % name)

    with open(os.path.join(part_dir, "__init__.py"), "w", encoding="utf-8", newline="") as handle:
        handle.write(PACKAGE_INIT)

    print("  __init__.py")

    cache = os.path.join(part_dir, "__pycache__")

    if os.path.isdir(cache):
        shutil.rmtree(cache)
        print("  __pycache__ entfernt")

    print("\nPalette -> %s" % library_dir)
    _install_pyp(library_dir)

    for name in _shadowing_scripts(scripts_dir):
        os.remove(os.path.join(scripts_dir, name))
        print("  flache Altdatei entfernt: %s" % name)

    if (plugin := plugin_dir(scripts_dir)):
        _refresh_plugin_copy(plugin)

    print("\nAllplan neu starten, falls das Part in dieser Sitzung schon lief.")

    return check(target_path)


def check(target_path):
    """Prueft, ob alles Noetige am Ziel liegt."""

    scripts_dir = os.path.join(target_path, "PythonPartsScripts")
    part_dir = os.path.join(scripts_dir, PART_FOLDER)
    pyp_path = os.path.join(target_path, "Library", LIBRARY_FOLDER, PYP_FILE)

    expected = [os.path.join(part_dir, name) for name in SCRIPTS]
    expected += [os.path.join(part_dir, "__init__.py"), pyp_path]

    print("\n--- Pruefung ---")
    missing = []

    for path in expected:
        present = os.path.exists(path)
        print("  %s  %s" % ("OK  " if present else "FEHLT", path))

        if not present:
            missing.append(path)

    nested_tag = "<Name>%s\\%s</Name>" % (PART_FOLDER, MAIN_SCRIPT)

    if os.path.isfile(pyp_path):
        with open(pyp_path, "r", encoding="utf-8") as handle:
            path_ok = nested_tag in handle.read()

        print("  %s  Skriptpfad ist %s" % ("OK  " if path_ok else "FALSCH", nested_tag))

        if not path_ok:
            missing.append("Skriptpfad in " + pyp_path)

    if (shadowing := _shadowing_scripts(scripts_dir)):
        print("  FALSCH  flache Altdateien: %s" % ", ".join(shadowing))
        missing.append("flache Altdateien in " + scripts_dir)

    if (plugin := plugin_dir(scripts_dir)):
        stale = [name for name in SCRIPTS
                 if not _same_file(os.path.join(SRC, name), os.path.join(plugin, name))]
        print("  %s  Plugin-Kopie %s%s" % ("OK  " if not stale else "ALT ", plugin,
                                          "" if not stale else " - veraltet: " + ", ".join(stale)))

        if stale:
            missing.append("veraltete Plugin-Kopie " + plugin)

    if missing:
        print("\n%d Problem(e) - das Part laeuft so nicht." % len(missing))

        return 1

    print("\nAlle %d benoetigten Dateien vorhanden." % len(expected))

    return 0


def main():
    parser = argparse.ArgumentParser(description="3MFStudio nach Allplan kopieren")
    parser.add_argument("--version", default=DEFAULT_VERSION,
                        help="Allplan-Version (Standard: %s)" % DEFAULT_VERSION)
    parser.add_argument("--usr-path", default=None, help="freier Zielordner")
    parser.add_argument("--check", action="store_true", help="nur pruefen")
    parser.add_argument("--force", action="store_true", help="deployen, obwohl Allplan laeuft")
    args = parser.parse_args()

    target = args.usr_path or usr_path(args.version)

    if args.check:
        return check(target)

    return deploy(target, args.force)


if __name__ == "__main__":
    sys.exit(main())
