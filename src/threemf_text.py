"""Sichtbare Texte von 3MFStudio auf Deutsch oder Englisch - je nach Sprache von Allplan.

Jeder Text fuer den Anwender laeuft durch `tr("deutscher Text {wert}", wert=...)`. Der deutsche Text ist zugleich
der Schluessel; steht Allplan nicht auf Deutsch, kommt die englische Fassung aus ENGLISH. Allplan liefert die
Sprache als zwei Buchstaben (AllplanLocalisationService.Language(), live "de" am 2026-11-07); "de" ist Deutsch,
jede andere Sprache Englisch - wie Allplans eigene Sprachdateien auf Englisch zurueckfallen.
Ein Test prueft, dass jeder `tr`-Text im Quelltext hier eine englische Fassung hat (tests/test_threemf_text.py).
"""

from __future__ import annotations

_LANGUAGE = ["de"]


def set_language(code: str) -> str:
    """Sprache setzen ("de" -> Deutsch, sonst Englisch); gibt die gesetzte Sprache zurueck."""
    _LANGUAGE[0] = "de" if str(code or "").strip().lower().startswith("de") else "en"
    return _LANGUAGE[0]


def language() -> str:
    return _LANGUAGE[0]


def tr(message: str, /, **values) -> str:
    """Der Text in der eingestellten Sprache, Platzhalter {name} durch `values` ersetzt."""
    template = message if _LANGUAGE[0] == "de" else ENGLISH.get(message, message)
    return template.format(**values) if values else template


