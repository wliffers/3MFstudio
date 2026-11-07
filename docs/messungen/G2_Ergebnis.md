# Gate G2 – Ergebnis

Stand 2026-11-06 · gemessen im laufenden **Allplan 2027.0**, Projekt „000_AI_ModelLink_playground“,
über den Entwicklermodus von AI ModelLink · Skript `g2_messung.py` · Proben auf dem eigenen
Teilbild 900 „3MFStudio Proben“.

**Vier von sieben Fragen sind gemessen, drei brauchen einen Menschen an der Maus** (Auswahl im
Modell, Dateidialog). Für den Weg „Körper lesen → Datei schreiben“ ist damit alles belegt.

## Antworten

| # | Frage | Antwort | Status |
|---|---|---|---|
| 1 | Liefert eine Wand ihren Körper selbst oder über ihre Schichten? | Die Wand selbst hat **keinen** Körper. Ihre Kinder vom Typ Wandschicht tragen ihn. Was die Auswahl im Werkzeug zurückgibt (Wand oder Schicht), ist noch nicht gemessen – das Werkzeug behandelt beides. | teilweise |
| 2 | Layername aus der Layernummer | Geht: Kurzname, Langname und „Kurz (Lang)“, z. B. „AR_B_FT (Wand Beton Fertigteil)“. | gemessen |
| 3 | Dateidialog aus dem Werkzeug | Braucht einen Klick. | offen |
| 4 | Körper lesen: Würfel, Wand mit Fenster, Decke mit Durchbruch | Maße exakt, Netze geschlossen, Löcher richtig (Tabelle unten). | gemessen |
| 5 | Auswahl im Modell aus einem Klick im eigenen Fenster starten | Braucht einen Klick. | offen |
| 6 | Mehrere Markierungsfarben gleichzeitig | **Geht nicht.** Allplan kennt nur eine Markierungsfarbe für alles Markierte – die zuletzt gesetzte gilt für alle. | gemessen |
| 7 | Stimmt die gelesene Farbe mit dem Bild überein? | Ja für echte Farben (Rot, Grün, Blau). Sonderfall Farbe 1: gelesen als Schwarz, im Grundriss schwarz, in der Animation weiß. | gemessen |

## Messwerte Körper (Frage 4)

| Probe | Typ in Allplan | Flächen | davon mit Loch | Dreiecke | geschlossen | Maße (mm) | Volumen |
|---|---|---:|---:|---:|---|---|---|
| Würfel 1 000 mm (3 Stück) | 3D-Körper | 6 | 0 | 12 | ja | 1000 × 1000 × 1000 | exakt |
| Grundkörper | 3D-Körper | 6 | 0 | 12 | ja | 40 × 20 × 10 | exakt |
| Einlage | 3D-Körper | 6 | 0 | 12 | ja | 20 × 6 × 5 | exakt |
| Wandschicht 24 cm mit Fenster | Wandschicht | 10 | 2 | 32 | ja | 4000 × 240 × 2500 | exakt (Wand minus Fenster) |
| Wandschicht 12 cm mit Fenster | Wandschicht | 10 | 2 | 32 | ja | 4000 × 120 × 2500 | exakt |
| Decke mit Durchbruch | Decke | 10 | 2 | 32 | ja | 4000 × 3000 × 200 | exakt (Decke minus Durchbruch) |

- **Außenseite:** Allplan liefert die Körper fast immer „nach innen gedreht“ (Volumen kommt negativ
  heraus), einzelne Hilfskörper nach außen. Das Werkzeug dreht jeden Körper anhand seines Volumens
  richtig herum.
- **Bestand im Brücken-Teilbild:** Die dortigen Körper sind gerundete Körper (BRep). Das Werkzeug
  muss sie vor dem Schreiben in Dreiecke zerlegen; dieser Weg ist im Projekt AnimationVR gemessen.

## Folgen für das Werkzeug

1. **Was als Körper zählt:** Hat ein Bauteil selbst einen Körper, wird genau der genommen. Nur wenn es
   keinen hat (Wand), werden seine Schichten genommen. Sonst **nicht** in die Kinder absteigen: Dort
   liegen Kopien des Bauteils und Hohlkörper (Fensteröffnung, Deckendurchbruch), die niemand
   drucken will.
2. **Fensteröffnungen, Durchbrüche, Attribut-Speicher** sind keine druckbaren Körper und werden mit
   Hinweis übergangen.
3. **Markierung im Modell:** Nur eine Farbe. Markiert werden deshalb die Körper des gerade aktiven
   Filaments; welches Filament welche Körper hat, zeigt das Fenster. Mehrfarbige Anzeige wäre nur
   über Vorschau-Kopien möglich (nicht gemessen).
4. **Farbe 1** (Schwarz/Weiß je nach Hintergrund) wird im Fenster als neutrale Farbe gezeigt.
5. **Layername** steht für Hinweise und Vorschläge zur Verfügung.

## Import: aus der Datei wieder saubere Körper (Nachtrag, gleicher Tag)

Vorgabe von Willi: Beim Import müssen saubere BRep-Körper entstehen, keine Dreiecks-Netze.

Eine 3MF-Datei enthält nur Dreiecke. Legt man sie unverändert ab, hat ein Quader 12 Dreiecksflächen
mit Diagonalen. Allplan kann das selbst bereinigen – gemessen:

| Form | Dreiecke in der Datei | Flächen nach dem Zusammenfassen | als BRep abgelegt |
|---|---:|---:|---|
| Quader 30 × 20 × 10 | 12 | 6 | gültig, 6 Flächen |
| Platte mit Loch | 32 | 10 (zwei mit Loch) | gültig, 10 Flächen |
| Rundkörper, 24 Seiten | 92 | 26 | gültig, 26 Flächen |

Kette: Dreiecke → Körper bauen → Allplans „Normalisieren“ fasst ebene Nachbardreiecke zu einer Fläche
zusammen → Umwandeln in BRep → „3D-Körper allgemein“. Foto des Allplan-Fensters: keine Diagonalen.

**Grenze:** Rundungen bleiben facettiert (der Rundkörper hat 24 ebene Streifen). Die Datei enthält
keine Kurven, daraus lässt sich keine echte Zylinderfläche zurückgewinnen.

## Rundreise (mit den Modulen aus `src/`)

| Schritt | Ergebnis |
|---|---|
| Grundkörper + Einlage aus Allplan lesen, Datei schreiben | Reihenfolge von selbst richtig (Grundkörper zuerst), 40 × 20 × 10 mm, beide Netze geschlossen |
| Diese Datei mit Bambu Studio slicen | Namen „Grundkörper“ und „Text“ kommen an, Filament 1: 3,82 g, Filament 2: 0,45 g, 25 Wechsel – genau wie die Rechenprobe aus G1 |
| Drei BRep-Körper aus Allplan lesen, schreiben, slicen | fehlerfrei, 222 × 30 × 20 mm, Volumen exakt |
| Eigene Datei zurück nach Allplan | zwei BRep-Körper mit je 6 Flächen, Maße exakt |
| Von Bambu geschriebene Projektdatei nach Allplan | dasselbe Ergebnis, Namen und Filamentnummern stimmen |

## Offen (braucht die Maus)

- Frage 1, zweiter Teil: Gibt die Auswahl die Wand oder die Schicht zurück?
- Frage 3: Dateidialog.
- Frage 5: Auswahl aus einem Klick im eigenen Fenster.

Diese drei zeigen sich beim ersten Lauf des Werkzeug-Gerüsts.

## Aufräumen

Die ersten Proben lagen 500 m abseits im Brücken-Teilbild 300. Sie sind gelöscht; der Vergleich mit
dem Schnappschuss von vorher meldet: nichts neu, nichts verschwunden. Seitdem liegen Proben nur noch
auf dem eigenen Teilbild 900. Dort liegen sie noch: Das Leeren des Teilbilds hat Willi abgelehnt.

## Belege (Allplan 2027, live)

| Baustein | Beleg |
|---|---|
| `adapter.GetModelGeometry()` → `Polyhedron3D` bei 3D-Körper, Wandschicht, Decke; `None` bei Wand, Fensteröffnung | `g2_messung.py`, Lauf 2026-11-06 |
| `BaseElementAdapterChildElementsService.GetChildElements(ele, False)` – liefert auch Kopien und Hohlkörper | ebd.; `entwickler api` |
| Typnamen `Volume3D_TypeUUID`, `Wall_TypeUUID`, `WallTier_TypeUUID`, `Window_TypeUUID`, `WindowTier_TypeUUID`, `Slab_TypeUUID`, `SlabOpening_TypeUUID`, `AttributeContainer_TypeUUID`, `BRep3D_Volume_TypeUUID` | ebd. |
| `LayerService.GetNameByID / GetShortNameByID / GetLongNameByID(layerID, document.GetDocumentID())`, `GetIDByShortName(name, document)` | ebd.; `entwickler api` |
| `CommonProperties.Color / ColorByLayer / Layer`, `GetColorPenStrokeByLayerFromLayerNumber(layer)` → `[Stift, Strich, Farbe]`, `GetColorById(n)` → `.Red/.Green/.Blue` (6 → 255,0,0 · 4 → 0,255,0 · 7 → 0,0,255 · 1 → 0,0,0) | ebd. |
| `HighlightService.HighlightElements(liste, farbe, flaechen=False)` – eine Farbe für alle; `CancelAllHighlightedElements()`; `ExecutePreviewDraw(document, True)` | ebd.; Fotos des Allplan-Fensters |
| `ModelElement3D(props, Polyhedron3D.CreateCuboid(p1, p2))` über `baue([...])` ablegen | ebd. |
| Körper aus Punkten, Kanten, Flächen: `Polyhedron3D(PolyhedronType.tVolume, n, n, n, False)`, `Polyhedron3DBuilder`, `AppendVertex`, `AppendEdge(GeometryEdge)`, `CreateFace`, `AppendEdge(OrientedEdge)`, `Complete()`, `InvertWithFlagUnchanged()` | Muster `Allplans Beispiel ConnectionToolbox, AutomatedConnectionsCtrl.py:2511-2538`; Lauf 2026-11-06 |
| `Polyhedron3D.Normalize(2)` fasst ebene Dreiecke zusammen (12 → 6); `Normalize(3)` und `MakeUnion` tun es nicht | Lauf 2026-11-06; Stub `NemAll_Python_Geometry.pyi:23204` |
| `CreateBRep3D(polyhedron)` → `(Fehlercode, BRep3D)`; scheitert bei nach außen gewendetem Körper, gelingt nach `InvertWithFlagUnchanged()` | Lauf 2026-11-06 |
