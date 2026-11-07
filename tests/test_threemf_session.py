"""Zuordnung Koerper -> Filament und Teileliste fuer die Datei - ohne Allplan."""

import pytest

import threemf_model as model
from shapes import box
from threemf_model import ThreeMfError
from threemf_reader import read_3mf
from threemf_session import Body, Session
from threemf_writer import write_3mf

RED, BLUE, GREEN = (6, (255, 0, 0)), (7, (0, 0, 255)), (4, (0, 255, 0))


def body(key, part, colour=RED):
    return Body(key, key, colour[0], colour[1], part)


def base_and_inlay():
    return (body("grund", box(500, 500, 0, 40, 20, 10, inward=True), BLUE),
            body("schrift", box(510, 507, 5, 20, 6, 5, inward=True), RED))


def test_bodies_are_counted_per_filament_and_move_when_assigned_again():
    session = Session()
    base, inlay = base_and_inlay()
    assert session.assign(1, [base, inlay]) == 2
    assert session.assign(2, [inlay]) == 1
    assert (session.count(1), session.count(2), session.total()) == (1, 1, 2)
    assert session.assign(2, [inlay]) == 0
    assert session.keys(2) == ["schrift"]
    assert (session.filament_of("grund"), session.filament_of("schrift"), session.filament_of("fremd")) == (1, 2, None)


def test_picking_adds_and_picking_the_same_again_takes_out():
    session = Session()
    base, inlay = base_and_inlay()
    assert session.pick(1, [base]) == (1, 0)
    assert session.pick(1, [base, inlay]) == (1, 0)        # gemischt: der neue kommt dazu, keiner geht
    assert session.keys(1) == ["grund", "schrift"]
    assert session.pick(1, [inlay]) == (0, 1)              # nochmal angeklickt: wieder heraus
    assert (session.keys(1), session.filament_of("schrift")) == (["grund"], None)
    assert session.pick(2, [base]) == (1, 0)               # anderes Filament: der Koerper zieht um
    assert (session.count(1), session.count(2)) == (0, 1)
    assert session.pick(2, []) == (0, 0)


def test_view_gives_plain_data_for_the_window():
    session = Session(names={1: "Grundkörper"})
    empty = session.view()
    assert [item["summary"] for item in empty["filaments"]] == ["leer"] * model.MAX_FILAMENTS
    assert (empty["size"], empty["can_export"]) == ("Noch nichts zugeordnet", False)
    base, inlay = base_and_inlay()
    session.assign(1, [base])
    session.assign(2, [inlay])
    view = session.view(armed=2)
    first, second = view["filaments"][0], view["filaments"][1]
    assert (first["name"], first["shown"], first["count"], first["armed"]) == ("Grundkörper", "Grundkörper", 1, False)
    assert (second["name"], second["shown"], second["armed"], second["colours"]) == ("", "Filament 2", True, [(255, 0, 0)])
    assert (view["size"], view["can_export"]) == ("40.0 × 20.0 × 10.0 mm (Originalgröße)", True)


def test_view_does_not_warn_about_the_build_volume_but_refuses_a_nonsense_scale():
    session = Session()
    session.assign(1, [body("haus", box(0, 0, 0, 10000, 8000, 3000))])
    view = session.view()
    # Den Bauraum seines Druckers kennt der Anwender selbst (Wunsch 2026-11-06): keine Warnung, Schreiben geht.
    assert (view["size"], view["can_export"]) == ("10000.0 × 8000.0 × 3000.0 mm (Originalgröße)", True)
    session.scale_on, session.reduction = True, 0
    broken = session.view()
    assert (broken["size"], broken["can_export"]) == ("Der Maßstab muss größer als 0 sein.", False)


def test_clear_empties_one_filament_only():
    session = Session()
    base, inlay = base_and_inlay()
    session.assign(1, [base])
    session.assign(2, [inlay])
    assert session.clear(2) == 1
    assert (session.count(1), session.count(2)) == (1, 0)