ENGLISH: dict[str, str] = {
    # --- Fenster
    "3MFStudio · Filamente": "3MFStudio · Filaments",
    "Farbkachel antippen: Farbe und Sorte wählen": "Click the colour tile: choose colour and type",
    "Hier anfassen und verschieben": "Drag here to move",
    "3MFStudio schließen": "Close 3MFStudio",
    "Einstellungen": "Settings",
    "Zur Leiste verkleinern": "Collapse to bar",
    "Slicer-Programm": "Slicer program",
    "Programm wählen…": "Choose program…",
    "Die .exe deines Slicers wählen (Bambu Studio, OrcaSlicer, PrusaSlicer …)":
        "Choose your slicer's .exe (Bambu Studio, OrcaSlicer, PrusaSlicer …)",
    "Windows-Standard": "Windows default",
    "Kein eigenes Programm: Windows öffnet die Datei mit dem Programm, das für 3MF eingestellt ist":
        "No program of your own: Windows opens the file with the program set up for 3MF",
    "Universelle 3MF schreiben": "Write a universal 3MF",
    "Aus: Ist Bambu Studio der Slicer, wird die Datei gleich das Bambu-Projekt mit Farben, Sorten und dem Drucker "
    "aus Bambu Studio. An: neutrale 3MF für jeden Slicer, ohne Bambu-Daten.":
        "Off: with Bambu Studio as the slicer, the file becomes the Bambu project with colours, materials and the "
        "printer from Bambu Studio. On: a neutral 3MF for any slicer, without Bambu data.",
    "Datei: universelle 3MF – ohne Farben und Sorten für Bambu Studio":
        "File: universal 3MF – no colours or materials for Bambu Studio",
    "Datei: universelle 3MF – Bambu Studio ist nicht der Slicer":
        "File: universal 3MF – Bambu Studio is not the slicer",
    "Datei: Bambu-Projekt für {printer} (aus Bambu Studio)": "File: Bambu project for {printer} (from Bambu Studio)",
    "Datei: Bambu-Projekt, Drucker offen – in Bambu Studio ist keiner eingestellt":
        "File: Bambu project, printer left open – none is set in Bambu Studio",
    "Bambu-Projekt wird gebaut": "Building the Bambu project",
    "Bambu Studio legt Farben und Sorten in die Datei …": "Bambu Studio is putting colours and materials into the file …",
    "Bambu Studio hat kein Projekt gebaut. Die Datei ist die universelle 3MF; Farben und Sorten fehlen in Bambu Studio.":
        "Bambu Studio did not build a project. The file is the universal 3MF; colours and materials are missing in "
        "Bambu Studio.",
    "＋  Filament hinzufügen": "＋  Add filament",
    "＋  Filament {number} hinzufügen": "＋  Add filament {number}",
    "Verkleinern": "Scale down",
    "Aus: Originalgröße in mm": "Off: original size in mm",
    "Größe": "Size",
    "Maßstab": "Scale",
    "Maßstab 1:{value}": "Scale 1:{value}",
    "aktuell {scale}": "current {scale}",
    "3MF schreiben": "Write 3MF",
    "Schreibt die Druckdatei für den Slicer": "Writes the print file for the slicer",
    "3MF importieren": "Import 3MF",
    "Datei wählen, dann die Körper per Mausklick in Allplan absetzen":
        "Choose a file, then place the bodies in Allplan with a mouse click",
    "Im Slicer öffnen": "Open in slicer",
    "Fenster aufklappen": "Expand window",
    "Filament {number}": "Filament {number}",
    "Filament {number} leeren": "Clear filament {number}",
    "Auswählen": "Select",
    "Fertig": "Done",
    "Körper für Filament {number} auswählen": "Select bodies for filament {number}",
    "Farbe und Sorte wählen": "Choose colour and type",
    "Farbe für Filament {number} wählen": "Choose colour for filament {number}",
    "Körper mit einem anderen Filament tauschen": "Swap bodies with another filament",
    "Filament {number} tauschen": "Swap filament {number}",
    "Tauschen: jetzt ⇅ beim anderen Filament drücken (nochmal ⇅ bricht ab).":
        "Swap: now press ⇅ on the other filament (⇅ again cancels).",
    # --- Farbauswahl
    "Farbauswahl schließen": "Close colour selection",
    "Farbe für Filament {number}": "Colour for filament {number}",
    "Hersteller": "Brand",
    "Sorte": "Type",
    "Meine Farben": "My colours",
    "Allplan-Farbe": "Allplan colour",
    "Keine eigene Wahl: das Filament hat die Farbe seiner Körper in Allplan":
        "No choice of your own: the filament has the colour of its bodies in Allplan",
    "Eigene Farbe": "Own colour",
    "Farbwert links eintippen, Sorte wie oben gewählt": "Type the colour value on the left, type as chosen above",
    "Farbwert als #RRGGBB, z. B. #00AE42": "Colour value as #RRGGBB, e.g. #00AE42",
    "Eigener Farbwert": "Own colour value",
    "Bildschirmfarbe – das gedruckte Filament kann etwas anders aussehen.":
        "Screen colour – the printed filament may look slightly different.",
    "{count} Farben – Name beim Darüberfahren": "{count} colours – hover for the name",
    "Keine Farben für diesen Hersteller": "No colours for this brand",
    "„{text}“ ist kein Farbwert. Bitte so eingeben: #00AE42": "“{text}” is not a colour value. Please enter it like this: #00AE42",
    "Farbliste wird geladen": "Loading colour list",
    "Diese Farbe gibt es in der Liste nicht mehr.": "This colour is no longer in the list.",
    "Allplan hat die Farbe der Körper nicht übernommen.": "Allplan did not accept the colour of the bodies.",
    # --- Druckplatte
    "Druckplatte": "Build plate",
    "Drucker für die Druckplatte": "Printer for the build plate",
    "B": "W",
    "T": "D",
    "H": "H",
    "Breite in mm": "Width in mm",
    "Tiefe in mm": "Depth in mm",
    "Höhe in mm": "Height in mm",
    "Druckplatte ablegen": "Place build plate",
    "Legt die Platte ins Modell: Oberseite auf Z = 0, Mitte auf X = 0 / Y = 0":
        "Places the plate in the model: top face at Z = 0, centre at X = 0 / Y = 0",
    "Bauraum als Linien": "Build volume as lines",
    "Oberseite auf Z = 0, Mitte auf X/Y = 0 · kommt nicht in die 3MF-Datei":
        "Top face at Z = 0, centre at X/Y = 0 · not written to the 3MF file",
    "Eigene Maße": "Custom size",
    "„{text}“ ist keine Zahl. Maße bitte in mm eingeben, z. B. 256.":
        "“{text}” is not a number. Please enter sizes in mm, e.g. 256.",
    "Maße müssen größer als 0 und höchstens {maximum} mm sein.":
        "Sizes must be greater than 0 and at most {maximum} mm.",
    "Name des Filaments – kommt in Bambu Studio an": "Name of the filament – arrives in Bambu Studio",
    "Name von Filament {number}": "Name of filament {number}",
    "leer": "empty",
    " · läuft": " · running",
    "Originalgröße": "original size",
    "Das hat nicht geklappt: {error}": "That did not work: {error}",
    # --- Ladefenster
    "3MF wird importiert": "Importing 3MF",
    "3MF wird geschrieben": "Writing 3MF",
    "Körper werden gelesen": "Reading bodies",
    "Slicer wird vorbereitet": "Preparing the slicer",
    "Datei wird gelesen …": "Reading the file …",
    "Vorschau wird vorbereitet …": "Preparing the preview …",
    "Körper {part} von {parts} wird gebaut …": "Building body {part} of {parts} …",
    "Körper {part} von {parts} wird gebaut (Stück {piece} von {pieces}) …":
        "Building body {part} of {parts} (piece {piece} of {pieces}) …",
    "Allplan legt die Körper ab …": "Allplan is placing the bodies …",
    "Körper {done} von {total} wird gelesen …": "Reading body {done} of {total} …",
    "Datei wird geschrieben …": "Writing the file …",
    "Bambu Studio baut das Projekt mit den Filamentfarben …":
        "Bambu Studio is building the project with the filament colours …",
    # --- Sitzung
    "1 Körper": "1 body",
    "{number} Körper": "{number} bodies",
    "{text} · Gruppe {names}": "{text} · group {names}",
    "{text} · Farbe {colour}": "{text} · colour {colour}",
    "Farbe {colour}": "colour {colour}",
    "{text} · {count} Farben": "{text} · {count} colours",
    "Noch nichts zugeordnet": "Nothing assigned yet",
    "{width} × {depth} × {height} mm ({mode})": "{width} × {depth} × {height} mm ({mode})",
    "Es gibt nur Filament 1 bis {maximum}.": "There are only filaments 1 to {maximum}.",
    "Noch ist kein Körper einem Filament zugeordnet.": "No body is assigned to a filament yet.",
    "Der Maßstab muss größer als 0 sein.": "The scale must be greater than 0.",
    # --- Werkzeug
    "Bedienung im 3MFStudio-Fenster": "Use the 3MFStudio window",
    "3MF-Datei speichern": "Save 3MF file",
    "3MF-Datei öffnen": "Open 3MF file",
    "Slicer-Programm wählen": "Choose slicer program",
    "Die Datei gibt es schon:\n{path}\n\nÜberschreiben?": "The file already exists:\n{path}\n\nOverwrite?",
    "Das Fenster von 3MFStudio ließ sich nicht öffnen.": "The 3MFStudio window could not be opened.",
    "Einzelheiten stehen in Dokumente\\3MFStudio_debug.log.": "Details are in Documents\\3MFStudio_debug.log.",
    "Das hat nicht geklappt.": "That did not work.",
    "Körper für „{name}“ anklicken – „Fertig“ oder ESC beendet":
        "Click bodies for “{name}” – “Done” or ESC ends",
    "Ablagepunkt für die importierten Körper anklicken": "Click the placement point for the imported bodies",
    "{count} Körper sind in der Datei bemalt (Farbe auf der Oberfläche). Ein Allplan-Körper hat genau eine Farbe – "
    "die Bemalung kommt nicht mit, der Körper schon.":
        "{count} bodies are painted in the file (colour on the surface). An Allplan body has exactly one colour – "
        "the painting does not come along, the body does.",
    "{count} Körper kamen nur als Flächenkörper an: ihr Netz ist in der Datei nicht geschlossen oder für einen "
    "Allplan-Körper zu groß. Sie sehen gleich aus und lassen sich wieder schreiben.":
        "{count} bodies arrived as surface bodies only: their mesh is not closed in the file or too large for one "
        "Allplan body. They look the same and can be written again.",
    "Grundkörper": "Base",
    "Sockel": "Plinth",
    "Würfel": "Cube",
    "Würfel {number}": "Cube {number}",
    # --- Slicer
    "Bitte ein Programm (.exe) wählen.": "Please choose a program (.exe).",
    "Das Programm gibt es nicht:\n{path}": "The program does not exist:\n{path}",
    "Noch keine 3MF-Datei geschrieben.": "No 3MF file written yet.",
    "Die Datei gibt es nicht mehr:\n{path}": "The file no longer exists:\n{path}",
    "Windows-Standard für 3MF-Dateien": "Windows default for 3MF files",
    "Zuerst „3MF schreiben“ – dann öffnet dieser Knopf die Datei im Slicer":
        "First “Write 3MF” – then this button opens the file in the slicer",
    "Öffnet {file} mit {program}": "Opens {file} with {program}",
    "dem Programm, das Windows für 3MF eingestellt hat": "the program Windows has set up for 3MF",
    "Unter ⚙ ein anderes Programm wählen oder „Windows-Standard“ nehmen.":
        "Choose another program under ⚙ or use “Windows default”.",
    "{program} ließ sich nicht starten:\n{error}": "{program} could not be started:\n{error}",
    "Für 3MF-Dateien ist kein Programm eingerichtet. Die Datei liegt hier:\n{path}\n\nUnter ⚙ den Slicer wählen.":
        "No program is set up for 3MF files. The file is here:\n{path}\n\nChoose the slicer under ⚙.",
    # --- Dateien und Koerper (Fehlermeldungen)
    "„{name}“ hat keinen druckbaren Körper.": "“{name}” has no printable body.",
    "Aus „{name}“ lässt sich kein gültiger Körper bauen.": "No valid body can be built from “{name}”.",
    "Aus „{name}“ lässt sich auch kein Flächenkörper bauen.": "Not even a surface body can be built from “{name}”.",
    "Eine Lageangabe hat {count} statt 12 Zahlen.": "A transform has {count} numbers instead of 12.",
    "In der Datei fehlt der Teil „{name}“.": "The file is missing the part “{name}”.",
    "Der Teil „{name}“ ist beschädigt: {error}": "The part “{name}” is damaged: {error}",
    "Unbekannte Längeneinheit „{unit}“.": "Unknown length unit “{unit}”.",
    "„{path}“ ist keine lesbare 3MF-Datei: {error}": "“{path}” is not a readable 3MF file: {error}",
    "Die Datei verweist im Kreis auf ihre eigenen Körper.": "The file refers to its own bodies in a circle.",
    "Die Datei verweist auf einen Körper {id}, den es nicht gibt.": "The file refers to a body {id} that does not exist.",
    "Die Datei enthält keinen Körper.": "The file contains no body.",
    "Es ist kein Körper zum Schreiben da.": "There is no body to write.",
    "„{name}“ hat keine Flächen.": "“{name}” has no faces.",
    "„{name}“ hat keine gültige Filamentnummer ({number}).": "“{name}” has no valid filament number ({number}).",
    "„{name}“ verweist auf Punkte, die es nicht gibt.": "“{name}” refers to points that do not exist.",
}
