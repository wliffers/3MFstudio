"""3MF schreiben - jeder Koerper ein Teil mit Namen und Filamentnummer, sich durchdringende Koerper in einem Objekt.

Aufbau wie in Gate G1 mit Bambu Studio 02.09.01.70 gemessen (Messreihe G1,
Belege je Schluessel in docs/messungen/G1_Belege.md des Repos):

- Koerper, die ineinander stecken, bilden EIN Objekt aus Komponenten (nur dort trennt Bambu den gemeinsamen
  Bereich sauber); getrennt liegende Koerper sind eigene Objekte (37 Puzzleteile, Beispiel 3D+PUZZLE)
- Filamentnummer je Teil als `extruder` in Metadata/model_settings.config
- keine Metadata/project_settings.config, keine Farbangaben nach 3MF-Standard
- `Application` beginnt nicht mit "BambuStudio-"
- die Reihenfolge der Teile entscheidet ueber gemeinsame Bereiche: das spaetere Teil gewinnt.
  Der Schreiber aendert die Reihenfolge nicht - `threemf_model.ordered_for_overlap` legt sie fest.

Reine Standardbibliothek, kein Allplan.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from typing import Sequence
from xml.sax.saxutils import escape

from threemf_text import tr  # pyright: ignore[reportMissingImports]
from threemf_model import Part, ThreeMfError, grouped_for_objects  # pyright: ignore[reportMissingImports]

CORE_NAMESPACE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
BAMBU_NAMESPACE = "http://schemas.bambulab.com/package/2021"
MODEL_FILE = "3D/3dmodel.model"
CONTENT_TYPES_FILE = "[Content_Types].xml"
RELATIONSHIPS_FILE = "_rels/.rels"
MODEL_CONFIG_FILE = "Metadata/model_settings.config"
APPLICATION = "3MFStudio"
IDENTITY_3X4 = "1 0 0 0 1 0 0 0 1 0 0 0"
IDENTITY_4X4 = "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"

CONTENT_TYPES_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
    ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
    ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
    ' <Default Extension="png" ContentType="image/png"/>\n'
    ' <Default Extension="gcode" ContentType="text/x.gcode"/>\n'
    "</Types>"
)
RELATIONSHIPS_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
    f' <Relationship Target="/{MODEL_FILE}" Id="rel-1" '
    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
    "</Relationships>"
)


def _attribute(text: str) -> str:
    """Freier Text (Namen des Anwenders) fuer ein Attribut in doppelten Anfuehrungszeichen."""
    return escape(text, {'"': "&quot;"})


def _number(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _check(parts: Sequence[Part]) -> None:
    if not parts:
        raise ThreeMfError(tr("Es ist kein Körper zum Schreiben da."))
    for part in parts:
        if not part.triangles:
            raise ThreeMfError(tr("„{name}“ hat keine Flächen.", name=part.name))
        if part.filament < 1:
            raise ThreeMfError(tr("„{name}“ hat keine gültige Filamentnummer ({number}).", name=part.name,
                                   number=part.filament))
        highest = len(part.vertices) - 1
        if any(index < 0 or index > highest for triangle in part.triangles for index in triangle):
            raise ThreeMfError(tr("„{name}“ verweist auf Punkte, die es nicht gibt.", name=part.name))


def _layout(groups: Sequence[Sequence[Part]], object_name: str) -> list[tuple[int, str, list[tuple[int, Part]]]]:
    """Ids vergeben: erst alle Netze (1..n), danach je Gruppe ein Objekt aus Komponenten."""
    layout = []
    mesh_id = 0
    total = sum(len(group) for group in groups)
    for index, group in enumerate(groups):
        members = []
        for part in group:
            mesh_id += 1
            members.append((mesh_id, part))
        name = object_name if len(groups) == 1 else f"{object_name} {index + 1}"
        layout.append((total + index + 1, name, members))
    return layout


def _model_xml(layout) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="de-DE" xmlns="{CORE_NAMESPACE}" xmlns:BambuStudio="{BAMBU_NAMESPACE}">',
        f' <metadata name="Application">{escape(APPLICATION)}</metadata>',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        " <resources>",
    ]
    for _wrapper, _name, members in layout:
        for object_id, part in members:
            lines.append(f'  <object id="{object_id}" name="{_attribute(part.name)}" type="model">')
            lines.append("   <mesh>")
            lines.append("    <vertices>")
            lines += [f'     <vertex x="{_number(x)}" y="{_number(y)}" z="{_number(z)}"/>'
                      for x, y, z in part.vertices]
            lines.append("    </vertices>")
            lines.append("    <triangles>")
            lines += [f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in part.triangles]
            lines.append("    </triangles>")
            lines.append("   </mesh>")
            lines.append("  </object>")
    for wrapper, name, members in layout:
        lines.append(f'  <object id="{wrapper}" name="{_attribute(name)}" type="model">')
        lines.append("   <components>")
        lines += [f'    <component objectid="{object_id}" transform="{IDENTITY_3X4}"/>' for object_id, _part in members]
        lines.append("   </components>")
        lines.append("  </object>")
    lines += [" </resources>", " <build>"]
    # Kein printable="1": nicht im Kernstandard, lib3mf lehnt es streng ab; Bambu druckt gleich (gemessen 2026-11-08).
    lines += [f'  <item objectid="{wrapper}" transform="{IDENTITY_3X4}"/>' for wrapper, _n, _m in layout]
    lines += [" </build>", "</model>"]
    return "\n".join(lines) + "\n"


def _model_settings_xml(layout) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    for wrapper, name, members in layout:
        lines += [f'  <object id="{wrapper}">',
                  f'    <metadata key="name" value="{_attribute(name)}"/>',
                  f'    <metadata key="extruder" value="{members[0][1].filament}"/>',
                  f'    <metadata face_count="{sum(len(part.triangles) for _id, part in members)}"/>']
        for object_id, part in members:
            lines += [f'    <part id="{object_id}" subtype="normal_part">',
                      f'      <metadata key="name" value="{_attribute(part.name)}"/>',
                      f'      <metadata key="matrix" value="{IDENTITY_4X4}"/>',
                      f'      <metadata key="extruder" value="{part.filament}"/>',
                      f'      <mesh_stat face_count="{len(part.triangles)}" edges_fixed="0" degenerate_facets="0" '
                      'facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
                      "    </part>"]
        lines.append("  </object>")
    lines.append("</config>")
    return "\n".join(lines) + "\n"


def write_3mf(path: str, parts: Sequence[Part], object_name: str | None = None) -> None:
    """Schreibt die Teile in genau dieser Reihenfolge, je Gruppe sich durchdringender Koerper ein Objekt.

    Die Datei entsteht erst vollstaendig, dann am Zielort.
    """
    _check(parts)
    name = object_name or os.path.splitext(os.path.basename(path))[0]
    layout = _layout(grouped_for_objects(parts), name)
    folder = os.path.dirname(os.path.abspath(path))
    handle, temporary = tempfile.mkstemp(suffix=".tmp", dir=folder)
    os.close(handle)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(CONTENT_TYPES_FILE, CONTENT_TYPES_XML)
            archive.writestr(RELATIONSHIPS_FILE, RELATIONSHIPS_XML)
            archive.writestr(MODEL_FILE, _model_xml(layout))
            archive.writestr(MODEL_CONFIG_FILE, _model_settings_xml(layout))
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.remove(temporary)
        raise
