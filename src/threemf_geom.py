"""Reine Geometrie: Newell-Normale, Triangulierung, planare UV.

KOPIE von avr_geom.py aus dem Vorgaengerprojekt AnimationVR (Stand 2026-11-06), unveraendert bis auf diesen Kopf.
Jedes Projekt wird eigenstaendig ausgerollt, deshalb Kopie statt Import. Aenderungen zuerst dort
pruefen; die Tests liegen als Kopie in tests/test_threemf_geom.py.

Laeuft ohne Allplan, nur Standardbibliothek. Einheiten: Meter.

- newell_normal : Einheitsnormale eines ebenen 3D-Rings.
- triangulate   : Ohrenschnitt fuer ebene 3D-Polygone, konkav und mit Loechern
                  (Brueckenkanten zum rechtesten Lochpunkt).
- planar_uv     : metrische, weltbezogene UV-Projektion (Boden/Decke und Waende).
"""

from __future__ import annotations

import math
from typing import Sequence

Vec3 = tuple[float, float, float]

# Toleranzen (Meter bzw. Quadratmeter)
_EPS_POINT = 1e-9      # Punkte naeher als das gelten als gleich
_EPS_AREA = 1e-9       # Flaeche darunter gilt als entartet
_EPS_CROSS = 2e-9      # Kreuzprodukt (= 2 * Dreiecksflaeche) darunter: kollinear
_EPS_INSIDE = 1e-12    # Rundungsspielraum beim Punkt-im-Dreieck-Test

_WALL_THRESHOLD = 0.7071  # |normal.z| ab dem eine Flaeche als waagerecht gilt


class GeometryError(ValueError):
    """Eingabegeometrie ist nicht triangulierbar (zu wenig Punkte, Flaeche null, ...)."""


# --------------------------------------------------------------------------
# Vektorhilfen (3D)
# --------------------------------------------------------------------------

