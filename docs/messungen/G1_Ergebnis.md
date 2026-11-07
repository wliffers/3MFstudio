# Gate G1 – Ergebnis

Stand 2026-11-06 · gemessen auf diesem PC mit **Bambu Studio 02.09.01.70**, über dessen
Kommandozeile (kein Fenster, keine Fernsteuerung) · Skript `bambu_check.py`

**Bestanden.** Bambu Studio übernimmt die Filamentzuordnung aus der Datei – niemand muss im
Slicer etwas zuweisen.

```
AMPEL: GRUEN | G1 | check_probes.py | 6 Dateien: Struktur, Netze (+8000 mm3, geschlossen, 20 mm), Id-Verweise ok
AMPEL: GRUEN | G1 | bambu_check.py | 6 Dateien: Filament je Teil wie geschrieben, Verbrauch je Filament, Groessen ok | BambuStudio 02.09.01.70
```

Gegenprobe: Eine absichtlich verfälschte Datei (rechtes Teil auf Filament 1 gesetzt) macht
`bambu_check.py` rot. Die Prüfung misst also wirklich.

## Messwerte

Gesliced mit Drucker „Bambu Lab A1 0.4 nozzle“, Prozess „0.20mm Standard @BBL A1“, zweimal
„Bambu PLA Basic @BBL A1“. Verbrauch = Material im Modell, ohne Reinigungsturm.

| Datei | Was Bambu liest | Filament 1 | Filament 2 | Wechsel | Größe |
|---|---|---:|---:|---:|---|
| A1 ein Objekt, zwei Teile | 1 Objekt, Teil links = 1, Teil rechts = 2 | 3,68 g | 3,62 g | 100 | 50 × 20 × 20 mm |
| A2 wie A1 + Projektdatei | wie A1 | 3,68 g | 3,62 g | 100 | 50 × 20 × 20 mm |
| B1 zwei Objekte | 2 Objekte, links = 1, rechts = 2 | 3,69 g | 3,63 g | 100 | je 20 × 20 × 20 mm |
| B2 wie B1 + Projektdatei | wie B1 | 3,69 g | 3,63 g | 100 | je 20 × 20 × 20 mm |
| C Überlappung 5 mm | 1 Objekt, Teil links = 1, Teil rechts = 2 | 2,80 g | 3,70 g | 100 | 35 × 20 × 20 mm |
| D Kontrolle ohne Bambu-Zusatz | 2 Objekte, beide = 1 | 7,32 g | – | 0 | je 20 × 20 × 20 mm |

- **Maße** stimmen auf 0,01 mm, kein Reparatur- oder Fehlerhinweis in einer der sechs Dateien.
- **Projektdatei** ändert nichts: A1 = A2, B1 = B2.
- **Überlappung** (C): slict ohne Fehler. Der gemeinsame Bereich wurde dem zweiten Teil
  (Filament 2) zugeschlagen, das erste Teil verliert ihn. Nichts wird doppelt gedruckt.
- **Kontrolle** (D): ohne Zuordnung in der Datei bleibt alles auf Filament 1 – die Zuordnung
  kommt also aus unserer Datei, nicht aus einer Voreinstellung von Bambu.

## Festlegungen für den Schreiber (N1 / N2)

1. **Variante A:** ein Objekt mit mehreren Teilen; jedes Teil trägt seine Filamentnummer in
   `Metadata/model_settings.config`. Grund: Das Bambu-Fenster legt getrennte Objekte (Variante B)
   ohne Rückfrage zu einem Objekt mit Teilen zusammen, sobald sie unterschiedlich hoch beginnen
   (`Model.cpp:900-917`, `Plater.cpp:12587-12591`) – bei einem Gebäude der Normalfall. A ist das,
   was am Ende ohnehin entsteht, nur vorhersagbar.
2. **Keine Projektdatei** (`project_settings.config`). Sie bringt nichts und löst im Fenster den
   Hinweis „The 3mf file has invalid config, load geometry data only“ aus (`Plater.cpp:11796-11801`).
3. **Keine Farbangaben nach 3MF-Standard** (`basematerials`, Farbgruppen). Sonst löscht das Fenster
   die Filamentnummern und fragt stattdessen über einen Farbdialog (`Plater.cpp:12561-12576`).
4. **`Application` nicht mit `BambuStudio-` beginnen lassen.** Die Datei bleibt ehrlich als fremd
   erkennbar; die Zuordnung kommt trotzdem an.
5. **Überlappende Teile:** kein Abbruch. Den gemeinsamen Bereich bekommt das Teil, das in der
   Datei **später** steht (Nachmessung unten). Der Schreiber legt die Reihenfolge deshalb bewusst
   fest; N3 nennt jede Überlappung und wer gewinnt.

## Nachmessung: Körper steckt im Körper (Schriftzug, Einlage)

Anlass: Ein Schriftzug ragt 5 mm tief in seinen Grundkörper. Beide Körper belegen dort denselben
Raum. Er soll im Schriftzug-Filament gedruckt werden, der Grundkörper soll dort ausgespart sein –
und der Schriftzug darf nicht als loses Einzelstück neben dem Körper landen.

