"""Glatte Koerper aus Hoehenschnitten - reine Rechnung, kein Allplan.

Ein 3MF-Netz kennt nur Dreiecke. Fuer Teile, deren Querschnitt ueber die Hoehe denselben Aufbau behaelt
(Puzzleteile, Steckformen: ein Umriss, kein Loch), wird hier der Bauplan fuer einen glatten Allplan-Koerper
berechnet: Schnitte in mehreren Hoehen, je Schnitt ein Umriss mit gleichmaessig verteilten Punkten. Allplan
legt durch jeden Umriss eine glatte Kurve und zieht den Koerper hindurch (threemf_allplan.smooth_solid).

Gemessen am Puzzle1, Teil 0 (live 2026-11-07): 18 Schnitte, Punkte im Abstand 1 mm -> 19 glatte Flaechen statt
22 500 Dreiecke, Volumen -0,14 %. Dichtere Punkte machten den Koerper zu dick (2400 Punkte: +14 %), ungleiche
Abstaende rundeten Innenecken ab (+3,5 %) - deshalb wird jeder Koerper nachgemessen, bevor er gilt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from threemf_model import (  # pyright: ignore[reportMissingImports]
    Part, Vec3, bounding_box, chain_rings, face_regions, is_closed, signed_volume)

LOFT_LEVELS = 18              # Schnitte je Teil, an den Enden dichter (dort sitzen die Rundungen)
CAP_GAP_MM = 1e-3             # erster und letzter Schnitt so weit innen; Deckel liegen dann wieder genau
CURVED_MIN_NORMALS = 40       # weniger Flaechenrichtungen: ebenes Teil, der normale Weg baut es schon sauber
SECTION_JOIN_MM = 1e-4        # Schnittkanten-Enden so nah gelten als derselbe Punkt
MIN_PROFILE_POINTS = 24
MAX_PROFILE_POINTS = 1500
SPACINGS_MM = (1.0, 0.8, 1.25, 0.6)   # Punktabstand der Umrisse, in dieser Reihenfolge versucht
PROJECTION_CELL_MM = 1.0      # Rastergroesse fuer die Suche des naechsten Umrisspunkts
SAME_OUTLINE_MM = 1e-4        # Schnitte, deren Punkte so nah uebereinander liegen, sind gleich
FLAT_MM = 1e-5                # Dreieck mit drei so gleich hohen Ecken ist waagrecht
STEP_MIN_MM = 0.05            # Stufen naeher an Boden oder Deckel zaehlen nicht (gehoeren zur Kantenrundung)
MAX_ZONES = 6                 # mehr Abschnitte: kein Schnitt-Teil
CORNER_DEG = 30.0             # staerkerer Knick im Umriss ist eine scharfe Ecke (Pfeilspitze), keine Rundung
STRAIGHT_MM = 0.005           # Umrissstueck zwischen zwei Ecken, das so wenig von der Geraden abweicht, ist gerade


@dataclass(frozen=True)
class LoftPlan:
    """Schnitte eines Teils, nach Abschnitten: je Abschnitt (zwischen zwei Stufen) je Hoehe ein Umriss
    (gegen den Uhrzeigersinn, von oben); dazu die Sollwerte des ganzen Teils."""
    zones: tuple[tuple[tuple[Vec3, ...], ...], ...]
    volume: float
    area: float
    low: Vec3
    high: Vec3


def section(part: Part, height: float) -> list[tuple[list[Vec3], list[list[Vec3]]]]:
    """Schnitt mit der Ebene z = height: Umrisse mit ihren Loechern."""
    segments: list[tuple[Vec3, Vec3]] = []
    for a, b, c in part.triangles:
        points = (part.vertices[a], part.vertices[b], part.vertices[c])
        side = [p[2] - height for p in points]
        if all(s > 0 for s in side) or all(s < 0 for s in side):
            continue
        cut: list[Vec3] = []
        for i in range(3):
            p, q = points[i], points[(i + 1) % 3]
            sp, sq = side[i], side[(i + 1) % 3]
            if (sp < 0) != (sq < 0) and sp != sq:
                t = sp / (sp - sq)
                cut.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]), height))
        if len(cut) != 2:
            continue
        u = [points[1][k] - points[0][k] for k in range(3)]
        v = [points[2][k] - points[0][k] for k in range(3)]
        nx, ny = u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2]
        # Richtung = oben x Normale: das Material liegt links, der Umriss laeuft gegen den Uhrzeigersinn
        if (cut[1][0] - cut[0][0]) * -ny + (cut[1][1] - cut[0][1]) * nx < 0:
            cut.reverse()
        segments.append((cut[0], cut[1]))
    return face_regions(chain_rings(segments, SECTION_JOIN_MM))


def surface_area(part: Part) -> float:
    total = 0.0
    for a, b, c in part.triangles:
        p, q, s = part.vertices[a], part.vertices[b], part.vertices[c]
        u = (q[0] - p[0], q[1] - p[1], q[2] - p[2])
        v = (s[0] - p[0], s[1] - p[1], s[2] - p[2])
        total += 0.5 * math.sqrt((u[1] * v[2] - u[2] * v[1]) ** 2 + (u[2] * v[0] - u[0] * v[2]) ** 2
                                 + (u[0] * v[1] - u[1] * v[0]) ** 2)
    return total


def is_curved(part: Part, minimum: int = CURVED_MIN_NORMALS) -> bool:
    """Hat das Netz mindestens `minimum` verschiedene Flaechenrichtungen (auf 0,01 gerundet)?"""
    seen: set[tuple[float, float, float]] = set()
    for a, b, c in part.triangles:
        p, q, s = part.vertices[a], part.vertices[b], part.vertices[c]
        u = (q[0] - p[0], q[1] - p[1], q[2] - p[2])
        v = (s[0] - p[0], s[1] - p[1], s[2] - p[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        length = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
        if length > 0.0:
            seen.add((round(n[0] / length, 2), round(n[1] / length, 2), round(n[2] / length, 2)))
            if len(seen) >= minimum:
                return True
    return False


def step_heights(part: Part, low: float, high: float) -> list[float]:
    """Hoehen waagrechter Flaechen zwischen Boden und Deckel: dort springt der Querschnitt (Stufe, Absatz)."""
    heights: set[float] = set()
    for a, b, c in part.triangles:
        za, zb, zc = part.vertices[a][2], part.vertices[b][2], part.vertices[c][2]
        if abs(za - zb) <= FLAT_MM and abs(za - zc) <= FLAT_MM and low + STEP_MIN_MM < za < high - STEP_MIN_MM:
            heights.add(round(za, 4))
    return sorted(heights)


def _zone_rings(part: Part, bottom: float, top: float, levels: int) -> tuple[tuple[Vec3, ...], ...] | None:
    rings: list[tuple[Vec3, ...]] = []
    for k in range(levels):
        share = (1.0 - math.cos(math.pi * k / (levels - 1))) / 2.0
        regions = section(part, bottom + CAP_GAP_MM + (top - bottom - 2 * CAP_GAP_MM) * share)
        if len(regions) != 1 or regions[0][1] or len(regions[0][0]) < 3:
            return None
        z = bottom if k == 0 else top if k == levels - 1 else None
        rings.append(tuple(regions[0][0] if z is None else [(x, y, z) for x, y, _z in regions[0][0]]))
    return tuple(rings)


def loft_plan(part: Part, levels: int = LOFT_LEVELS, split_steps: bool = True) -> LoftPlan | None:
    """Bauplan fuer einen glatten Koerper - oder None, wenn das Teil kein Schnitt-Teil ist.

    Schnitt-Teil: geschlossen, gerundet, und jeder Schnitt ist genau ein Umriss ohne Loch. An waagrechten
    Stufen (Shape Toy: breite Grundplatte, schmaler Zapfen) wird geteilt - ein Loft ueber die Stufe hinweg
    machte daraus eine Schraege (-21 % Volumen, live 2026-11-07); jeder Abschnitt bekommt seine eigenen Schnitte.
    """
    if not part.triangles or not is_closed(part) or not is_curved(part):
        return None
    low, high = bounding_box([part])
    steps = step_heights(part, low[2], high[2]) if split_steps else []
    bounds = [low[2]] + steps + [high[2]]
    if len(bounds) - 1 > MAX_ZONES or any(top - bottom <= 20 * CAP_GAP_MM for bottom, top in zip(bounds, bounds[1:])):
        return None
    zones = []
    for bottom, top in zip(bounds, bounds[1:]):
        rings = _zone_rings(part, bottom, top, levels)
        if rings is None:
            return None
        zones.append(rings)
    return LoftPlan(tuple(zones), abs(signed_volume(part)), surface_area(part), low, high)


def perimeter(ring: tuple[Vec3, ...] | list[Vec3]) -> float:
    return sum(math.dist(ring[i - 1], ring[i]) for i in range(len(ring)))


def _projected(points: list[Vec3], ring: tuple[Vec3, ...]) -> list[Vec3] | None:
    """Jeden Punkt auf den naechsten Punkt des Umrisses `ring` setzen (in dessen Hoehe).

    None, wenn die Punkte dabei nicht der Reihe nach um den Umriss laufen - dann wuerde der Koerper sich falten.
    """
    n = len(ring)
    cumulative = [0.0]
    for i in range(n):
        cumulative.append(cumulative[-1] + math.dist(ring[i], ring[(i + 1) % n]))
    total = cumulative[-1]
    cell = PROJECTION_CELL_MM
    grid: dict[tuple[int, int], list[int]] = {}
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        for gx in range(math.floor(min(a[0], b[0]) / cell), math.floor(max(a[0], b[0]) / cell) + 1):
            for gy in range(math.floor(min(a[1], b[1]) / cell), math.floor(max(a[1], b[1]) / cell) + 1):
                grid.setdefault((gx, gy), []).append(i)
    z = ring[0][2]
    result: list[Vec3] = []
    params: list[float] = []
    for p in points:
        best: tuple[float, float, Vec3] | None = None
        reach = 0
        while best is None or reach <= 1 + int(best[0] / cell):
            gx, gy = math.floor(p[0] / cell), math.floor(p[1] / cell)
            for ix in range(gx - reach, gx + reach + 1):
                for iy in range(gy - reach, gy + reach + 1):
                    if max(abs(ix - gx), abs(iy - gy)) != reach:
                        continue
                    for i in grid.get((ix, iy), ()):
                        a, b = ring[i], ring[(i + 1) % n]
                        dx, dy = b[0] - a[0], b[1] - a[1]
                        length2 = dx * dx + dy * dy
                        t = 0.0 if length2 <= 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy)
                                                             / length2))
                        q = (a[0] + t * dx, a[1] + t * dy, z)
                        d = math.hypot(p[0] - q[0], p[1] - q[1])
                        if best is None or d < best[0]:
                            best = (d, cumulative[i] + t * (cumulative[i + 1] - cumulative[i]), q)
            reach += 1
            if reach > 10000:
                return None
        result.append(best[2])
        params.append(best[1])
    # der Reihe nach: genau ein Ruecksprung (der Umlauf schliesst sich), sonst keiner
    steps = [(params[(i + 1) % len(params)] - params[i]) % total for i in range(len(params))]
    if any(step <= 0.0 or step > total / 2 for step in steps):
        return None
    return result


@dataclass(frozen=True)
class Profiles:
    """Punkte aller Schnitte eines Abschnitts (je Schnitt gleich viele, uebereinander liegend), dazu die Ecken:
    Punktnummern scharfer Ecken (leer = ein glatter Umlauf) und je Stueck zwischen zwei Ecken, ob es gerade ist."""
    points: tuple[tuple[Vec3, ...], ...]
    corners: tuple[int, ...]
    straight: tuple[bool, ...]


def _counter_clockwise(ring: tuple[Vec3, ...] | list[Vec3]) -> list[Vec3]:
    points = list(ring)
    twice_area = sum(points[i - 1][0] * points[i][1] - points[i][0] * points[i - 1][1] for i in range(len(points)))
    return points[::-1] if twice_area < 0 else points


def _corner_indices(points: list[Vec3]) -> list[int]:
    """Punkte, an denen der Umriss um mehr als CORNER_DEG abknickt (von oben gesehen)."""
    n = len(points)
    corners = []
    for i in range(n):
        a, b, c = points[i - 1], points[i], points[(i + 1) % n]
        u, v = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
        if math.hypot(*u) <= 0.0 or math.hypot(*v) <= 0.0:
            continue
        turn = abs(math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])))
        if turn > CORNER_DEG:
            corners.append(i)
    return corners


def _resampled_open(points: list[Vec3], segments: int) -> list[Vec3]:
    """Offener Linienzug -> `segments` gleich lange Stuecke (segments + 1 Punkte, Enden bleiben)."""
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    total, result, j = lengths[-1], [], 0
    for k in range(segments + 1):
        target = total * k / segments
        while j < len(points) - 2 and lengths[j + 1] < target:
            j += 1
        t = (target - lengths[j]) / max(lengths[j + 1] - lengths[j], 1e-12)
        a, b = points[j], points[j + 1]
        result.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2])))
    return result


def master_profile(ring: tuple[Vec3, ...], spacing: float) -> tuple[list[Vec3], list[int], list[bool]]:
    """Punkte des Leit-Schnitts: Ecken bleiben genau erhalten, gerade Stuecke nur mit ihren Enden, gerundete
    Stuecke mit Punkten im Abstand `spacing`. Ohne Ecken: gleichmaessig verteilt (profile_points)."""
    points = _counter_clockwise(ring)
    corners = _corner_indices(points)
    if not corners:
        return profile_points(ring, spacing), [], []
    result: list[Vec3] = []
    corner_positions: list[int] = []
    straight: list[bool] = []
    for index, first in enumerate(corners):
        last = corners[(index + 1) % len(corners)]
        arc = points[first:last + 1] if last > first else points[first:] + points[:last + 1]
        chord = (arc[-1][0] - arc[0][0], arc[-1][1] - arc[0][1])
        length = math.hypot(*chord)
        is_straight = length > 0.0 and all(
            abs(chord[0] * (p[1] - arc[0][1]) - chord[1] * (p[0] - arc[0][0])) / length <= STRAIGHT_MM for p in arc)
        corner_positions.append(len(result))
        straight.append(is_straight)
        if is_straight:
            result.append(arc[0])
        else:
            arc_length = sum(math.dist(a, b) for a, b in zip(arc, arc[1:]))
            result += _resampled_open(arc, max(2, round(arc_length / spacing)))[:-1]
    return result, corner_positions, straight


def aligned_profiles(rings: tuple[tuple[Vec3, ...], ...], spacing: float) -> Profiles | None:
    """Punkte fuer alle Schnitte eines Abschnitts, die genau uebereinander liegen: verteilt auf dem mittleren
    Schnitt, dann auf jeden anderen Umriss projiziert. Einzeln verteilte Punkte verrutschen von Schnitt zu Schnitt -
    der Koerper verdreht sich dann und Allplan baut ihn nicht (Puzzle1, sechs von acht Teilen, live 2026-11-07).
    Gleiche Schnitte hintereinander werden zu einem Abschnitt zusammengefasst (erster und letzter bleiben).
    """
    master, corners, straight = master_profile(rings[len(rings) // 2], spacing)
    shares = _shares(master)
    profiles: list[list[Vec3]] = []
    for ring in rings:
        projected = _projected(master, ring) or _proportional(shares, master[0], ring)
        if projected is None:
            return None
        profiles.append(projected)
    kept = [profiles[0]]
    for k in range(1, len(profiles) - 1):
        if not (_same_outline(profiles[k], profiles[k - 1]) and _same_outline(profiles[k], profiles[k + 1])):
            kept.append(profiles[k])
    kept.append(profiles[-1])
    return Profiles(tuple(tuple(p) for p in kept), tuple(corners), tuple(straight))


def _shares(points: list[Vec3]) -> list[float]:
    """Lage jedes Punkts als Anteil am Umfang des geschlossenen Linienzugs (0 <= Anteil < 1)."""
    lengths = [0.0]
    for i in range(1, len(points)):
        lengths.append(lengths[-1] + math.dist(points[i - 1], points[i]))
    total = lengths[-1] + math.dist(points[-1], points[0])
    return [length / total for length in lengths] if total > 0 else [0.0] * len(points)


def _proportional(shares: list[float], anchor: Vec3, ring: tuple[Vec3, ...]) -> list[Vec3] | None:
    """Ersatz fuer _projected: Punkte nach Umfangsanteil auf den Umriss legen, beginnend am Umrisspunkt naechst
    `anchor`. Laeuft immer der Reihe nach, trifft Ecken aber nur ungefaehr (Shape Toy, Pfeil-Grundplatte)."""
    points = _counter_clockwise(ring)
    if len(points) < 3:
        return None
    start = min(range(len(points)), key=lambda i: math.hypot(points[i][0] - anchor[0], points[i][1] - anchor[1]))
    loop = points[start:] + points[:start] + [points[start]]
    lengths = [0.0]
    for a, b in zip(loop, loop[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    total = lengths[-1]
    result: list[Vec3] = []
    j = 0
    for share in shares:
        target = share * total
        while j < len(loop) - 2 and lengths[j + 1] < target:
            j += 1
        t = (target - lengths[j]) / max(lengths[j + 1] - lengths[j], 1e-12)
        a, b = loop[j], loop[j + 1]
        result.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2])))
    return result


def _same_outline(a: list[Vec3], b: list[Vec3]) -> bool:
    return all(abs(p[0] - q[0]) <= SAME_OUTLINE_MM and abs(p[1] - q[1]) <= SAME_OUTLINE_MM for p, q in zip(a, b))


def profile_points(ring: tuple[Vec3, ...] | list[Vec3], spacing: float) -> list[Vec3]:
    """Umriss mit gleichen Punktabstaenden (etwa `spacing` mm), gegen den Uhrzeigersinn.

    Jeder Umriss beginnt am Punkt rechts vom Schwerpunkt: so liegen die Anfaenge aller Schnitte uebereinander
    und der Koerper verdreht sich nicht.
    """
    points = list(ring)
    twice_area = sum(points[i - 1][0] * points[i][1] - points[i][0] * points[i - 1][1] for i in range(len(points)))
    if twice_area < 0:
        points.reverse()
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    start = max(range(len(points)), key=lambda i: (points[i][0] - cx) - 10.0 * abs(points[i][1] - cy))
    points = points[start:] + points[:start] + [points[start]]
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    total = lengths[-1]
    count = max(MIN_PROFILE_POINTS, min(MAX_PROFILE_POINTS, round(total / spacing)))
    result: list[Vec3] = []
    j = 0
    for k in range(count):
        target = total * k / count
        while lengths[j + 1] < target:
            j += 1
        t = (target - lengths[j]) / max(lengths[j + 1] - lengths[j], 1e-12)
        a, b = points[j], points[j + 1]
        result.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2])))
    return result
