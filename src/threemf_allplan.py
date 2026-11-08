"""Allplan-Seite des 3MF-Austauschs (Allplan 2027): Koerper lesen und Koerper ablegen.

Jeder Schritt ist im laufenden Allplan gemessen (Messreihe G2, 2026-11-06)
oder aus dem gemessenen Vorgaengerprojekt AnimationVR (avr_scene.py) uebernommen.

Lesen (Export)
    Bauteil -> seine Koerper -> Flaechen -> Ringe (Aussen + Loecher) -> Dreiecke -> `Part`, Spalten an den
    Naehten gerundeter Flaechen zugenaeht (threemf_model.sealed).
    Hat ein Bauteil selbst einen Koerper, zaehlt genau der. Nur eine Wand hat keinen: dort zaehlen
    ihre Schichten. In andere Kinder wird NICHT abgestiegen - dort liegen Kopien und Hohlkoerper.

Ablegen (Import)
    Schnitt-Teil (threemf_loft): glatter BRep3D durch Hoehenschnitte, nachgemessen.
    Sonst: `Part` -> Polyhedron3D -> ebene Dreiecke zu sauberen Flaechen zusammenfassen -> BRep3D.
    Ergebnis ist ein "3D-Koerper allgemein" ohne Dreiecks-Diagonalen.
"""

from __future__ import annotations

import logging
from typing import Callable

import NemAll_Python_BaseElements as AllplanBaseEle
import NemAll_Python_BasisElements as AllplanBasisEle
import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_IFW_ElementAdapter as AllplanElementAdapter

from TypeCollections.Curve3DList import Curve3DList

import threemf_geom  # pyright: ignore[reportMissingImports]
from threemf_loft import (  # pyright: ignore[reportMissingImports]
    LoftPlan, Profiles, SPACINGS_MM, aligned_profiles, loft_plan, profile_points)
from threemf_text import tr  # pyright: ignore[reportMissingImports]
from threemf_model import (  # pyright: ignore[reportMissingImports]
    Part, ThreeMfError, Vec3, bounding_box, chain_rings, combined, face_regions, is_closed,
    splice_touching_holes, split_shells, merge_vertices, orient_outward, prepared, repaired_shells, sealed)

RING_JUMP_MM = 1e-3            # Kantenende und Kantenanfang naeher als das gelten als derselbe Punkt
BREP_DENSITY = 0.2             # Annaeherung runder Koerper, Werte aus AnimationVR (nur die Dichte wirkt)
BREP_ANGLE_DEG = 10.0
PREVIEW_MAX_TRIANGLES = 5000   # groessere Teile zeigt die Vorschau als Quader
BREP_MAX_FACES = 5000         # mehr ebene Flaechen = ueberwiegend gerundet: kein BRep (Puzzle1: 95 000, 49 s umsonst)
SPLIT_ABOVE_TRIANGLES = 20000  # groessere Koerper aus mehreren Stuecken je Stueck bauen (Puzzle1: 76 s -> 7 s)
ALLPLAN_MIN_EDGE_MM = 0.0105   # kuerzere Kanten lehnt Allplan ab (Pruefdreieck: 0,0099 nein, 0,01 ja)
MAX_BODY_TRIANGLES = 100000   # hoechstens so viele Dreiecke je Allplan-Koerper: 97 680 gingen, 225 000 stuerzten ab
FACE_CHUNK_TRIANGLES = 20000   # Flaechenstuecke so klein: Allplans Pruefung waechst mehr als linear (184 000: 110 s)
MAX_FACE_SPLITS = 12         # Flaechenkoerper hoechstens so oft halbieren (bis 4096 Stuecke)
NORMALIZE_FACES = 2           # Polyhedron3D.Normalize: fasst ebene Nachbardreiecke zu einer Flaeche zusammen
ALLPLAN_BLACK_WHITE = 1        # Farbe 1: schwarz im Grundriss, weiss in der Animation
LOFT_SCALE = 100.0             # glatte Koerper in dieser Vergroesserung bauen (Allplan scheitert an engen Schnitten)
LOFT_VOLUME_TOLERANCE = 0.005  # glatter Koerper gilt bei hoechstens 0,5 % Volumen- und
LOFT_AREA_TOLERANCE = 0.015    # 1,5 % Oberflaechenabweichung (Rundungen der Kanten sind gestuft angenaehert)
LOFT_SIZE_TOLERANCE_MM = 0.2   # und hoechstens 0,2 mm Abweichung in Laenge, Breite, Hoehe (Kurven schwingen
                               # an engen Rundungen leicht aus: Puzzle1 Teil 4 +0,10 mm bei -0,08 % Volumen)

