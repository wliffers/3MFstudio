# Änderungen

Alle nennenswerten Änderungen an 3MFStudio. Die Paketnummer (z. B. 1.1.2) ist die des `.allep`;
der Plugin-Manager von Allplan bietet nur bei höherer Nummer ein Update an.

## [1.1.3] – 2026-11-08

### Neu
- **Bauraum mit einem Klick:** Würfel-Symbol links neben dem Zahnrad. Es öffnet die Karte „Bauraum“ im Stil
  der Farbauswahl: Drucker aus der Liste oder eigene Maße X, Y, Z. Jede Änderung wird sofort gespeichert;
  ins Modell kommt nur etwas über „Druckplatte ablegen“. Der Abschnitt Druckplatte ist dafür aus dem Zahnrad
  umgezogen. Es ist immer nur eine Karte offen.
- **Hilfslayer KO_HK:** Druckplatte und Bauraum-Linien liegen auf dem Layer KO_HK (Hilfskonstruktion).
  Alles auf diesem Layer bleibt aus der 3MF-Datei: „Auswählen“ übergeht es, und vor dem Schreiben fallen
  zugeordnete Körper, die inzwischen auf KO_HK liegen, mit einem Hinweis heraus. Gibt es den Layer im
  Projekt nicht, sagt 3MFStudio das.
- **Import von Standardfarben:** Farben nach 3MF-Standard (z. B. aus anderen Programmen) werden zu
  Filamenten mit ihrer Farbe.

### Geprüft und behoben
- Lesen und Schreiben sind gegen die offiziellen Konformitätstests des 3MF-Konsortiums geprüft.
- Dateien, die eine von 3MFStudio nicht unterstützte Erweiterung voraussetzen (z. B. Beam Lattice, Slice,
  Production Alternatives) oder verschlüsselt sind, werden mit einer klaren Meldung abgelehnt.
- Beschädigte Dateien (ungültige Zahlen, Verweise auf fehlende Punkte, doppelte Nummern) werden abgelehnt,
  statt einen Absturz oder falsche Körper zu erzeugen.
- Geschriebene Dateien bestehen die strenge Prüfung von lib3mf; Bambu Studio liest sie unverändert.

## [1.1.2] – 2026-11-08

### Neu
- **Bambu-Projekt direkt beim Schreiben:** Ist Bambu Studio der Slicer, ist die geschriebene Datei das
  Bambu-Projekt mit Farben, Sorten und dem in Bambu Studio eingestellten Drucker samt Druck- und
  Filamentprofilen. Ohne erkannten Drucker bleibt er im Projekt offen.
- Haken **„Universelle 3MF schreiben“** im Zahnrad für eine neutrale Datei; darunter steht, was die
  nächste Datei wird.
- **Elementgruppen:** Körper einer Allplan-Elementgruppe werden ein Teil mit dem Namen der Gruppe.
- Die Karte zeigt „n Körper · Gruppe NAME“.

### Behoben
- Start nach einem Update ohne Allplan-Neustart: eine ältere Zuordnung im Speicher wird jetzt sauber
  übernommen statt das Fenster zu verhindern.

## [1.1.1] – 2026-11-07

### Neu
- **Druckplatte** im Zahnrad: Drucker aus einer Liste (93, Bambu Lab zuerst) oder eigene Maße; Platte
  1 mm stark mit Oberseite auf Z = 0, Mitte auf X/Y = 0; Bauraum auf Wunsch als 3D-Linien. Die
  Druckerliste liegt vollständig im Paket.

## [1.1.0] – 2026-11-07

### Neu
- **Farbe und Sorte je Filament** aus einer Liste echter Filamente (Open Filament Database, 161
  Hersteller, Bambu Lab zuerst; mit installiertem Bambu Studio dessen offizielle Farbnamen) oder eigene
  Farbe; zuletzt genutzte Farben werden gemerkt.
- Die gewählte Farbe färbt die Körper in Allplan mit (nächste der 255 Allplan-Farben).
- **⇅ tauscht** die Körper zweier Filamente – für ineinander steckende Körper.
- „Im Slicer öffnen“ mit Bambu Studio: Projekt mit Sorte und Farbe je Filament.

## [1.0.0] – 2026-11-07

### Erste Veröffentlichung
- Körper aus Allplan als 3MF schreiben: Filament je Körper (bis 16), Teilnamen, ineinander steckende
  Körper als ein Objekt (der kleinere gewinnt den gemeinsamen Bereich), offene Allplan-Nähte zugenäht.
- 3MF importieren: Körper als saubere Allplan-Körper, Filamentfarben und -zuordnung, Netzreparatur;
  glatte runde Flächen für Teile mit gleichbleibendem Querschnitt.
- Schwebendes Fenster über Allplan, Ladefenster ab 3 Sekunden, Deutsch/Englisch nach Allplan.
- „Im Slicer öffnen“ und Slicer-Wahl im Zahnrad; Auslieferung als `.allep` für den Plugin-Manager.
