"""Den Ordner "Online Repo" aus dem Projekt zusammenstellen - das, was veroeffentlicht wird.

Der Projektordner ist Arbeitsplatz, "Online Repo" ist das Produkt: Quellcode, Tests, Bauskripte, Icons und
die Installationsanleitung werden kopiert; Arbeitsnotizen (AGENTS/STATE/PLAN/prompt*), Fremddaten (input/),
Versuche (spike_*) und Laufzeitreste bleiben draussen. Die von Hand geschriebenen Dateien im Repo (README,
LICENSE, Hinweise, CHANGELOG, .gitignore, docs/, .github/) fasst das Skript nie an.

Das fertige Paket (dist/*.allep, *.zip) landet in "Online Repo/release/" - fuer den GitHub-Release, nicht
zum Einchecken (steht in .gitignore).

Danach prueft das Skript alle Textdateien auf Rechnerpfade und Geheimnisse und nennt jeden Treffer mit
Datei:Zeile. Es behebt nichts still.

    python publish_repo.py            # kopieren + pruefen
    python publish_repo.py --check    # nur pruefen
"""

import argparse
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "Online Repo")

FOLDERS = ["src", "tests", "__snapshots__", "assets"]
FILES = ["build_allep.py", "build_filaments.py", "build_printers.py", "deploy.py", "fetch_conformance.py",
         "publish_repo.py", "LIESMICH_Installation.txt"]
#: Messprotokolle, die die Formatregeln belegen: Quelle im Projekt -> Name unter docs/messungen/
MEASUREMENTS = {"spike_g1/ERGEBNIS.md": "G1_Ergebnis.md", "spike_g1/BELEGE.md": "G1_Belege.md",
                "spike_g2/ERGEBNIS.md": "G2_Ergebnis.md"}
RELEASE_FROM = os.path.join(HERE, "dist")
RELEASE_TO = os.path.join(TARGET, "release")

SKIP_NAMES = {"__pycache__", "___pyp__", ".pytest_cache", ".claude"}   # .claude: Marker der Entwicklungsumgebung
SKIP_SUFFIXES = (".pyc", ".pyo", ".log")

TEXT_SUFFIXES = (".py", ".pyp", ".txt", ".md", ".json", ".yml", ".yaml", ".cfg", ".toml", ".xml", ".mjs")
FORBIDDEN = [
    (re.compile(r"C:\\\\?Users\\\\?(?!<USER>)", re.IGNORECASE), "Benutzerpfad"),   # <USER> ist der Platzhalter der Doku
    (re.compile(r"C:\\\\?sandbox", re.IGNORECASE), "Arbeitsordner"),
    (re.compile(re.escape(os.environ.get("USERNAME", "") or "<kein Benutzer>"), re.IGNORECASE), "Benutzername"),
    (re.compile(r"api[_-]?key|secret|password|passwort|\bBearer\b", re.IGNORECASE), "Geheimnis?"),
    (re.compile(r"\.\./\.\./scripts|projects[\\/](?!3MF)", re.IGNORECASE), "Workspace-Abhaengigkeit"),
]


def _skip(name):
    return name in SKIP_NAMES or name.endswith(SKIP_SUFFIXES)


def copy_tree(source, target):
    """Kopiert einen Ordner ohne Laufzeitreste; am Ziel verschwinden Dateien, die es in der Quelle nicht mehr gibt."""
    if os.path.isdir(target):
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=lambda _folder, names: [name for name in names if _skip(name)])


def assemble():
    os.makedirs(TARGET, exist_ok=True)
    print("Ziel: %s" % TARGET)
    for name in FOLDERS:
        copy_tree(os.path.join(HERE, name), os.path.join(TARGET, name))
        print("  %s/" % name)
    for name in FILES:
        shutil.copy2(os.path.join(HERE, name), os.path.join(TARGET, name))
        print("  %s" % name)
    measurements = os.path.join(TARGET, "docs", "messungen")
    os.makedirs(measurements, exist_ok=True)
    for source, name in MEASUREMENTS.items():
        shutil.copy2(os.path.join(HERE, source), os.path.join(measurements, name))
        print("  docs/messungen/%s" % name)
    os.makedirs(RELEASE_TO, exist_ok=True)
    for name in sorted(os.listdir(RELEASE_FROM)) if os.path.isdir(RELEASE_FROM) else []:
        if name.endswith((".allep", ".zip")):
            shutil.copy2(os.path.join(RELEASE_FROM, name), os.path.join(RELEASE_TO, name))
            print("  release/%s" % name)


def check():
    """Rechnerpfade, Benutzername, Geheimnisse, Workspace-Abhaengigkeiten - jeder Treffer mit Datei:Zeile."""
    findings = []
    for folder, names, files in os.walk(TARGET):
        names[:] = [name for name in names if name not in SKIP_NAMES and name != ".git"]
        for name in files:
            if not name.endswith(TEXT_SUFFIXES) or name == os.path.basename(__file__):
                continue                                 # die eigenen Suchmuster sind keine Funde
            path = os.path.join(folder, name)
            try:
                with open(path, encoding="utf-8") as handle:
                    lines = handle.read().splitlines()
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(lines, 1):
                for pattern, label in FORBIDDEN:
                    if pattern.search(line):
                        findings.append((os.path.relpath(path, TARGET), number, label, line.strip()[:100]))
    print("\n--- Pruefung ---")
    for path, number, label, text in findings:
        print("  %-22s %s:%d  %s" % (label, path, number, text))
    print("%d Befund(e)." % len(findings) if findings else "  keine Rechnerpfade, Benutzernamen oder Geheimnisse")
    return 1 if findings else 0


def main():
    parser = argparse.ArgumentParser(description='Ordner "Online Repo" zusammenstellen und pruefen')
    parser.add_argument("--check", action="store_true", help="nur pruefen, nichts kopieren")
    args = parser.parse_args()
    if not args.check:
        assemble()
    return check()


if __name__ == "__main__":
    sys.exit(main())