#: Bauteile ohne eigenen Koerper -> Kindtyp, der die Koerper traegt (gemessen: Wand -> Wandschicht).
BODY_CHILDREN = {"Wall_TypeUUID": "WallTier_TypeUUID"}

#: Volumenkoerper, die Allplan nur ueber Segmentierung annaehert (AnimationVR, gemessen 2026-10-25).
SEGMENTED_SOLIDS = frozenset({"Cylinder3D", "Cone3D", "Cuboid3D", "Ellipsoid3D",
                              "ExtrudedAreaSolid3D", "ClippedSweptSolid3D"})

#: Hohlraeume und Hilfskoerper: haben Geometrie, sind aber Loecher oder Zeichenhilfen - nichts zum Drucken.
#: Liste aus AnimationVR (avr_scene.py, SKIPPED_TYPES); hier gemessen: Window, WindowTier, SlabOpening.
VOID_TYPES = frozenset({
    "Door_TypeUUID", "Window_TypeUUID", "DoorTier_TypeUUID", "WindowTier_TypeUUID",
    "DoorReveal_TypeUUID", "WindowReveal_TypeUUID", "SlabOpening_TypeUUID",
    "NetStorey_TypeUUID", "ArchitectureElevation_TypeUUID",
    "WindowDoor_TypeUUID", "WindowDoorTier_TypeUUID", "WindowDoorReveal_TypeUUID",
    "CornerWindow_TypeUUID", "CornerWindowTier_TypeUUID", "CornerWindowReveal_TypeUUID",
    "Niche_TypeUUID", "NicheTier_TypeUUID", "NicheReveal_TypeUUID",
    "PolygonalNiche_TypeUUID", "PolygonalNicheTier_TypeUUID",
    "Recess_TypeUUID", "RecessTier_TypeUUID", "RecessReveal_TypeUUID",
    "PolygonalRecess_TypeUUID", "PolygonalRecessTier_TypeUUID",
    "BeamPolygonalRecess_TypeUUID", "BeamPolygonalRecessTier_TypeUUID",
    "SlabRecess_TypeUUID", "PrecastSlabRecess_TypeUUID", "PrecastSlabRecessRepresentation_TypeUUID",
    "UserDefinedSolidOpening_TypeUUID", "ArchitectureOpeningPlane_TypeUUID",
    "ClippingPath_TypeUUID", "ClippingPathBody_TypeUUID", "ClippingPathText_TypeUUID",
    "ClippingPathRepresentation_TypeUUID", "UVSClippingPathSymbol_TypeUUID",
    "NicheSmartSymbol_TypeUUID", "RecessSmartSymbol_TypeUUID",
    "SlabOpeningSmartSymbol_TypeUUID", "SlabRecessSmartSymbol_TypeUUID",
    "AttributeContainer_TypeUUID",
})

GROUP_NAME_ATTRIBUTE = 507     # Allplan-Attribut "Bezeichnung" - der Name einer Elementgruppe (live 2026-11-07)
GROUP_SEARCH_DEPTH = 8         # so viele Eltern-Stufen hoch wird nach der Elementgruppe gesucht

LOG = logging.getLogger("threemfstudio.part")

_TYPE_NAMES: dict[str, str] = {}


def type_name(element) -> str:
    """Sprachunabhaengiger Typname des Bauteils ("Wall_TypeUUID"); leer, wenn unbekannt."""
    if not _TYPE_NAMES:
        for name in dir(AllplanElementAdapter):
            if name.endswith("_TypeUUID"):
                _TYPE_NAMES[str(getattr(AllplanElementAdapter, name)).lower()] = name
    return _TYPE_NAMES.get(str(element.GetElementAdapterType().GetGuid()).lower(), "")


# ---------------------------------------------------------------------------------------- Lesen

