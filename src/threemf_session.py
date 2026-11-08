"""Zuordnung Koerper -> Filament und der Weg zur Datei - reine Rechnung, kein Allplan, keine Oberflaeche.

Das Fenster ruft nur diese Klasse: Koerper einem Filament geben, Namen setzen, Groesse waehlen,
Teileliste fuer die Datei holen.

Regeln (prompt.de.md):
- hoechstens 16 Filamente (MAX_FILAMENTS); ein Koerper gehoert zu hoechstens einem Filament - erneut zuordnen verschiebt ihn
- nochmal anklicken, waehrend dasselbe Filament in Auswahl ist, nimmt den Koerper wieder heraus
- Teilname in der Datei = Name des Filaments ("Text"), bei mehreren Koerpern durchgezaehlt
- Reihenfolge in der Datei: groesster Koerper zuerst, bei gleicher Groesse der zuletzt zugeordnete zuletzt
- Originalgroesse in mm ist Standard, Verkleinern ist eine Option; den Bauraum seines Druckers kennt der Anwender selbst (keine Warnung)
- je Filament optional eine gewaehlte Farbe und Sorte (Choice); ohne Wahl gilt die Allplan-Farbe seiner Koerper
- tauschen: zwei Filamente tauschen ihre Koerper; Name, Farbe und Sorte bleiben beim Filament
"""

from __future__ import annotations

import logging
from dataclasses import MISSING, dataclass, field, fields, replace

import threemf_model as model  # pyright: ignore[reportMissingImports]
from threemf_text import tr  # pyright: ignore[reportMissingImports]
from threemf_model import MAX_FILAMENTS, Part, ThreeMfError  # pyright: ignore[reportMissingImports]


@dataclass(frozen=True)
class Body:
    """Ein Koerper aus dem Modell: Kennung, Anzeigename, Allplan-Farbe und sein Netz in mm.

    `group` ist die Kennung der Allplan-Elementgruppe, in der er steckt (leer: keine), `group_name` ihre
    Bezeichnung. Koerper einer Gruppe auf demselben Filament werden in der Datei EIN Teil mit diesem Namen."""
    key: str
    label: str
    colour: int
    rgb: tuple[int, int, int]
    part: Part
    group: str = ""
    group_name: str = ""


@dataclass(frozen=True)
class Choice:
    """Die gewaehlte Farbe eines Filaments: Farbwert "#RRGGBB", Farbname und Sorte aus der Liste.

    `code` ist Bambus Filament-Kennung (fuer das Bambu-Profil). `allplan` > 0 heisst: festgehaltene Allplan-Farbe
    dieser Nummer (beim Tauschen ohne eigene Wahl) - dann gibt es keinen Farbnamen."""
    hex: str
    name: str = ""
    brand: str = ""
    line: str = ""
    material: str = ""
    code: str = ""
    allplan: int = 0

    def label(self) -> str:
        """"PLA Basic Jadeweiß" - leer, wenn weder Sorte noch Farbname bekannt sind."""
        return " ".join(part for part in (self.line, self.name) if part)

    def rgb(self) -> tuple[int, int, int]:
        value = self.hex.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


MINE_KEY = "meine_farben"          # Eintrag in %APPDATA%\3MFStudio\einstellungen.json
MINE_LIMIT = 16


def mine_from_settings(settings: dict) -> list[Choice]:
    """"Meine Farben" aus den Einstellungen; unbrauchbare Eintraege fallen still heraus (Datei des Anwenders)."""
    result = []
    for entry in settings.get(MINE_KEY) or []:
        if not isinstance(entry, dict):
            continue
        value = str(entry.get("hex", ""))
        if len(value) != 7 or not value.startswith("#"):
            continue
        try:
            int(value[1:], 16)
        except ValueError:
            continue
        text = {name: str(entry.get(name, "")) for name in ("name", "brand", "line", "material", "code")}
        result.append(Choice(value.upper(), text["name"], text["brand"], text["line"], text["material"], text["code"]))
    return result


