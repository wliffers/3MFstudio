# Haftungsausschluss und Hinweise zur Nutzung

*English version below.*

## Privates Projekt

3MFStudio ist ein privates Freizeitprojekt einer Einzelperson. Es ist **kein Produkt** der ALLPLAN GmbH,
der Nemetschek Group oder von Bambu Lab und steht mit diesen in keiner Verbindung. Es gibt keinen
Support-Anspruch, keine zugesicherten Reaktionszeiten und keine Pflicht zur Pflege oder Weiterentwicklung.

## Keine Gewährleistung

Die Software wird **so bereitgestellt, wie sie ist** („as is“), ohne jede ausdrückliche oder
stillschweigende Gewährleistung – insbesondere ohne Zusicherung der Fehlerfreiheit, der Eignung für einen
bestimmten Zweck, der Vollständigkeit erzeugter Dateien oder der Verträglichkeit mit künftigen Versionen
von Allplan, Bambu Studio oder anderen Programmen. Maßgeblich ist der Lizenztext in [LICENSE](LICENSE).

## Keine Haftung

Soweit gesetzlich zulässig, haftet der Urheber nicht für Schäden, die aus der Nutzung oder der
Unmöglichkeit der Nutzung entstehen – weder für Datenverlust, fehlerhafte Modelle, missglückte oder
beschädigte Drucke, Materialverbrauch, Geräteschäden noch für Folgeschäden jeder Art. Unberührt bleibt
eine Haftung, die sich nach zwingendem Recht nicht ausschließen lässt (etwa bei Vorsatz).

## Benutzung auf eigene Gefahr

- **Prüfe, was du druckst.** 3MFStudio erzeugt Geometrie aus Allplan-Körpern und liest fremde Dateien.
  Kontrolliere Maße, Lage, Überschneidungen und Filamentzuordnung im Slicer, bevor du druckst oder Dateien
  weitergibst.
- **Sichere deine Projekte.** Das Werkzeug legt Körper im Modell ab und färbt Körper um. Arbeite mit
  Sicherungen deiner Allplan-Projekte; Allplans „Rückgängig“ nimmt die Schritte zurück.
- **Fremde Dateien.** Beim Import liest 3MFStudio Dateien aus fremden Quellen. Öffne nur Dateien, denen
  du vertraust.
- **Drucker und Slicer.** Druckerprofile, Temperaturen, Materialeinstellungen und alles Weitere rund um
  den Druck liegen allein bei dir und deinem Slicer. 3MFStudio übernimmt nur, was in Bambu Studio
  eingestellt ist, und verändert dort nichts.

## Daten

3MFStudio verbindet sich nicht mit dem Internet und sendet keine Daten. Es schreibt Einstellungen nach
`%APPDATA%\3MFStudio\` und ein Protokoll nach `Dokumente\3MFStudio_debug.log`. In eine 3MF-Datei kommen
Geometrie, Filamentzuordnung und Teilnamen – bei einem Bambu-Projekt zusätzlich Farben, Sorten und
Druckerprofil –, aber keine Projektdaten, Attribute oder Pfade aus Allplan. Wer eine Datei weitergibt,
gibt deren Inhalt weiter.

## Marken

ALLPLAN ist eine Marke der ALLPLAN GmbH / Nemetschek Group. Bambu Lab und Bambu Studio sind Marken von
Bambu Lab. Alle weiteren Namen gehören ihren jeweiligen Inhabern und werden nur zur Beschreibung der
Zusammenarbeit genannt.

## Kein Rechtsrat

Dieser Text ist ein Hinweis des Urhebers, keine Rechtsberatung. Verbindlich ist die Lizenz in
[LICENSE](LICENSE).

---

# Disclaimer and Notes on Use (English)

## Private project

3MFStudio is a private spare-time project of an individual. It is **not a product** of ALLPLAN GmbH, the
Nemetschek Group or Bambu Lab and is not affiliated with any of them. There is no entitlement to support,
no promised response time and no obligation to maintain or extend it.

## No warranty

The software is provided **"as is"**, without warranty of any kind, express or implied – in particular
without any assurance of being free of defects, fit for a particular purpose, producing complete files, or
remaining compatible with future versions of Allplan, Bambu Studio or other programs. The licence text in
[LICENSE](LICENSE) governs.

## No liability

To the extent permitted by law, the author is not liable for any damage arising from the use or the
inability to use the software – including loss of data, faulty models, failed or damaged prints, material
consumption, damage to equipment, or consequential damage of any kind. Liability that cannot be excluded
under mandatory law (for example for intent) remains unaffected.

## Use at your own risk

- **Check what you print.** 3MFStudio generates geometry from Allplan bodies and reads foreign files.
  Verify dimensions, position, overlaps and filament assignment in your slicer before printing or passing
  files on.
- **Back up your projects.** The tool places bodies in the model and recolours bodies. Keep backups of
  your Allplan projects; Allplan's Undo reverts the steps.
- **Foreign files.** On import, 3MFStudio reads files from external sources. Open only files you trust.
- **Printer and slicer.** Printer profiles, temperatures, material settings and everything else about
  printing remain entirely with you and your slicer. 3MFStudio only picks up what is set in Bambu Studio
  and changes nothing there.

## Data

3MFStudio does not connect to the internet and sends no data. It writes settings to `%APPDATA%\3MFStudio\`
and a log to `Documents\3MFStudio_debug.log`. A 3MF file contains geometry, filament assignment and part
names – for a Bambu project also colours, materials and the printer profile – but no project data,
attributes or paths from Allplan. Whoever passes a file on passes its content on.

## Trademarks

ALLPLAN is a trademark of ALLPLAN GmbH / Nemetschek Group. Bambu Lab and Bambu Studio are trademarks of
Bambu Lab. All other names belong to their respective owners and are mentioned only to describe
interoperability.

## Not legal advice

This text is a notice by the author, not legal advice. The licence in [LICENSE](LICENSE) is binding.