def _approximated(solid):
    """BRep und andere runde Koerper in ein Polyhedron3D annaehern; None, wenn Allplan es nicht schafft.

    Ein BRep wird dafuer an den Nullpunkt geholt und das Ergebnis zurueckgeschoben: weit draussen zerlegt Allplan
    ungenau (Puzzleteil bei 6,4 m: +0,9 % Volumen, bei 50 m +7 %; am Nullpunkt exakt - live 2026-11-07).
    """
    offset = None
    if type(solid).__name__ in SEGMENTED_SOLIDS:
        settings = AllplanGeo.ApproximationSettings(AllplanGeo.eApproximationSettingsType.ASET_SEGMENTATION)
    else:
        settings = AllplanGeo.ApproximationSettings(AllplanGeo.eApproximationSettingsType.ASET_BREP_TESSELATION)
        settings.SetBRepTesselation(BREP_DENSITY, AllplanGeo.Angle.FromDeg(BREP_ANGLE_DEG), 0, 0)
        if isinstance(solid, AllplanGeo.BRep3D):
            error, reference = solid.GetVertex(0)
            if error == AllplanGeo.eGeometryErrorCode.eOK:
                offset = AllplanGeo.Vector3D(reference.X, reference.Y, reference.Z)
                solid = AllplanGeo.Move(solid, AllplanGeo.Vector3D(-reference.X, -reference.Y, -reference.Z))
    result = AllplanGeo.CreatePolyhedron(solid, settings)
    error, polyhedron = result[0], result[1]
    if error != AllplanGeo.eGeometryErrorCode.eOK or polyhedron is None or polyhedron.GetFacesCount() == 0:
        return None
    if offset is not None:
        back = AllplanGeo.Matrix3D()
        back.SetTranslation(offset)
        polyhedron = AllplanGeo.Transform(polyhedron, back)
    return polyhedron


def _polyhedra(geometry) -> list:
    if geometry is None:
        return []
    solids = []
    for item in (list(geometry) if isinstance(geometry, (list, tuple)) else [geometry]):
        if isinstance(item, AllplanGeo.Polyhedron3D):
            if item.GetFacesCount() > 0:
                solids.append(item)
        elif isinstance(item, AllplanGeo.BRep3D) or type(item).__name__ in SEGMENTED_SOLIDS:
            polyhedron = _approximated(item)
            if polyhedron is not None:
                solids.append(polyhedron)
    return solids


def _own_solids(element) -> list:
    solids = _polyhedra(element.GetModelGeometry())
    return solids or _polyhedra(element.GetPureArchitectureElementGeometry())


def solids_of(element) -> list:
    """Die druckbaren Koerper eines Bauteils als Polyhedron3D; leer bei Hohlraeumen und Bauteilen ohne Koerper."""
    kind = type_name(element)
    if kind in VOID_TYPES:
        return []
    solids = _own_solids(element)
    if solids or kind not in BODY_CHILDREN:
        return solids
    children = AllplanElementAdapter.BaseElementAdapterChildElementsService.GetChildElements(element, False)
    return [solid for child in children if type_name(child) == BODY_CHILDREN[kind] for solid in _own_solids(child)]


def _face_rings(polyhedron, face_index: int) -> list[list[Vec3]]:
    """Die Kanten einer Flaeche als geschlossene Ringe in mm (Aussenrand und Loecher).

    Die Ringe werden aus den Kanten selbst zusammengesetzt (Ende -> passender Anfang): bei verwinkelten Flaechen
    mit Loechern liefert Allplan die Kanten nicht der Reihe nach (Beispiel 3D+PUZZLE, live 2026-11-07).
    """
    segments: list[tuple[Vec3, Vec3]] = []
    for oriented_edge in polyhedron.GetFace(face_index).GetEdges():
        error, start, end = polyhedron.GetEdgeVertices(oriented_edge)
        if error == AllplanGeo.eGeometryErrorCode.eOK:
            segments.append(((start.X, start.Y, start.Z), (end.X, end.Y, end.Z)))
    return chain_rings(segments, RING_JUMP_MM)


def part_from_solids(solids: list, name: str, filament: int) -> tuple[Part, int]:
    """Koerper -> ein Teil in mm, Aussenseite nach aussen; dazu die Zahl der Flaechen, die nicht zerlegbar waren."""
    vertices: list[Vec3] = []
    triangles: list[tuple[int, int, int]] = []
    failed = 0
    for polyhedron in solids:
        for face_index in range(polyhedron.GetFacesCount()):
            regions = face_regions(_face_rings(polyhedron, face_index))
            if not regions:
                failed += 1
                continue
            for outer, holes in regions:
                if not holes and len(outer) == 3:
                    offset = len(vertices)          # ein Dreieck braucht keine Zerlegung
                    vertices += outer
                    triangles.append((offset, offset + 1, offset + 2))
                    continue
                # in Millimetern zerlegen: die Toleranzen von threemf_geom sind fuer Meter gesetzt und strichen an
                # feinen Rundungen Punkte (3D+PUZZLE: bis 20 % Flaeche weg, live 2026-11-07)
                try:
                    points, face_triangles = threemf_geom.triangulate(outer, holes)
                except threemf_geom.GeometryError:
                    try:
                        points, face_triangles = threemf_geom.triangulate(
                            *splice_touching_holes(outer, holes, RING_JUMP_MM))
                    except threemf_geom.GeometryError:
                        failed += 1
                        continue
                offset = len(vertices)
                vertices += points
                triangles += [(a + offset, b + offset, c + offset) for a, b, c in face_triangles]
    if not triangles:
        raise ThreeMfError(tr("„{name}“ hat keinen druckbaren Körper.", name=name))
    # gerundete Koerper zerlegt Allplan je Flaeche fuer sich - an den Naehten bleiben Spalten (sealed)
    return orient_outward(sealed(Part(name, filament, tuple(vertices), tuple(triangles)))), failed


