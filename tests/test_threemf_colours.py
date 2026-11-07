"""Farbe und Sorte je Filament, Tauschen, Umfaerben, "Meine Farben" - ohne Allplan und ohne Fenster."""

import threemf_slicer as slicer
import threemf_window as window
from shapes import box
from threemf_session import Body, Choice, Session, mine_from_settings, remember_mine

PALETTE = {1: (0, 0, 0), 4: (0, 255, 0), 6: (255, 0, 0), 7: (0, 0, 255), 9: (255, 255, 255)}
GREEN = Choice("#00AE42", "Bambu Grün", "Bambu Lab", "PLA Basic", "PLA", "GFA00")


def _session():
    session = Session()
    session.assign(1, [Body("aussen", "Grundkörper", 6, (255, 0, 0), box(0, 0, 0, 40, 20, 10))])
    session.assign(2, [Body("innen", "Schrift", 9, (255, 255, 255), box(10, 5, 5, 20, 6, 5))])
    return session


def test_a_chosen_colour_names_the_filament_and_goes_to_bambu():
    session = _session()
    session.choose(1, GREEN)
    assert session.name_of(1) == "PLA Basic Bambu Grün"
    assert session.filament_colours() == {1: "#00AE42", 2: "#FFFFFF"}
    assert session.filament_choices() == {1: GREEN}
    assert session.summary(1) == "1 Körper · PLA Basic Bambu Grün"
    names = {part.filament: part.name for part in session.parts()}
    assert names[1] == "PLA Basic Bambu Grün" and names[2] == "Filament 2"


def test_an_own_name_still_wins_and_allplan_colour_comes_back():
    session = _session()
    session.choose(1, GREEN)
    session.names[1] = "Sockel"
    assert session.name_of(1) == "Sockel"
    session.choose(1, None)
    assert session.filament_colours()[1] == "#FF0000" and session.name_of(1) == "Sockel"


def test_the_window_shows_the_chosen_colour_and_the_name_it_will_get():
    session = _session()
    session.choose(1, GREEN)
    entry = session.view()["filaments"][0]
    assert entry["colours"] == [(0, 174, 66)] and entry["chosen"] and entry["hint"] == "PLA Basic Bambu Grün"
    assert session.view()["filaments"][1]["hint"] == "Filament 2"


def test_recolouring_targets_the_nearest_allplan_colour_and_only_bodies_that_differ():
    session = _session()
    assert session.to_recolour(1, PALETTE) == (0, [])            # ohne eigene Wahl wird nichts umgefaerbt
    session.choose(1, GREEN)
    assert session.to_recolour(1, PALETTE) == (4, ["aussen"])
    session.recoloured("aussen", "aussen-neu", 4, (0, 255, 0))
    assert session.to_recolour(1, PALETTE) == (4, [])
    assert session.keys(1) == ["aussen-neu"] and session.body("aussen-neu").colour == 4
    assert session.body("aussen") is None


def test_swapping_moves_the_bodies_and_keeps_colour_with_the_filament():
    session = _session()
    session.choose(2, GREEN)
    assert session.swap(1, 2) == 2
    assert session.keys(1) == ["innen"] and session.keys(2) == ["aussen"]
    # Filament 1 hatte keine eigene Wahl: seine Allplan-Farbe (rot, 6) bleibt bei ihm und faerbt den Innenkoerper
    assert session.choices[1].allplan == 6 and session.to_recolour(1, PALETTE) == (6, ["innen"])
    assert session.to_recolour(2, PALETTE) == (4, ["aussen"])
    assert session.summary(1) == "1 Körper · Farbe 6"
    assert session.name_of(1) == "Filament 1"                    # festgehaltene Allplan-Farbe gibt keinen Namen


def test_swapping_with_an_empty_filament_and_with_itself():
    session = _session()
    assert session.swap(1, 1) == 0
    assert session.swap(1, 5) == 1
    assert session.keys(5) == ["aussen"] and 5 not in session.choices and session.choices[1].allplan == 6


def test_the_overlap_winner_does_not_change_by_swapping():
    session = _session()
    before = [part.name for part in session.parts()]
    session.swap(1, 2)
    assert [part.name for part in session.parts()][-1] == "Filament 1"   # der kleinere Koerper steht weiter zuletzt
    assert len(before) == 2


def test_my_colours_are_kept_newest_first_without_doubles(tmp_path):
    settings = {"slicer": ""}
    own = Choice("#123456", "#123456", "Bambu Lab", "PLA Basic", "PLA", "GFA00")
    remember_mine(settings, own)
    remember_mine(settings, Choice("#ABCDEF", "#ABCDEF"))
    remember_mine(settings, own)
    assert [choice.hex for choice in mine_from_settings(settings)] == ["#123456", "#ABCDEF"]
    path = str(tmp_path / "einstellungen.json")
    slicer.save(settings, path)
    assert mine_from_settings(slicer.load(path))[0] == own


def test_broken_my_colours_entries_are_left_out():
    settings = {"meine_farben": [{"hex": "#12345"}, "Unsinn", {"hex": "#GG0000"}, {"hex": "#00ff00", "name": "grün"}]}
    assert mine_from_settings(settings) == [Choice("#00FF00", "grün")]


def test_labels_of_the_colour_selection():
    assert window.line_label("PLA Basic", "PLA") == "PLA Basic"
    assert window.line_label("PolyTerra", "PLA") == "PolyTerra (PLA)"
    assert window.mine_label(Choice("#00AE42", "#00AE42", "Bambu Lab", "PLA Basic")) == "PLA Basic · #00AE42"
    assert window.mine_label(Choice("#00AE42")) == "#00AE42"


def test_the_window_description_has_the_colour_selection_and_the_swap_buttons():
    xaml = window.build_xaml()
    for name in ("ColourPanel", "ColourBrand", "ColourLine", "ColourTiles", "ColourMine", "ColourHex", "ColourAuto",
                 "ColourOwn", "SwapHint", "ChipButton1", "Swap16"):
        assert 'x:Name="%s"' % name in xaml
