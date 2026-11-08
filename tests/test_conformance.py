"""3MF nach Standard: Lesen gegen die Konformitaetstests des 3MF-Konsortiums, Schreiben gegen lib3mf.

Drei Teile:
1. Kleine selbstgebaute Dateien - laufen immer: Standardfarben, Pflicht-Erweiterungen, DTD, kaputte Zahlen,
   falsche Punktnummern, doppelte Nummern, Verschluesselung.
2. Die offiziellen Testdateien (conformance/test_suites, `python fetch_conformance.py`): jede gueltige Datei wird
   gelesen, keine Datei bringt den Leser zum Absturz, und jeder ungueltige Fall ist entschieden - abgelehnt
   oder mit Grund geduldet. Ein neuer Fall ohne Entscheidung macht den Test rot. Dauer: etwa 90 s.
3. Unsere geschriebenen Dateien gegen den strengen Leser von lib3mf (MCP-Server des Konsortiums, ueber
   tests/check_3mf.mjs; braucht Node.js).
Was fehlt, wird uebersprungen - das heisst "nicht geprueft", nie "in Ordnung".
"""

import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from shapes import box
from threemf_model import ThreeMfError, merged
from threemf_reader import read_file
from threemf_writer import write_3mf

PROJECT = Path(__file__).resolve().parents[1]
SUITES = Path(os.environ.get("THREEMF_TEST_SUITES", PROJECT / "conformance" / "test_suites"))
CHECKER = Path(__file__).resolve().parent / "check_3mf.mjs"
MCP_CLI = PROJECT / "conformance" / "3mf-mcp" / "dist" / "cli.js"

CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
MATERIAL_NS = "http://schemas.microsoft.com/3dmanufacturing/material/2015/02"
RELS = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
        'relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>{extra}</Relationships>')
CUBE_VERTICES = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for z in (0, 10) for y in (0, 10) for x in (0, 10))
CUBE_TRIANGLES = ((0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
                  (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5))


def _cube(object_id: int, attributes: str = "", triangle_attributes=None) -> str:
    extra = triangle_attributes or (lambda index: "")
    triangles = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"{extra(index)}/>'
                        for index, (a, b, c) in enumerate(CUBE_TRIANGLES))
    return (f'<object id="{object_id}" type="model"{attributes}><mesh><vertices>{CUBE_VERTICES}</vertices>'
            f'<triangles>{triangles}</triangles></mesh></object>')


def _package(tmp_path, resources: str, items: str, head: str = "", prolog: str = "", rels_extra: str = "",
             name: str = "probe.3mf") -> str:
    model = (f'<?xml version="1.0" encoding="UTF-8"?>{prolog}<model unit="millimeter" xmlns="{CORE_NS}"{head}>'
             f'<resources>{resources}</resources><build>{items}</build></model>')
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("_rels/.rels", RELS.format(extra=rels_extra))
        archive.writestr("3D/3dmodel.model", model)
    return str(path)


# --- 1. Selbstgebaute Faelle -------------------------------------------------------------------------------------

def test_standard_colours_become_filaments_in_file_order(tmp_path):
    resources = (f'<basematerials id="1"><base name="Rot" displaycolor="#FF0000"/><base name="Blau" '
                 f'displaycolor="#0000ffcc"/></basematerials>'
                 + _cube(2, ' pid="1" pindex="1"') + _cube(3, ' pid="1" pindex="0"') + _cube(4, ' pid="1" pindex="1"'))
    parts = read_file(_package(tmp_path, resources, '<item objectid="2"/><item objectid="3"/><item objectid="4"/>')).parts
    assert [(part.filament, part.colour) for part in parts] == [(1, "#0000FF"), (2, "#FF0000"), (1, "#0000FF")]


def test_colour_group_of_the_materials_extension_is_read(tmp_path):
    resources = (f'<m:colorgroup id="5"><m:color color="#00FF00"/></m:colorgroup>' + _cube(2, ' pid="5" pindex="0"'))
    head = f' xmlns:m="{MATERIAL_NS}" requiredextensions="m"'
    parts = read_file(_package(tmp_path, resources, '<item objectid="2"/>', head)).parts
    assert (parts[0].filament, parts[0].colour) == (1, "#00FF00")


def test_triangles_in_several_colours_count_as_painted_and_keep_the_most_frequent(tmp_path):
    resources = ('<basematerials id="1"><base name="a" displaycolor="#111111"/><base name="b" displaycolor="#222222"/>'
                 '</basematerials>' + _cube(2, ' pid="1" pindex="0"', lambda i: ' p1="1"' if i < 3 else ""))
    result = read_file(_package(tmp_path, resources, '<item objectid="2"/>'))
    assert (result.parts[0].colour, result.painted_parts) == ("#111111", 1)


def test_file_without_colours_stays_on_filament_one(tmp_path):
    parts = read_file(_package(tmp_path, _cube(2) + _cube(3), '<item objectid="2"/><item objectid="3"/>')).parts
    assert [(part.filament, part.colour) for part in parts] == [(1, ""), (1, "")]