def colour_of(element) -> tuple[int, tuple[int, int, int]]:
    """Allplan-Farbnummer des Bauteils (bei "Farbe von Layer" die des Layers) und ihr Rot/Gruen/Blau."""
    props = element.GetCommonProperties()
    number = int(props.Color)
    if props.ColorByLayer:
        values = list(AllplanBaseEle.CommonProperties.GetColorPenStrokeByLayerFromLayerNumber(int(props.Layer)))
        if len(values) >= 3:
            number = int(values[2])
    argb = AllplanBaseEle.GetColorById(number)
    return number, (int(argb.Red), int(argb.Green), int(argb.Blue))


def group_of(element) -> tuple[str, str]:
    """Kennung und Bezeichnung der Allplan-Elementgruppe, in der das Bauteil steckt; ("", "") ohne Gruppe.

    Die Gruppe haengt nicht direkt am Koerper: dazwischen liegt Allplans Attribut-Huelle ("Erweitertes Element").
    Deshalb geht die Suche die Elternkette hoch (live gemessen 2026-11-07: Koerper -> Huelle -> Elementgruppe).
    Ein Fehler dabei kostet nur die Gruppe, nie den Koerper.
    """
    try:
        if not AllplanElementAdapter.BaseElementAdapterService.IsElementFromElementGroup(element):
            return "", ""
        current = element
        for _level in range(GROUP_SEARCH_DEPTH):
            current = AllplanElementAdapter.BaseElementAdapterParentElementService.GetParentElement(current)
            if current is None or current.IsNull():
                break
            if current.GetElementAdapterType().GetGuid() == AllplanElementAdapter.ElementGroup_TypeUUID:
                return str(current.GetElementUUID()), _group_name(current)
        LOG.info("Koerper %s steckt in einer Gruppe, die Elementgruppe war aber nicht zu finden",
                 element.GetElementUUID())
    except Exception:                                   # Allplan nennt hier keine bestimmte Fehlerart
        LOG.exception("Elementgruppe von %s nicht lesbar", element.GetElementUUID())
    return "", ""


def _group_name(group) -> str:
    for number, value in group.GetAttributes(AllplanBaseEle.eAttibuteReadState.ReadAll):
        if int(number) == GROUP_NAME_ATTRIBUTE:
            return str(value).strip()
    return ""


def palette() -> dict[int, tuple[int, int, int]]:
    """Allplans Farbtabelle 1-255 als Rot/Gruen/Blau (GetColorById, live gleich ColorPenStrokeService, 2026-11-07)."""
    table = {}
    for number in range(1, 256):
        argb = AllplanBaseEle.GetColorById(number)
        table[number] = (int(argb.Red), int(argb.Green), int(argb.Blue))
    return table


HELP_LAYER = "KO_HK"                       # Hilfskonstruktion: Druckplatte, Bauraum - und alles darauf bleibt aus der 3MF


def layer_id(short_name: str, document) -> int:
    """Layer-ID zum Kurznamen; 0 = gibt es im Projekt nicht (GetIDByShortName liefert dann 0, live gemessen in
    AI ModelLink 2026-09-16; Signatur (Kurzname, Dokument) per inspect_symbol 2027)."""
    return int(AllplanBaseEle.LayerService.GetIDByShortName(short_name, document))


def on_layer(element, layer: int) -> bool:
    """True, wenn das Bauteil auf dem Layer mit dieser ID liegt; 0 = kein Layer, nie wahr."""
    return bool(layer) and int(element.GetCommonProperties().Layer) == layer


def layer_name_of(element, document) -> str:
    """Layer des Bauteils als "Kurz (Lang)"."""
    return AllplanBaseEle.LayerService.GetNameByID(int(element.GetCommonProperties().Layer), document.GetDocumentID())


# ---------------------------------------------------------------------------------------- Ablegen

