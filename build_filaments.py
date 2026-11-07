"""Farbliste fuer 3MFStudio aus der Open Filament Database bauen (beim Paketbau, nie in Allplan).

    python build_filaments.py                 # neuesten Stand herunterladen
    python build_filaments.py --source all.json.gz   # vorhandene Datei verkleinern

Quelle: Open Filament Database (Open Filament Collective, MIT-Lizenz),
https://github.com/OpenFilamentCollective/open-filament-database - der Stand erscheint taeglich als
Release-Datei `all.json.gz`. Das Skript laedt sie, prueft den Aufbau und schreibt nur, was die Farbauswahl
braucht, nach src/threemf_filaments.json.gz (Hersteller -> Sorte -> Farben) und den Lizenztext nach
src/LICENSE_OpenFilamentDatabase.txt. Ausgelaufene Sorten und Farben bleiben draussen.

Aufbau der erzeugten Datei (kurze Listen statt Schluessel, damit sie klein bleibt):
    {"version": "2026.11.07", "source": "...", "brands": [[Hersteller, [[Sorte, Material, [[Name, "#RRGGBB", ...]]]]]]}
Weitere Farbwerte hinter dem ersten gehoeren zu mehrfarbigem Filament.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "src", "threemf_filaments.json.gz")
LICENSE_TARGET = os.path.join(HERE, "src", "LICENSE_OpenFilamentDatabase.txt")
RELEASE_URL = ("https://github.com/OpenFilamentCollective/open-filament-database/releases/latest/download/"
               "all.json.gz")
LICENSE_URL = "https://raw.githubusercontent.com/OpenFilamentCollective/open-filament-database/main/LICENSE"
SOURCE_NOTE = "Open Filament Database (Open Filament Collective), MIT"
MIN_BRANDS = 100                       # weniger heisst: Aufbau geaendert oder Datei abgeschnitten
TIMEOUT_S = 60
HEX = re.compile(r"^#?([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?$")


class BuildError(RuntimeError):
    pass


def normal_hex(value) -> str:
    """"#aabbcc", "aabbcc" oder "#AABBCCFF" -> "#AABBCC"; Unbrauchbares -> ""."""
    match = HEX.match(str(value or "").strip())
    return "#" + match.group(1).upper() if match else ""


def reduce(data: dict) -> dict:
    """Die volle Datenbank auf Hersteller -> Sorte -> Farben verkleinern."""
    for key in ("version", "brands", "filaments", "variants"):
        if key not in data:
            raise BuildError("Die Datenbank hat kein Feld '%s' - Aufbau geaendert?" % key)
    if len(data["brands"]) < MIN_BRANDS:
        raise BuildError("Nur %s Hersteller in der Datenbank - erwartet mindestens %s." % (len(data["brands"]), MIN_BRANDS))
    brand_names = {brand["id"]: str(brand["name"]).strip() for brand in data["brands"]}
    colours: dict[str, list] = {}
    for variant in data["variants"]:
        tone = normal_hex(variant.get("color_hex"))
        if variant.get("discontinued") or not tone:
            continue
        extra = [normal_hex(value) for value in variant.get("color_hexes") or []]
        tones = [tone] + [value for value in extra if value and value != tone]
        colours.setdefault(variant["filament_id"], []).append([str(variant["name"]).strip()] + tones)
    lines: dict[str, dict[str, list]] = {}
    for filament in data["filaments"]:
        found = colours.get(filament["id"])
        brand = brand_names.get(filament.get("brand_id"), "")
        if filament.get("discontinued") or not found or not brand:
            continue
        name = str(filament["name"]).strip()
        entry = lines.setdefault(brand, {}).setdefault(name, [name, str(filament.get("material") or "").strip(), []])
        entry[2].extend(found)                      # gleiche Sorte zweimal im Hersteller: Farben zusammenlegen
    brands = []
    for brand in sorted(lines, key=str.casefold):
        entries = sorted(lines[brand].values(), key=lambda entry: entry[0].casefold())
        for entry in entries:
            entry[2].sort(key=lambda swatch: swatch[0].casefold())
        brands.append([brand, entries])
    return {"version": str(data["version"]), "source": SOURCE_NOTE, "brands": brands}


def download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:   # noqa: S310 - feste https-Adresse
        return response.read()


def write(reduced: dict, licence: str) -> None:
    raw = json.dumps(reduced, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with open(TARGET, "wb") as handle:
        handle.write(gzip.compress(raw, compresslevel=9, mtime=0))
    with open(LICENSE_TARGET, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("Farbliste in threemf_filaments.json.gz: %s, Stand %s.\n\n%s"
                     % (SOURCE_NOTE, reduced["version"], licence.strip() + "\n"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", help="vorhandene all.json(.gz) statt Download")
    parser.add_argument("--license", help="vorhandener Lizenztext statt Download")
    args = parser.parse_args(argv)
    try:
        if args.source:
            with open(args.source, "rb") as handle:
                packed = handle.read()
        else:
            packed = download(RELEASE_URL)
        data = json.loads(gzip.decompress(packed) if packed[:2] == b"\x1f\x8b" else packed)
        if args.license:
            with open(args.license, encoding="utf-8") as handle:
                licence = handle.read()
        else:
            licence = download(LICENSE_URL).decode("utf-8")
        if "MIT" not in licence and "Permission is hereby granted" not in licence:
            raise BuildError("Der Lizenztext ist nicht mehr MIT - erst pruefen, dann mitliefern.")
        reduced = reduce(data)
        write(reduced, licence)
    except (OSError, ValueError, BuildError) as exc:
        print("Farbliste NICHT gebaut: %s" % exc, file=sys.stderr)
        return 1
    count = sum(len(entry[2]) for _brand, entries in reduced["brands"] for entry in entries)
    print("Farbliste %s: %s Hersteller, %s Farben -> %s (%s KB)"
          % (reduced["version"], len(reduced["brands"]), count, TARGET, os.path.getsize(TARGET) // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
