"""3MF lesen - Dateien dieses Werkzeugs, Dateien nach 3MF-Kernstandard und Projektdateien von Bambu Studio.

Ergebnis ist eine flache Liste von `Part` in Millimetern, jede Lage (Komponenten, Platzierung) schon
eingerechnet. Name und Filamentnummer kommen, wenn vorhanden, aus Metadata/model_settings.config, die Farbe
des Filaments aus Metadata/project_settings.config. Bambus Hilfskoerper (Bereiche fuer andere Einstellungen,
Stuetzen-Sperren, Abzugskoerper) sind keine Koerper zum Drucken und werden uebergangen und gezaehlt.
Abnahme: die 13 Beispiele in input/examples (tests/test_examples.py).

Bambu Studio legt die Netze eines Objekts in eine eigene Datei (3D/Objects/object_N.model) und
verweist ueber `p:path` darauf - gemessen an Bambus zurueckgeschriebener Datei, Version 02.09.01.70.

Dateien nach Standard ohne Bambu-Angaben: Farben aus `basematerials` (Kern) und `colorgroup` (Materials-
Erweiterung); jede neue Farbe wird ein eigenes Filament. Geprueft gegen die Konformitaetstests des 3MF-
Konsortiums (tests/test_conformance.py): was eine Pflicht-Erweiterung verlangt, die hier fehlt, wird abgelehnt,
statt einen unvollstaendigen Koerper abzulegen.

Reine Standardbibliothek, kein Allplan.
"""

from __future__ import annotations

import io
import json
import math
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass

from threemf_text import tr  # pyright: ignore[reportMissingImports]
from threemf_model import MAX_FILAMENTS, Part, ThreeMfError, Triangle, Vec3  # pyright: ignore[reportMissingImports]

CORE = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
MATERIAL = "{http://schemas.microsoft.com/3dmanufacturing/material/2015/02}"
PRODUCTION_PATH = "{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}path"
RELATIONSHIP = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
MODEL_RELATIONSHIP_TYPE = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
KEYSTORE_RELATIONSHIP_TYPE = "http://schemas.microsoft.com/3dmanufacturing/2019/04/keystore"   # Secure Content
# Erweiterungen, die eine Datei verlangen darf: was sie bedeuten, liest dieses Modul oder es aendert die Form nicht.
SUPPORTED_EXTENSIONS = frozenset({
    "http://schemas.microsoft.com/3dmanufacturing/production/2015/06",      # p:path - Bambu verlangt sie immer
    "http://schemas.microsoft.com/3dmanufacturing/material/2015/02",        # Farbgruppen
    "http://schemas.microsoft.com/3dmanufacturing/trianglesets/2021/07",    # benannte Dreiecksgruppen, Form gleich
    "http://schemas.bambulab.com/package/2021",
})
EXTENSION_NAMES = (("beamlattice", "Beam Lattice"), ("slice", "Slice"), ("securecontent", "Secure Content"),
                   ("volumetric", "Volumetric"), ("booleanoperations", "Boolean Operations"),
                   ("displacement", "Displacement"), ("alternatives", "Production Alternatives"))
FIRST_ELEMENT = re.compile(rb"<[A-Za-z_]")      # erstes Element; davor steht der Prolog mit einer moeglichen DTD
DEFAULT_MODEL_FILE = "3D/3dmodel.model"
RELATIONSHIPS_FILE = "_rels/.rels"
MODEL_CONFIG_FILE = "Metadata/model_settings.config"
PROJECT_CONFIG_FILE = "Metadata/project_settings.config"
NORMAL_PART = "normal_part"     # Bambus druckbares Teil; modifier_part, negative_part, support_* sind Hilfskoerper
PAINT_COLOUR = "paint_color"    # Bambus Flaechenbemalung je Dreieck
UNIT_TO_MM = {"micron": 0.001, "millimeter": 1.0, "centimeter": 10.0, "inch": 25.4, "foot": 304.8, "meter": 1000.0}
MAX_DEPTH = 16          # Komponenten in Komponenten; tiefer ist ein Kreis oder eine kaputte Datei