def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross3(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot3(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm3(a: Vec3) -> float:
    return math.sqrt(_dot3(a, a))


def _dist3(a: Vec3, b: Vec3) -> float:
    return _norm3(_sub(a, b))


def _as_vec3(p: Sequence[float]) -> Vec3:
    return (float(p[0]), float(p[1]), float(p[2]))


# --------------------------------------------------------------------------
# Newell-Normale
# --------------------------------------------------------------------------

def _newell_vector(points: Sequence[Vec3]) -> Vec3:
    """Newell-Vektor = 2 * Flaeche * Einheitsnormale (zum ersten Punkt verschoben)."""
    o = points[0]
    sx = sy = sz = 0.0
    n = len(points)
    for i in range(n):
        a = _sub(points[i], o)
        b = _sub(points[(i + 1) % n], o)
        sx += (a[1] - b[1]) * (a[2] + b[2])
        sy += (a[2] - b[2]) * (a[0] + b[0])
        sz += (a[0] - b[0]) * (a[1] + b[1])
    return (sx, sy, sz)


def newell_normal(points: Sequence[Vec3]) -> Vec3:
    """Einheitsnormale nach Newell; (0, 0, 0) bei entarteter Flaeche (< 3 Punkte, Flaeche ~0)."""
    if len(points) < 3:
        return (0.0, 0.0, 0.0)
    pts = [_as_vec3(p) for p in points]
    v = _newell_vector(pts)
    length = _norm3(v)
    if 0.5 * length < _EPS_AREA:
        return (0.0, 0.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


# --------------------------------------------------------------------------
# Ring bereinigen
# --------------------------------------------------------------------------

def _clean_ring(points: Sequence[Vec3]) -> list[Vec3]:
    """Entfernt doppelte Folgepunkte, den Schlusspunkt und kollineare Punkte."""
    pts = [_as_vec3(p) for p in points]
    changed = True
    while changed:
        changed = False
        # doppelte Folgepunkte (zyklisch)
        out: list[Vec3] = []
        for p in pts:
            if not out or _dist3(p, out[-1]) > _EPS_POINT:
                out.append(p)
        while len(out) > 1 and _dist3(out[0], out[-1]) <= _EPS_POINT:
            out.pop()
        if len(out) != len(pts):
            changed = True
        pts = out
        # kollineare Punkte
        i = 0
        while i < len(pts) and len(pts) >= 3:
            a = pts[i - 1]
            b = pts[i]
            c = pts[(i + 1) % len(pts)]
            if _norm3(_cross3(_sub(b, a), _sub(c, b))) <= _EPS_CROSS:
                del pts[i]
                changed = True
                break  # Duplikate koennen entstanden sein -> von vorn
            i += 1
    return pts


# --------------------------------------------------------------------------
# 2D-Hilfen
# --------------------------------------------------------------------------

Pt2 = tuple[float, float]


def _cross2(o: Pt2, a: Pt2, b: Pt2) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _signed_area2(ring: Sequence[Pt2]) -> float:
    s = 0.0
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        s += a[0] * b[1] - b[0] * a[1]
    return 0.5 * s


def _in_triangle(a: Pt2, b: Pt2, c: Pt2, p: Pt2) -> bool:
    """Punkt im (oder auf dem Rand des) Dreiecks a, b, c; beliebige Orientierung."""
    d1 = _cross2(a, b, p)
    d2 = _cross2(b, c, p)
    d3 = _cross2(c, a, p)
    has_neg = d1 < -_EPS_INSIDE or d2 < -_EPS_INSIDE or d3 < -_EPS_INSIDE
    has_pos = d1 > _EPS_INSIDE or d2 > _EPS_INSIDE or d3 > _EPS_INSIDE
    return not (has_neg and has_pos)


def _basis(normal: Vec3) -> tuple[Vec3, Vec3]:
    """Rechtshaendige Basis (u, v) senkrecht zur Normalen; u x v = normal."""
    helper = (0.0, 0.0, 1.0) if abs(normal[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = _cross3(helper, normal)
    ul = _norm3(u)
    u = (u[0] / ul, u[1] / ul, u[2] / ul)
    v = _cross3(normal, u)
    return u, v


# --------------------------------------------------------------------------
# Loecher einbinden (Brueckenkanten)
# --------------------------------------------------------------------------

def _locally_inside(poly: list[int], pts: list[Pt2], k: int, target: Pt2) -> bool:
    """Liegt target im Innenwinkel der CCW-Schleife am Index k?"""
    n = len(poly)
    v = pts[poly[k]]
    a = pts[poly[k - 1]]
    c = pts[poly[(k + 1) % n]]
    if _cross2(a, v, c) >= 0.0:  # konvex
        return _cross2(v, c, target) >= 0.0 and _cross2(v, target, a) >= 0.0
    # reflex: Innen = alles ausser dem Aussenwinkel a -> c
    return not (_cross2(v, a, target) > 0.0 and _cross2(v, target, c) > 0.0)


def _find_bridge(poly: list[int], pts: list[Pt2], m_idx: int) -> int:
    """Position in poly des Eckpunkts, zu dem die Brueckenkante vom Lochpunkt m_idx fuehrt."""
    m = pts[m_idx]
    n = len(poly)
    best_x = math.inf
    best_k = -1
    for k in range(n):
        a = pts[poly[k]]
        b = pts[poly[(k + 1) % n]]
        if a[1] < b[1] and a[1] <= m[1] <= b[1]:
            x = a[0] + (m[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x >= m[0] - _EPS_POINT and x < best_x:
                best_x = x
                best_k = k
    if best_k < 0:
        raise GeometryError("Ein Loch liegt nicht innerhalb des Aussenumrisses.")

    ia = poly[best_k]
    ib = poly[(best_k + 1) % n]
    a, b = pts[ia], pts[ib]
    hit = (best_x, m[1])

    # Strahl trifft direkt einen Eckpunkt
    if math.hypot(hit[0] - a[0], hit[1] - a[1]) <= _EPS_POINT:
        target = ia
    elif math.hypot(hit[0] - b[0], hit[1] - b[1]) <= _EPS_POINT:
        target = ib
    else:
        # P = Endpunkt mit groesserem x; verdeckende Spitzen im Dreieck M, I, P pruefen
        p_idx = ia if a[0] > b[0] else ib
        p = pts[p_idx]
        best_tan = math.inf
        best_dist = math.inf
        target = p_idx
        for r_idx in set(poly):
            r = pts[r_idx]
            if r_idx == p_idx or r == m or r == p or r == hit:
                continue
            dx = r[0] - m[0]
            if dx <= 0.0:
                continue
            if not _in_triangle(m, hit, p, r):
                continue
            # nur Spitzen (reflexe Ecken) koennen die Sicht versperren
            reflex = False
            for k, pi in enumerate(poly):
                if pi == r_idx and _cross2(pts[poly[k - 1]], r, pts[poly[(k + 1) % n]]) < 0.0:
                    reflex = True
                    break
            if not reflex:
                continue
            tan = abs(r[1] - m[1]) / dx
            dist = dx * dx + (r[1] - m[1]) ** 2
            if tan < best_tan - 1e-15 or (abs(tan - best_tan) <= 1e-15 and dist < best_dist):
                best_tan = tan
                best_dist = dist
                target = r_idx

    # richtiges Vorkommen waehlen (Eckpunkte koennen nach frueheren Bruecken doppelt sein)
    first = -1
    for k, pi in enumerate(poly):
        if pi == target:
            if first < 0:
                first = k
            if _locally_inside(poly, pts, k, m):
                return k
    return first


def _merge_holes(outer: list[int], holes: list[list[int]], pts: list[Pt2]) -> list[int]:
    """Bindet alle Loecher (CW) ueber Brueckenkanten in die CCW-Aussenschleife ein."""
    poly = list(outer)
    order = sorted(holes, key=lambda h: max(pts[i][0] for i in h), reverse=True)
    for hole in order:
        mpos = max(range(len(hole)), key=lambda j: (pts[hole[j]][0], -pts[hole[j]][1]))
        rot = hole[mpos:] + hole[:mpos]
        k = _find_bridge(poly, pts, rot[0])
        poly = poly[:k + 1] + rot + [rot[0], poly[k]] + poly[k + 1:]
    return poly


# --------------------------------------------------------------------------
# Ohrenschnitt
# --------------------------------------------------------------------------

def _clip_ears(poly: list[int], pts: list[Pt2]) -> list[tuple[int, int, int]]:
    """Ohrenschnitt auf einer CCW-Schleife (Indizes duplizierbar). Liefert CCW-Dreiecke."""
    idx = list(poly)
    tris: list[tuple[int, int, int]] = []
    start = 0
    while len(idx) > 3:
        n = len(idx)
        clipped = False
        i = start % n
        for _ in range(n):
            ia, ib, ic = idx[i - 1], idx[i], idx[(i + 1) % n]
            a, b, c = pts[ia], pts[ib], pts[ic]
            cr = _cross2(a, b, c)
            if abs(cr) <= _EPS_CROSS:
                del idx[i]  # Spitze/kollinear: traegt keine Flaeche bei
                clipped = True
                break
            if cr > 0.0:
                blocked = False
                for j in range(n):
                    if j == i or j == (i - 1) % n or j == (i + 1) % n:
                        continue
                    p = pts[idx[j]]
                    if p == a or p == b or p == c:
                        continue
                    if _in_triangle(a, b, c, p):
                        blocked = True
                        break
                if not blocked:
                    tris.append((ia, ib, ic))
                    del idx[i]
                    clipped = True
                    break
            i = (i + 1) % n
        if clipped:
            start = max(i - 1, 0)
            continue
        # Kein sauberer Ohr gefunden (Rundungsfall): erste konvexe Ecke trotzdem schneiden
        for i in range(n):
            ia, ib, ic = idx[i - 1], idx[i], idx[(i + 1) % n]
            if _cross2(pts[ia], pts[ib], pts[ic]) > 0.0:
                tris.append((ia, ib, ic))
                del idx[i]
                start = max(i - 1, 0)
                clipped = True
                break
        if not clipped:
            raise GeometryError("Triangulierung nicht moeglich: Umriss ist ungueltig "
                                "(vermutlich selbstueberschneidend).")
    if len(idx) == 3 and _cross2(pts[idx[0]], pts[idx[1]], pts[idx[2]]) > _EPS_CROSS:
        tris.append((idx[0], idx[1], idx[2]))
    return tris


# --------------------------------------------------------------------------
# triangulate
# --------------------------------------------------------------------------

def triangulate(outer: Sequence[Vec3], holes: Sequence[Sequence[Vec3]] = ()) \
        -> tuple[list[Vec3], list[tuple[int, int, int]]]:
    """Triangulierung eines ebenen 3D-Polygons mit optionalen Loechern.

    Rueckgabe: (Eckpunkte, Dreiecke). Die Eckpunkte sind outer + holes nach
    Bereinigung (doppelte und kollineare Punkte entfernt); die Dreiecke
    indizieren diese Liste und laufen in Richtung der Newell-Normale von
    ``outer`` (so wie uebergeben, auch bei Uhrzeigersinn).

    Loecher mit weniger als 3 Punkten oder Flaeche ~0 werden ausgelassen.
    GeometryError bei weniger als 3 Punkten, Flaeche ~0 oder wenn ein Loch
    ausserhalb liegt bzw. der Umriss nicht triangulierbar ist.
    """
    outer_c = _clean_ring(outer)
    if len(outer_c) < 3:
        raise GeometryError("Flaeche hat weniger als 3 verschiedene Punkte.")
    nvec = _newell_vector(outer_c)
    nlen = _norm3(nvec)
    if 0.5 * nlen < _EPS_AREA:
        raise GeometryError("Flaeche ist entartet (Flaeche nahe null).")
    normal = (nvec[0] / nlen, nvec[1] / nlen, nvec[2] / nlen)

    hole_rings: list[list[Vec3]] = []
    for hole in holes:
        hc = _clean_ring(hole)
        if len(hc) < 3:
            continue
        hv = _newell_vector(hc)
        if 0.5 * _norm3(hv) < _EPS_AREA:
            continue
        hole_rings.append(hc)

    verts: list[Vec3] = list(outer_c)
    ranges: list[list[int]] = []
    for hc in hole_rings:
        base = len(verts)
        verts.extend(hc)
        ranges.append(list(range(base, base + len(hc))))

    # Projektion in die Ebene, Ursprung = erster Aussenpunkt
    u, v = _basis(normal)
    o = outer_c[0]
    pts: list[Pt2] = []
    for p in verts:
        d = _sub(p, o)
        pts.append((_dot3(d, u), _dot3(d, v)))

    outer_idx = list(range(len(outer_c)))
    if _signed_area2([pts[i] for i in outer_idx]) < 0.0:  # numerische Absicherung
        outer_idx.reverse()
    hole_idx: list[list[int]] = []
    expected = abs(_signed_area2([pts[i] for i in outer_idx]))
    for r in ranges:
        area = _signed_area2([pts[i] for i in r])
        expected -= abs(area)
        hole_idx.append(r[::-1] if area > 0.0 else list(r))  # Loecher CW
    if expected < _EPS_AREA:
        raise GeometryError("Die Loecher verbrauchen die gesamte Flaeche.")

    poly = _merge_holes(outer_idx, hole_idx, pts) if hole_idx else outer_idx
    tris = _clip_ears(poly, pts)

    got = sum(0.5 * _cross2(pts[a], pts[b], pts[c]) for a, b, c in tris)
    if abs(got - expected) > max(1e-6 * expected, 1e-8):
        raise GeometryError(
            "Triangulierung unstimmig (Flaeche %.6f statt %.6f m2): Umriss oder Loecher "
            "schneiden sich vermutlich." % (got, expected))
    return verts, tris


# --------------------------------------------------------------------------
# planar_uv
# --------------------------------------------------------------------------

def planar_uv(points: Sequence[Vec3], normal: Vec3, scale_u: float, scale_v: float,
              rotation: float = 0.0, offset: tuple[float, float] = (0.0, 0.0)) \
        -> list[tuple[float, float]]:
    """Metrische, weltbezogene UV-Projektion.

    scale_u / scale_v = Meter je Texturwiederholung (> 0).
    Flach (|normal.z| >= 0.7071): s = x, t = -y.
    Sonst (Wand): T = normalize(cross((0,0,1), normal)), s = dot(p, T), t = -z.
    Weltbezogen, damit Kacheln ueber Flaechengrenzen durchlaufen. t ist negiert, weil
    glTF den UV-Ursprung oben links hat (v waechst nach unten): so steht ein Wandbild
    aufrecht und ein Bodenbild zeigt mit seiner Oberkante nach +y.
    Ohne Drehung und Versatz: u = s / scale_u, v = t / scale_v.

    rotation: Bogenmass, dreht die Projektionskoordinaten (s, t) in METERN um den
        Weltursprung der Projektion, vor dem Teilen durch scale_u / scale_v. Positiv =
        gegen den Uhrzeigersinn in der Bildebene (wie KHR_texture_transform, aber ohne
        Verzerrung bei nicht quadratischer Kachel):
        s' = cos * s + sin * t, t' = -sin * s + cos * t.
    offset: Versatz (u, v) in Kachel-Anteilen, nach dem Teilen addiert.
    """
    if not (scale_u > 0.0 and scale_v > 0.0):
        raise GeometryError("Texturmassstab muss groesser als 0 sein (u=%r, v=%r)."
                            % (scale_u, scale_v))
    try:
        rotation = float(rotation)
        off_u, off_v = (float(v) for v in offset)
    except (TypeError, ValueError):
        raise GeometryError("Texturdrehung/-versatz nicht als Zahlen lesbar (rotation=%r, offset=%r)."
                            % (rotation, offset))
    if not (math.isfinite(rotation) and math.isfinite(off_u) and math.isfinite(off_v)):
        raise GeometryError("Texturdrehung/-versatz muss endlich sein (rotation=%r, offset=%r)."
                            % (rotation, offset))
    n = _as_vec3(normal)
    nl = _norm3(n)
    if nl <= 1e-12:
        raise GeometryError("Normale ist der Nullvektor; UV-Projektion nicht moeglich.")
    n = (n[0] / nl, n[1] / nl, n[2] / nl)

    if abs(n[2]) >= _WALL_THRESHOLD:
        st = [(p[0], -p[1]) for p in points]
    else:
        t = _cross3((0.0, 0.0, 1.0), n)
        tl = _norm3(t)
        t = (t[0] / tl, t[1] / tl, 0.0)
        st = [(p[0] * t[0] + p[1] * t[1], -p[2]) for p in points]

    if rotation != 0.0:
        cos_r, sin_r = math.cos(rotation), math.sin(rotation)
        st = [(cos_r * s + sin_r * t, -sin_r * s + cos_r * t) for s, t in st]
    if off_u == 0.0 and off_v == 0.0:
        return [(s / scale_u, t / scale_v) for s, t in st]
    return [(s / scale_u + off_u, t / scale_v + off_v) for s, t in st]
