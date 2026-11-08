# -*- coding: utf-8 -*-
"""3MFStudio als Allplan-Erweiterungspaket (.allep) bauen - zum Weitergeben an Kunden.

    python build_allep.py            # dist/3MFStudio-<VERSION>.allep und dist/3MFStudio_Installation.zip
    python build_allep.py --check    # nur pruefen, ob alles fuer den Bau da ist

Ein .allep ist ein ZIP mit install-config.yml in der Wurzel; der Plugin-Manager von Allplan installiert es,
wenn der Anwender die Datei ins Allplan-Fenster zieht (Aufbau am 2026-10-28 mit einem anderen Part frisch
installiert und geprueft). Die Programmdateien kommen aus deploy.SCRIPTS - Paket und Direkt-Deploy laufen so
nie auseinander.

Layout im Paket:

    install-config.yml
    Library/Willi Liffers/3MFStudio.pyp, 3MFStudio.png
    PythonPartsScripts/willi_liffers/3MFStudio/__init__.py, 3MFStudio.py, threemf_*.py
    PythonPartsActionbar/willi_liffers/3MFStudio_24.png, _24_dark.png, _128.png, _128_dark.png

Das Weitergabe-ZIP enthaelt das .allep, die Anleitung und dieselben Dateien unter Manuell/ (Installation von
Hand, falls der Plugin-Manager gesperrt ist).
"""

import argparse
import os
import re
import sys
import zipfile

import deploy

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = deploy.SRC
ASSETS = os.path.join(HERE, "assets")
DIST = os.path.join(HERE, "dist")
README = os.path.join(HERE, "LIESMICH_Installation.txt")

PLUGIN_NAME = "3MFStudio"
PLUGIN_UUID = "dd4d9405-17ab-4674-88e1-0f0dad922584"   # nie aendern - der Plugin-Manager erkennt Updates daran
#: Muss bei jeder Weitergabe steigen (SemVer), sonst bietet der Plugin-Manager kein Update an.
VERSION = "1.1.3"
#: Hersteller im Plugin-Manager und Bibliotheksordner (Entscheidung des Anwenders, 2026-11-07).
DEVELOPER = "Willi Liffers"
#: Python-taugliche Form fuer Programm- und Actionbar-Ordner (kein Leerzeichen in Modulpfaden).
DEVELOPER_SLUG = deploy.DEVELOPER_SLUG
MIN_ALLPLAN_VERSION = 2027

SCRIPTS_PREFIX = "PythonPartsScripts/%s/%s" % (DEVELOPER_SLUG, deploy.PART_FOLDER)
LIBRARY_PREFIX = "Library/%s" % DEVELOPER
ACTIONBAR_PREFIX = "PythonPartsActionbar/%s" % DEVELOPER_SLUG
ICON_NAMES = ["3MFStudio_24.png", "3MFStudio_24_dark.png", "3MFStudio_128.png", "3MFStudio_128_dark.png"]
LIBRARY_TILE = "3MFStudio.png"