def polyhedron_from_part(part: Part) -> tuple:
    """Vorbereitetes Teil -> (Polyhedron3D in Allplans Ausrichtung, ebene Dreiecke zusammengefasst ja/nein).

    Scheitert das Zusammenfassen (viele winzige, fast ebene Facetten - Beispiel 3D+Printer+Test, "Koerper1173",
    live 2026-11-07: als Dreiecksnetz gueltig, zusammengefasst nicht), bleibt der Koerper ein Dreiecksnetz.
    """
    polyhedron = _polyhedron(part)
    polyhedron.InvertWithFlagUnchanged()
    if polyhedron.Normalize(NORMALIZE_FACES) == AllplanGeo.eGeometryErrorCode.eOK and polyhedron.IsValid():
        return polyhedron, True
    polyhedron = _polyhedron(part)
    polyhedron.InvertWithFlagUnchanged()
    if not polyhedron.IsValid():
        raise ThreeMfError(tr("Aus „{name}“ lässt sich kein gültiger Körper bauen.", name=part.name))
    return polyhedron, False


def _polyhedron(part: Part, kind=None):
    """Das Netz Dreieck fuer Dreieck als Polyhedron3D (noch in 3MF-Ausrichtung)."""
    edges: dict[tuple[int, int], int] = {}
    faces: list[list[tuple[int, bool]]] = []
    for a, b, c in part.triangles:
        face = []
        for start, end in ((a, b), (b, c), (c, a)):
            key = (min(start, end), max(start, end))
            if key not in edges:
                edges[key] = len(edges)
            face.append((edges[key], start < end))
        faces.append(face)
    polyhedron = AllplanGeo.Polyhedron3D(kind or AllplanGeo.PolyhedronType.tVolume, len(part.vertices), len(edges),
                                         len(faces), False)
    builder = AllplanGeo.Polyhedron3DBuilder(polyhedron)
    for x, y, z in part.vertices:
        builder.AppendVertex(AllplanGeo.Point3D(x, y, z))
    for start, end in sorted(edges, key=edges.__getitem__):
        polyhedron.AppendEdge(AllplanGeo.GeometryEdge(start, end))
    for face in faces:
        new_face = polyhedron.CreateFace(len(face))
        for edge_index, forward in face:
            new_face.AppendEdge(AllplanGeo.OrientedEdge(edge_index, forward))
    builder.Complete()
    return polyhedron


def _loft_attempt(plan: LoftPlan, spacing: float):
    """Ein glatter Koerper durch die Schnitte des Plans, am Nullpunkt; None, wenn Allplan ihn nicht baut.

    Mehrere Abschnitte werden einzeln gebaut und vereinigt (MakeUnion fuer zwei BReps). Baut Allplan einen
    Abschnitt mit Kurven nicht, bekommt er Vieleck-Umrisse: senkrechte ebene Streifen statt Dreiecken.
    """
    result = None
    for rings in plan.zones:
        zone = _zone_loft(rings, plan.low, spacing, smooth=True) or _zone_loft(rings, plan.low, spacing, smooth=False)
        if zone is None:
            return None
        if result is None:
            result = zone
            continue
        error, result = AllplanGeo.MakeUnion(result, zone)
        if error != AllplanGeo.eGeometryErrorCode.eOK or result is None:
            return None
    return result


def _profile_curve(points: list, corners: tuple[int, ...], straight: tuple[bool, ...], smooth: bool):
    """Ein Umriss als Allplan-Kurve: glatte geschlossene Kurve, Kette aus Geraden und Kurvenstuecken (bei scharfen
    Ecken) oder Vieleck."""
    if not smooth:
        polyline = AllplanGeo.Polyline3D()
        for point in points + points[:1]:
            polyline += point
        return polyline
    if not corners:
        return AllplanGeo.Spline3D.CreateClosedSpline(points)
    path = AllplanGeo.Path3D()
    for index, first in enumerate(corners):
        last = corners[(index + 1) % len(corners)]
        run = points[first:last + 1] if last > first else points[first:] + points[:last + 1]
        if straight[index] or len(run) == 2:
            path.Add(AllplanGeo.Line3D(run[0], run[-1]))
        else:
            spline = AllplanGeo.Spline3D()
            for point in run:
                spline += point
            path.Add(spline)
    return path


def _zone_loft(rings: tuple[tuple[Vec3, ...], ...], origin: Vec3, spacing: float, smooth: bool):
    profiles = aligned_profiles(rings, spacing) or \
        Profiles(tuple(tuple(profile_points(ring, spacing)) for ring in rings), (), ())
    curves = []
    for profile in profiles.points:
        points = [AllplanGeo.Point3D((x - origin[0]) * LOFT_SCALE, (y - origin[1]) * LOFT_SCALE,
                                     (z - origin[2]) * LOFT_SCALE) for x, y, z in profile]
        curves.append(_profile_curve(points, profiles.corners, profiles.straight, smooth))
    error, brep = AllplanGeo.CreateLoftedBRep3D(Curve3DList(curves), Curve3DList(), True, False, True, False)
    if error != AllplanGeo.eGeometryErrorCode.eOK or brep is None:
        return None
    shrink = AllplanGeo.Matrix3D()
    shrink.Scaling(1.0 / LOFT_SCALE, 1.0 / LOFT_SCALE, 1.0 / LOFT_SCALE)
    return AllplanGeo.Transform(brep, shrink)


