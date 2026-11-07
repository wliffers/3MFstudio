# Mitmachen

Danke fürs Interesse. 3MFStudio ist ein privates Freizeitprojekt – Rückmeldungen sind willkommen, eine
Antwort oder Behebung kann ich aber nicht zusichern.

## Fehler melden

Bitte als Issue mit:

1. **Allplan-Version** (z. B. 2027.0.1) und Sprache.
2. **Bambu-Studio-Version**, falls Bambu Studio beteiligt war – oder „ohne Bambu Studio“.
3. **Was du getan hast** (Schritte) und **was stattdessen passiert ist**.
4. Die letzten Zeilen aus `C:\Users\<USER>\Documents\3MFStudio_debug.log` (bitte vorher auf Pfade oder Namen schauen,
   die du nicht veröffentlichen willst).
5. Wenn möglich: die 3MF-Datei oder ein kleines Allplan-Beispiel, mit dem es sich nachstellen lässt.

## Ideen

Gern als Issue mit dem Anwendungsfall: Was willst du erreichen, und was fehlt dir dafür?

## Änderungen beisteuern

- Fork, Branch, Pull Request – mit einer kurzen Beschreibung, was sich ändert und warum.
- `python -m pytest tests` muss durchlaufen (ohne Bambu Studio werden dessen Tests übersprungen).
- Allplan-Aufrufe (`NemAll_Python_*`) bitte nur mit Beleg aus der Allplan-Dokumentation oder einem
  Beispiel – geratene Methodennamen fallen erst in Allplan auf.
- Neue Texte für das Fenster brauchen einen englischen Eintrag in `src/threemf_text.py`.
- Reine Rechnung (`threemf_model`, `threemf_session`, `threemf_bambu` …) bleibt ohne Allplan testbar;
  Allplan-Aufrufe gehören nach `threemf_allplan.py` oder `3MFStudio.py`.

## Lokal entwickeln

```bash
python -m pytest tests            # Tests, etwa 7 Minuten
python deploy.py                  # ins Allplan-Benutzerverzeichnis kopieren (--force bei laufendem Allplan)
python build_allep.py             # Paket bauen
```

Allplan lädt das Hauptskript einmal je Sitzung; nach einem Deploy Allplan neu starten.
