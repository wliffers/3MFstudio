# Belege für die G1-Probedateien

Quelle: BambuStudio, Branch `master`, `src/libslic3r/Format/bbs_3mf.cpp` sowie `Config.cpp`,
`PrintConfig.cpp`, `Model.cpp` – geladen am 2026-11-06 (Commit siehe unten). Zeilennummern beziehen
sich auf diesen Stand. Die 3MF-Grundstruktur folgt der 3MF Core Specification 1.x (Namespace
`http://schemas.microsoft.com/3dmanufacturing/core/2015/02`).

Commit `master` am 2026-11-06: `355d71eee5a9ebc794693fe57e63674806019770` (2026-11-06T00:41:57Z).

Gemessen wurde mit der hier installierten Version **02.09.01.70** = Tag `v02.09.01.70`
(Commit `56a57d00a591360cf41bf21383915ee5bf357be5`, 2026-11-03). Die Tabellen bis „Rückfall- und
Nachbearbeitungsregeln“ nennen Zeilen aus `master`; die beiden Abschnitte danach nennen Zeilen aus
dem Tag. Messwerte und Festlegungen: `ERGEBNIS.md`.

## Dateien im Archiv

| Pfad | Beleg |
|---|---|
| `3D/3dmodel.model` | `bbs_3mf.cpp:155` (`MODEL_FILE`, „the only format of the string which works with CURA“) |
| `[Content_Types].xml` | `:163`; Inhalt 1:1 wie Bambus Schreiber `:7341-7347` – nur `rels`, `model`, `png`, `gcode`; **kein** Eintrag für `.config` |
| `_rels/.rels` | `:164`; Inhalt `:7467-7470` (`Target="/3D/3dmodel.model" Id="rel-1" Type=…/2013/01/3dmodel`) |
| `Metadata/model_settings.config` | `:174` (`BBS_MODEL_CONFIG_FILE`) |
| `Metadata/project_settings.config` | `:173` (`BBS_PROJECT_CONFIG_FILE`) |

## Kopf von `3dmodel.model`

| Element | Beleg |
|---|---|
| `<model unit="millimeter" xml:lang="en-US" xmlns=core xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">` | Schreiber `:7592`; Produktions-Erweiterung `xmlns:p` nur bei `m_production_ext` `:7593-7594` → weggelassen |
| `<metadata name="Application">…</metadata>` | `:138`, `:7669`. **Beginnt der Wert mit `BambuStudio-`, gilt die Datei als Bambu-eigen** (`m_is_bbl_3mf`, `:4575-4579`). Die Proben tragen bewusst `Export3MF-G1-Probe` → Fremd-3MF-Pfad |
| `<metadata name="BambuStudio:3mfVersion">1</metadata>` | `:113`, Wert `VERSION_BBS_3MF = 1` `:109`; wird nur in `m_version` übernommen `:4566-4568`, setzt **nicht** `m_is_bbl_3mf` |
| `<object id type="model">` | leerer Typ = „model“ `:680-684`; `id`, `name`, `p:UUID` gelesen `:4173-4179` (UUID optional) |
| `<components><component objectid transform/>` | Schreiber `:7917-7950`; Leser `:4481-4500` – `p:path` optional, ohne `p:path` gilt dieselbe Modelldatei (`m_sub_model_path.empty() ? path : …`) |
| `transform` als 12 Zahlen | Schreiber `:7940-7947`: Spalte für Spalte, je 3 Zeilen |
| `<build><item objectid transform printable/>` | Leser `:4523-4538` (`printable` optional) |
| `<vertex x y z/>`, `<triangle v1 v2 v3/>` | Konstanten `:318-323`; Core Spec |

## `Metadata/model_settings.config`

| Element | Beleg |
|---|---|
| `<config>` Wurzel | `:263`, Schreiber `:8621` |
| `<object id="N">` – `N` = Objekt-Id in `3dmodel.model` (das **Build-Objekt**, bei A die Komponentenhülle) | Schreiber `:8630`; Leser `:4825-4836`, Zuordnung zu Modellobjekten `:2539-2551` |
| `<metadata key="name" value=…/>` am Objekt | Schreiber `:8634`; Leser `:2546-2547` |
| `<metadata key="extruder" value="1"/>` am Objekt | alle Config-Schlüssel des Objekts werden so geschrieben `:8642-8644`; gelesen über `set_deserialize` `:2551`; `extruder` ist `coInt` (`PrintConfig.cpp:2806`, 0 = Vorgabe) |
| `<metadata face_count="…"/>` | `:8645` (`MESH_STAT_FACE_COUNT` `:408`) – informativ |
| `<part id="M" subtype="normal_part">` – `M` = Objekt-Id des Teil-Netzes | Schreiber `:8658-8668`; Leser `:4858-4866`: ohne `lastid` wird `id` als Unterobjekt-Id gespeichert; Zuordnung `:5643-5648` (`volumes[...].subobject_id == sub_object->id`) |
| `subtype="normal_part"` | `Model.cpp:3688` (`type_to_string(MODEL_PART)`), Rückweg `:3669-3670` |
| `<metadata key="name"/>` im Teil | Schreiber `:8675`; Leser `:5832-5833` |
| `<metadata key="matrix" value="16 Zahlen"/>` | Schreiber `:8688-8697` (4×4, zeilenweise); Leser `:5660-5663` |
| `<metadata key="extruder" value="2"/>` im Teil | Config-Schlüssel des Teils `:8717-8719`; Leser `:5860-5861` (`volume->config.set_deserialize`) |
| `<mesh_stat face_count edges_fixed …/>` | Schreiber `:8731-8738`; Leser `:4876-4899` (Attribute `:408-413`) |

