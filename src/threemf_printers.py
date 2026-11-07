"""Druckerliste und Druckplatte - reines Python, kein Allplan.

Die Liste liegt vollstaendig im PythonPart (threemf_printers.json neben diesem Modul, gebaut von
build_printers.py; Wunsch 2026-11-07 "Die Daten liegen 100 % bei uns"). Je Drucker: Name, Hersteller, Breite und
Tiefe der Druckflaeche, Bauhoehe in mm.

Lage (Wunsch 2026-11-07): Platte 1 mm stark, Oberseite genau auf Z = 0, Mitte auf X = 0 / Y = 0. Der Bauraum ist
ein Quader von Z = 0 bis zur Bauhoehe und wird nur als Kanten gezeigt (3D-Linien).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from threemf_model import ThreeMfError  # pyright: ignore[reportMissingImports]
from threemf_text import tr  # pyright: ignore[reportMissingImports]

HERE = os.path.dirname(os.path.abspath(__file__))
PRINTERS_FILE = os.path.join(HERE, "threemf_printers.json")
BAMBU_BRAND = "Bambu Lab"
PLATE_THICKNESS_MM = 1.0
MAX_SIZE_MM = 5000.0                      # groesser ist kein Drucker - Tippfehler abfangen

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class Printer:
    name: str
    brand: str
    width: float
    depth: float
    height: float


def load(path: str = PRINTERS_FILE) -> list[Printer]:
    """Die mitgelieferte Liste, Bambu Lab zuerst, die anderen alphabetisch."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    printers = [Printer(str(entry["name"]), str(entry["brand"]), float(entry["width"]), float(entry["depth"]),
                        float(entry["height"])) for entry in data["printers"]]
    return sorted(printers, key=lambda printer: (printer.brand != BAMBU_BRAND, printer.brand.casefold(),
                                                  printer.name.casefold()))


def find(printers: list[Printer], name: str) -> Printer | None:
    return next((printer for printer in printers if printer.name == name), None)


def size_value(text) -> float:
    """Eingabe des Anwenders in mm ("256", "256,5") -> Zahl; sonst Meldung."""
    try:
        value = float(str(text).strip().replace(",", "."))
    except ValueError:
        raise ThreeMfError(tr("„{text}“ ist keine Zahl. Maße bitte in mm eingeben, z. B. 256.", text=text)) from None
    if not 0.0 < value <= MAX_SIZE_MM:
        raise ThreeMfError(tr("Maße müssen größer als 0 und höchstens {maximum} mm sein.", maximum=int(MAX_SIZE_MM)))
    return value


def custom(width, depth, height) -> Printer:
    """Eigene Maße (Texte oder Zahlen in mm) als Drucker."""
    return Printer("", "", size_value(width), size_value(depth), size_value(height))


def plate_box(printer: Printer) -> tuple[Vec3, Vec3]:
    """(Ecke unten links hinten, Ausdehnung) der Platte: Oberseite auf Z = 0, Mitte auf X/Y = 0."""
    return ((-printer.width / 2.0, -printer.depth / 2.0, -PLATE_THICKNESS_MM),
            (printer.width, printer.depth, PLATE_THICKNESS_MM))


def volume_lines(printer: Printer) -> list[list[Vec3]]:
    """Die Kanten des Bauraums: unterer und oberer Rahmen (geschlossen) und vier senkrechte Kanten."""
    x, y = printer.width / 2.0, printer.depth / 2.0
    corners = [(-x, -y), (x, -y), (x, y), (-x, y)]
    bottom = [(cx, cy, 0.0) for cx, cy in corners + corners[:1]]
    top = [(cx, cy, printer.height) for cx, cy in corners + corners[:1]]
    return [bottom, top] + [[(cx, cy, 0.0), (cx, cy, printer.height)] for cx, cy in corners]