Matrix = tuple[float, ...]                                  # 12 Zahlen, Zeilen eines 4x3-Blocks (3MF Core 3.3)
IDENTITY: Matrix = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)


@dataclass
class _Object:
    name: str
    vertices: list[Vec3]
    triangles: list[Triangle]
    components: list[tuple[str, int, Matrix]]              # Modelldatei, Objekt-Id, Lage
    painted: bool = False                                  # Farbe je Dreieck (Bambus paint_color oder Standardfarben)
    colour: str = ""                                       # Standardfarbe "#RRGGBB"; bei mehreren die haeufigste


@dataclass
class _Model:
    unit_to_mm: float
    objects: dict[int, _Object]
    items: list[tuple[str, int, Matrix]]
    application: str = ""


def _float(text: str) -> float:
    """Zahl nach 3MF (Punkt als Dezimalzeichen, endlich); alles andere ist eine kaputte Datei, kein Absturz."""
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        raise ThreeMfError(tr("„{text}“ ist in der Datei keine gültige Zahl.", text=text))
    return value


def _int(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise ThreeMfError(tr("„{text}“ ist in der Datei keine gültige Zahl.", text=text)) from None


def _matrix(text: str | None) -> Matrix:
    if not text:
        return IDENTITY
    values = tuple(_float(value) for value in text.split())
    if len(values) != 12:
        raise ThreeMfError(tr("Eine Lageangabe hat {count} statt 12 Zahlen.", count=len(values)))
    return values


def _apply(matrix: Matrix, point: Vec3) -> Vec3:
    x, y, z = point
    return (x * matrix[0] + y * matrix[3] + z * matrix[6] + matrix[9],
            x * matrix[1] + y * matrix[4] + z * matrix[7] + matrix[10],
            x * matrix[2] + y * matrix[5] + z * matrix[8] + matrix[11])


def _combine(first: Matrix, then: Matrix) -> Matrix:
    """Erst `first`, danach `then` (Punkte stehen als Zeilenvektor links)."""
    rows = [first[0:3], first[3:6], first[6:9], first[9:12]]
    out: list[float] = []
    for index, row in enumerate(rows):
        for column in range(3):
            value = row[0] * then[column] + row[1] * then[3 + column] + row[2] * then[6 + column]
            out.append(value + (then[9 + column] if index == 3 else 0.0))
    return tuple(out)


def _mirrors(matrix: Matrix) -> bool:
    a, b, c, d, e, f, g, h, i = matrix[0:9]
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g) < 0.0


def _normalised(path: str) -> str:
    return path.lstrip("/")


def _read(archive: zipfile.ZipFile, name: str) -> bytes:
    """Rohinhalt eines Teils; eine DTD wird abgewiesen (3MF verbietet sie, Entitaeten koennen Speicher fluten)."""
    try:
        data = archive.read(name)
    except KeyError as exc:
        raise ThreeMfError(tr("In der Datei fehlt der Teil „{name}“.", name=name)) from exc
    first = FIRST_ELEMENT.search(data)
    if b"<!DOCTYPE" in data[:first.start() if first else len(data)]:
        raise ThreeMfError(tr("Der Teil „{name}“ enthält eine DTD-Angabe. 3MF erlaubt das nicht – die Datei wird "
                              "aus Sicherheitsgründen nicht gelesen.", name=name))
    return data


def _parse(archive: zipfile.ZipFile, name: str, data: bytes | None = None) -> ET.Element:
    try:
        return ET.fromstring(_read(archive, name) if data is None else data)
    except ET.ParseError as exc:
        raise ThreeMfError(tr("Der Teil „{name}“ ist beschädigt: {error}", name=name, error=exc)) from exc


def _root_namespaces(data: bytes) -> dict[str, str]:
    """Praefix -> Namensraum, wie das Wurzelelement sie erklaert (ElementTree vergisst die Praefixe)."""
    found: dict[str, str] = {}
    for event, item in ET.iterparse(io.BytesIO(data), events=("start-ns", "start")):
        if event == "start":
            break
        prefix, uri = item
        found[prefix] = uri
    return found


def _extension_name(uri: str) -> str:
    lowered = uri.lower()
    return next((name for key, name in EXTENSION_NAMES if key in lowered), uri)


