<p align="center">
  <img src="assets/library/3MFStudio.png" alt="3MFStudio" width="128">
</p>

<h1 align="center">3MFStudio</h1>

<p align="center">
  <strong>3MFStudio verbindet Allplan mit dem 3D-Druck.</strong><br>
  Ein PythonPart für Allplan 2027.
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/Version-1.1.2-2563eb">
  <img alt="Allplan" src="https://img.shields.io/badge/Allplan-2027-0f766e">
  <img alt="Plattform" src="https://img.shields.io/badge/Plattform-Windows-6b7280">
  <a href="LICENSE"><img alt="Lizenz" src="https://img.shields.io/badge/Lizenz-MIT-16a34a"></a>
  <img alt="Projekt" src="https://img.shields.io/badge/Projekt-privat%2C%20ohne%20Gew%C3%A4hr-f59e0b">
</p>

<p align="center">
  <a href="#funktionen">Funktionen</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#aus-allplan-exportieren">Exportieren</a> ·
  <a href="#nach-allplan-importieren">Importieren</a> ·
  <a href="#universelle-3mf-datei-und-bambu-projekt">3MF und Bambu-Projekt</a> ·
  <a href="#grenzen">Grenzen</a> ·
  <a href="#haftung-und-lizenz">Haftung &amp; Lizenz</a> ·
  <a href="README.en.md">English</a>
</p>

---

<p align="center">
  <img src="docs/images/3mfstudio-ablauf.gif" alt="Ablauf in 10 Sekunden: In Allplan werden die Körper eines A mit der Aufschrift MAX in 3MFStudio zwei Filamenten zugeordnet, die 3MF-Datei wird geschrieben, Bambu Studio zeigt die zwei Filamente, und der Drucker druckt das blaue A mit der Aufschrift MAX" width="800">
</p>

Mit 3MFStudio exportierst du 3D-Körper aus Allplan 2027 als 3MF-Dateien und importierst vorhandene
3MF-Modelle zurück nach Allplan. Für den Mehrfarbdruck ordnest du den Körpern Filamente zu. Ist Bambu
Studio installiert, speichert 3MFStudio zusätzlich Farben, Materialtypen und Druckprofile in einem
Bambu-Projekt.

Die Bedienung erfolgt in einem kompakten Fenster direkt in Allplan. Die Sprache der Benutzeroberfläche
richtet sich nach der Spracheinstellung von Allplan (Deutsch oder Englisch).

> **Privates Projekt.** 3MFStudio ist ein Freizeitprojekt und steht in keiner Verbindung zu Nemetschek,
> ALLPLAN oder Bambu Lab. Die Software wird ohne Gewährleistung und ohne Haftung bereitgestellt.
> Einzelheiten stehen im [Haftungsausschluss](HAFTUNGSAUSSCHLUSS.md).

## Funktionen

**Körper für den Mehrfarbdruck exportieren.**
Du wählst Körper im Modell aus und ordnest sie einem von bis zu 16 Filamenten zu. 3MFStudio speichert sie
als 3MF-Datei mit Teilnamen und Filamentnummer je Teil.

**Farbe und Filament festlegen.**
Für jedes Filament wählst du Hersteller, Filamentserie und Farbe aus einer mitgelieferten Liste realer
Filamente (161 Hersteller, Bambu Lab steht oben). Aus der Filamentserie ergibt sich der Materialtyp, zum
Beispiel PLA oder PETG. Alternativ gibst du einen eigenen Farbwert ein. Die Körper in Allplan erhalten die
ähnlichste der 255 Allplan-Farben, damit das Modell der späteren Farbverteilung entspricht.

**Filamente tauschen.**
Mit ⇅ tauschen zwei Filamente ihre Körper. Name, Farbe und Filamentserie bleiben dabei an der jeweiligen
Filamentkarte. Das ist hilfreich, wenn ein innenliegender Körper im Modell schwer anzuklicken ist.

**Elementgruppen zusammenhalten.**
Körper, die in Allplan zu einer Elementgruppe zusammengefasst sind und dasselbe Filament haben, werden als
ein Teil mit dem Namen der Gruppe exportiert. Im Slicer lässt sich dieses Teil in einem Schritt umfärben.