def test_unknown_required_extension_is_refused_by_name(tmp_path):
    head = ' xmlns:b="http://schemas.microsoft.com/3dmanufacturing/beamlattice/2017/02" requiredextensions="b"'
    with pytest.raises(ThreeMfError, match="Beam Lattice"):
        read_file(_package(tmp_path, _cube(2), '<item objectid="2"/>', head))


def test_required_prefix_without_namespace_is_refused(tmp_path):
    with pytest.raises(ThreeMfError, match="„q“"):
        read_file(_package(tmp_path, _cube(2), '<item objectid="2"/>', ' requiredextensions="q"'))


def test_known_required_extensions_are_accepted(tmp_path):
    head = (' xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
            'xmlns:t="http://schemas.microsoft.com/3dmanufacturing/trianglesets/2021/07" requiredextensions="p t"')
    assert len(read_file(_package(tmp_path, _cube(2), '<item objectid="2"/>', head)).parts) == 1


def test_dtd_is_refused(tmp_path):
    prolog = '<!DOCTYPE model [<!ENTITY a "aaaa">]>'
    with pytest.raises(ThreeMfError, match="DTD"):
        read_file(_package(tmp_path, _cube(2), '<item objectid="2"/>', prolog=prolog))


@pytest.mark.parametrize("value", ["20,000", "nan", "inf"])
def test_broken_number_is_a_message_not_a_crash(tmp_path, value):
    resources = _cube(2).replace('x="10"', f'x="{value}"', 1)
    with pytest.raises(ThreeMfError, match="keine gültige Zahl"):
        read_file(_package(tmp_path, resources, '<item objectid="2"/>'))


def test_triangle_pointing_past_the_vertices_is_refused(tmp_path):
    resources = _cube(2).replace('v3="1"/>', 'v3="9"/>', 1)
    with pytest.raises(ThreeMfError, match="Punkte, die es nicht gibt"):
        read_file(_package(tmp_path, resources, '<item objectid="2"/>'))


def test_duplicate_resource_number_is_refused(tmp_path):
    with pytest.raises(ThreeMfError, match="doppelt"):
        read_file(_package(tmp_path, _cube(2) + _cube(2), '<item objectid="2"/>'))


def test_encrypted_file_gets_its_own_message(tmp_path):
    keystore = ('<Relationship Target="/Secure/keystore.xml" Id="rel1" '
                'Type="http://schemas.microsoft.com/3dmanufacturing/2019/04/keystore"/>')
    with pytest.raises(ThreeMfError, match="verschlüsselt"):
        read_file(_package(tmp_path, _cube(2), '<item objectid="2"/>', rels_extra=keystore))


# --- 2. Konformitaetstests des 3MF-Konsortiums ------------------------------------------------------------------

#: Gueltige Dateien, die 3MFStudio bewusst nicht liest - die Meldung muss den Grund nennen.
UNSUPPORTED_POSITIVE = {"0720": "Production Alternatives", "0722": "Production Alternatives",
                        "0740": "verschlüsselt"}
#: Ungueltige Faelle, die abgelehnt werden muessen (Testnummer -> warum).
MUST_REFUSE = {
    "0202": "Teilname endet auf Punkt - Modell nicht auffindbar",
    "0203": "Punkt als Pfadsegment - Modell nicht auffindbar",
    "0402": "Modellbeziehung zeigt ins Leere",
    "0412": "Dreieck verweist hinter die Punktliste",
    "0422": "Komma statt Punkt in Zahlen",
    "0428": "unbekannte Pflicht-Erweiterung",
    "0801": "Produktionsverweis auf fehlenden Koerper oder Teil",
    "0820": "Production Alternatives verlangt", "0822": "Production Alternatives verlangt",
}
#: Einzelne Dateien eines Falls, die abgelehnt werden muessen, wo andere desselben Falls geduldet sind.
MUST_REFUSE_FILES = {"N_XXX_0413_02", "N_XPX_0413_02", "N_XPX_0415_02", "N_XPX_0415_03", "N_XPX_0415_04"}
#: Ungueltige Faelle, die gelesen werden duerfen: die Form stimmt trotzdem, oder der Import repariert und meldet.
TOLERATED = {
    "0204": "Verpackung: Parameter an der Beziehung", "0205": "Verpackung: doppelter Inhaltstyp",
    "0206": "Verpackung: leere Dateiendung", "0207": "Verpackung: leerer Teilname",
    "0208": "Verpackung: Unicode im Zip-Namen", "0403": "externe Beziehung - wird nie verfolgt",
    "0404": "Verpackung: Inhaltstypen", "0405": "Verpackung: Beziehungen zum Vorschaubild",
    "0406": "Verpackung: doppelte Beziehung", "0407": "Verpackung: Beziehungsziel fehlt (nicht das Modell)",
    "0409": "xml:space am Wurzelelement - ohne Wirkung", "0410": "fremde oder doppelte Metadaten - nicht gelesen",
    "0411": "Dreieck mit doppeltem Punkt - der Import entfernt es",
    "0413": "doppelte Beziehungs-Id (_01) - nur die Modellbeziehung zaehlt",
    "0415": "Teilname mit Punkt am Anfang (_01) - wird im Paket gefunden",
    "0416": "nach innen gedrehtes Netz - der Import dreht es nach aussen",
    "0418": "einzelne Flaeche nach innen - der Import richtet sie aus", "0419": "CMYK-Vorschaubild - nicht gelesen",
    "0420": "DTD in [Content_Types].xml - diese Datei liest 3MFStudio nicht",
    "0421": "Lage ausserhalb des Druckraums - in Allplan ohne Bedeutung",
    "0424": "Material an einem Objekt aus Komponenten - ohne Wirkung",
    "0426": "weniger als 4 Dreiecke - kommt als Flaechenkoerper mit Meldung",
    "0427": "doppelter Punkt, nicht-mannigfaltige Kante - der Import repariert",
    "0802": "UUIDs der Produktionserweiterung - nicht gebraucht",
    "0803": "Pfad in einem Nicht-Wurzelteil - aufgeloest wird nur im Paket",
    "2800": "fehlerhafte Dreiecksgruppen - Gruppen werden nicht ausgewertet",
    "2802": "fehlerhafte Dreiecksgruppen - Gruppen werden nicht ausgewertet",
}