def _check_required(root: ET.Element, data: bytes) -> None:
    """3MF Core 2.3.1: eine verlangte, aber unbekannte Erweiterung heisst ablehnen - sonst fehlt still ein Teil."""
    wanted = root.get("requiredextensions", "").split()
    if not wanted:
        return
    namespaces = _root_namespaces(data)
    missing = [_extension_name(namespaces[prefix]) if prefix in namespaces else prefix
               for prefix in wanted if namespaces.get(prefix) not in SUPPORTED_EXTENSIONS]
    if missing:
        raise ThreeMfError(tr("Die Datei verlangt die 3MF-Erweiterung „{names}“, die 3MFStudio nicht kennt. Ohne sie "
                              "wäre der Körper unvollständig – die Datei wird deshalb nicht gelesen.",
                              names=", ".join(missing)))


def _relationship_targets(archive: zipfile.ZipFile) -> dict[str, str]:
    """Beziehungstyp -> Ziel aus _rels/.rels (der erste je Typ)."""
    if RELATIONSHIPS_FILE not in archive.namelist():
        return {}
    found: dict[str, str] = {}
    for relationship in _parse(archive, RELATIONSHIPS_FILE).iter(RELATIONSHIP):
        if relationship.get("Type") and relationship.get("Target"):
            found.setdefault(relationship.get("Type", ""), _normalised(relationship.get("Target", "")))
    return found


def _palettes(resources: ET.Element | None) -> dict[int, list[str]]:
    """Farbliste je Ressource: basematerials (Kern, displaycolor) und colorgroup (Materials-Erweiterung)."""
    palettes: dict[int, list[str]] = {}
    if resources is None:
        return palettes
    for group in resources.iterfind(f"{CORE}basematerials"):
        palettes[_int(group.get("id", "0"))] = [_hex_colour(base.get("displaycolor", ""))
                                                for base in group.iterfind(f"{CORE}base")]
    for group in resources.iterfind(f"{MATERIAL}colorgroup"):
        palettes[_int(group.get("id", "0"))] = [_hex_colour(colour.get("color", ""))
                                                for colour in group.iterfind(f"{MATERIAL}color")]
    return palettes


def _colour(palettes: dict[int, list[str]], group: str | None, index: str | None) -> str:
    entries = palettes.get(_int(group), []) if group else []
    position = _int(index) if index else 0
    return entries[position] if 0 <= position < len(entries) else ""


def _check_unique_ids(resources: ET.Element | None) -> None:
    seen: set[int] = set()
    for element in resources if resources is not None else ():
        if element.get("id") is None:
            continue
        number = _int(element.get("id", ""))
        if number in seen:
            raise ThreeMfError(tr("Die Datei vergibt die Nummer {id} doppelt.", id=number))
        seen.add(number)


def _load_model(archive: zipfile.ZipFile, path: str) -> _Model:
    data = _read(archive, path)
    root = _parse(archive, path, data)
    _check_required(root, data)
    unit = root.get("unit", "millimeter")
    if unit not in UNIT_TO_MM:
        raise ThreeMfError(tr("Unbekannte Längeneinheit „{unit}“.", unit=unit))
    resources = root.find(f"{CORE}resources")
    _check_unique_ids(resources)
    palettes = _palettes(resources)
    objects: dict[int, _Object] = {}
    for element in root.iterfind(f"{CORE}resources/{CORE}object"):
        entry = _Object(element.get("name", ""), [], [], [])
        mesh = element.find(f"{CORE}mesh")
        if mesh is not None:
            entry.vertices = [(_float(v.get("x", "0")), _float(v.get("y", "0")), _float(v.get("z", "0")))
                              for v in mesh.iterfind(f"{CORE}vertices/{CORE}vertex")]
            object_group, object_index = element.get("pid"), element.get("pindex")
            colours: Counter = Counter()
            for triangle in mesh.iterfind(f"{CORE}triangles/{CORE}triangle"):
                entry.triangles.append((_int(triangle.get("v1", "0")), _int(triangle.get("v2", "0")),
                                        _int(triangle.get("v3", "0"))))
                entry.painted = entry.painted or bool(triangle.get(PAINT_COLOUR))
                if palettes:
                    colours[_colour(palettes, triangle.get("pid", object_group),
                                    triangle.get("p1", object_index))] += 1
            count = len(entry.vertices)
            if any(not 0 <= index < count for triangle in entry.triangles for index in triangle):
                raise ThreeMfError(tr("„{name}“ verweist auf Punkte, die es nicht gibt.", name=entry.name))
            colours.pop("", None)
            if colours:
                entry.colour = colours.most_common(1)[0][0]
                entry.painted = entry.painted or len(colours) > 1
        for component in element.iterfind(f"{CORE}components/{CORE}component"):
            entry.components.append((_normalised(component.get(PRODUCTION_PATH, path)),
                                     _int(component.get("objectid", "0")), _matrix(component.get("transform"))))
        objects[_int(element.get("id", "0"))] = entry
    items = [(_normalised(item.get(PRODUCTION_PATH, path)), _int(item.get("objectid", "0")),
              _matrix(item.get("transform")))
             for item in root.iterfind(f"{CORE}build/{CORE}item")]
    application = next((str(entry.text or "").strip() for entry in root.iterfind(f"{CORE}metadata")
                        if entry.get("name") == "Application"), "")
    return _Model(UNIT_TO_MM[unit], objects, items, application)


