# Ein Release veröffentlichen

So kommt eine neue Fassung von 3MFStudio zu den Anwendern. Alles läuft im Arbeitsprojekt; der
Repo-Ordner wird daraus zusammengestellt.

## 1. Nummern erhöhen

- `build_allep.py`: `VERSION` erhöhen (z. B. `1.1.2` → `1.1.3`). Ohne höhere Nummer bietet der
  Plugin-Manager kein Update an.
- `src/3MFStudio.py`: `SCRIPT_BUILD` anpassen (steht im Protokoll, hilft bei Fehlermeldungen).
- `LIESMICH_Installation.txt`: Versionsnummer in Überschrift und Dateinamen.
- `CHANGELOG.md`: Abschnitt für die neue Fassung.

## 2. Prüfen

```bash
python -m pytest tests            # alle Tests grün?
python build_allep.py --check     # alles für den Bau da?
```

## 3. Paket bauen

```bash
python build_allep.py             # dist/3MFStudio-<VERSION>.allep und dist/3MFStudio_Installation.zip
```

Das Skript prüft die Paketdateien auf Rechnerpfade und Schlüssel und bricht sonst ab.

## 4. Repo-Ordner auffrischen

```bash
python publish_repo.py            # kopiert src/, tests/, assets/, Bauskripte, Messprotokolle, release/
```

Es meldet jeden Fund von Rechnerpfaden, Benutzernamen oder Geheimnissen mit Datei:Zeile. Zwei Treffer
sind gewollt (Testtexte in `tests/test_build_allep.py` und `tests/test_threemf_slicer.py`); alles andere
vor dem Commit bereinigen.

## 5. Einchecken und taggen

```bash
git add -A
git commit -m "Release 1.1.3"
git tag v1.1.3
git push && git push --tags
```

`release/` ist in `.gitignore` – die Paketdateien gehören nicht ins Repo, sondern an den Release.

## 6. GitHub-Release anlegen

1. Auf GitHub unter **Releases → Draft a new release** den Tag `v1.1.3` wählen.
2. Titel `3MFStudio 1.1.3`, als Text den Abschnitt aus `CHANGELOG.md`.
3. Aus `release/` anhängen: `3MFStudio-1.1.3.allep` **und** `3MFStudio_Installation.zip`.
4. Veröffentlichen. Der Link „Release-Seite“ in der README zeigt automatisch auf die neueste Fassung.

## Was nie ins Repo gehört

- `input/` (fremde Beispieldateien), `spike_*/` (Versuche), `STATE.md`, `PLAN.md`, `prompt*.md`,
  `AGENTS.md` – Arbeitsnotizen des Projekts.
- Dateien aus Bambu Studio (Profile, Farbdatei) – sie werden nur beim Anwender gelesen.
- Rechnerpfade, Benutzernamen, Schlüssel.