#: Gueltige Wurzelordner bei target-location USR; andere ueberspringt der Plugin-Manager STILL (IfcQualityCheck).
VALID_ROOTS = {"library", "pythonpartsscripts", "pythonpartsactionbar", "reports", "visualscripts"}
#: Darf in den Dateien des Pakets nie stehen: Pfade dieses Rechners (Arbeitsordner, Profil des angemeldeten
#: Benutzers - der Name kommt aus der Umgebung, damit er nicht selbst im Code steht) und Schluessel.
FORBIDDEN_TEXT = [re.compile(pattern) for pattern in (
    r"(?i)c:[\\/]+sandbox", r"(?i)[\\/]users[\\/]+" + re.escape(os.environ.get("USERNAME", "") or "<kein Benutzer>"),
    r"github_pat_[A-Za-z0-9_]{20,}", r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{20,}")]
TEXT_SUFFIXES = (".py", ".pyp", ".txt", ".yml")

INSTALL_CONFIG = """\
# 3MFStudio - Allplan Extension Package (gebaut von build_allep.py, hier nicht bearbeiten)
plugin:
  name: {name}
  UUID: {uuid}
  version: {version}
  developer: '{developer}'
  default-language: de
  min-allplan-version: {min_version}

installation:
  target-location: USR

tools:
  - id: 3mf-studio
    pyp: '{library}\\3MFStudio.pyp'
    display-name:
      de: '3MFStudio - 3D-Druck'
      en: '3MFStudio - 3D printing'
    icons:
      small: '{actionbar}\\3MFStudio_24.png'
      large: '{actionbar}\\3MFStudio_128.png'

task-area:
  display-name:
    de: '3MFStudio'
    en: '3MFStudio'
  layout:
    - 3mf-studio
"""


class PackageError(Exception):
    """Pflichtdateien fehlen oder das Paket verletzt eine Regel - mit Klartext."""


def missing_sources() -> list:
    """Fehlende Pflichtdateien (leer = baubereit)."""
    missing = ["src/%s" % name for name in deploy.SCRIPTS + [deploy.PYP_FILE]
               if not os.path.isfile(os.path.join(SRC, name))]
    missing += ["assets/actionbar/%s" % name for name in ICON_NAMES
                if not os.path.isfile(os.path.join(ASSETS, "actionbar", name))]
    if not os.path.isfile(os.path.join(ASSETS, "library", LIBRARY_TILE)):
        missing.append("assets/library/%s" % LIBRARY_TILE)
    if not os.path.isfile(README):
        missing.append(os.path.basename(README))
    return missing


def rewrite_pyp(text: str) -> str:
    """<Name> der Palette auf den Programmordner im Paket umschreiben (nur in der ausgelieferten Kopie)."""
    flat = "<Name>%s</Name>" % deploy.MAIN_SCRIPT
    nested = "<Name>%s\\%s\\%s</Name>" % (DEVELOPER_SLUG, deploy.PART_FOLDER, deploy.MAIN_SCRIPT)
    if nested in text:
        return text
    if flat not in text:
        raise PackageError("Skriptpfad nicht ersetzbar: weder %s noch %s in %s" % (flat, nested, deploy.PYP_FILE))
    return text.replace(flat, nested, 1)


def _read(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def package_entries() -> dict:
    """Alle Dateien des Pakets ausser install-config.yml: {Pfad mit /: Bytes}."""
    missing = missing_sources()
    if missing:
        raise PackageError("Pflichtdateien fehlen:\n  " + "\n  ".join(missing))
    entries = {"%s/%s" % (SCRIPTS_PREFIX, name): _read(os.path.join(SRC, name)) for name in deploy.SCRIPTS}
    entries["%s/__init__.py" % SCRIPTS_PREFIX] = deploy.PACKAGE_INIT.encode("utf-8")
    pyp = _read(os.path.join(SRC, deploy.PYP_FILE)).decode("utf-8-sig")
    entries["%s/%s" % (LIBRARY_PREFIX, deploy.PYP_FILE)] = rewrite_pyp(pyp).encode("utf-8")
    entries["%s/%s" % (LIBRARY_PREFIX, LIBRARY_TILE)] = _read(os.path.join(ASSETS, "library", LIBRARY_TILE))
    for name in ICON_NAMES:
        entries["%s/%s" % (ACTIONBAR_PREFIX, name)] = _read(os.path.join(ASSETS, "actionbar", name))
    return entries


def install_config(version: str = VERSION) -> str:
    """install-config.yml als Text (von Hand formatiert, kein PyYAML noetig)."""
    return INSTALL_CONFIG.format(name=PLUGIN_NAME, uuid=PLUGIN_UUID, version=version, developer=DEVELOPER,
                                 min_version=MIN_ALLPLAN_VERSION, library=LIBRARY_PREFIX.replace("/", "\\"),
                                 actionbar=ACTIONBAR_PREFIX.replace("/", "\\"))


def zip_time(version: str) -> tuple:
    """ZIP-Zeit aus der Version: gleicher Inhalt ergibt dieselbe Datei, neue Version neue Dateizeit."""
    major, minor, patch = (int(part) for part in version.split("."))
    if major > 23 or minor > 59 or patch > 29:
        raise PackageError("Die Version %s passt nicht in die ZIP-Zeit (major <= 23, minor <= 59, patch <= 29)." % version)
    return (2026, 11, 7, major, minor, patch * 2)


def _write(archive: zipfile.ZipFile, name: str, data: bytes, stamp: tuple) -> None:
    info = zipfile.ZipInfo(name, date_time=stamp)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)


def build_allep(entries: dict, dist: str = DIST, version: str = VERSION) -> str:
    """dist/3MFStudio-<version>.allep schreiben -> Pfad."""
    os.makedirs(dist, exist_ok=True)
    target = os.path.join(dist, "%s-%s.allep" % (PLUGIN_NAME, version))
    temporary = target + ".tmp"
    stamp = zip_time(version)
    with zipfile.ZipFile(temporary, "w") as archive:
        _write(archive, "install-config.yml", install_config(version).encode("utf-8"), stamp)
        for name, data in sorted(entries.items()):
            _write(archive, name, data, stamp)
    os.replace(temporary, target)
    return target


def build_zip(entries: dict, allep_path: str, dist: str = DIST, version: str = VERSION) -> str:
    """Weitergabe-ZIP: Anleitung, das .allep und dieselben Dateien unter Manuell/ -> Pfad."""
    target = os.path.join(dist, "%s_Installation.zip" % PLUGIN_NAME)
    temporary = target + ".tmp"
    stamp = zip_time(version)
    with zipfile.ZipFile(temporary, "w") as archive:
        _write(archive, os.path.basename(README), _read(README), stamp)
        _write(archive, os.path.basename(allep_path), _read(allep_path), stamp)
        for name, data in sorted(entries.items()):
            if not name.startswith("PythonPartsActionbar/"):
                _write(archive, "Manuell/" + name, data, stamp)
    os.replace(temporary, target)
    return target


def verify_allep(path: str) -> list:
    """Regeln des Plugin-Managers und der Weitergabe gegen ein fertiges .allep -> Liste der Probleme."""
    problems = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "install-config.yml" not in names:
            return ["install-config.yml fehlt in der Wurzel"]
        config = archive.read("install-config.yml").decode("utf-8")
        name_set = set(names)
        for name in names:
            if name == "install-config.yml":
                continue
            if name.split("/", 1)[0].lower() not in VALID_ROOTS:
                problems.append("Wurzelordner wird vom Plugin-Manager uebersprungen: %s" % name)
            if "__pycache__" in name.split("/") or name.endswith((".pyc", ".pyo")):
                problems.append("Zwischenspeicher im Paket: %s" % name)
            if os.path.basename(name).startswith("test_"):
                problems.append("Testdatei im Paket: %s" % name)
            if name.endswith(TEXT_SUFFIXES):
                text = archive.read(name).decode("utf-8", errors="replace")
                problems += ["Unerlaubter Inhalt (%s) in %s" % (pattern.pattern, name)
                             for pattern in FORBIDDEN_TEXT if pattern.search(text)]
        for quoted in re.findall(r"(?:pyp|small|large): '([^']+)'", config):
            if quoted.replace("\\", "/") not in name_set:
                problems.append("install-config verweist auf fehlende Datei: %s" % quoted)
        if not re.search(r"^  version: \d+\.\d+\.\d+$", config, re.MULTILINE):
            problems.append("Version ist keine SemVer-Nummer")
        pyp = archive.read("%s/%s" % (LIBRARY_PREFIX, deploy.PYP_FILE)).decode("utf-8")
        script = re.search(r"<Script>\s*(?:<!--.*?-->\s*)?<Name>([^<]+)</Name>", pyp, re.DOTALL)
        if not script:
            problems.append("Skriptname in der .pyp nicht gefunden")
        elif "PythonPartsScripts/" + script.group(1).replace("\\", "/") not in name_set:
            problems.append("Skript aus der .pyp fehlt im Paket: %s" % script.group(1))
        for name in deploy.SCRIPTS + ["__init__.py"]:
            if "%s/%s" % (SCRIPTS_PREFIX, name) not in name_set:
                problems.append("Programmdatei fehlt im Paket: %s" % name)
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="3MFStudio als .allep bauen")
    parser.add_argument("--check", action="store_true", help="nur pruefen, ob alles fuer den Bau da ist")
    args = parser.parse_args(argv)
    missing = missing_sources()
    if missing:
        print("nicht baubereit - es fehlen:\n  " + "\n  ".join(missing))
        return 1
    if args.check:
        print("vollstaendig - baubereit")
        return 0
    entries = package_entries()
    allep = build_allep(entries)
    problems = verify_allep(allep)
    if problems:
        print("Paket verletzt Regeln:\n  " + "\n  ".join(problems))
        return 1
    bundle = build_zip(entries, allep)
    print("geschrieben: %s (%d KB)" % (allep, os.path.getsize(allep) // 1024))
    print("geschrieben: %s (%d KB)" % (bundle, os.path.getsize(bundle) // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