def remember_mine(settings: dict, choice: Choice) -> list[Choice]:
    """Eigene Farbe vorne in "Meine Farben" (gleiche Farbe und Sorte nur einmal, hoechstens MINE_LIMIT)."""
    mine = [choice] + [old for old in mine_from_settings(settings)
                       if (old.hex, old.brand, old.line) != (choice.hex, choice.brand, choice.line)]
    mine = mine[:MINE_LIMIT]
    settings[MINE_KEY] = [{"hex": entry.hex, "name": entry.name, "brand": entry.brand, "line": entry.line,
                           "material": entry.material, "code": entry.code} for entry in mine]
    return mine


def names_from_parts(parts: list[Part]) -> dict[int, str]:
    """Filamentnamen aus einer Datei dieses Werkzeugs zurueckgewinnen: Teile heissen "Text" bzw. "Text 1", "Text 2".

    Nur ein Name, den alle Teile eines Filaments gemeinsam tragen, wird uebernommen; "Filament 2" ist kein Name.
    """
    names: dict[int, str] = {}
    by_filament: dict[int, list[str]] = {}
    for part in parts:
        by_filament.setdefault(part.filament, []).append(part.name)
    for filament, labels in by_filament.items():
        bases = set()
        for label in labels:
            stem, _space, number = label.rpartition(" ")
            bases.add(stem if len(labels) > 1 and stem and number.isdigit() else label)
        if len(bases) == 1:
            base = bases.pop().strip()
            if base and base != f"Filament {filament}":
                names[filament] = base
    return names