@dataclass
class _PartSetting:
    object_id: int
    subtype: str
    meta: dict[str, str]


@dataclass
class ReadResult:
    """Was eine Datei hergibt: die druckbaren Koerper und was dabei bewusst uebergangen wurde."""
    parts: list[Part]
    skipped_helpers: int = 0          # Bambus Hilfskoerper (Einstellungs-Bereiche, Stuetzen-Sperren, Abzugskoerper)
    painted_parts: int = 0            # Koerper mit Flaechenbemalung - die Bemalung kommt nicht mit
    application: str = ""             # wer die Datei geschrieben hat ("3MFStudio", "BambuStudio-02.09...")


def _metadata(element: ET.Element) -> dict[str, str]:
    return {m.get("key", ""): m.get("value", "") for m in element.iterfind("metadata") if m.get("key")}


def _settings(archive: zipfile.ZipFile) -> dict[int, dict]:
    """Objekt-Id -> {'name', 'extruder', 'parts': [_PartSetting in Dateireihenfolge]} aus Bambus Zusatzdatei.

    Die Teile bleiben eine LISTE: Bambu verweist mehrfach auf dasselbe Netz (Beispiel 3Layers4ColorsPlate1,
    neunmal "Cube" aus drei Netzen) - zugeordnet wird in der Reihenfolge, nicht ueber die Netznummer allein.
    """
    if MODEL_CONFIG_FILE not in archive.namelist():
        return {}
    result: dict[int, dict] = {}
    for element in _parse(archive, MODEL_CONFIG_FILE).iterfind("object"):
        own = _metadata(element)
        result[int(element.get("id", "0"))] = {
            "name": own.get("name", ""), "extruder": own.get("extruder", ""),
            "parts": [_PartSetting(int(part.get("id", "0")), part.get("subtype", NORMAL_PART), _metadata(part))
                      for part in element.iterfind("part")],
        }
    return result


def _filament_colours(archive: zipfile.ZipFile) -> list[str]:
    """Farbe je Filament ("#RRGGBB") aus Bambus Projekteinstellungen; leer, wenn die Datei keine hat."""
    if PROJECT_CONFIG_FILE not in archive.namelist():
        return []
    try:
        data = json.loads(archive.read(PROJECT_CONFIG_FILE))
    except ValueError:
        return []                     # kaputte Einstellungen kosten nur die Farben, nicht die Koerper
    colours = data.get("filament_colour") if isinstance(data, dict) else None
    if not isinstance(colours, list):
        return []
    return [_hex_colour(value) for value in colours]


def _hex_colour(value) -> str:
    text = str(value).strip()
    if len(text) in (7, 9) and text.startswith("#"):
        try:
            int(text[1:], 16)
            return text[:7].upper()   # "#804000FE": die letzten zwei Stellen sind die Deckkraft
        except ValueError:
            pass
    return ""