def _loft_matches(brep, plan: LoftPlan) -> bool:
    """Stimmt der glatte Koerper mit dem Netz ueberein? Volumen und Oberflaeche (Allplans genaue Rechnung,
    am Zylinder 3140 statt 3141,6 mm3) und die Groesse seiner Zerlegung."""
    if not brep.IsValid():
        return False
    mass = AllplanGeo.CalcMass(brep)
    if mass[0] != AllplanGeo.eGeometryErrorCode.eOK:
        return False
    volume, area = abs(float(mass[1])), float(mass[2])
    if abs(volume - plan.volume) > LOFT_VOLUME_TOLERANCE * plan.volume or \
            abs(area - plan.area) > LOFT_AREA_TOLERANCE * plan.area:
        return False
    polyhedron = _approximated(brep)
    if polyhedron is None:
        return False
    box, result = AllplanGeo.CalcMinMax(polyhedron)
    if result != AllplanGeo.eServiceResult.NO_ERR:
        return False
    measured = (box.GetSizeX(), box.GetSizeY(), box.GetSizeZ())
    wanted = tuple(plan.high[k] - plan.low[k] for k in range(3))
    return all(abs(a - b) <= LOFT_SIZE_TOLERANCE_MM for a, b in zip(measured, wanted))


def smooth_solid(part: Part):
    """Glatter BRep3D fuer ein Schnitt-Teil (siehe threemf_loft) - oder None, dann baut der normale Weg.

    Allplan baut den Koerper nur, wenn die Schnitte weit genug auseinander liegen (0,25 mm: nein, 1,2 mm: ja),
    deshalb in hundertfacher Groesse und danach verkleinert (live 2026-11-07). Gebaut wird am Nullpunkt, erst
    der gepruefte Koerper wandert an seinen Platz. Mehrere Punktabstaende werden versucht, der erste, der
    nachgemessen stimmt, gilt.
    """
    plan = loft_plan(part)
    if plan is None:
        return None
    plans = [plan]
    if len(plan.zones) > 1:
        whole = loft_plan(part, split_steps=False)      # kleine Absaetze baut Allplan oft lieber in einem Zug (ksr)
        if whole is not None:
            plans.append(whole)
    for candidate in plans:
        for spacing in SPACINGS_MM:
            brep = _loft_attempt(candidate, spacing)
            if brep is not None and _loft_matches(brep, candidate):
                return AllplanGeo.Move(brep, AllplanGeo.Vector3D(*candidate.low))
    return None


def solid_from_part(part: Part, prepare: bool = True):
    """Teil -> sauberer BRep3D ("immer BRep", Entscheidung 2026-11-07): glatt bei Schnitt-Teilen, sonst mit
    zusammengefassten ebenen Flaechen.

    Ein Polyhedron3D bleibt nur, wenn Allplan keinen BRep baut, oder wenn das Netz ueberwiegend gerundet ist
    und kein Schnitt-Teil. `prepare=False` fuer schon reparierte Stuecke: Vorbereiten legte ihre verdoppelten
    Punkte wieder zusammen.
    """
    ready = prepared(part) if prepare else part
    smooth = smooth_solid(ready)
    if smooth is not None:
        return smooth
    polyhedron, merged = polyhedron_from_part(ready)
    if not merged or polyhedron.GetFacesCount() > BREP_MAX_FACES:
        return polyhedron           # Dreiecksnetz oder ueberwiegend gerundet: ein BRep kostet nur Zeit (Puzzle1)
    error, brep = AllplanGeo.CreateBRep3D(polyhedron)
    if error == AllplanGeo.eGeometryErrorCode.eOK and brep is not None and brep.IsValid():
        return brep
    return polyhedron


def preview_element(part: Part, colour: int):
    """Ein schneller Koerper fuer die Vorschau am Mauszeiger.

    Kleine Teile zeigen ihre Form (Flaechen, ohne Volumenpruefung); grosse nur ihren umschliessenden Quader:
    Allplan prueft einen Flaechenkoerper aus 184 000 Dreiecken 110 s lang und lehnt ihn dann ab (Puzzle1,
    live 2026-11-07). None, wenn Allplan auch das ablehnt - dann fehlt der Koerper nur in der Vorschau.
    """
    if len(part.triangles) > PREVIEW_MAX_TRIANGLES:
        low, high = bounding_box([part])
        geometry = AllplanGeo.Polyhedron3D.CreateCuboid(AllplanGeo.Point3D(*low), AllplanGeo.Point3D(*high))
        return AllplanBasisEle.ModelElement3D(_props(colour), geometry)
    polyhedron = _faces_polyhedron(merge_vertices(part))
    return None if polyhedron is None else AllplanBasisEle.ModelElement3D(_props(colour), polyhedron)


