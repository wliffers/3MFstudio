"""Netz-Modell fuer den 3MF-Austausch - reine Rechnung, kein Allplan.

Ein `Part` ist ein Koerper als Dreiecksnetz in Millimetern, mit Namen und Filamentnummer. Die
Funktionen hier bereiten eine Teileliste fuer die Datei vor: Aussenseite nach aussen drehen,
verkleinern, auf die Druckplatte stellen, Reihenfolge fuer ueberlappende Koerper festlegen.

Gemessene Grundlagen (Messreihen G1 und G2, 2026-11-06):
- Allplan liefert Koerper meist mit nach innen zeigender Aussenseite -> am Volumen ausrichten.
- In Bambu Studio bekommt das SPAETERE Teil eines Objekts den gemeinsamen Bereich -> groesster
  Koerper zuerst, kleinster zuletzt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Sequence

Vec3 = tuple[float, float, float]
Triangle = tuple[int, int, int]

BUILD_VOLUME_MM = 256.0          # Bambu A1: 256 x 256 x 256 mm
PLATE_CENTRE_MM = (128.0, 128.0)
MAX_FILAMENTS = 16               # Bambu-Projekte mit bis zu 16 Filamenten (Beispiel "AMS test 16 colors")
OVERLAP_TOLERANCE_MM = 0.01      # kleinerer Abstand gilt als Beruehren
SLIVER_TOLERANCE_MM = 1e-4       # liegt eine Ecke so nah an der Gegenkante, hat das Dreieck die Flaeche null
MAX_HOLE_EDGES = 64             # groessere Loecher werden nicht geflickt (dann eher Flaechenkoerper)
WELD_TOLERANCE_MM = 0.02         # Allplan lehnt Kanten um 0,01 mm ab: 0,0099 nein, 0,01 ja (Pruefdreieck), in Netzen
                                 # aber auch noch 0,0108-0,0129 (3D_Printer_test) - gemessen 2026-11-07
MERGE_DIGITS = 6                # Punkte, die sich erst ab der 6. Nachkommastelle unterscheiden, sind einer
T_JUNCTION_MM = 1e-4             # Randpunkt so nah an einer offenen Kante: die Kante wird dort geteilt
CRACK_MAX_WIDTH_MM = 0.5         # schmalere Spalten schliesst "sealed" (Allplans Naehte: bis ~0,3 mm breit)


class ThreeMfError(ValueError):
    """Eine 3MF-Datei laesst sich nicht schreiben oder nicht lesen; der Text sagt dem Anwender, warum."""


@dataclass(frozen=True)
class Part:
    """Ein Koerper: Punkte in mm, Dreiecke als Punktnummern, von aussen gegen den Uhrzeigersinn.

    `colour` ist die Farbe seines Filaments als "#RRGGBB", soweit bekannt (beim Lesen aus Bambus Projekt);
    in die Datei schreibt der Schreiber sie nicht (Bambu loescht sonst die Filamentnummern, G1).
    """
    name: str
    filament: int
    vertices: tuple[Vec3, ...]
    triangles: tuple[Triangle, ...]
    colour: str = ""


def signed_volume(part: Part) -> float:
    """Volumen in mm3; positiv, wenn die Dreiecke von aussen gegen den Uhrzeigersinn laufen."""
    total = 0.0
    for a, b, c in part.triangles:
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = part.vertices[a], part.vertices[b], part.vertices[c]
        total += x1 * (y2 * z3 - y3 * z2) - y1 * (x2 * z3 - x3 * z2) + z1 * (x2 * y3 - x3 * y2)
    return total / 6.0


def orient_outward(part: Part) -> Part:
    """Dreht ein nach innen gewendetes Netz um (Allplan liefert Koerper meist so)."""
    if signed_volume(part) >= 0.0:
        return part
    return replace(part, triangles=tuple((a, c, b) for a, b, c in part.triangles))


def is_closed(part: Part) -> bool:
    """Jede Kante gehoert zu genau zwei Dreiecken, einmal in jeder Richtung."""
    directed: dict[tuple[int, int], int] = {}
    for a, b, c in part.triangles:
        for edge in ((a, b), (b, c), (c, a)):
            directed[edge] = directed.get(edge, 0) + 1
    return bool(directed) and all(count == 1 and directed.get((end, start)) == 1
                                  for (start, end), count in directed.items())


def merge_vertices(part: Part) -> Part:
    """Gleiche Punkte zusammenlegen; entartete Dreiecke entfallen. Erst danach ist `is_closed` aussagekraeftig."""
    index_of: dict[Vec3, int] = {}
    vertices: list[Vec3] = []
    mapping: list[int] = []
    for vertex in part.vertices:
        key = (round(vertex[0], MERGE_DIGITS), round(vertex[1], MERGE_DIGITS), round(vertex[2], MERGE_DIGITS))
        if key not in index_of:
            index_of[key] = len(vertices)
            vertices.append(key)
        mapping.append(index_of[key])
    triangles = [(mapping[a], mapping[b], mapping[c]) for a, b, c in part.triangles]
    triangles = [t for t in triangles if len(set(t)) == 3]
    return replace(part, vertices=tuple(vertices), triangles=tuple(triangles))


def weld_short_edges(part: Part, tolerance: float = WELD_TOLERANCE_MM) -> Part:
    """Kanten kuerzer als `tolerance` mm zu einem Punkt zusammenziehen; dabei flach gewordene Dreiecke entfallen.

    Allplan lehnt Kanten unter 0,01 mm ab (Beispiele 3D+Printer+Test, "Koerper1173": 0,000025 mm; torture test,
    "Body18": 0,009998 mm; Grenze live gemessen 2026-11-07). Nur fuer den Weg nach Allplan, nie fuer die Datei.
    Zwei Dreiecke, die danach dieselben drei Punkte haben, heben sich auf und entfallen beide.
    """
    parent = list(range(len(part.vertices)))
    radius = [0.0] * len(part.vertices)                  # groesster Abstand eines Gruppenpunkts zu seinem Vertreter

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def distance(a: int, b: int) -> float:
        p, q = part.vertices[a], part.vertices[b]
        return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2) ** 0.5

    edges = sorted({(min(a, b), max(a, b)) for t in part.triangles for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0]))
                    if distance(a, b) < tolerance}, key=lambda edge: distance(*edge))
    joined = False
    for start, end in edges:
        keep, gone = root(start), root(end)
        if keep == gone:
            continue
        # Nie verketten: jeder Punkt bleibt naeher als `tolerance` an seinem Vertreter. Sonst fiel ein Bogen aus
        # vielen kurzen Kanten zu einem Punkt zusammen (Nick Stress test: 166 000 -> 33 000 Dreiecke, 2026-11-07).
        reach = distance(keep, gone) + radius[gone]
        if reach >= tolerance:
            continue
        parent[gone] = keep
        radius[keep] = max(radius[keep], reach)
        joined = True
    if not joined:
        return part
    triangles = [(root(a), root(b), root(c)) for a, b, c in part.triangles]
    triangles = [t for t in triangles if len(set(t)) == 3]
    seen: dict[frozenset, int] = {}
    for t in triangles:
        seen[frozenset(t)] = seen.get(frozenset(t), 0) + 1
    triangles = [t for t in triangles if seen[frozenset(t)] == 1]
    used = sorted({index for t in triangles for index in t})
    renumber = {old: new for new, old in enumerate(used)}
    return replace(part, vertices=tuple(part.vertices[index] for index in used),
                   triangles=tuple((renumber[a], renumber[b], renumber[c]) for a, b, c in triangles))


def _rotations(triangle: Triangle) -> set[Triangle]:
    a, b, c = triangle
    return {(a, b, c), (b, c, a), (c, a, b)}


def drop_duplicate_faces(part: Part) -> Part:
    """Doppelte Dreiecke: gleich gerichtete bleiben einmal, gegenlaeufige Paare (Innenflaechen) entfallen beide."""
    groups: dict[frozenset, list[Triangle]] = {}
    for triangle in part.triangles:
        groups.setdefault(frozenset(triangle), []).append(triangle)
    kept: list[Triangle] = []
    for triangle in part.triangles:
        group = groups.get(frozenset(triangle))
        if group is None:
            continue
        del groups[frozenset(triangle)]
        first = _rotations(group[0])
        surplus = sum(1 if candidate in first else -1 for candidate in group)
        if surplus > 0:
            kept.append(group[0])
        elif surplus < 0:
            kept.append(next(candidate for candidate in group if candidate not in first))
    return replace(part, triangles=tuple(kept))


def _edge_pairs(part: Part) -> dict[tuple[int, int], int]:
    """Gerichtete Kante (Dreieck, Stelle) -> Partnerdreieck. An Kanten mit mehr als zwei Dreiecken (Koerper
    beruehren sich entlang einer Linie) wird nach der Lage um die Kante gepaart: Partner ist das Dreieck, das mit
    ihm dasselbe Material umschliesst."""
    owners: dict[frozenset, list[tuple[int, int, int, int]]] = {}
    for index, triangle in enumerate(part.triangles):
        for slot in range(3):
            start, end, third = triangle[slot], triangle[(slot + 1) % 3], triangle[(slot + 2) % 3]
            owners.setdefault(frozenset((start, end)), []).append((index, start, end, third))
    partner: dict[tuple[int, int], int] = {}
    for faces in owners.values():
        if len(faces) == 2:
            (i, s1, _e1, _t1), (j, s2, _e2, _t2) = faces
            if s1 != s2:
                partner[(i, s1)], partner[(j, s2)] = j, i
            continue
        if len(faces) < 4 or len(faces) % 2:
            continue
        low = min(faces[0][1], faces[0][2])
        high = max(faces[0][1], faces[0][2])
        a, b = part.vertices[low], part.vertices[high]
        axis = [b[k] - a[k] for k in range(3)]
        length = sum(v * v for v in axis) ** 0.5
        if length <= 0.0:
            continue
        axis = [v / length for v in axis]
        helper = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.9 else (0.0, 1.0, 0.0)
        first = [helper[1] * axis[2] - helper[2] * axis[1], helper[2] * axis[0] - helper[0] * axis[2],
                 helper[0] * axis[1] - helper[1] * axis[0]]
        norm = sum(v * v for v in first) ** 0.5
        first = [v / norm for v in first]
        second = [axis[1] * first[2] - axis[2] * first[1], axis[2] * first[0] - axis[0] * first[2],
                  axis[0] * first[1] - axis[1] * first[0]]

        def angle(face) -> float:
            t = part.vertices[face[3]]
            offset = [t[k] - a[k] for k in range(3)]
            return math.atan2(sum(offset[k] * second[k] for k in range(3)), sum(offset[k] * first[k] for k in range(3)))

        ordered = sorted(faces, key=angle)
        # Material liegt zwischen einem Dreieck mit Kante high->low und dem naechsten (gegen den Uhrzeigersinn)
        # mit Kante low->high.
        for position, face in enumerate(ordered):
            following = ordered[(position + 1) % len(ordered)]
            if face[1] == high and following[1] == low:
                partner[(face[0], face[1])], partner[(following[0], following[1])] = following[0], face[0]
    return partner


def split_nonmanifold(part: Part) -> Part:
    """Kanten und Punkte, an denen sich Koerperteile nur beruehren, verdoppeln - jedes Teil bekommt eigene Punkte.

    Danach gehoert jede Kante zu genau zwei Dreiecken (Beispiel torture test, Body18/Body19: vier Dreiecke an
    einer Kante). Die Kopien bleiben am selben Ort - Allplan nimmt das an (live 2026-11-07, Body18 als BRep).
    """
    partner = _edge_pairs(part)
    incident: dict[int, list[int]] = {}
    for index, triangle in enumerate(part.triangles):
        for vertex in triangle:
            incident.setdefault(vertex, []).append(index)
    vertices = list(part.vertices)
    copy_of: dict[tuple[int, int], int] = {}             # (Dreieck, Punkt) -> Punktnummer fuer dieses Dreieck
    for vertex, faces in incident.items():
        remaining = set(faces)
        first_fan = True
        while remaining:
            seed = remaining.pop()
            fan, stack = [seed], [seed]
            while stack:
                current = stack.pop()
                triangle = part.triangles[current]
                slot = triangle.index(vertex)
                for start in (triangle[slot], triangle[(slot + 2) % 3]):     # beide Kanten am Punkt
                    neighbour = partner.get((current, start))
                    if neighbour in remaining:
                        remaining.discard(neighbour)
                        fan.append(neighbour)
                        stack.append(neighbour)
            number = vertex
            if not first_fan:
                number = len(vertices)
                vertices.append(part.vertices[vertex])
            first_fan = False
            for face in fan:
                copy_of[(face, vertex)] = number
    triangles = tuple(tuple(copy_of[(index, vertex)] for vertex in triangle)
                      for index, triangle in enumerate(part.triangles))
    return replace(part, vertices=tuple(vertices), triangles=triangles)  # type: ignore[arg-type]


def split_shells(part: Part) -> list[Part]:
    """Das Netz in seine Stuecke trennen; verbunden sind Dreiecke nur ueber Kanten mit genau einem Gegenstueck.

    Eine Kante, an der sich vier Dreiecke treffen (zwei Wuerfel beruehren sich an einer Kante), trennt die Stuecke.
    """
    directed: dict[tuple[int, int], list[int]] = {}
    for index, (a, b, c) in enumerate(part.triangles):
        for edge in ((a, b), (b, c), (c, a)):
            directed.setdefault(edge, []).append(index)
    parent = list(range(len(part.triangles)))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for (start, end), owners in directed.items():
        partners = directed.get((end, start), [])
        if len(owners) == 1 and len(partners) == 1:
            parent[root(owners[0])] = root(partners[0])
    groups: dict[int, list[Triangle]] = {}
    for index, triangle in enumerate(part.triangles):
        groups.setdefault(root(index), []).append(triangle)
    shells = []
    for triangles in groups.values():
        used = sorted({index for triangle in triangles for index in triangle})
        renumber = {old: new for new, old in enumerate(used)}
        shells.append(replace(part, vertices=tuple(part.vertices[index] for index in used),
                              triangles=tuple((renumber[a], renumber[b], renumber[c]) for a, b, c in triangles)))
    return shells


def fill_holes(part: Part, largest: int = MAX_HOLE_EDGES) -> Part:
    """Loecher schliessen, deren Rand ein einfacher Ring aus hoechstens `largest` Kanten ist (Faecher-Dreiecke).

    Typisch: ein fehlendes Dreieck (Beispiel 3D+PUZZLE). Verzweigte oder groessere Raender bleiben offen.
    """
    directed: dict[tuple[int, int], int] = {}
    for a, b, c in part.triangles:
        for edge in ((a, b), (b, c), (c, a)):
            directed[edge] = directed.get(edge, 0) + 1
    boundary = [edge for edge, count in directed.items() if count == 1 and (edge[1], edge[0]) not in directed]
    following: dict[int, list[int]] = {}
    for start, end in boundary:
        following.setdefault(start, []).append(end)
    added: list[Triangle] = []
    visited: set[tuple[int, int]] = set()
    for first in boundary:
        if first in visited:
            continue
        loop, edge, simple = [first[0]], first, True
        while True:
            visited.add(edge)
            if edge[1] == loop[0]:
                break
            loop.append(edge[1])
            candidates = [end for end in following.get(edge[1], []) if (edge[1], end) not in visited]
            if len(candidates) != 1 or len(loop) > largest:
                simple = False
                break
            edge = (edge[1], candidates[0])
        if simple and len(loop) >= 3 and len(set(loop)) == len(loop):
            added += [(loop[0], loop[index + 1], loop[index]) for index in range(1, len(loop) - 1)]
    return replace(part, triangles=part.triangles + tuple(added)) if added else part


def prepared(part: Part) -> Part:
    """Fuer Allplan vorbereitet: gleiche und fast gleiche Punkte vereint, Nullflaechen weg, Aussenseite aussen."""
    return orient_outward(drop_slivers(weld_short_edges(merge_vertices(part))))


def repaired_shells(part: Part) -> list[Part]:
    """Fuer Allplan repariert: Innenflaechen weg, in Stuecke getrennt, kleine Loecher zu, je Stueck vorbereitet."""
    whole = split_nonmanifold(drop_duplicate_faces(weld_short_edges(merge_vertices(part))))
    return [orient_outward(drop_slivers(fill_holes(shell))) for shell in split_shells(whole)]


def chain_rings(segments: Sequence[tuple[Vec3, Vec3]], tolerance: float) -> list[list[Vec3]]:
    """Gerichtete Kanten in beliebiger Reihenfolge -> geschlossene Ringe (je Ring die Anfangspunkte der Kanten).

    Ein Ende passt zu einem Anfang, wenn beide auf `tolerance` mm gleich sind. Ringe mit weniger als drei Punkten
    entfallen.
    """
    def key(point: Vec3) -> tuple[int, int, int]:
        return (round(point[0] / tolerance), round(point[1] / tolerance), round(point[2] / tolerance))

    starting: dict[tuple[int, int, int], list[int]] = {}
    for index, (start, _end) in enumerate(segments):
        starting.setdefault(key(start), []).append(index)
    unused = set(range(len(segments)))
    rings: list[list[Vec3]] = []
    for first in range(len(segments)):
        if first not in unused:
            continue
        unused.discard(first)
        ring = [segments[first][0]]
        current = first
        while key(segments[current][1]) != key(segments[first][0]):
            following = next((index for index in starting.get(key(segments[current][1]), []) if index in unused), None)
            if following is None:
                break
            unused.discard(following)
            ring.append(segments[following][0])
            current = following
        rings += [loop for loop in _split_at_pinches(ring, key) if len(loop) >= 3]
    return rings


def _split_at_pinches(ring: list[Vec3], key) -> list[list[Vec3]]:
    """Ein Umriss, der sich in einem Punkt selbst beruehrt (eine Acht), wird dort in einfache Ringe geteilt."""
    loops: list[list[Vec3]] = []
    stack: list[Vec3] = []
    seen: dict = {}
    for point in ring:
        k = key(point)
        if k in seen:
            start = seen[k]
            loops.append(stack[start:])
            for removed in stack[start + 1:]:
                seen.pop(key(removed), None)
            del stack[start + 1:]
            continue
        seen[k] = len(stack)
        stack.append(point)
    loops.append(stack)
    return loops


def _newell(ring: Sequence[Vec3]) -> tuple[float, float, float]:
    nx = ny = nz = 0.0
    for index, (x1, y1, z1) in enumerate(ring):
        x2, y2, z2 = ring[(index + 1) % len(ring)]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return nx, ny, nz


def _signed_area_2d(ring: Sequence[Vec3], u: int, v: int) -> float:
    return 0.5 * sum(ring[i][u] * ring[(i + 1) % len(ring)][v] - ring[(i + 1) % len(ring)][u] * ring[i][v]
                     for i in range(len(ring)))


def _inside_2d(point: Vec3, ring: Sequence[Vec3], u: int, v: int) -> bool:
    inside = False
    for index in range(len(ring)):
        a, b = ring[index], ring[index - 1]
        if (a[v] > point[v]) != (b[v] > point[v]):
            if point[u] < (b[u] - a[u]) * (point[v] - a[v]) / (b[v] - a[v]) + a[u]:
                inside = not inside
    return inside


def face_regions(rings: Sequence[list[Vec3]]) -> list[tuple[list[Vec3], list[list[Vec3]]]]:
    """Die gerichteten Ringe einer ebenen Flaeche -> (Aussenrand, Loecher) je zusammenhaengendem Stueck.

    Die Umlaufrichtung entscheidet: Aussenraender laufen wie der groesste Ring, Loecher andersherum (so liefert
    Allplan Flaechen, von aussen gesehen gegen den Uhrzeigersinn). Ein Loch gehoert zum kleinsten groesseren
    Aussenrand, der es umschliesst - auch wenn es ihn in einem Punkt beruehrt (3D+PUZZLE, live 2026-11-07).
    """
    if not rings:
        return []
    normal = _newell(max(rings, key=lambda ring: sum(c * c for c in _newell(ring))))
    drop = max(range(3), key=lambda axis: abs(normal[axis]))
    u, v = [axis for axis in range(3) if axis != drop]
    sign = 1.0 if normal[drop] >= 0.0 else -1.0
    if drop == 1:
        sign = -sign                                     # (z, x) statt (x, z): die Projektion spiegelt
    outers, holes = [], []
    for ring in rings:
        area = sign * _signed_area_2d(ring, u, v)
        (outers if area > 0.0 else holes).append((abs(area), ring))
    outers.sort(key=lambda entry: entry[0])
    regions = {id(ring): (ring, []) for _area, ring in outers}
    for hole_area, hole in holes:
        inner = [point for point in hole if not any(point in ring for _a, ring in outers)] or hole
        centre = tuple(sum(point[axis] for point in inner) / len(inner) for axis in range(3))
        owner = next((ring for area, ring in outers                                    # Insel im Loch zaehlt nicht
                      if area > hole_area and _inside_2d(centre, ring, u, v)), None)  # type: ignore[arg-type]
        if owner is not None:
            regions[id(owner)][1].append(hole)
    return list(regions.values())


def splice_touching_holes(outer: list[Vec3], holes: list[list[Vec3]],
                          tolerance: float) -> tuple[list[Vec3], list[list[Vec3]]]:
    """Loecher, die den Aussenrand in einem Punkt beruehren, dort in den Rand einfuegen (ein Umriss statt zwei).

    Die Zerlegung mit Bruecken kommt mit einem Loch am Rand nicht zurecht (3D+PUZZLE, drei Flaechen); als ein
    Umriss, der den Beruehrpunkt zweimal besucht, schon.
    """
    def key(point: Vec3) -> tuple[int, int, int]:
        return (round(point[0] / tolerance), round(point[1] / tolerance), round(point[2] / tolerance))

    remaining = []
    for hole in holes:
        where = {key(point): index for index, point in enumerate(outer)}
        touch = next(((where[key(point)], index) for index, point in enumerate(hole) if key(point) in where), None)
        if touch is None:
            remaining.append(hole)
            continue
        at_outer, at_hole = touch
        outer = outer[:at_outer + 1] + hole[at_hole + 1:] + hole[:at_hole + 1] + outer[at_outer + 1:]
    return outer, remaining


def combined(parts: Sequence[Part]) -> Part:
    """Mehrere Netze als ein Teil (Name, Filament und Farbe vom ersten); die Punkte bleiben getrennt."""
    vertices: list[Vec3] = []
    triangles: list[Triangle] = []
    for part in parts:
        offset = len(vertices)
        vertices += part.vertices
        triangles += [(a + offset, b + offset, c + offset) for a, b, c in part.triangles]
    return replace(parts[0], vertices=tuple(vertices), triangles=tuple(triangles))


def _sliver_middle(points: tuple[Vec3, Vec3, Vec3], tolerance: float) -> int | None:
    """Liegt eine Ecke des Dreiecks (bis auf `tolerance` mm) auf der gegenueberliegenden Kante, ihre Stelle 0-2."""
    for index in range(3):
        middle, start, end = points[index], points[(index + 1) % 3], points[(index + 2) % 3]
        edge = [end[axis] - start[axis] for axis in range(3)]
        length2 = sum(value * value for value in edge)
        if length2 <= 0.0:
            continue
        offset = [middle[axis] - start[axis] for axis in range(3)]
        along = sum(offset[axis] * edge[axis] for axis in range(3)) / length2
        if not 0.0 < along < 1.0:
            continue
        distance2 = sum((offset[axis] - along * edge[axis]) ** 2 for axis in range(3))
        if distance2 <= tolerance * tolerance:
            return index
    return None


def drop_slivers(part: Part, tolerance: float = SLIVER_TOLERANCE_MM) -> Part:
    """Dreiecke mit Flaeche null (drei Ecken auf einer Linie) entfernen, ohne das Netz zu oeffnen.

    Solche Reste aus CAD-Programmen stoeren Bambu nicht, Allplan lehnt den Koerper ab (Beispiel 8_Colors_AMS_Test,
    live 2026-11-07). Die mittlere Ecke liegt auf der langen Kante; das Nachbardreieck an dieser Kante wird dort
    geteilt. Form und Volumen bleiben exakt, das Netz bleibt geschlossen.
    """
    triangles: dict[int, Triangle] = dict(enumerate(part.triangles))
    owner: dict[tuple[int, int], int] = {}

    def edges(triangle: Triangle):
        x, y, z = triangle
        return ((x, y), (y, z), (z, x))

    def add(key: int, triangle: Triangle) -> None:
        triangles[key] = triangle
        for edge in edges(triangle):
            owner[edge] = key

    def remove(key: int) -> Triangle:
        triangle = triangles.pop(key)
        for edge in edges(triangle):
            if owner.get(edge) == key:
                del owner[edge]
        return triangle

    def middle_of(triangle: Triangle) -> int | None:
        a, b, c = triangle
        return _sliver_middle((part.vertices[a], part.vertices[b], part.vertices[c]), tolerance)

    for key, triangle in triangles.items():
        for edge in edges(triangle):
            owner[edge] = key
    queue = [key for key, triangle in triangles.items() if middle_of(triangle) is not None]
    next_key, budget = len(part.triangles), 10 * len(part.triangles) + 10
    while queue and budget > 0:
        budget -= 1
        key = queue.pop()
        if key not in triangles:
            continue
        middle = middle_of(triangles[key])
        if middle is None:
            continue
        sliver = remove(key)
        b, c, a = sliver[middle], sliver[(middle + 1) % 3], sliver[(middle + 2) % 3]   # lange Kante c -> a
        other = owner.get((a, c))
        if other is None:
            continue
        x, y, z = remove(other)
        s = next(rot[2] for rot in ((x, y, z), (y, z, x), (z, x, y)) if rot[0] == a and rot[1] == c)
        for piece in ((a, b, s), (b, c, s)):
            add(next_key, piece)
            if middle_of(piece) is not None:
                queue.append(next_key)
            next_key += 1
    return replace(part, triangles=tuple(triangles[key] for key in sorted(triangles)))


def bounding_box(parts: Sequence[Part]) -> tuple[Vec3, Vec3]:
    """Kleinster und groesster Punkt ueber alle Teile."""
    points = [vertex for part in parts for vertex in part.vertices]
    if not points:
        raise ValueError("Ohne Punkte gibt es keine Abmessungen.")
    low = (min(p[0] for p in points), min(p[1] for p in points), min(p[2] for p in points))
    high = (max(p[0] for p in points), max(p[1] for p in points), max(p[2] for p in points))
    return low, high


def size(parts: Sequence[Part]) -> Vec3:
    low, high = bounding_box(parts)
    return (high[0] - low[0], high[1] - low[1], high[2] - low[2])


def fits_build_volume(parts: Sequence[Part]) -> bool:
    return all(extent <= BUILD_VOLUME_MM + 1e-6 for extent in size(parts))


def scaled(parts: Sequence[Part], reduction: float) -> list[Part]:
    """Verkleinern 1:reduction (1 = Originalgroesse)."""
    if not reduction > 0.0:
        raise ValueError(f"Massstab 1:{reduction} ist nicht moeglich - die Zahl muss groesser als 0 sein.")
    factor = 1.0 / reduction
    return [replace(part, vertices=tuple((x * factor, y * factor, z * factor) for x, y, z in part.vertices))
            for part in parts]


def moved(parts: Sequence[Part], offset: Vec3) -> list[Part]:
    dx, dy, dz = offset
    return [replace(part, vertices=tuple((x + dx, y + dy, z + dz) for x, y, z in part.vertices)) for part in parts]


def placed_on_plate(parts: Sequence[Part]) -> list[Part]:
    """Tiefster Punkt auf 0, Mitte des Modells auf die Plattenmitte."""
    low, high = bounding_box(parts)
    return moved(parts, (PLATE_CENTRE_MM[0] - (low[0] + high[0]) / 2.0,
                         PLATE_CENTRE_MM[1] - (low[1] + high[1]) / 2.0,
                         -low[2]))


def grouped_for_objects(parts: Sequence[Part], tolerance: float = OVERLAP_TOLERANCE_MM) -> list[list[Part]]:
    """Koerper, deren umschliessende Kaesten sich durchdringen oder beruehren, kommen in ein gemeinsames Objekt.

    Im Objekt gilt Bambus Regel "das spaetere Teil gewinnt den gemeinsamen Bereich" (G1), und Bambu laesst die
    Lage der Teile zueinander stehen. Ein eigenes Objekt stellt Bambu dagegen auf die Platte - aufeinander
    liegende Schichten (Beispiel 3Layers4ColorsPlate1) muessen deshalb zusammenbleiben. Nur Koerper mit Abstand
    (Puzzleteile auf zwei Platten, Beispiel 3D+PUZZLE) werden eigene Objekte, die Bambu einzeln anordnen kann.
    Reihenfolge: Gruppen nach ihrem ersten Teil, Teile innerhalb einer Gruppe wie uebergeben.
    """
    boxes = [bounding_box([part]) for part in parts]
    parent = list(range(len(parts)))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for first in range(len(parts)):
        for second in range(first + 1, len(parts)):
            (low_a, high_a), (low_b, high_b) = boxes[first], boxes[second]
            if all(min(high_a[axis], high_b[axis]) - max(low_a[axis], low_b[axis]) >= -tolerance for axis in range(3)):
                parent[root(second)] = root(first)
    groups: dict[int, list[Part]] = {}
    for index, part in enumerate(parts):
        groups.setdefault(root(index), []).append(part)
    return list(groups.values())


def hex_rgb(colour: str) -> tuple[int, int, int] | None:
    """"#RRGGBB" -> (r, g, b); None, wenn der Text keine Farbe ist."""
    text = colour.strip().lstrip("#")
    if len(text) < 6:
        return None
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return None


def nearest_colour(rgb: tuple[int, int, int], palette: dict[int, tuple[int, int, int]]) -> int:
    """Die Farbnummer der Tabelle, die dem Farbton am naechsten kommt (gewichteter Abstand "redmean")."""
    if not palette:
        raise ValueError("Ohne Farbtabelle gibt es keine naechste Farbe.")

    def distance(other: tuple[int, int, int]) -> float:
        mean = (rgb[0] + other[0]) / 2.0
        dr, dg, db = rgb[0] - other[0], rgb[1] - other[1], rgb[2] - other[2]
        return (2.0 + mean / 256.0) * dr * dr + 4.0 * dg * dg + (2.0 + (255.0 - mean) / 256.0) * db * db

    return min(sorted(palette), key=lambda number: distance(palette[number]))


def _boundary_edges(triangles: Sequence[Triangle]) -> list[tuple[int, int]]:
    directed = {edge for a, b, c in triangles for edge in ((a, b), (b, c), (c, a))}
    return [edge for edge in directed if (edge[1], edge[0]) not in directed]


def split_t_junctions(part: Part, tolerance: float = T_JUNCTION_MM, rounds: int = 4) -> Part:
    """Liegt ein Randpunkt auf einer offenen Kante (Abstand <= `tolerance`), wird die Kante dort geteilt.

    So entstehen Raender, wenn die Nachbarflaeche an derselben Kante mehr Punkte hat (T-Stoss) - etwa weil das
    Zerlegen einer Flaeche Punkte auf einer Geraden weglaesst. Der Punkt bleibt, wo er ist.
    """
    vertices, triangles = part.vertices, list(part.triangles)
    for _round in range(rounds):
        edges = _boundary_edges(triangles)
        if not edges:
            break
        cell = max(tolerance * 4.0, 0.5)

        def key(point: Vec3) -> tuple[int, int, int]:
            return (math.floor(point[0] / cell), math.floor(point[1] / cell), math.floor(point[2] / cell))

        grid: dict[tuple[int, int, int], list[int]] = {}
        for index in {v for edge in edges for v in edge}:
            grid.setdefault(key(vertices[index]), []).append(index)
        splits: dict[tuple[int, int], list[int]] = {}
        for start, end in edges:
            a, b = vertices[start], vertices[end]
            d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
            length2 = d[0] * d[0] + d[1] * d[1] + d[2] * d[2]
            if length2 <= 0.0:
                continue
            low = key((min(a[0], b[0]) - tolerance, min(a[1], b[1]) - tolerance, min(a[2], b[2]) - tolerance))
            high = key((max(a[0], b[0]) + tolerance, max(a[1], b[1]) + tolerance, max(a[2], b[2]) + tolerance))
            found = []
            for gx in range(low[0], high[0] + 1):
                for gy in range(low[1], high[1] + 1):
                    for gz in range(low[2], high[2] + 1):
                        for index in grid.get((gx, gy, gz), ()):
                            if index in (start, end):
                                continue
                            p = vertices[index]
                            t = ((p[0] - a[0]) * d[0] + (p[1] - a[1]) * d[1] + (p[2] - a[2]) * d[2]) / length2
                            if 1e-9 < t < 1.0 - 1e-9 and math.dist(p, (a[0] + t * d[0], a[1] + t * d[1],
                                                                       a[2] + t * d[2])) <= tolerance:
                                found.append((t, index))
            if found:
                splits[(start, end)] = [index for _t, index in sorted(found)]
        if not splits:
            break
        result: list[Triangle] = []
        for triangle in triangles:
            for i in range(3):
                a, b, c = triangle[i], triangle[(i + 1) % 3], triangle[(i + 2) % 3]
                if (a, b) in splits:
                    chain = [a] + splits[(a, b)] + [b]
                    result += [(chain[k], chain[k + 1], c) for k in range(len(chain) - 1)]
                    break
            else:
                result.append(triangle)
        triangles = result
    return replace(part, triangles=tuple(triangles))


def _simple_loops(edges: Sequence[tuple[int, int]]) -> list[list[int]]:
    """Gerichtete Randkanten -> einfache Ringe; an Punkten, die ein Rand zweimal beruehrt, wird geteilt."""
    following: dict[int, list[int]] = {}
    for start, end in edges:
        following.setdefault(start, []).append(end)
    loops: list[list[int]] = []
    for first in list(following):
        while following.get(first):
            path, position = [first], {first: 0}
            while following.get(path[-1]):
                step = following[path[-1]].pop()
                if step in position:
                    begin = position[step]
                    loops.append(path[begin:])
                    for gone in path[begin + 1:]:
                        del position[gone]
                    path = path[:begin + 1]
                else:
                    position[step] = len(path)
                    path.append(step)
    return [loop for loop in loops if len(loop) >= 3]


def _zipper(polygon: list[int], vertices: Sequence[Vec3], taken: set[tuple[int, int]]) -> list[Triangle]:
    """Ein schmales Loch als Streifen schliessen: von einem Ende her abwechselnd die kuerzere Diagonale.

    Eine Diagonale, die schon als Kante im Netz liegt (`taken`, ungerichtet), wird gemieden - sonst haengen an
    ihr drei Dreiecke.
    """
    n = len(polygon)
    start = max(range(n), key=lambda i: math.dist(vertices[polygon[0]], vertices[polygon[i]]))
    ring = polygon[start:] + polygon[:start]
    triangles: list[Triangle] = []
    low, high = 0, n - 1

    def cost(a: int, b: int) -> float:
        used = (min(a, b), max(a, b)) in taken
        return math.dist(vertices[a], vertices[b]) + (1e9 if used else 0.0)

    while high - low > 1:
        forward = cost(ring[low + 1], ring[high])
        backward = cost(ring[low], ring[high - 1])
        if forward <= backward:
            triangles.append((ring[low], ring[low + 1], ring[high]))
            low += 1
        else:
            triangles.append((ring[low], ring[high - 1], ring[high]))
            high -= 1
    return triangles


def _loop_width(loop: list[int], vertices: Sequence[Vec3]) -> float:
    """Ungefaehre Breite eines Lochs: doppelte Flaeche durch Umfang (ein Streifen der Breite w ergibt ~ w/2)."""
    nx = ny = nz = 0.0
    perimeter = 0.0
    for i, index in enumerate(loop):
        p, q = vertices[index], vertices[loop[(i + 1) % len(loop)]]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
        perimeter += math.dist(p, q)
    area = 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)
    return 2.0 * area / perimeter if perimeter > 0.0 else 0.0


def sealed(part: Part, max_width: float = CRACK_MAX_WIDTH_MM) -> Part:
    """Schmale Spalten in einem fast geschlossenen Netz schliessen (fuer "3MF schreiben").

    Allplan zerlegt gekruemmte Flaechen eines Koerpers je Flaeche fuer sich: an den Naehten passen die Punkte
    nicht aufeinander (Loft-Puzzleteil: 506 offene Kanten, keine Einstellung hilft - live 2026-11-07). Erst
    T-Stoesse teilen, dann jeden verbleibenden schmalen Ring als Streifen fuellen. Breite Loecher (eine offene
    Flaeche) bleiben offen - die sind gewollt oder ein anderer Fehler.
    """
    merged = merge_vertices(part)
    if is_closed(merged):
        return merged
    split = split_t_junctions(merged)
    taken = {(min(a, b), max(a, b)) for t in split.triangles for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0]))}
    added: list[Triangle] = []
    for loop in _simple_loops(_boundary_edges(split.triangles)):
        polygon = loop[::-1]        # Fuellung laeuft gegen den Rand, damit jede Kante zwei Richtungen hat
        if len(loop) <= 4 or _loop_width(loop, split.vertices) <= max_width:
            filling = _zipper(polygon, split.vertices, taken)
            taken |= {(min(a, b), max(a, b)) for t in filling for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0]))}
            added += filling
    # zwei Ringe ueber denselben drei Punkten in Gegenrichtung ergeben ein Dreieckspaar ohne Volumen: beide weg
    return drop_duplicate_faces(replace(split, triangles=split.triangles + tuple(added)))


def open_edge_count(part: Part) -> int:
    """Kanten, die nur ein Dreieck haben (0 = dicht)."""
    return len(_boundary_edges(part.triangles))


def merged(parts: Sequence[Part], name: str) -> Part:
    """Mehrere Koerper als EIN Teil (Allplan-Elementgruppe): Punkte aneinandergehaengt, Dreiecke nachnummeriert.

    Filament und Farbe kommen vom ersten Koerper; jeder Koerper muss vorher fuer sich nach aussen gedreht sein,
    das Volumen des Ganzen ist dann die Summe. In Bambu Studio ist das Teil mit einem Klick umzufaerben und
    laesst sich dort bei Bedarf wieder in seine Koerper trennen ("Teilen").
    """
    if not parts:
        raise ValueError("merged: keine Koerper fuer %r" % name)
    vertices: list[Vec3] = []
    triangles: list[Triangle] = []
    for part in parts:
        offset = len(vertices)
        vertices.extend(part.vertices)
        triangles.extend((a + offset, b + offset, c + offset) for a, b, c in part.triangles)
    return replace(parts[0], name=name, vertices=tuple(vertices), triangles=tuple(triangles))


def ordered_for_overlap(parts: Sequence[Part]) -> list[Part]:
    """Groesster Koerper zuerst, kleinster zuletzt; bei gleicher Groesse bleibt die Reihenfolge der Eingabe.

    Bambu Studio gibt den gemeinsamen Bereich dem spaeteren Teil - so gewinnt der eingesteckte Koerper,
    bei Gleichstand der zuletzt angeklickte.
    """
    return sorted(parts, key=lambda part: -abs(signed_volume(part)))