def _filament(value: str) -> int:
    """Filamentnummer; 0 = keine eigene Angabe (Bambu: "0" heisst "wie das Objekt")."""
    text = value.strip()
    return int(text) if text.isdigit() and int(text) > 0 else 0


def read_file(path: str) -> ReadResult:
    """Alle druckbaren Koerper der Datei als Teile in Millimetern, in der Reihenfolge der Datei."""
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ThreeMfError(tr("„{path}“ ist keine lesbare 3MF-Datei: {error}", path=path, error=exc)) from exc
    with archive:
        targets = _relationship_targets(archive)
        if KEYSTORE_RELATIONSHIP_TYPE in targets:
            raise ThreeMfError(tr("Die Datei ist verschlüsselt (3MF-Erweiterung Secure Content). 3MFStudio kann "
                                  "verschlüsselte Dateien nicht lesen."))
        root_path = targets.get(MODEL_RELATIONSHIP_TYPE, DEFAULT_MODEL_FILE)
        models: dict[str, _Model] = {}
        standard_filaments: dict[str, int] = {}      # Standardfarbe -> Filament, in der Reihenfolge der Datei

        def standard_filament(colour: str) -> int:
            if not colour:
                return 0
            if colour not in standard_filaments:
                standard_filaments[colour] = min(len(standard_filaments) + 1, MAX_FILAMENTS)
            return standard_filaments[colour]

        def model(model_path: str) -> _Model:
            if model_path not in models:
                models[model_path] = _load_model(archive, model_path)
            return models[model_path]

        settings = _settings(archive)
        colours = _filament_colours(archive)
        unit_to_mm = model(root_path).unit_to_mm
        result = ReadResult([], application=model(root_path).application)
        pending: dict[int, list[_PartSetting]] = {top_id: list(entry["parts"]) for top_id, entry in settings.items()}

        def part_setting(top_id: int, object_id: int) -> _PartSetting | None:
            """Der naechste noch freie Eintrag fuer dieses Netz; mehrfach benutzte Netze nacheinander."""
            queue = pending.get(top_id, [])
            for index, entry in enumerate(queue):
                if entry.object_id == object_id:
                    return queue.pop(index)
            return None

        def collect(model_path: str, object_id: int, placement: Matrix, top_id: int, depth: int) -> None:
            if depth > MAX_DEPTH:
                raise ThreeMfError(tr("Die Datei verweist im Kreis auf ihre eigenen Körper."))
            entry = model(model_path).objects.get(object_id)
            if entry is None:
                raise ThreeMfError(tr("Die Datei verweist auf einen Körper {id}, den es nicht gibt.", id=object_id))
            if entry.triangles:
                top = settings.get(top_id, {})
                own = part_setting(top_id, object_id)
                if own is not None and own.subtype != NORMAL_PART:
                    result.skipped_helpers += 1
                else:
                    meta = own.meta if own is not None else {}
                    name = meta.get("name") or entry.name or top.get("name") or f"Teil {len(result.parts) + 1}"
                    filament = (_filament(meta.get("extruder", "")) or _filament(top.get("extruder", ""))
                                or standard_filament(entry.colour) or 1)
                    colour = (colours[filament - 1] if filament <= len(colours) else "") or entry.colour
                    triangles = [(a, c, b) for a, b, c in entry.triangles] if _mirrors(placement) \
                        else entry.triangles
                    vertices = [_apply(placement, vertex) for vertex in entry.vertices]
                    result.parts.append(Part(
                        name, filament,
                        tuple((x * unit_to_mm, y * unit_to_mm, z * unit_to_mm) for x, y, z in vertices),
                        tuple(triangles), colour))
                    result.painted_parts += int(entry.painted)
            for child_path, child_id, child_placement in entry.components:
                collect(child_path, child_id, _combine(child_placement, placement), top_id, depth + 1)

        for item_path, item_id, item_placement in model(root_path).items:
            collect(item_path, item_id, item_placement, item_id, 0)
    if not result.parts:
        raise ThreeMfError(tr("Die Datei enthält keinen Körper."))
    return result


def read_3mf(path: str) -> list[Part]:
    """Wie `read_file`, nur die Teile."""
    return read_file(path).parts