def test_sixteen_filaments_like_the_largest_bambu_example():
    Session().assign(16, list(base_and_inlay()))
    with pytest.raises(ThreeMfError):
        Session().assign(17, list(base_and_inlay()))
    with pytest.raises(ThreeMfError):
        Session().assign(0, list(base_and_inlay()))


def test_names_fall_back_to_the_filament_number():
    session = Session(names={2: "Text", 3: "   "})
    assert [session.name_of(n) for n in (1, 2, 3)] == ["Filament 1", "Text", "Filament 3"]


def test_summary_tells_count_and_allplan_colour():
    session = Session()
    base, inlay = base_and_inlay()
    assert session.summary(1) == "leer"
    session.assign(1, [base])
    assert session.summary(1) == "1 Körper · Farbe 7"
    session.assign(1, [inlay])
    assert session.summary(1) == "2 Körper · 2 Farben"
    assert session.colours(1)[0][0] in (6, 7)


def test_parts_are_named_oriented_placed_and_the_inlay_comes_last():
    session = Session(names={1: "Grundkörper", 2: "Text"})
    base, inlay = base_and_inlay()
    session.assign(2, [inlay])            # zuerst die Einlage gewaehlt - in der Datei muss sie trotzdem hinten stehen
    session.assign(1, [base])
    parts = session.parts()
    assert [(p.name, p.filament) for p in parts] == [("Grundkörper", 1), ("Text", 2)]
    assert all(model.signed_volume(p) > 0 for p in parts)
    low, high = model.bounding_box(parts)
    assert low[2] == pytest.approx(0.0)
    assert ((low[0] + high[0]) / 2, (low[1] + high[1]) / 2) == pytest.approx((128.0, 128.0))
    assert session.print_size() == pytest.approx((40.0, 20.0, 10.0))


def test_several_bodies_of_one_filament_are_numbered():
    session = Session(names={1: "Wand"})
    session.assign(1, [body("a", box(0, 0, 0, 10, 10, 10)), body("b", box(20, 0, 0, 10, 10, 5))])
    assert [p.name for p in session.parts()] == ["Wand 1", "Wand 2"]


def letters(group="g1", name="MAX"):
    """Drei Buchstaben einer Allplan-Elementgruppe, nach innen gewendet wie Allplan sie liefert."""
    return [Body(group + key, key, 6, (255, 0, 0), box(x, 0, 5, 8, 8, 4, inward=True), group=group, group_name=name)
            for key, x in (("m", 0), ("a", 10), ("x", 20))]


def test_an_element_group_becomes_one_part_named_like_the_group():
    session = Session(names={1: "Grundkörper", 2: "Schrift"})
    session.assign(2, letters())
    session.assign(1, [body("grund", box(-2, -2, 0, 32, 12, 5, inward=True), BLUE)])
    parts = session.parts()
    assert [(p.name, p.filament) for p in parts] == [("Grundkörper", 1), ("MAX", 2)]
    merged = parts[1]
    assert len(merged.vertices) == 3 * 8 and len(merged.triangles) == 3 * 12
    assert model.signed_volume(merged) == pytest.approx(3 * 8 * 8 * 4)      # jeder Buchstabe fuer sich nach aussen
    assert model.is_closed(merged)
    assert session.summary(2) == "3 Körper · Gruppe MAX · Farbe 6"
    assert session.view()["filaments"][1]["summary"] == "3 Körper · Gruppe MAX · Farbe 6"


def test_groups_and_loose_bodies_share_a_filament_and_an_unnamed_group_is_numbered():
    session = Session(names={1: "Teil"})
    session.assign(1, [body("solo", box(40, 0, 0, 5, 5, 5))] + letters() + letters("g2", ""))
    names = [p.name for p in session.parts()]
    assert sorted(names) == ["MAX", "Teil 1", "Teil 3"]
    assert session.summary(1) == "7 Körper · Gruppe MAX · Farbe 6"
    assert session.count(1) == 7 and len(session.units(1)) == 3