Probe: Grundkörper 40 × 20 × 10 mm, Einlage 20 × 6 mm, 5 mm tief, oben bündig. Skript
`overlap_check.py`, Bambu Studio 02.09.01.70.

```
AMPEL: GRUEN | G1b | overlap_check.py | Regel bestaetigt: in einem Objekt bekommt das spaetere Teil den gemeinsamen Bereich, unabhaengig von der Filamentnummer | BambuStudio 02.09.01.70
```

| Aufbau der Datei | Filament 1 | Filament 2 | Wechsel | Was gedruckt wird |
|---|---:|---:|---:|---|
| Grundkörper allein (Vergleich) | 3,88 g | – | 0 | ein Stück |
| ein Objekt, Grundkörper zuerst, **Einlage danach** | 3,82 g | 0,45 g | 25 | **richtig:** Einlage sitzt im ausgesparten Grundkörper |
| ein Objekt, **Einlage zuerst**, Grundkörper danach | 3,88 g | – | 0 | **falsch:** Einlage verschwindet ganz, ohne jeden Hinweis |
| wie Zeile 2, Filamentnummern getauscht | 0,45 g | 3,82 g | 25 | richtig – die Nummer spielt keine Rolle, nur die Reihenfolge |
| **zwei getrennte Objekte** | 3,88 g | 0,49 g | 26 | **falsch:** Grundkörper voll, Einlage als loses Stück daneben auf der Platte |
| ein Objekt, zwei Würfel Fläche an Fläche | 3,55 g | 3,49 g | 100 | ein Stück 40 × 20 × 20 mm in zwei Filamenten |

Folgen für den Schreiber:

- Alles bleibt **ein Objekt** (Festlegung 1) – getrennte Objekte reißen zusammengehörige Körper auseinander.
- Die **Reihenfolge der Teile ist entscheidend.** Vorschlag: größter Körper zuerst, kleinster zuletzt –
  so gewinnt der eingesteckte Körper (Schriftzug, Einlage, Fenster in der Wand).
- Ein eigenes Ausschneiden in Allplan ist nicht nötig; Bambu Studio trennt beim Slicen selbst.
- Berührende Körper (Wand auf Decke) sind unkritisch.

## Nachmessung: Namen

Der Nutzer gibt je Filament einen Namen ein („Grundkörper“, „Text“); er wird als Teilname
geschrieben. Skript `name_check.py`, Bambu Studio 02.09.01.70.

```
AMPEL: GRUEN | G1c | name_check.py | 3 Namen kommen unveraendert an (Umlaute, Anfuehrungszeichen, &, <, >), Filament je Name stimmt | BambuStudio 02.09.01.70
```

Zurückgelesen aus Bambus eigener Datei: `Grundkörper`, `Text`, `Schild "Eingang" & <Maß>` – jeweils
mit dem richtigen Filament. Der Schreiber muss Namen für die Datei maskieren (`&`, `<`, `>`, `"`).
Nicht übertragbar ist ein Name für das Filament selbst (Bambus Filamentleiste) – dort stehen
Bambus eigene Filamentprofile.

## Was nur das Bambu-Fenster zeigt

Nicht gemessen – das Fenster wird nicht ferngesteuert. Aus dem Quelltext genau dieser Version
(Tag `v02.09.01.70`, Commit `56a57d0`):

- Hinweis „The 3mf is not from Bambu Lab, load geometry data and color data only.“ erscheint einmal
  je Öffnen; abschaltbar (`Plater.cpp:12557-12581`).
- Die Filamentnummern bleiben erhalten (`Plater.cpp:11893-11916`), fehlende Filamente ergänzt das
  Fenster selbst bis zur höchsten benutzten Nummer (`Plater.cpp:11697-11720`, Aufruf `:12583`).
- Auf leerer Platte öffnet die Datei ohne Rückfrage; liegen schon Objekte dort, fragt Bambu
  „Projekt öffnen / nur Geometrie“ (`Plater.cpp:26231-26257`, `bbs_3mf.cpp:10039-10051`).

## Fallen der Kommandozeile (für spätere Prüfläufe)

| Falle | Folge | Umgang |
|---|---|---|
| Ohne `--filament-colour` mit so vielen Farben wie Filamenten | Absturz nach dem Slicen, Druckprogramm einfarbig (`BambuStudio.cpp:4146-4155`) | Farben immer mitgeben |
| Profile der Installation sind Teilstücke (`inherits`, `include`) | Kommandozeile verlangt vollständige Dateien | `bambu_check.py` setzt sie zusammen |
| Keine Textausgabe im Konsolenfenster unter Windows | Fehler nur über `result.json` und fehlende Ausgabedateien sichtbar | Skript liest `result.json` |
| Reihenfolge der Objekte in der zurückgeschriebenen Datei wechselt | Vergleich nach Position schlägt zufällig fehl | Vergleich nach Namen |

## Berichtigung zur ersten Paketfassung

Probe C der ersten Zip-Datei enthielt **keine** Überlappung, sondern 5 mm Abstand (Rechenfehler im
Generator). Behoben; die Selbstprüfung misst den Abstand jetzt mit. Die Zip-Datei ist neu gebaut –
eine ältere Kopie bitte verwerfen.
