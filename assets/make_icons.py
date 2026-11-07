"""Symbole fuer das 3MFStudio-Paket aus dem Entwurf des Anwenders schneiden (Pillow).

    python assets/make_icons.py

Quelle: assets/source/3MFStudio_entwurf.png (Entwurf vom 2026-11-07, "Nimm bitte das Logo/Icon!"). Das grosse
Symbol links oben wird ausgeschnitten, ausserhalb der abgerundeten Kachel durchsichtig gemacht und in die
Groessen fuer Actionbar (24/128 px, hell und dunkel) und Bibliothekskachel verkleinert. Die Kachel ist hell und
hebt sich auch auf dunklem Hintergrund ab - die dunkle Fassung ist deshalb dasselbe Bild.
"""

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "source", "3MFStudio_entwurf.png")
TILE_BOX = (63, 199, 607, 731)     # Kachel im Entwurf (links, oben, rechts, unten), am Bild gemessen
TILE_RADIUS = 88                   # Eckenrundung der Kachel im Entwurf


def tile() -> Image.Image:
    """Die Kachel aus dem Entwurf, quadratisch, ausserhalb der Rundung durchsichtig."""
    left, top, right, bottom = TILE_BOX
    cut = Image.open(SOURCE).convert("RGBA").crop(TILE_BOX)
    mask = Image.new("L", cut.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, right - left - 1, bottom - top - 1], radius=TILE_RADIUS, fill=255)
    cut.putalpha(mask)
    side = max(cut.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(cut, ((side - cut.size[0]) // 2, (side - cut.size[1]) // 2), cut)
    return square


def main() -> None:
    actionbar = os.path.join(HERE, "actionbar")
    library = os.path.join(HERE, "library")
    os.makedirs(actionbar, exist_ok=True)
    os.makedirs(library, exist_ok=True)
    source = tile()
    for size in (24, 128):
        icon = source.resize((size, size), Image.LANCZOS)
        icon.save(os.path.join(actionbar, "3MFStudio_%d.png" % size))
        icon.save(os.path.join(actionbar, "3MFStudio_%d_dark.png" % size))
    source.resize((128, 128), Image.LANCZOS).save(os.path.join(library, "3MFStudio.png"))
    print("Symbole geschrieben:", actionbar, library)


if __name__ == "__main__":
    main()
