"""Farb- und Materialliste fuer die Farbauswahl - reines Python, kein Allplan, kein Netz.

Zwei Quellen (prompt.de.md, "Farbe und Material je Filament"):

- threemf_filaments.json.gz neben diesem Modul: die verkleinerte Open Filament Database (MIT, Lizenztext in
  LICENSE_OpenFilamentDatabase.txt), gebaut von build_filaments.py. Hersteller -> Sorte -> Farben.
- Ist Bambu Studio installiert, ersetzt dessen eigene Farbliste (filaments_color_codes.json, 342 Farben,
  offizielle Namen in 12 Sprachen) die Bambu-Lab-Eintraege: sie traegt Bambus Filament-Kennung (GFA00 ...),
  ueber die "Im Slicer oeffnen" das passende Bambu-Profil findet. Die Datei wird beim Kunden nur gelesen, nie
  mitgeliefert (Bambu Studio steht unter AGPL).

Reihenfolge der Hersteller: Bambu Lab zuerst, die anderen alphabetisch (Wunsch 2026-11-07).
"""

from __future__ import annotations

import gzip
import json
import logging
import os
from dataclasses import dataclass

LOG = logging.getLogger("threemfstudio.part")

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLED_FILE = os.path.join(HERE, "threemf_filaments.json.gz")
BAMBU_BRAND = "Bambu Lab"
BAMBU_COLOUR_FILE = "filaments_color_codes.json"
_BAMBU_PROFILE_DIRS = (                              # unter %APPDATA% bzw. dem Programmordner von Bambu Studio
    ("BambuStudio", "system", "BBL", "filament"),
    ("resources", "profiles", "BBL", "filament"),
)
DEFAULT_BAMBU_PROGRAM_DIR = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Bambu Studio")


@dataclass(frozen=True)
class Swatch:
    """Eine Filamentfarbe: Name, Farbwert "#RRGGBB" und - bei mehrfarbigem Filament - weitere Farbwerte."""
    name: str
    hex: str
    more: tuple[str, ...] = ()


@dataclass(frozen=True)
class Line:
    """Eine Sorte eines Herstellers (z. B. Bambu Lab "PLA Basic", Material "PLA") mit ihren Farben.

    `code` ist Bambus Filament-Kennung (nur aus Bambus eigener Liste), sonst leer."""
    brand: str
    name: str
    material: str
    swatches: tuple[Swatch, ...]
    code: str = ""


def normal_hex(value) -> str:
    """"#aabbcc", "aabbcc" oder "#AABBCCFF" -> "#AABBCC"; Unbrauchbares -> ""."""
    text = str(value or "").strip().lstrip("#")
    if len(text) not in (6, 8) or any(char not in "0123456789abcdefABCDEF" for char in text):
        return ""
    return "#" + text[:6].upper()


def brand_order(brand: str) -> tuple[int, str]:
    return (0 if brand == BAMBU_BRAND else 1, brand.casefold())


class Catalogue:
    """Alle Sorten, gruppiert nach Hersteller. Nur Daten und Nachschlagen - geladen wird ausserhalb."""

    def __init__(self, lines: list[Line], version: str = "", bambu_file: str = ""):
        self.version = version
        self.bambu_file = bambu_file                 # gesetzt, wenn die Bambu-Farben aus Bambu Studio stammen
        self._by_brand: dict[str, list[Line]] = {}
        for line in lines:
            self._by_brand.setdefault(line.brand, []).append(line)
        for entries in self._by_brand.values():
            entries.sort(key=lambda line: line.name.casefold())

    def brands(self) -> list[str]:
        return sorted(self._by_brand, key=brand_order)

    def lines(self, brand: str) -> list[Line]:
        return list(self._by_brand.get(brand, []))

    def line(self, brand: str, name: str) -> Line | None:
        return next((line for line in self._by_brand.get(brand, []) if line.name == name), None)

    def count(self) -> int:
        return sum(len(line.swatches) for entries in self._by_brand.values() for line in entries)


# ---------------------------------------------------------------------------------------------- laden