## `Metadata/project_settings.config`

| Punkt | Beleg |
|---|---|
| Format JSON, Schlüssel einzeln gesetzt; Arrays von Strings erlaubt; unbekannte Schlüssel landen in `unrecognized_keys`, kein Abbruch | `bbs_3mf.cpp:3087-3109` (`load_from_json`), `Config.cpp:885-1040` |
| `filament_colour` als `coStrings`, „Only used as a visual help on UI“ | `PrintConfig.cpp:2984-2986` |
| **Falle:** `filament_settings_id` begrenzt die zulässige Filamentnummer; `extruder` größer als die Anzahl → **auf 1 zurückgesetzt** | `bbs_3mf.cpp:2676-2683`. Die Proben enthalten den Schlüssel deshalb **nicht** |

## Rückfall- und Nachbearbeitungsregeln beim Laden (für N2 merken)

| Regel | Beleg |
|---|---|
| Objekt ohne `extruder` oder mit 0 → Filament 1 | `:2677-2683` |
| Objekt mit genau einem Teil → `extruder` des Teils wird gelöscht, das Objekt bestimmt (Variante B) | `:2685-2687` |
| Mehrere Teile → Teil-`extruder` 0 wird gelöscht, zu groß → 1 (Variante A) | `:2689-2699` |
| `model_settings.config` wird auch bei Fremd-3MF gelesen; nur Fehler darin sind dann nicht tödlich | `:2351-2358` |
| Fehlt `model_settings.config`, wird je Netz-Objekt genau ein Teil erzeugt (Kontrolle D) | `:2555-2563` |
| Datei gilt als „Projekt“, sobald `model_settings.config` **oder** `project_settings.config` vorhanden ist (→ Rückfrage Projekt / nur Geometrie wahrscheinlich) | `:10048-10060` (`is_bbs_project_3mf`) |
| Fremd-3MF mit genau einem Objekt: Objektname = Dateiname | `:4122-4127` |

## Bambu-Fenster: Regeln für fremde 3MF (Tag `v02.09.01.70`)

Aus dem Quelltext gelesen, nicht gemessen – das Fenster wird nicht ferngesteuert.

| Regel | Beleg |
|---|---|
| Datei ohne eigene Einstellungen: `load_config` wird abgeschaltet, Objekt- und Teil-Einstellungen bleiben unangetastet | `Plater.cpp:11880-11891` |
| Werden Einstellungen verworfen, bleibt `extruder` an Objekt und Teil ausdrücklich erhalten | `Plater.cpp:11893-11916` |
| Fehlende Filamente ergänzt das Fenster bis zur höchsten benutzten Nummer | `Plater.cpp:11697-11720`, Aufruf `:12582-12583` |
| Hinweis „The 3mf is not from Bambu Lab, load geometry data and color data only.“, abschaltbar über `skip_non_bambu_3mf_warning` | `Plater.cpp:12557-12581` |
| **Falle:** Enthält die Datei Farbangaben nach 3MF-Standard, wird `extruder` an Objekt und Teil **gelöscht** und ein Farbdialog übernimmt | `Plater.cpp:12561-12576` |
| **Falle:** Projektdatei, die Bambu nicht als eigene erkennt → Hinweis „The 3mf file has invalid config, load geometry data only“ | `Plater.cpp:11796-11801` |
| Mehrere Objekte mit je einem Teil und unterschiedlicher Unterkante werden ohne Rückfrage zu einem Objekt mit Teilen zusammengelegt; `extruder` wandert mit (Teil vor Objekt) | `Plater.cpp:12587-12591`, `Model.cpp:900-917`, `:928-970` (Vorrang `:954-958`) |
| Öffnen: gilt als Projekt, sobald eine der beiden Config-Dateien vorhanden ist; leere Platte → ohne Rückfrage, sonst Rückfrage Projekt / Geometrie | `bbs_3mf.cpp:10039-10051`, `Plater.cpp:26231-26257` |

## Kommandozeile (Tag `v02.09.01.70`)

| Punkt | Beleg |
|---|---|
| Aufruf, Optionen `--load-settings`, `--load-filaments`, `--slice`, `--export-3mf`, `--outputdir` | Bambu-Wiki „Command Line Usage“; gemessen in `bambu_check.py` |
| 3MF wird mit `LoadModel \| LoadConfig` geladen; `extruder` wird nur bei `--load-filament-ids` überschrieben | `BambuStudio.cpp:2051-2069`, `:2328-2331` |
| Filamentfarben kommen aus `--filament-colour`; ohne sie bleibt ein einziger Eintrag → Absturz nach dem Slicen, sobald Filament 2 benutzt wird (gemessen) | `BambuStudio.cpp:4146-4155` |
| Ergebnis steht in `result.json` im Ausgabeordner (`return_code`, je Platte `filaments`, `objects`, `filament_change_times`) | gemessen |

## Offen

- Fensterverhalten ist gelesen, nicht gemessen (siehe oben).
- Ob `[Content_Types].xml` ohne `.config`-Eintrag einen externen Validator (lib3mf) stört – N1.
- Überlappung: gemessen ist „das spätere Teil eines Objekts gewinnt, unabhängig von der
  Filamentnummer“ (`overlap_check.py`, `ERGEBNIS.md`). Die Stelle im Quelltext, die das festlegt,
  ist nicht herausgesucht.