needs_suites = pytest.mark.skipif(not SUITES.is_dir(), reason="conformance/test_suites fehlt - python "
                                                               "fetch_conformance.py; nicht geprueft")


def _suite_files(prefix: str) -> list[Path]:
    return sorted(path for path in SUITES.glob("suite*/**/*.3mf") if path.name.startswith(prefix))


def _code(path: Path) -> str:
    return path.stem.split("_")[2]


@needs_suites
def test_every_valid_test_file_is_read_or_refused_with_its_reason():
    problems = []
    for path in _suite_files("P_"):
        reason = UNSUPPORTED_POSITIVE.get(_code(path))
        try:
            parts = read_file(str(path)).parts
        except ThreeMfError as exc:
            if reason is None or reason not in str(exc):
                problems.append(f"{path.name}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 - jeder andere Fehler ist ein Absturz des Lesers
            problems.append(f"{path.name}: ABSTURZ {type(exc).__name__}: {exc}")
            continue
        if reason is not None:
            problems.append(f"{path.name}: gelesen, obwohl nicht unterstuetzt ({reason})")
        elif not parts:
            problems.append(f"{path.name}: keine Koerper")
    assert not problems, "\n".join(problems)


@needs_suites
def test_every_invalid_test_file_is_decided_and_never_crashes_the_reader():
    problems = []
    for path in _suite_files("N_"):
        code = _code(path)
        refuse = code in MUST_REFUSE or path.stem in MUST_REFUSE_FILES
        if not refuse and code not in TOLERATED:
            problems.append(f"{path.name}: neuer Fall ohne Entscheidung")
            continue
        try:
            read_file(str(path))
        except ThreeMfError:
            continue
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{path.name}: ABSTURZ {type(exc).__name__}: {exc}")
            continue
        if refuse:
            problems.append(f"{path.name}: gelesen, muss abgelehnt werden ({MUST_REFUSE.get(code, 'Einzelfall')})")
    assert not problems, "\n".join(problems)


# --- 3. Unsere Dateien gegen den strengen Leser von lib3mf ---------------------------------------------------------

needs_lib3mf = pytest.mark.skipif(shutil.which("node") is None or not MCP_CLI.is_file(),
                                  reason="Node.js oder conformance/3mf-mcp fehlt - python fetch_conformance.py; "
                                         "nicht geprueft")


@needs_lib3mf
def test_our_files_pass_the_strict_lib3mf_reader(tmp_path):
    files = {
        "einzel.3mf": [box(0, 0, 0, 20, 20, 20)],
        "zwei_objekte.3mf": [box(0, 0, 0, 20, 20, 20, "A", 1), box(40, 0, 0, 20, 20, 20, "B", 2)],
        "steckend.3mf": [box(0, 0, 0, 40, 40, 10, "Platte", 1), box(10, 10, 9, 10, 10, 5, "Schrift ÄÖÜ & <x>", 2)],
        "gruppe.3mf": [merged([box(0, 0, 0, 10, 10, 10), box(20, 0, 0, 10, 10, 10)], "Gruppe MAX")],
    }
    for name, parts in files.items():
        write_3mf(str(tmp_path / name), parts)
    run = subprocess.run(["node", str(CHECKER)] + [str(tmp_path / name) for name in files],
                         capture_output=True, text=True, encoding="utf-8", timeout=300, check=False)
    lines = [json.loads(line) for line in run.stdout.splitlines() if line.startswith("{")]
    assert len(lines) == len(files), run.stderr
    verdicts = {Path(line["file"]).name: line["result"].get("validation", {}) for line in lines}
    failed = {name: [entry["message"] for entry in result.get("strict", {}).get("errors", [])]
                    + [entry["message"] for entry in result.get("nonStrict", {}).get("warnings", [])]
              for name, result in verdicts.items()
              if not (result.get("compliant") and result.get("preflightPassed"))}
    assert not failed, failed