def load_bundled(path: str = BUNDLED_FILE) -> tuple[list[Line], str]:
    """Die mitgelieferte Liste (build_filaments.py) -> (Sorten, Stand)."""
    with open(path, "rb") as handle:
        data = json.loads(gzip.decompress(handle.read()).decode("utf-8"))
    lines = []
    for brand, entries in data["brands"]:
        for name, material, swatches in entries:
            lines.append(Line(brand, name, material,
                              tuple(Swatch(entry[0], entry[1], tuple(entry[2:])) for entry in swatches)))
    return lines, str(data.get("version", ""))


def bambu_colour_file(program: str = "", appdata: str | None = None) -> str:
    """Bambus Farbliste auf diesem Rechner - erst die Kopie unter %APPDATA%, dann der Programmordner; sonst leer."""
    appdata = os.environ.get("APPDATA", "") if appdata is None else appdata
    candidates = []
    if appdata:
        candidates.append(os.path.join(appdata, *_BAMBU_PROFILE_DIRS[0], BAMBU_COLOUR_FILE))
    for folder in (os.path.dirname(program) if program else "", DEFAULT_BAMBU_PROGRAM_DIR):
        if folder:
            candidates.append(os.path.join(folder, *_BAMBU_PROFILE_DIRS[1], BAMBU_COLOUR_FILE))
    return next((path for path in candidates if os.path.isfile(path)), "")


def bambu_colour_name(names, language: str) -> str:
    """Name in der Sprache des Anwenders; fehlt er, der englische."""
    if not isinstance(names, dict):
        return str(names or "").strip()
    return str(names.get(language) or names.get("en") or next(iter(names.values()), "")).strip()


def load_bambu(path: str, language: str, materials: dict[str, str] | None = None) -> list[Line]:
    """Bambus Farbliste -> Sorten von Bambu Lab mit Filament-Kennung.

    `materials` ordnet der Kennung das Material aus Bambus Profil zu (threemf_bambu.base_profiles); fehlt sie,
    gilt das erste Wort der Sorte ("PETG HF" -> "PETG")."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    grouped: dict[tuple[str, str], list[Swatch]] = {}
    for entry in data.get("data", []):
        line, code = str(entry.get("fila_type") or "").strip(), str(entry.get("fila_id") or "").strip()
        tones = [normal_hex(value) for value in entry.get("fila_color") or []]
        tones = [tone for tone in tones if tone]
        name = bambu_colour_name(entry.get("fila_color_name"), language)
        if not line or not tones or not name:
            continue
        grouped.setdefault((line, code), []).append(Swatch(name, tones[0], tuple(tones[1:])))
    lines = []
    for (line, code), swatches in grouped.items():
        material = (materials or {}).get(code) or line.split()[0]
        swatches.sort(key=lambda swatch: swatch.name.casefold())
        lines.append(Line(BAMBU_BRAND, line, material, tuple(swatches), code))
    return lines


def catalogue(language: str, program: str = "", materials: dict[str, str] | None = None,
              bundled: str = BUNDLED_FILE, appdata: str | None = None) -> Catalogue:
    """Die ganze Liste: mitgelieferter Stand, Bambu Lab aus Bambu Studio, wenn es da ist.

    Fehlt die mitgelieferte Datei oder ist sie kaputt, bleibt die Liste ohne sie (Protokoll) - die Auswahl
    zeigt dann nur Bambu Lab oder nichts, eigene Farben gehen immer."""
    lines: list[Line] = []
    version = ""
    try:
        lines, version = load_bundled(bundled)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        LOG.error("Mitgelieferte Farbliste nicht lesbar (%s): %s", bundled, exc)
    bambu_file = bambu_colour_file(program, appdata)
    if bambu_file:
        try:
            bambu = load_bambu(bambu_file, language, materials)
        except (OSError, ValueError, TypeError) as exc:
            LOG.warning("Bambus Farbliste nicht lesbar (%s): %s", bambu_file, exc)
            bambu, bambu_file = [], ""
        if bambu:
            lines = [line for line in lines if line.brand != BAMBU_BRAND] + bambu
    return Catalogue(lines, version, bambu_file)