**Bauraum und Druckplatte als Orientierung.**
Das Würfel-Symbol neben dem Zahnrad öffnet die Bauraum-Karte. Dort wählst du einen Drucker aus einer Liste
von 93 Modellen oder trägst eigene Maße für X, Y und Z ein; jede Änderung wird sofort gespeichert. Mit
**Druckplatte ablegen** entsteht die Platte im Modell: Oberseite auf Z = 0, Mitte auf X/Y = 0, auf Wunsch
mit dem Bauraum als 3D-Linien. Platte und Linien liegen auf dem Layer **KO_HK** (Hilfskonstruktion).
Alles auf diesem Layer wird nicht exportiert – auch eigene Hilfskörper, die du dorthin legst.

**3MF-Dateien importieren.**
3MFStudio liest 3MF-Dateien und legt ihre Teile als Allplan-Körper ab. Filamentfarben und die Zuordnung
der Teile zu Filamenten werden übernommen, sofern die Datei sie enthält. Welche Art von Körper entsteht, hängt von der Geometrie ab;
siehe [Nach Allplan importieren](#nach-allplan-importieren).

### Überlappende Körper

Körper, die sich berühren oder ineinanderstecken, exportiert 3MFStudio als ein gemeinsames Objekt. So bleibt
ihre Lage zueinander im Slicer erhalten. Den Bereich, den sich zwei Körper teilen, druckt der Slicer mit dem
Filament des kleineren Körpers. Bei gleich großen Körpern gilt das Filament des zuletzt zugeordneten Körpers.

*Beispiel:* Ein Schriftzug steckt 1 mm tief in einer Grundplatte. Die Buchstaben werden vollständig mit
ihrem eigenen Filament gedruckt, die Grundplatte ist an diesen Stellen ausgespart.

Körper mit Abstand zueinander werden eigene Objekte, die der Slicer einzeln auf der Platte anordnen kann.

## Installation

**Voraussetzung:** Allplan 2027 unter Windows. Bambu Studio ist optional.

1. Lade die aktuelle Datei `3MFStudio-<Version>.allep` von der [Release-Seite](../../releases/latest) herunter.
2. Starte Allplan 2027 und ziehe die `.allep`-Datei mit der Maus in das Allplan-Fenster.
3. Folge den Hinweisen des Plugin-Managers und starte Allplan anschließend neu.

3MFStudio steht danach in der Bibliothek unter **Privat › Willi Liffers › 3MFStudio** und in der
Actionbar-Konfiguration unter den Plug-ins. Updates installierst du auf dieselbe Weise. Deinstalliert wird
über den Plugin-Manager.

<details>
<summary>Installation ohne Plugin-Manager</summary>

1. Beende Allplan.
2. Kopiere aus `3MFStudio_Installation.zip` den Inhalt des Ordners `Manuell` in den Allplan-Benutzerordner,
   meist `C:\Users\<USER>\Documents\Nemetschek\Allplan\2027\Usr\Local\`.
3. Starte Allplan. 3MFStudio steht in der Bibliothek unter Privat › Willi Liffers.

Verwende nur einen der beiden Installationswege. Eine ausführliche Anleitung steht in
[LIESMICH_Installation.txt](LIESMICH_Installation.txt).
</details>

## Aus Allplan exportieren

1. Starte 3MFStudio. Das Fenster öffnet sich über dem Allplan-Modell.
2. Klicke bei einem Filament auf **Auswählen**, wähle die Körper im Modell aus und klicke auf **Fertig**.
3. Klicke auf das Farbfeld der Filamentkarte. Wähle **Hersteller**, **Sorte** (die Filamentserie, zum
   Beispiel „PLA Basic“) und eine Farbe – oder gib über **Eigene Farbe** einen Farbwert ein.
4. Wiederhole die Schritte 2 und 3 für weitere Filamente.
5. Klicke auf **3MF schreiben** und wähle Speicherort und Dateinamen.
6. Öffne die Datei in deinem Slicer, entweder über **Im Slicer öffnen** oder direkt aus dem Explorer.

Die Körper werden in Originalgröße exportiert. Über **Verkleinern** lässt sich ein Maßstab wählen.

## Nach Allplan importieren

1. Starte 3MFStudio und klicke auf **3MF importieren**.
2. Wähle die 3MF-Datei. Die Teile hängen anschließend am Mauszeiger.
3. Klicke im Modell auf den Ablagepunkt.

Welche Körper entstehen:

- **Geschlossene Teile mit ebenen Flächen** werden Volumenkörper. Nebeneinanderliegende Dreiecke einer
  Ebene fasst 3MFStudio zu einer Fläche zusammen, sodass keine Dreiecksteilung sichtbar bleibt.
- **Teile mit gleichbleibendem Querschnitt**, etwa Puzzleteile oder Steckformen, erhalten glatte, gerundete
  Flächen. 3MFStudio vergleicht dafür Volumen, Oberfläche und Maße mit dem Original und verwendet die
  glatte Form nur, wenn sie innerhalb enger Toleranzen übereinstimmt.
- **Überwiegend gerundete Freiformen** wie Figuren bleiben Körper aus Dreiecksflächen.
- **Teile mit offenem Netz** werden als Flächenkörper abgelegt. 3MFStudio weist nach dem Import darauf hin.
- **Bemalte Teile** (Farbe auf einzelnen Flächen) werden mit einer Farbe übernommen. Die Bemalung selbst
  wird nicht importiert; auch darauf weist 3MFStudio hin.
- **Farben nach 3MF-Standard**, wie sie andere Programme schreiben, werden zu Filamenten mit ihrer Farbe.
- **Dateien, die 3MFStudio nicht sicher lesen kann**, werden mit Grund abgelehnt: Dateien, die eine nicht
  unterstützte Erweiterung voraussetzen (zum Beispiel Beam Lattice, Slice oder Production Alternatives),
  verschlüsselte Dateien und beschädigte Dateien.

## Universelle 3MF-Datei und Bambu-Projekt

3MFStudio speichert entweder eine universelle 3MF-Datei oder ein Bambu-Projekt. Was entsteht, steht im
Einstellungsbereich (Zahnrad) unter der Option **Universelle 3MF schreiben**.

| Inhalt | Universelle 3MF-Datei | Bambu-Projekt |
|---|---|---|
| Geometrie und Teilnamen | ✓ | ✓ |
| Filamentnummer je Teil | ✓ ¹ | ✓ |
| Farben der Filamente | – | ✓ |
| Materialtyp und Filamentprofil je Filament | – | ✓ |
| Drucker und Druckprofil | – | ✓ ² |

¹ Gespeichert in einer Zusatzdatei von Bambu Studio. Ob ein anderer Slicer diese Zuordnung übernimmt,
hängt vom Slicer ab; geprüft ist Bambu Studio.
² Übernommen wird der Drucker, der in Bambu Studio eingestellt ist. Wird keiner gefunden, bleibt der
Drucker im Projekt offen.

**Wann entsteht ein Bambu-Projekt?** Wenn Bambu Studio installiert ist, als Slicer gilt und die Option
**Universelle 3MF schreiben** ausgeschaltet ist. Als Slicer gilt Bambu Studio, wenn es im Einstellungsbereich
unter **Slicer-Programm** gewählt ist oder wenn Windows 3MF-Dateien damit öffnet. In diesem Fall öffnet ein
Doppelklick auf die gespeicherte Datei das Projekt in Bambu Studio mit Farben, Materialtypen und Drucker.

**Woher die Profile stammen:** Zum gewählten Filament sucht 3MFStudio das passende Filamentprofil in der
Installation von Bambu Studio. Gibt es kein eigenes Profil, wird das allgemeine Profil des Materialtyps
verwendet (zum Beispiel „Generic PETG“). Filamente ohne eigene Auswahl erhalten das Filament, das in Bambu
Studio im entsprechenden Fach eingestellt ist.

Ohne Bambu Studio, oder wenn das Projekt nicht erstellt werden kann, speichert 3MFStudio die universelle
Datei und meldet das. Farben und Materialtypen legst du dann im Slicer fest.

## Gespeicherte und gelesene Daten

- **In der 3MF-Datei:** die Inhalte aus der Tabelle oben. Projektdaten, Attribute oder Dateipfade aus
  Allplan werden nicht exportiert.
- **Auf deinem Rechner:** Einstellungen unter `C:\Users\<USER>\AppData\Roaming\3MFStudio\einstellungen.json`
  und ein Protokoll für die Fehlersuche unter `C:\Users\<USER>\Documents\3MFStudio_debug.log`.
- **Von Bambu Studio:** Einstellungen und Profile werden nur gelesen und nicht verändert.
- **Internet:** 3MFStudio stellt keine Verbindung her und sendet keine Daten.

## Grenzen

- Gerundete Freiformen werden beim Import nicht in glatte Flächen umgewandelt (siehe oben).
- Die Bemalung einzelner Flächen wird nicht importiert.
- 3MFStudio prüft nicht, ob ein Modell in den Bauraum passt. Dafür kannst du die Druckplatte einblenden.
- Pflicht-Erweiterungen von 3MF außer Produktion, Material und Dreiecksgruppen werden nicht unterstützt;
  solche Dateien werden abgelehnt (siehe oben).
- Bildschirmfarben sind Näherungen. Das gedruckte Filament kann abweichen.
- Wenn etwas nicht funktioniert, steht der Grund im Protokoll `C:\Users\<USER>\Documents\3MFStudio_debug.log`.

## Rückmeldungen

Fehlerberichte und Vorschläge sind als Issue willkommen. Hilfreich sind die Allplan-Version, gegebenenfalls
die Version von Bambu Studio und die letzten Zeilen aus dem Protokoll. 3MFStudio wird in der Freizeit
gepflegt. Ich antworte, sobald ich kann, kann aber keine Antwortzeiten oder Korrekturen zusagen. Mehr dazu
in [CONTRIBUTING.md](CONTRIBUTING.md).

## Für Entwickler

```
src/                  Programm: 3MFStudio.py (Script Object) und threemf_*.py (ohne Allplan testbar)
tests/                pytest; läuft ohne Allplan, Tests mit Bambu Studio werden ohne Installation übersprungen
fetch_conformance.py  holt die Konformitätstests und den Prüfer (lib3mf) des 3MF-Konsortiums nach conformance/
assets/               Symbole für Bibliothek und Actionbar
docs/messungen/       Messprotokolle: wie Bambu Studio fremde 3MF-Dateien liest
build_allep.py        erstellt das Paket dist/3MFStudio-<Version>.allep und das Installations-ZIP
build_filaments.py    aktualisiert die Filamentliste aus der Open Filament Database
build_printers.py     aktualisiert die Druckerliste
deploy.py             kopiert 3MFStudio direkt in eine Allplan-Installation
publish_repo.py       stellt diesen Ordner aus dem Arbeitsprojekt zusammen und prüft ihn auf Pfade und Geheimnisse
```

```bash
python fetch_conformance.py     # einmalig: Konformitätstests des 3MF-Konsortiums (Prüfer braucht Node.js 22)
python -m pytest tests          # etwa 7 Minuten; ohne conformance/ werden diese Tests übersprungen
python deploy.py                # nach Allplan 2027; --force bei laufendem Allplan
python build_allep.py           # Paket erstellen; vorher VERSION in build_allep.py erhöhen
```

**Interne Verarbeitung des Bambu-Projekts:** 3MFStudio speichert zuerst die universelle Datei. Danach erstellt
die Kommandozeile von Bambu Studio daraus das Projekt, das die universelle Datei ersetzt. Das Fenster von
Bambu Studio wird dabei nicht gesteuert. Allplan lädt das Hauptskript einmal je Sitzung; nach einem Deploy
ist ein Neustart von Allplan nötig. Der Ablauf eines Releases steht in [docs/RELEASING.md](docs/RELEASING.md).

## Haftung und Lizenz

- **Lizenz:** [MIT](LICENSE) – frei nutzbar, auch im Betrieb, ohne Gewährleistung.
- **Haftungsausschluss:** Benutzung auf eigene Gefahr. Prüfe Geometrie und Druckdateien, bevor du
  druckst oder weitergibst, und sichere deine Allplan-Projekte. [HAFTUNGSAUSSCHLUSS.md](HAFTUNGSAUSSCHLUSS.md)
- **Fremdanteile:** Farbliste aus der [Open Filament Database](https://github.com/OpenFilamentCollective/open-filament-database)
  (MIT). Alles Weitere in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- **Marken:** ALLPLAN ist eine Marke der ALLPLAN GmbH / Nemetschek Group. Bambu Lab und Bambu Studio sind
  Marken von Bambu Lab. 3MFStudio ist ein unabhängiges Projekt und mit keinem der Genannten verbunden.

---

<p align="center">Version 1.1.2 · zuletzt geprüft am 2026-11-08</p>
