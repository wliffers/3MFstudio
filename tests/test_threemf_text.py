"""Deutsch und Englisch: jeder sichtbare Text hat eine englische Fassung mit denselben Platzhaltern."""

import ast
import os
import string

import threemf_text
from threemf_text import ENGLISH, set_language, tr

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


def used_texts() -> set:
    """Alle Texte, die im Quelltext an tr(...) oder T(...) gehen."""
    found = set()
    for name in os.listdir(SRC):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(SRC, name), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("tr", "T") \
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                found.add(node.args[0].value)
    return found


def fields(text: str) -> set:
    return {field for _literal, field, _spec, _conv in string.Formatter().parse(text) if field}


def test_every_visible_text_has_an_english_version():
    missing = sorted(used_texts() - set(ENGLISH))
    assert missing == []


def test_english_texts_keep_the_placeholders():
    wrong = [german for german, english in ENGLISH.items() if fields(german) != fields(english)]
    assert wrong == []


def test_no_english_text_is_left_unused():
    assert sorted(set(ENGLISH) - used_texts()) == []


def test_language_follows_allplan_and_falls_back_to_english():
    try:
        assert set_language("de") == "de"
        assert tr("{number} Körper", number=3) == "3 Körper"
        assert set_language("en") == "en"
        assert tr("{number} Körper", number=3) == "3 bodies"
        assert set_language("fr") == "en"
        assert set_language("") == "en"
        assert tr("unbekannter Text {x}", x=1) == "unbekannter Text 1"     # ohne Fassung: der deutsche Text
    finally:
        set_language("de")


def test_the_window_description_is_well_formed_in_english_too():
    import xml.etree.ElementTree as ET
    import threemf_window
    try:
        set_language("en")
        root = ET.fromstring(threemf_window.build_xaml())
        texts = [element.get("Content") for element in root.iter() if element.get("Content")]
        assert "Write 3MF" in texts and "Import 3MF" in texts
        ET.fromstring(threemf_window.busy_xaml(tr("3MF wird importiert"), tr("Datei wird gelesen …")))
    finally:
        set_language("de")
    assert threemf_text.language() == "de"
