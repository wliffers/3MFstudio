"""Das Kundenpaket (.allep): alle Programmdateien drin, Regeln des Plugin-Managers eingehalten."""

import os
import sys
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import build_allep  # noqa: E402
import deploy  # noqa: E402


def test_every_program_file_and_the_package_init_go_into_the_package():
    entries = build_allep.package_entries()
    for name in deploy.SCRIPTS + ["__init__.py"]:
        assert "%s/%s" % (build_allep.SCRIPTS_PREFIX, name) in entries
    assert "threemf_text.py" in deploy.SCRIPTS and "threemf_loft.py" in deploy.SCRIPTS


def test_the_palette_points_to_the_program_folder_of_the_package():
    entries = build_allep.package_entries()
    pyp = entries["%s/%s" % (build_allep.LIBRARY_PREFIX, deploy.PYP_FILE)].decode("utf-8")
    assert "<Name>willi_liffers\\3MFStudio\\3MFStudio.py</Name>" in pyp


def test_a_built_package_keeps_the_plugin_manager_rules(tmp_path):
    entries = build_allep.package_entries()
    allep = build_allep.build_allep(entries, dist=str(tmp_path))
    assert build_allep.verify_allep(allep) == []
    with zipfile.ZipFile(allep) as archive:
        config = archive.read("install-config.yml").decode("utf-8")
        assert "UUID: dd4d9405-17ab-4674-88e1-0f0dad922584" in config
        assert "developer: 'Willi Liffers'" in config
        assert not any(name.endswith(".pyc") or "/tests/" in name for name in archive.namelist())
    bundle = build_allep.build_zip(entries, allep, dist=str(tmp_path))
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
    assert "LIESMICH_Installation.txt" in names and os.path.basename(allep) in names
    assert "Manuell/PythonPartsScripts/willi_liffers/3MFStudio/3MFStudio.py" in names


def test_verify_finds_a_broken_package(tmp_path):
    broken = tmp_path / "kaputt.allep"
    with zipfile.ZipFile(broken, "w") as archive:
        archive.writestr("install-config.yml", "plugin:\n  version: 1.0\n")
        archive.writestr("Fremd/irgendwas.txt", "C:\\sandbox\\geheim")
        archive.writestr("%s/%s" % (build_allep.LIBRARY_PREFIX, deploy.PYP_FILE),
                         "<Script><Name>gibtsnicht.py</Name></Script>")
    problems = build_allep.verify_allep(str(broken))
    assert any("Wurzelordner" in p for p in problems)
    assert any("SemVer" in p for p in problems)
    assert any("fehlt im Paket" in p for p in problems)