@dataclass
class Session:
    names: dict[int, str] = field(default_factory=dict)
    scale_on: bool = False
    reduction: float = 100.0
    last_file: str = ""                                              # zuletzt geschriebene Datei, fuer "Im Slicer oeffnen"
    last_colours: dict[int, str] = field(default_factory=dict)      # Farbe je Filament dieser Datei, fuer Bambu
    last_choices: dict[int, Choice] = field(default_factory=dict)   # Sorte je Filament dieser Datei, fuer Bambu
    last_is_project: bool = False                                    # die Datei ist schon Bambus Projekt (Farben + Sorten drin)
    choices: dict[int, Choice] = field(default_factory=dict)        # gewaehlte Farbe je Filament
    _bodies: dict[str, Body] = field(default_factory=dict)
    _filament: dict[str, int] = field(default_factory=dict)      # Kennung -> Filament, in der Reihenfolge der Zuordnung

    # ------------------------------------------------------------------ zuordnen

    def assign(self, filament: int, bodies: list[Body]) -> int:
        """Gibt die Koerper diesem Filament; schon anders zugeordnete wandern. Rueckgabe: Zahl der neuen oder verschobenen."""
        if not 1 <= filament <= MAX_FILAMENTS:
            raise ThreeMfError(tr("Es gibt nur Filament 1 bis {maximum}.", maximum=MAX_FILAMENTS))
        changed = 0
        for body in bodies:
            if self._filament.get(body.key) != filament:
                changed += 1
            self._filament.pop(body.key, None)          # hinten neu einreihen: "zuletzt zugeordnet"
            self._filament[body.key] = filament
            self._bodies[body.key] = body
        return changed

    def pick(self, filament: int, bodies: list[Body]) -> tuple[int, int]:
        """Anklicken im Modell: gibt die Koerper diesem Filament; gehoeren schon ALLE dazu, kommen sie wieder heraus.

        Rueckgabe: (Zahl der neuen oder verschobenen, Zahl der herausgenommenen).
        """
        if bodies and all(self._filament.get(body.key) == filament for body in bodies):
            for body in bodies:
                del self._filament[body.key]
                del self._bodies[body.key]
            return 0, len(bodies)
        return self.assign(filament, bodies), 0

    def release(self, keys) -> int:
        """Nimmt Koerper aus der Zuordnung (z. B. inzwischen auf dem Hilfslayer). Rueckgabe: wie viele es waren."""
        released = 0
        for key in keys:
            if self._filament.pop(key, None) is not None:
                self._bodies.pop(key, None)
                released += 1
        return released

    def clear(self, filament: int) -> int:
        keys = [key for key, value in self._filament.items() if value == filament]
        for key in keys:
            del self._filament[key]
            del self._bodies[key]
        return len(keys)

    def choose(self, filament: int, choice: Choice | None) -> None:
        """Farbe und Sorte fuer dieses Filament festlegen; None = wieder die Allplan-Farbe seiner Koerper."""
        if not 1 <= filament <= MAX_FILAMENTS:
            raise ThreeMfError(tr("Es gibt nur Filament 1 bis {maximum}.", maximum=MAX_FILAMENTS))
        if choice is None:
            self.choices.pop(filament, None)
        else:
            self.choices[filament] = choice

    def swap(self, first: int, second: int) -> int:
        """Die beiden Filamente tauschen ihre Koerper; Name, Farbe und Sorte bleiben beim Filament.

        Ein Filament ohne eigene Wahl haelt vorher seine sichtbare Allplan-Farbe fest - sonst wanderte die Farbe
        mit den Koerpern und der Tausch zeigte keine Wirkung. Rueckgabe: Zahl der bewegten Koerper."""
        if first == second:
            return 0
        for filament in (first, second):
            if filament not in self.choices:
                colours = self.colours(filament)
                if colours:
                    number, rgb = colours[0]
                    self.choices[filament] = Choice("#%02X%02X%02X" % rgb, allplan=number)
        moved = 0
        for key, value in self._filament.items():
            if value in (first, second):
                self._filament[key] = second if value == first else first
                moved += 1
        return moved

    def recoloured(self, old_key: str, new_key: str, colour: int, rgb: tuple[int, int, int]) -> None:
        """Nach dem Umfaerben in Allplan: neue Farbe merken; vergibt Allplan eine neue Kennung, zieht sie mit
        (Reihenfolge der Zuordnung bleibt)."""
        if old_key not in self._filament:
            return
        body = replace(self._bodies.pop(old_key), key=new_key, colour=colour, rgb=rgb)
        if new_key == old_key:
            self._bodies[old_key] = body
            return
        self._filament = {(new_key if key == old_key else key): value for key, value in self._filament.items()}
        self._bodies[new_key] = body

    # ------------------------------------------------------------------ lesen

    def filament_of(self, key: str) -> int | None:
        """Zu welchem Filament der Koerper gehoert; None, wenn er keinem zugeordnet ist."""
        return self._filament.get(key)

    def count(self, filament: int) -> int:
        return sum(1 for value in self._filament.values() if value == filament)

    def total(self) -> int:
        return len(self._filament)

    def keys(self, filament: int) -> list[str]:
        return [key for key, value in self._filament.items() if value == filament]

    def body(self, key: str) -> Body | None:
        return self._bodies.get(key)

    def units(self, filament: int | None = None) -> list[tuple[int, list[Body]]]:
        """Die Einheiten fuer die Datei: jeder lose Koerper fuer sich, die Koerper einer Elementgruppe auf
        demselben Filament zusammen - in der Reihenfolge ihrer ersten Zuordnung. `filament` schraenkt ein."""
        grouped: dict[tuple[int, str], list[Body]] = {}
        for key, value in self._filament.items():
            if filament is not None and value != filament:
                continue
            body = self._bodies[key]
            grouped.setdefault((value, body.group or key), []).append(body)
        return [(value, bodies) for (value, _unit), bodies in grouped.items()]

    def group_names(self, filament: int) -> list[str]:
        """Die Bezeichnungen der Elementgruppen auf diesem Filament, ohne Dubletten, namenlose ausgelassen."""
        names: list[str] = []
        for _value, bodies in self.units(filament):
            name = bodies[0].group_name if bodies[0].group else ""
            if name and name not in names:
                names.append(name)
        return names

    def name_of(self, filament: int) -> str:
        """Eigener Name, sonst "Sorte Farbname" der gewaehlten Farbe, sonst "Filament n"."""
        choice = self.choices.get(filament)
        return self.names.get(filament, "").strip() or (choice.label() if choice else "") or f"Filament {filament}"

    def target_colour(self, filament: int, palette: dict[int, tuple[int, int, int]]) -> int:
        """Die Allplan-Farbnummer, die die Koerper dieses Filaments bekommen sollen; 0 ohne eigene Wahl.

        Festgehaltene Allplan-Farbe: genau diese Nummer; sonst die naechstliegende der Farbtabelle."""
        choice = self.choices.get(filament)
        if choice is None:
            return 0
        if choice.allplan:
            return choice.allplan
        return model.nearest_colour(choice.rgb(), palette) if palette else 0

    def to_recolour(self, filament: int, palette: dict[int, tuple[int, int, int]]) -> tuple[int, list[str]]:
        """(Zielfarbe, Kennungen der Koerper, die sie noch nicht haben) - leer ohne eigene Wahl."""
        number = self.target_colour(filament, palette)
        if not number:
            return 0, []
        return number, [key for key in self.keys(filament) if self._bodies[key].colour != number]

    def colours(self, filament: int) -> list[tuple[int, tuple[int, int, int]]]:
        """Allplan-Farben der Koerper dieses Filaments, haeufigste zuerst."""
        tally: dict[int, int] = {}
        rgb: dict[int, tuple[int, int, int]] = {}
        for key in self.keys(filament):
            body = self._bodies[key]
            tally[body.colour] = tally.get(body.colour, 0) + 1
            rgb[body.colour] = body.rgb
        return [(colour, rgb[colour]) for colour in sorted(tally, key=lambda colour: -tally[colour])]

    def filament_colours(self) -> dict[int, str]:
        """Farbe je benutztem Filament als "#RRGGBB": die gewaehlte, sonst die haeufigste Farbe seiner Koerper."""
        result = {}
        for filament in sorted(set(self._filament.values())):
            choice = self.choices.get(filament)
            colours = self.colours(filament)
            if choice:
                result[filament] = choice.hex
            elif colours:
                result[filament] = "#%02X%02X%02X" % tuple(max(0, min(255, int(v))) for v in colours[0][1])
        return result

    def filament_choices(self) -> dict[int, Choice]:
        """Gewaehlte Sorte je benutztem Filament - fuer das Bambu-Projekt."""
        return {filament: self.choices[filament] for filament in sorted(set(self._filament.values()))
                if filament in self.choices}

    def summary(self, filament: int) -> str:
        """Eine Zeile fuer die Anzeige: "6 Körper · PLA Basic Jadeweiß", "6 Körper · Farbe 7" oder "leer"."""
        number = self.count(filament)
        choice = self.choices.get(filament)
        if not number:
            return (choice.label() if choice else "") or tr("leer")
        text = tr("1 Körper") if number == 1 else tr("{number} Körper", number=number)
        groups = self.group_names(filament)
        if groups:
            text = tr("{text} · Gruppe {names}", text=text, names=", ".join(groups))
        if choice:
            label = choice.label() or (tr("Farbe {colour}", colour=choice.allplan) if choice.allplan else choice.hex)
            return f"{text} · {label}"
        colours = self.colours(filament)
        if len(colours) == 1:
            return tr("{text} · Farbe {colour}", text=text, colour=colours[0][0])
        return tr("{text} · {count} Farben", text=text, count=len(colours))

    def view(self, armed: int = 0) -> dict:
        """Der Stand fuer das Fenster als schlichte Daten - ohne Bedienelemente.

        `armed` ist das Filament, fuer das gerade Koerper angeklickt werden (0 = keines).
        """
        filaments = [{"number": number, "name": str(self.names.get(number, "")), "shown": self.name_of(number),
                      "count": self.count(number), "summary": self.summary(number),
                      "colours": self._tile_colours(number), "chosen": number in self.choices,
                      "hint": self.name_of(number) if number in self.choices else f"Filament {number}",
                      "armed": armed == number}
                     for number in range(1, MAX_FILAMENTS + 1)]
        try:
            size, usable = self.size_text(), bool(self._filament)
        except ThreeMfError as exc:
            size, usable = str(exc), False
        return {"filaments": filaments, "scale_on": self.scale_on, "reduction": self.reduction, "size": size,
                "can_export": usable, "last_file": self.last_file}

    def _tile_colours(self, filament: int) -> list[tuple[int, int, int]]:
        choice = self.choices.get(filament)
        return [choice.rgb()] if choice else [rgb for _colour, rgb in self.colours(filament)]

    # ------------------------------------------------------------------ Datei

    def parts(self) -> list[Part]:
        """Die Teile fuer die Datei: benannt, in Druckgroesse, auf der Platte, in der Reihenfolge fuer Ueberlappungen."""
        if not self._filament:
            raise ThreeMfError(tr("Noch ist kein Körper einem Filament zugeordnet."))
        if self.scale_on and not self.reduction > 0.0:
            raise ThreeMfError(tr("Der Maßstab muss größer als 0 sein."))
        units = self.units()
        per_filament: dict[int, int] = {}
        for filament, _bodies in units:
            per_filament[filament] = per_filament.get(filament, 0) + 1
        numbered: dict[int, int] = {}
        named: list[Part] = []
        for filament, bodies in units:
            numbered[filament] = numbered.get(filament, 0) + 1
            base = self.name_of(filament)
            # Eine Elementgruppe heisst wie in Allplan; lose Koerper (und namenlose Gruppen) nach dem Filament,
            # durchnummeriert, sobald das Filament mehr als eine Einheit hat.
            own = bodies[0].group_name if bodies[0].group else ""
            name = own or (base if per_filament[filament] == 1 else f"{base} {numbered[filament]}")
            oriented = [model.orient_outward(replace(body.part, name=name, filament=filament)) for body in bodies]
            named.append(oriented[0] if len(oriented) == 1 else model.merged(oriented, name))
        sized = model.scaled(named, self.reduction) if self.scale_on else named
        return model.placed_on_plate(model.ordered_for_overlap(sized))

    def print_size(self) -> tuple[float, float, float]:
        return model.size(self.parts())

    def size_text(self) -> str:
        if not self._filament:
            return tr("Noch nichts zugeordnet")
        width, depth, height = self.print_size()
        mode = f"1:{self.reduction:g}" if self.scale_on else tr("Originalgröße")
        return tr("{width} × {depth} × {height} mm ({mode})", width=f"{width:.1f}", depth=f"{depth:.1f}",
                  height=f"{height:.1f}", mode=mode)