def _faces_polyhedron(part: Part):
    polyhedron = _polyhedron(part, AllplanGeo.PolyhedronType.tFaces)
    polyhedron.InvertWithFlagUnchanged()
    return polyhedron if polyhedron.IsValid() else None


def _subset(part: Part, triangles: list) -> Part:
    used = sorted({index for triangle in triangles for index in triangle})
    renumber = {old: new for new, old in enumerate(used)}
    return Part(part.name, part.filament, tuple(part.vertices[index] for index in used),
                tuple((renumber[a], renumber[b], renumber[c]) for a, b, c in triangles), part.colour)


def _loose_triangles(part: Part) -> Part:
    """Jedes Dreieck mit eigenen Eckpunkten (keine gemeinsamen Kanten); Dreiecke mit Flaeche null entfallen.

    Fuer Netze, an deren Kanten mehr als zwei Dreiecke haengen (Beispiel Nick Stress test: bis zu 11) - die lehnt
    Allplan auch als Flaechenkoerper ab, egal wie klein das Stueck ist. Aussehen gleich, nur ohne Verbindung;
    Dreiecke mit einer Kante unter 0,01 mm entfallen (unsichtbar, und Allplan lehnt sie ab).
    """
    vertices: list[Vec3] = []
    triangles: list[tuple[int, int, int]] = []
    for a, b, c in part.triangles:
        points = (part.vertices[a], part.vertices[b], part.vertices[c])
        u = [points[1][k] - points[0][k] for k in range(3)]
        v = [points[2][k] - points[0][k] for k in range(3)]
        cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        shortest = min(sum((points[i][k] - points[(i + 1) % 3][k]) ** 2 for k in range(3)) for i in range(3)) ** 0.5
        if sum(value * value for value in cross) <= 1e-12 or shortest < ALLPLAN_MIN_EDGE_MM:
            continue                                    # unsichtbar klein - Allplan lehnt es ab (Kante < 0,01 mm)
        offset = len(vertices)
        vertices += points
        triangles.append((offset, offset + 1, offset + 2))
    return Part(part.name, part.filament, tuple(vertices), tuple(triangles), part.colour)


def face_bodies(part: Part, depth: int = 0) -> list:
    """Letzter Weg: Koerper aus reinen Flaechen (PolyhedronType.tFaces), ohne Volumenpruefung - sie sehen gleich aus.

    Lehnt Allplan das ganze Netz ab, wird es raeumlich halbiert, bis jedes Stueck angenommen wird (Beispiel
    torture test, Body18: ganz abgelehnt, jede Haelfte angenommen - live 2026-11-07, Grund nicht benannt).
    Stuecke ueber FACE_CHUNK_TRIANGLES werden ungeprueft geteilt: grosse prueft Allplan sehr langsam oder stuerzt ab.
    """
    if len(part.triangles) <= FACE_CHUNK_TRIANGLES:
        polyhedron = _faces_polyhedron(part)
        if polyhedron is not None:
            return [polyhedron]
    if depth >= MAX_FACE_SPLITS or len(part.triangles) < 2:
        loose = _loose_triangles(part)
        if not loose.triangles:
            return []                                   # nur Dreiecke mit Flaeche null - nichts zu zeigen
        polyhedron = _faces_polyhedron(loose)
        if polyhedron is not None:
            return [polyhedron]
        raise ThreeMfError(tr("Aus „{name}“ lässt sich auch kein Flächenkörper bauen.", name=part.name))
    low, high = bounding_box([part])
    axis = max(range(3), key=lambda k: high[k] - low[k])
    centres = sorted((sum(part.vertices[i][axis] for i in triangle), triangle) for triangle in part.triangles)
    half = len(centres) // 2
    first, second = [t for _c, t in centres[:half]], [t for _c, t in centres[half:]]
    return face_bodies(_subset(part, first), depth + 1) + face_bodies(_subset(part, second), depth + 1)


