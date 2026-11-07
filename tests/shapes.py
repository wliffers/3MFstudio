"""Probekoerper fuer die Tests."""

from threemf_model import Part


def box(x0, y0, z0, dx, dy, dz, name="Quader", filament=1, inward=False):
    """Geschlossener Quader; `inward=True` wendet ihn nach innen, so wie Allplan Koerper liefert."""
    vertices = tuple((x0 + x * dx, y0 + y * dy, z0 + z * dz) for x, y, z in
                     ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)))
    triangles = ((0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
                 (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7))
    if inward:
        triangles = tuple((a, c, b) for a, b, c in triangles)
    return Part(name, filament, vertices, triangles)
