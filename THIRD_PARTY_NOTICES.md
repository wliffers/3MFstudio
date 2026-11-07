# Fremdanteile und Hinweise zu Drittsoftware

3MFStudio selbst steht unter der MIT-Lizenz ([LICENSE](LICENSE)). Diese Datei nennt, was nicht vom
Urheber stammt oder was mit fremder Software zusammenarbeitet.

## Mitgeliefert

### Open Filament Database – Farbliste

- **Was:** die Filament-Farbliste `src/threemf_filaments.json.gz` (Hersteller, Sorten, Farbnamen und
  Farbwerte), verkleinert aus der Open Filament Database, Stand 2026-11-07.
- **Quelle:** <https://github.com/OpenFilamentCollective/open-filament-database>
- **Lizenz:** MIT. Der Lizenztext liegt in [`src/LICENSE_OpenFilamentDatabase.txt`](src/LICENSE_OpenFilamentDatabase.txt)
  und wird mit jedem Paket ausgeliefert. Auffrischen: `python build_filaments.py` (lädt die aktuelle
  Fassung und prüft, dass die Lizenz unverändert MIT ist).

```
Copyright © 2025 OpenFilamentCollective
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the “Software”), to deal in the Software without restriction …
THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND …
```

### Druckerliste

- **Was:** `src/threemf_printers.json` – je Drucker Name, Hersteller und die drei Maße des Bauraums
  (Breite, Tiefe, Höhe in mm), 93 Drucker.
- **Herkunft:** die Maße wurden mit `build_printers.py` aus den öffentlich einsehbaren Druckerprofilen
  von Bambu Studio abgelesen. Übernommen wurden nur diese Zahlen und Namen – reine Sachangaben –, keine
  Profiltexte, Einstellungen oder G-Code.

### Testdatei

- `tests/data/bambu_02_09_01_70_zwei_teile.3mf` ist eine Vergleichsdatei für die Tests: zwei einfache
  Quader aus unserem eigenen Testcode, von Bambu Studio 02.09.01.70 als Projekt gespeichert. Sie dient nur
  dazu, zu prüfen, wie Bambu Studio eine Datei zurückschreibt.

## Zur Laufzeit gelesen, nicht mitgeliefert

### Bambu Studio

- 3MFStudio liest beim Anwender – nur wenn Bambu Studio dort installiert ist – dessen Farbdatei
  (`filaments_color_codes.json`), die Einstellungsdatei (`BambuStudio.conf`: eingestellter Drucker,
  Druckprofil, Filamente je Fach) und die Druck-, Drucker- und Filamentprofile aus dem Programmordner.
  Es startet Bambu Studios Kommandozeile, um aus der neutralen 3MF-Datei ein Bambu-Projekt zu bauen.
- **Nichts davon ist in diesem Repository oder im Paket enthalten.** Bambu Studio steht unter der
  GNU AGPL-3.0 (<https://github.com/bambulab/BambuStudio>); seine Dateien bleiben beim Anwender und werden
  von 3MFStudio nicht verändert.
- Ohne Bambu Studio arbeitet 3MFStudio vollständig; es entsteht dann die neutrale 3MF-Datei.

### Allplan 2027 (ALLPLAN GmbH / Nemetschek Group)

- 3MFStudio ist ein PythonPart und läuft innerhalb von Allplan 2027 über dessen PythonParts-Schnittstelle
  (`NemAll_Python_*`, PythonParts-Framework). Diese Schnittstelle ist Bestandteil von Allplan und wird
  nicht mitgeliefert. Eine gültige Allplan-Lizenz ist Voraussetzung.

### .NET / WPF

- Das Fenster von 3MFStudio nutzt die in Allplan vorhandene .NET/WPF-Laufzeit (über pythonnet). Es
  wird keine eigene Laufzeit ausgeliefert.

## Marken

ALLPLAN ist eine Marke der ALLPLAN GmbH / Nemetschek Group. Bambu Lab und Bambu Studio sind Marken von
Bambu Lab. OrcaSlicer und PrusaSlicer gehören ihren jeweiligen Projekten. 3MFStudio ist ein unabhängiges
privates Projekt und mit keinem der Genannten verbunden; die Namen dienen nur der Beschreibung der
Zusammenarbeit.

## Eigene Anteile

Icons (`assets/`), Programmcode, Tests, Messprotokolle (`docs/messungen/`) und Texte stammen vom Urheber
von 3MFStudio und stehen unter der MIT-Lizenz.
