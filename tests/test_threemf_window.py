"""Das Fenster ohne Allplan und ohne WPF: Beschreibung (XAML), Namen der Bedienteile, Anzeige-Regeln, Laufzeit.

Was hier NICHT geprueft werden kann: dass Allplan das Fenster wirklich zeigt und Klicks ankommen - das
belegt die Live-Probe (Fotos, Protokoll).
"""

import importlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import threemf_window as window
from shapes import box
from threemf_session import Body, Session

X = "{http://schemas.microsoft.com/winfx/2006/xaml}"
SOURCE = Path(window.__file__).read_text(encoding="utf-8")


def xaml_root():
    return ET.fromstring(window.build_xaml())


def xaml_names() -> set:
    return {element.get(X + "Name") for element in xaml_root().iter() if element.get(X + "Name")}


def test_description_is_well_formed_and_has_one_frame():
    root = xaml_root()
    assert root.tag.endswith("}Border")
    assert root.get(X + "Name") == "Shell"


def test_every_part_the_code_asks_for_exists_in_the_description():
    names = xaml_names()
    literal = set(re.findall(r'_(?:part|click)\("(\w+)"', SOURCE))
    per_filament = set(re.findall(r'_(?:part|click)\(f"(\w+)\{number\}"', SOURCE))
    per_scale = set(re.findall(r'_(?:part|click)\(f"(\w+)\{value\}"', SOURCE))
    grips = {"Header", "BarPanel"}
    assert literal and per_filament and per_scale
    wanted = literal | grips
    wanted |= {f"{stem}{number}" for stem in per_filament for number in window.FILAMENTS}
    wanted |= {f"{stem}{value}" for stem in per_scale for value in window.SCALE_PRESETS}
    assert wanted - names == set()


def test_part_names_are_unique():
    found = [element.get(X + "Name") for element in xaml_root().iter() if element.get(X + "Name")]
    # "bd" ist der Rahmen in jeder Knopf-Vorlage - der Name gilt nur innerhalb seiner Vorlage.
    found = [name for name in found if name != "bd"]
    assert len(found) == len(set(found))


def test_every_style_that_is_used_is_defined():
    text = window.build_xaml()
    defined = set(re.findall(r'x:Key="(\w+)"', text))
    used = set(re.findall(r"\{StaticResource (\w+)\}", text))
    switched = set(re.findall(r'FindResource\("(\w+)" if \w+ else "(\w+)"\)', SOURCE))
    used |= {name for pair in switched for name in pair}
    assert used and used - defined == set()


def test_colours_become_hex_and_stay_in_range():
    assert window.hex_colour((255, 0, 0)) == "#FF0000"
    assert window.hex_colour((300, -5, 16)) == "#FF0010"
    assert window.swatch_colours([]) == []
    assert window.swatch_colours([(0, 0, 255), (0, 255, 0), (1, 2, 3)]) == ["#0000FF", "#00FF00"]


def entry(number, count=0, name="", armed=False):
    return {"number": number, "name": name, "shown": name or f"Filament {number}", "count": count,
            "summary": "leer" if not count else f"{count} Körper · Farbe 7", "colours": [], "armed": armed}


def test_filaments_beyond_three_show_only_when_needed():
    assert all(window.card_visible(entry(number), 3) for number in (1, 2, 3))
    assert not window.card_visible(entry(4), 3)
    assert window.card_visible(entry(4), 4)
    assert window.card_visible(entry(9, count=1), 3)
    assert window.card_visible(entry(4, name="Stütze"), 3)
    assert window.card_visible(entry(16, armed=True), 3)


def test_add_button_opens_the_next_hidden_filament_and_disappears_at_sixteen():
    filaments = [entry(number) for number in window.FILAMENTS]
    assert window.next_hidden(filaments, 3) == 4
    filaments[3] = entry(4, count=2)                    # Filament 4 benutzt -> als naechstes kommt 5
    assert window.next_hidden(filaments, 3) == 5
    assert window.next_hidden(filaments, 16) == 0
    assert len(window.FILAMENTS) == 16