def import_geometries(part: Part, on_piece: Callable[[int, int], None] | None = None) \
        -> tuple[list[tuple[object, Part | None]], bool]:
    """Die Allplan-Geometrien fuer ein Teil der Datei, je mit dem Netz fuer "3MF schreiben"; dazu: nur Flaechen?

    `on_piece(n, gesamt)` meldet vor jedem Stueck eines mehrteiligen Teils den Fortschritt (Ladefenster).

    0. sehr grosse Teile aus mehreren geschlossenen Stuecken: je Stueck ein Koerper (schneller)
    1. das Teil, wie es ist (Normalfall)  2. repariert, als ein Koerper (Beispiel Gitterpyramide: doppelte
    Innenflaechen, Staebe, die sich an Kanten beruehren)  3. repariert und in Stuecke getrennt - jedes Stueck ein
    Koerper  4. Flaechenkoerper; das erste Stueck traegt das ganze Teil, die uebrigen (None) zeigen nur.
    Kein Allplan-Koerper bekommt mehr als MAX_BODY_TRIANGLES Dreiecke: Allplan stuerzte beim Pruefen eines
    Benchy aus 225 000 Dreiecken in einem Stueck ab (Stapelueberlauf, live 2026-11-07). Solche Teile gehen
    gleich als Flaechenstuecke nach Allplan.
    """
    if len(part.triangles) > SPLIT_ABOVE_TRIANGLES:
        # Allplans Zusammenfassen ebener Flaechen waechst mehr als linear: acht Puzzleteile in einem Netz brauchen
        # zusammen 76 s, einzeln 7 s (Puzzle1, live 2026-11-07). Nur wenn jedes Stueck fuer sich geschlossen ist.
        pieces = split_shells(prepared(part))
        if len(pieces) > 1 and all(is_closed(piece) and len(piece.triangles) <= MAX_BODY_TRIANGLES
                                   for piece in pieces):
            try:
                built = []
                for index, piece in enumerate(pieces):
                    if on_piece is not None:
                        on_piece(index + 1, len(pieces))
                    built.append((solid_from_part(piece, prepare=False), piece))
                return built, False
            except ThreeMfError:
                pass
    if len(part.triangles) > MAX_BODY_TRIANGLES:
        bodies = face_bodies(orient_outward(prepared(part)))
        return [(body, part if index == 0 else None) for index, body in enumerate(bodies)], True
    try:
        return [(solid_from_part(part), part)], False
    except ThreeMfError:
        pass
    shells = repaired_shells(part)
    whole = combined(shells)
    try:
        return [(solid_from_part(whole, prepare=False), whole)], False
    except ThreeMfError:
        pass
    try:
        return [(solid_from_part(shell, prepare=False), shell) for shell in shells], False
    except ThreeMfError:
        pass
    bodies = face_bodies(orient_outward(whole))
    return [(body, part if index == 0 else None) for index, body in enumerate(bodies)], True


def _props(colour: int | None, layer: int = 0):
    props = AllplanBaseEle.CommonProperties()
    props.GetGlobalProperties()
    if colour is not None:
        props.ColorByLayer = False
        props.Color = colour
    if layer:
        props.Layer = layer
    return props


def model_element(part: Part, colour: int | None = None):
    """Ein ablagefaehiger 3D-Koerper fuer ein gutes Teil; `colour` ist eine Allplan-Farbnummer."""
    return AllplanBasisEle.ModelElement3D(_props(colour), solid_from_part(part))


def plate_elements(box: tuple, lines: list, plate_colour: int, line_colour: int, layer: int = 0) -> list:
    """Druckplatte als Koerper (Quader aus `box` = (Ecke, Ausdehnung)) und Bauraum-Kanten als 3D-Linien,
    auf dem Layer `layer` (ID; 0 = eingestellter Layer).

    Quader: BRep3D.CreateCuboid (live 2026-11-07); 3D-Linie: ModelElement3D mit Polyline3D (AI ModelLink
    create_polyline mit raum=1)."""
    (x, y, z), (dx, dy, dz) = box
    cuboid = AllplanGeo.BRep3D.CreateCuboid(AllplanGeo.AxisPlacement3D(AllplanGeo.Point3D(x, y, z)), dx, dy, dz)
    elements = [AllplanBasisEle.ModelElement3D(_props(plate_colour, layer), cuboid)]
    for points in lines:
        line = AllplanGeo.Polyline3D()
        for px, py, pz in points:
            line += AllplanGeo.Point3D(px, py, pz)
        elements.append(AllplanBasisEle.ModelElement3D(_props(line_colour, layer), line))
    return elements


def model_elements(part: Part, colour: int | None = None, on_piece: Callable[[int, int], None] | None = None) \
        -> tuple[list[tuple[object, Part | None]], bool]:
    """Die ablagefaehigen 3D-Koerper fuer ein Teil der Datei (siehe import_geometries), je mit seinem Netz."""
    geometries, faces_only = import_geometries(part, on_piece)
    return [(AllplanBasisEle.ModelElement3D(_props(colour), geometry), piece) for geometry, piece in geometries], \
        faces_only