# ---------------------------------------------------------------------------------------------- Uebernahme

LOG = logging.getLogger("threemfstudio.part")
_KEPT_CLASSES = (Part, Choice, Body)                  # Reihenfolge: Body traegt einen Part


def refreshed(value):
    """Ein Objekt aus einem frueheren Werkzeugstart als Objekt der JETZIGEN Klasse.

    Die Zuordnung ueberlebt das Werkzeugende im Speicher von Allplan; wird der Code dazwischen ausgerollt, sind
    ihre Koerper noch Objekte der alten Klasse - ohne die Felder, die der neue Code erwartet (AttributeError
    beim Fensterstart, 2026-11-07). Neue Felder bekommen hier ihre Vorgabe; fehlt ein Pflichtfeld, kommt
    ValueError und die Zuordnung wird verworfen (adopt)."""
    for cls in _KEPT_CLASSES:
        if type(value) is cls or type(value).__name__ != cls.__name__:
            continue
        values = {}
        for member in fields(cls):
            if hasattr(value, member.name):
                values[member.name] = refreshed(getattr(value, member.name))
            elif member.default is not MISSING:
                values[member.name] = member.default
            elif member.default_factory is not MISSING:               # type: ignore[misc]
                values[member.name] = member.default_factory()        # type: ignore[misc]
            else:
                raise ValueError(f"{cls.__name__} aus aelterer Fassung ohne Feld {member.name}")
        return cls(**values)
    return value


def adopt(old) -> Session:
    """Die Zuordnung eines frueheren Werkzeugstarts in eine Sitzung des frisch geladenen Codes - oder eine
    leere Sitzung, wenn der alte Stand nicht mehr passt (steht dann im Protokoll)."""
    session = Session()
    if old is None:
        return session
    try:
        taken = dict(old.__dict__)
        taken["_bodies"] = {key: refreshed(body) for key, body in taken.get("_bodies", {}).items()}
        for name in ("choices", "last_choices"):
            taken[name] = {key: refreshed(choice) for key, choice in taken.get(name, {}).items()}
        session.__dict__.update(taken)
    except (ValueError, TypeError, AttributeError) as exc:
        LOG.warning("Zuordnung aus einer aelteren Fassung verworfen: %s", exc)
        return Session()
    return session