def test_an_older_sessions_bodies_get_the_new_fields_when_adopted():
    """Nach einem Ausrollen ohne Allplan-Neustart liegen im Speicher Koerper der alten Klasse (2026-11-07)."""
    from dataclasses import make_dataclass
    from threemf_session import Choice, adopt

    OldBody = make_dataclass("Body", [("key", str), ("label", str), ("colour", int), ("rgb", tuple), ("part", object)])
    OldChoice = make_dataclass("Choice", [("hex", str), ("name", str, ""), ("brand", str, "")])
    old = Session(names={1: "Alt"})
    old.assign(1, [body("a", box(0, 0, 0, 10, 10, 10))])
    old._bodies["a"] = OldBody("a", "a", 6, (255, 0, 0), box(0, 0, 0, 10, 10, 10))
    old.choices[1] = OldChoice("#112233", "Blau")
    old.last_file = "x.3mf"

    taken = adopt(old)
    assert type(taken.body("a")) is Body and taken.body("a").group == "" and taken.body("a").label == "a"
    assert type(taken.choices[1]) is Choice and taken.choices[1].hex == "#112233" and taken.choices[1].line == ""
    assert taken.names == {1: "Alt"} and taken.last_file == "x.3mf" and taken.count(1) == 1
    assert taken.summary(1) == "1 Körper · Blau"                        # der Fensterstart laeuft wieder

    Crippled = make_dataclass("Body", [("key", str)])                    # ohne Pflichtfelder: nicht uebernehmbar
    old._bodies["a"] = Crippled("a")
    assert adopt(old).total() == 0
    assert adopt(None).total() == 0


def test_a_group_split_over_two_filaments_gives_one_part_per_filament():
    session = Session(names={1: "Rot", 2: "Blau"})
    m, a, x = letters()
    session.assign(1, [m, x])
    session.assign(2, [a])
    assert sorted((p.name, p.filament) for p in session.parts()) == [("MAX", 1), ("MAX", 2)]


def test_equal_bodies_keep_the_order_of_assignment_so_the_last_one_wins():
    session = Session()
    first, second = body("erst", box(0, 0, 0, 10, 10, 10)), body("dann", box(5, 0, 0, 10, 10, 10))
    session.assign(1, [first])
    session.assign(2, [second])
    assert [p.filament for p in session.parts()] == [1, 2]
    session.assign(1, [first])            # erneut angeklickt -> jetzt der zuletzt zugeordnete
    assert [p.filament for p in session.parts()] == [2, 1]


def test_original_size_is_default_and_scaling_is_an_option():
    session = Session()
    session.assign(1, [body("haus", box(0, 0, 0, 10000, 8000, 3000))])
    assert session.size_text() == "10000.0 × 8000.0 × 3000.0 mm (Originalgröße)"
    session.scale_on = True
    session.reduction = 100
    assert session.print_size() == pytest.approx((100.0, 80.0, 30.0))
    assert session.size_text() == "100.0 × 80.0 × 30.0 mm (1:100)"


def test_nonsense_scale_and_empty_export_are_refused():
    session = Session()
    with pytest.raises(ThreeMfError):
        session.parts()
    session.assign(1, [body("a", box(0, 0, 0, 1, 1, 1))])
    session.scale_on, session.reduction = True, 0
    with pytest.raises(ThreeMfError):
        session.parts()


def test_session_to_file_and_back(tmp_path):
    session = Session(names={1: "Grundkörper", 2: "Text"})
    base, inlay = base_and_inlay()
    session.assign(1, [base])
    session.assign(2, [inlay])
    target = str(tmp_path / "schild.3mf")
    write_3mf(target, session.parts())
    back = read_3mf(target)
    assert [(p.name, p.filament) for p in back] == [("Grundkörper", 1), ("Text", 2)]
    assert model.size(back) == pytest.approx((40.0, 20.0, 10.0))