def test_texts_of_card_and_bar():
    assert window.sub_line(entry(1)) == "leer"
    assert window.sub_line(entry(2, count=3, armed=True)) == "3 Körper · Farbe 7 · läuft"
    assert window.bar_label(entry(2, count=3, name="Text")) == "Text  3"
    assert window.scale_label(100.0) == "1:100"
    assert window.scale_label(2.5) == "1:2.5"


def test_runtime_of_an_older_version_gets_the_new_fields():
    window.runtime()
    module = window.sys.modules[window.HOLDER]
    saved = module.runtime
    try:
        class Old:
            pass
        old = Old()
        old.position = (1.0, 2.0)
        module.runtime = old
        state = window.runtime()
        assert state is old and state.position == (1.0, 2.0)
        assert (state.adapters, state.session, state.timers) == ({}, None, [])
    finally:
        module.runtime = saved


def test_runtime_survives_reloading_the_module():
    state = window.runtime()
    state.position = (10.0, 20.0)
    state.collapsed = True
    try:
        reloaded = importlib.reload(window)
        assert reloaded.runtime() is state
        assert (reloaded.runtime().position, reloaded.runtime().collapsed) == ((10.0, 20.0), True)
    finally:
        state.position, state.collapsed = None, False


def test_closing_without_an_open_window_does_nothing():
    window.runtime().window = None
    window.close_window()
    assert window.runtime().window is None


class FakeWindow:
    def __init__(self):
        self.calls = []

    def detach(self):
        self.calls.append("detach")

    def close(self):
        self.calls.append("close")


def test_an_old_window_is_detached_before_it_closes():
    old = FakeWindow()
    window.runtime().window = old
    window.close_window()
    assert old.calls == ["detach", "close"]
    assert window.runtime().window is None


def test_the_view_of_a_session_feeds_the_window_rules():
    session = Session(names={2: "Text"})
    session.assign(2, [Body("a", "a", 7, (0, 0, 255), box(0, 0, 0, 40, 20, 10)),
                       Body("b", "b", 6, (255, 0, 0), box(50, 0, 0, 10, 10, 10))])
    view = session.view(armed=2)
    second = view["filaments"][1]
    assert window.swatch_colours(second["colours"]) in (["#0000FF", "#FF0000"], ["#FF0000", "#0000FF"])
    assert window.sub_line(second) == "2 Körper · 2 Farben · läuft"
    assert window.bar_label(second) == "Text  2"
    assert [window.card_visible(item, 3) for item in view["filaments"]] == [True, True, True] + [False] * 13
    assert view["last_file"] == ""
    session.last_file = r"C:\Druck\modell.3mf"
    assert session.view()["last_file"] == r"C:\Druck\modell.3mf"


def _named(name):
    return next(element for element in xaml_root().iter() if element.get(X + "Name") == name)


def test_build_volume_button_sits_left_of_the_gear():
    """Wunsch 2026-11-08: Wuerfel-Symbol links neben dem Zahnrad - rechts angedockt heisst: direkt danach."""
    order = [element.get(X + "Name") for element in _named("Header")]
    assert order.index("Volume") == order.index("Settings") + 1
    assert window._VOLUME in window.build_xaml()


def test_build_volume_card_looks_like_the_colour_selection_and_holds_the_plate():
    volume, colour = _named("VolumePanel"), _named("ColourPanel")
    for key in ("Margin", "Padding", "CornerRadius", "Background", "BorderBrush", "BorderThickness", "Visibility"):
        assert volume.get(key) == colour.get(key), key
    inside = {element.get(X + "Name") for element in volume.iter()}
    assert {"PlatePrinter", "PlatePlace", "PlateVolume", "VolumeStatus", "VolumeClose", *window.SIZE_BOXES} <= inside
    assert not {"PlatePrinter", "PlatePlace", "PlateWidth"} & {e.get(X + "Name") for e in _named("SettingsPanel").iter()}


def test_size_fields_are_always_visible():
    """X/Y/Z stehen immer da (frueher nur bei "Eigene Maße")."""
    assert "PlateCustom" not in xaml_names()
    for name in window.SIZE_BOXES:
        assert _named(name).get("Visibility") in (None, "Visible")
