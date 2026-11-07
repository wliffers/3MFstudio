"""Der Weg zum Slicer: Einstellung "Slicer-Programm" und "Im Slicer oeffnen" - reines Python, kein Allplan.

Kein Slicer wird vorausgesetzt (Pflicht seit 2026-11-07): ohne eigene Wahl oeffnet Windows die Datei mit dem
Programm, das fuer .3mf eingestellt ist; fehlt auch das, kommt nur eine Meldung zurueck.

Die Einstellung liegt je Windows-Benutzer in %APPDATA%\\3MFStudio\\einstellungen.json und ueberlebt den
Allplan-Neustart. Eine fehlende oder kaputte Datei ergibt die Vorgabe, nie einen Fehler beim Start.
Das Programm kommt nur aus dem Datei-Dialog; gestartet wird es mit Argumentliste, nie ueber eine Shell.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile

from threemf_text import tr  # pyright: ignore[reportMissingImports]

LOG = logging.getLogger("threemfstudio.part")

FOLDER = "3MFStudio"
FILE_NAME = "einstellungen.json"
MINE_KEY = "meine_farben"                   # eigene Farben der Farbauswahl (threemf_session.remember_mine)
DEFAULTS = {"slicer": "",                   # leer = Windows-Standard fuer 3MF-Dateien
            "universell": False,            # True: immer die neutrale 3MF schreiben, nie das Bambu-Projekt
            MINE_KEY: [],
            "drucker": "Bambu Lab A1",      # Druckplatte: gewaehlter Drucker, "" = eigene Masse
            "bauraum": True,                # Bauraum als Linien mit ablegen
            "eigene_masse": [256.0, 256.0, 256.0]}


# ---------------------------------------------------------------------------------------------- Einstellung

def settings_path(base: str = "") -> str:
    base = base or os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, FOLDER, FILE_NAME)


def load(path: str = "") -> dict:
    path = path or settings_path()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return dict(DEFAULTS)
    except (OSError, ValueError) as exc:
        LOG.warning("Einstellungen unlesbar, nehme Vorgaben (%s): %s", path, exc)
        return dict(DEFAULTS)
    data = data if isinstance(data, dict) else {}
    result = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        value = data.get(key)
        if isinstance(default, list) and key == "eigene_masse":
            ok = isinstance(value, list) and len(value) == 3 and all(isinstance(v, (int, float)) for v in value)
        else:
            ok = isinstance(value, type(default))
        if ok:
            result[key] = value
    return result


def save(settings: dict, path: str = "") -> None:
    """Schreibt erst vollstaendig daneben, dann an den Platz - eine halbe Datei bleibt nie liegen."""
    path = path or settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".neu"
    data = {key: settings.get(key, default) for key, default in DEFAULTS.items()}
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)
    LOG.info("Einstellungen gespeichert: %s", path)


def check_program(path: str) -> str:
    """Leer, wenn das gewaehlte Programm taugt; sonst die Meldung fuer den Anwender."""
    if not path.lower().endswith(".exe"):
        return tr("Bitte ein Programm (.exe) wählen.")
    if not os.path.isfile(path):
        return tr("Das Programm gibt es nicht:\n{path}", path=path)
    return ""


def program_label(slicer: str) -> str:
    if not slicer:
        return tr("Windows-Standard für 3MF-Dateien")
    return os.path.splitext(os.path.basename(slicer))[0]


def open_tip(last_file: str, slicer: str) -> str:
    if not last_file:
        return tr("Zuerst „3MF schreiben“ – dann öffnet dieser Knopf die Datei im Slicer")
    return tr("Öffnet {file} mit {program}", file=os.path.basename(last_file),
              program=program_label(slicer) if slicer else tr("dem Programm, das Windows für 3MF eingestellt hat"))


def windows_program(extension: str = ".3mf") -> str:
    """Das Programm, mit dem Windows Dateien dieser Endung oeffnet; leer, wenn keins eingestellt ist."""
    try:
        import ctypes                                       # pylint: disable=import-outside-toplevel
        size = ctypes.c_ulong(1024)
        buffer = ctypes.create_unicode_buffer(1024)
        # AssocQueryStringW(ASSOCF_NONE, ASSOCSTR_EXECUTABLE, ".3mf", "open", ...) - 0 heisst gefunden
        found = ctypes.windll.shlwapi.AssocQueryStringW(0, 2, extension, "open", buffer, ctypes.byref(size))  # type: ignore[attr-defined]
    except (AttributeError, OSError) as exc:
        LOG.info("Windows-Zuordnung fuer %s nicht lesbar: %s", extension, exc)
        return ""
    return buffer.value if found == 0 and os.path.isfile(buffer.value) else ""


def slicer_program(slicer: str) -> str:
    """Welches Programm "Im Slicer oeffnen" startet: das gewaehlte, sonst das von Windows fuer 3MF."""
    return slicer or windows_program()


def project_path(written: str) -> str:
    """Wohin das farbige Bambu-Projekt kommt: in den Temp-Ordner, nie ungefragt neben die Datei des Anwenders."""
    folder = os.path.join(tempfile.gettempdir(), FOLDER)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, os.path.splitext(os.path.basename(written))[0] + " (Farben).3mf")


# ---------------------------------------------------------------------------------------------- oeffnen

def open_in_slicer(path: str, slicer: str = "", start=None, launch=None) -> str:
    """Oeffnet die Datei im eingestellten Slicer, ohne Einstellung mit Windows' Programm fuer .3mf.

    Rueckgabe: leer, wenn der Auftrag angenommen wurde, sonst die Meldung. `start` ersetzt os.startfile,
    `launch` subprocess.Popen - beides nur im Test.
    """
    if not path:
        return tr("Noch keine 3MF-Datei geschrieben.")
    if not os.path.isfile(path):
        return tr("Die Datei gibt es nicht mehr:\n{path}", path=path)
    if slicer:
        problem = check_program(slicer)
        if problem:
            return problem + "\n\n" + tr("Unter ⚙ ein anderes Programm wählen oder „Windows-Standard“ nehmen.")
        try:
            (launch or subprocess.Popen)([slicer, path], close_fds=True)
        except OSError as exc:
            LOG.warning("Slicer %s startet nicht: %s", slicer, exc)
            return tr("{program} ließ sich nicht starten:\n{error}", program=program_label(slicer), error=exc)
        LOG.info("im Slicer %s geoeffnet: %s", slicer, path)
        return ""
    try:
        (start or os.startfile)(path)                       # type: ignore[attr-defined]  # nur unter Windows
    except OSError as exc:
        LOG.warning("Kein Programm fuer %s: %s", path, exc)
        return tr("Für 3MF-Dateien ist kein Programm eingerichtet. Die Datei liegt hier:\n{path}\n\n"
                  "Unter ⚙ den Slicer wählen.", path=path)
    LOG.info("mit Windows-Standard geoeffnet: %s", path)
    return ""
