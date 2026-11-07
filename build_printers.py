"""Druckerliste fuer 3MFStudio bauen (beim Paketbau, nie in Allplan).

    python build_printers.py                       # aus dem installierten Bambu Studio
    python build_printers.py --profiles <Ordner>   # anderer Ordner resources/profiles

Liest aus den Druckerprofilen von Bambu Studio nur Fakten - Druckername, Hersteller, Breite und Tiefe der
(rechteckigen) Druckflaeche und Bauhoehe in mm - und schreibt sie nach src/threemf_printers.json. Die Liste liegt danach vollstaendig im PythonPart
(Wunsch 2026-11-07: "Die Daten liegen 100 % bei uns"); zur Laufzeit liest 3MFStudio nichts von Bambu.
Je Druckermodell zaehlt das Profil mit 0,4-mm-Duese. Bambu Lab steht zuerst, die anderen alphabetisch.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

import threemf_bambu  # noqa: E402  # pyright: ignore[reportMissingImports]

TARGET = os.path.join(HERE, "src", "threemf_printers.json")
DEFAULT_PROFILES = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Bambu Studio", "resources",
                                "profiles")
BRANDS = {"BBL": "Bambu Lab"}             # Ordnername -> Herstellername, sonst gilt der Ordnername
PREFERRED_NOZZLE = "0.4"


class BuildError(RuntimeError):
    pass


def parse_area(values) -> list[list[float]]:
    """["0x0", "256x0", ...] -> [[0.0, 0.0], [256.0, 0.0], ...]."""
    points = []
    for value in values or []:
        x, _sep, y = str(value).partition("x")
        points.append([float(x), float(y)])
    if len(points) < 3:
        raise ValueError("Druckflaeche mit weniger als drei Punkten: %s" % values)
    return points


def printers_of(profiles: str, folder: str) -> dict[str, dict]:
    """Alle Druckermodelle eines Herstellerordners -> {Modell: Eintrag}; je Modell das 0,4-mm-Profil zuerst."""
    with open(os.path.join(profiles, folder + ".json"), encoding="utf-8") as handle:
        index = json.load(handle)
    machine_dir = os.path.join(profiles, folder, "machine")
    found: dict[str, tuple[bool, dict]] = {}
    for entry in index.get("machine_list", []):
        name = str(entry.get("name", ""))
        try:
            data = threemf_bambu.resolve_profile(machine_dir, name)
        except (OSError, ValueError):
            continue
        model = str(data.get("printer_model") or "").strip()
        if str(data.get("instantiation", "")).lower() != "true" or not model or "printable_area" not in data:
            continue
        nozzle = data.get("nozzle_diameter")
        nozzle = nozzle[0] if isinstance(nozzle, list) and nozzle else nozzle
        preferred = str(nozzle) == PREFERRED_NOZZLE
        if model in found and (found[model][0] or not preferred):
            continue
        try:
            area = parse_area(data["printable_area"])
            height = float(data.get("printable_height") or 0.0)
        except (TypeError, ValueError):
            continue
        xs, ys = [x for x, _y in area], [y for _x, y in area]
        if height <= 0.0 or len(area) != 4 or len(set(xs)) != 2 or len(set(ys)) != 2:
            print("uebergangen (nicht rechteckig oder ohne Hoehe): %s" % model, file=sys.stderr)
            continue
        found[model] = (preferred, {"name": model, "brand": BRANDS.get(folder, folder),
                                    "width": max(xs) - min(xs), "depth": max(ys) - min(ys), "height": height})
    return {model: entry for model, (_preferred, entry) in found.items()}


def build(profiles: str) -> list[dict]:
    if not os.path.isdir(profiles):
        raise BuildError("Kein Profilordner: %s" % profiles)
    printers: dict[str, dict] = {}
    for name in sorted(os.listdir(profiles)):
        if name.endswith(".json") and os.path.isdir(os.path.join(profiles, name[:-5])):
            printers.update(printers_of(profiles, name[:-5]))
    if not any(entry["brand"] == "Bambu Lab" for entry in printers.values()):
        raise BuildError("Keine Bambu-Lab-Drucker gefunden - Aufbau der Profile geaendert?")
    return sorted(printers.values(), key=lambda entry: (entry["brand"] != "Bambu Lab", entry["brand"].casefold(),
                                                        entry["name"].casefold()))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profiles", default=DEFAULT_PROFILES)
    args = parser.parse_args(argv)
    try:
        printers = build(args.profiles)
    except (OSError, ValueError, BuildError) as exc:
        print("Druckerliste NICHT gebaut: %s" % exc, file=sys.stderr)
        return 1
    data = {"source": "Druckermaße aus den Druckerprofilen von Bambu Studio (nur Name, Druckfläche, Bauhöhe)",
            "printers": printers}
    with open(TARGET, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=0)
    print("Druckerliste: %s Drucker -> %s" % (len(printers), TARGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
