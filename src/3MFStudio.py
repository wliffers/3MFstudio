"""3MFStudio - Austausch mit dem 3D-Druck fuer Allplan 2027 (Script Object, Bedienung im eigenen Fenster).

Export:  Koerper im Modell anklicken und einem von vier Filamenten geben, dann als 3MF-Datei schreiben.
         Bambu Studio uebernimmt Filamentnummer und Namen je Teil (gemessen, spike_g1/ERGEBNIS.md).
Import:  eine 3MF-Datei oeffnen und ihre Koerper als saubere BRep-Koerper per Mausklick absetzen
         (gemessen, spike_g2/ERGEBNIS.md).

Bedienung: Auswahl und Einstellungen stehen nur im schwebenden Fenster (threemf_window); die Allplan-Palette
zeigt bloss eine Info-Zeile. Das Werkzeug laeuft, solange das Fenster offen ist - Klicks ins Modell brauchen ein
laufendes Werkzeug (ohne gibt Allplan die Markierung nicht heraus, gemessen 2026-11-06). ESC ohne laufende Auswahl
oder das Kreuz im Fenster beenden 3MFStudio. Die Zuordnung bleibt bis zum naechsten Start erhalten, solange Allplan
laeuft (Laufzeit-Halter in threemf_window).

Ablauf im Rahmen (BaseScriptObject): ein Fensterklick setzt einen Interactor und startet ihn selbst - der Rahmen
startet einen ausserhalb seiner Ereignisse gesetzten Interactor nicht (so gemessen mit einem aelteren Script Object).
Ist der Interactor fertig, ruft der Rahmen `start_next_input`; dort steht in `_pending`, was mit dem Ergebnis
geschieht. Ein Filament bleibt "in Auswahl", bis ESC oder "Fertig": nach jedem Klick steht sofort die naechste
Auswahl bereit, und der Rahmen startet sie (ScriptObjectService.start_next_input).

Die Rechnung liegt in threemf_session (Zuordnung), threemf_model/-writer/-reader (Datei) und threemf_allplan
(Koerper lesen und ablegen); sie sind ohne Bedienung getestet (tests/).
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
import tempfile

import NemAll_Python_AllplanSettings as AllplanSettings
import NemAll_Python_BaseElements as AllplanBaseEle
import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_IFW_ElementAdapter as AllplanElementAdapter
import NemAll_Python_IFW_Input as AllplanIFW
import NemAll_Python_Utility as AllplanUtil

from BaseScriptObject import BaseScriptObject, BaseScriptObjectData
from BuildingElement import BuildingElement
from CreateElementResult import CreateElementResult
from ScriptObjectInteractors.MultiElementSelectInteractor import (
    MultiElementSelectInteractor, MultiElementSelectInteractorResult)
from ScriptObjectInteractors.OnCancelFunctionResult import OnCancelFunctionResult
from ScriptObjectInteractors.PointInteractor import PointInteractor, PointInteractorResult
from ScriptObjectInteractors.StartFunctionResult import StartFunctionResult
from TypeCollections.ModelEleList import ModelEleList

# Allplan legt den Skriptordner nicht verlaesslich auf den Suchpfad. Er kommt HINTEN an: vorne verdraengt die
# Datei 3MFStudio.py beim naechsten Laden das gleichnamige Paket ("3MFStudio is not a package", live gesehen
# 2026-11-06; docs/wpf-dauerfenster-in-allplan.md Abschnitt 4.8).
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

import threemf_text  # noqa: E402  # pyright: ignore[reportMissingImports]
import threemf_geom  # noqa: E402  # pyright: ignore[reportMissingImports]
import threemf_model  # noqa: E402  # pyright: ignore[reportMissingImports]
import threemf_loft  # noqa: E402  # pyright: ignore[reportMissingImports]
import threemf_writer  # noqa: E402  # pyright: ignore[reportMissingImports]
import threemf_reader  # noqa: E402  # pyright: ignore[reportMissingImports]
import threemf_session  # noqa: E402  # pyright: ignore[reportMissingImports]
import threemf_allplan  # noqa: E402  # pyright: ignore[reportMissingImports]
import threemf_window  # noqa: E402  # pyright: ignore[reportMissingImports]
import threemf_slicer  # noqa: E402  # pyright: ignore[reportMissingImports]
import threemf_bambu  # noqa: E402  # pyright: ignore[reportMissingImports]
import threemf_filaments  # noqa: E402  # pyright: ignore[reportMissingImports]
import threemf_printers  # noqa: E402  # pyright: ignore[reportMissingImports]

# Hilfsmodule hart neu laden, in der Reihenfolge ihrer Abhaengigkeit - sonst laeuft nach einem Ausrollen
# alter Code weiter, bis Allplan neu startet. Fenster und Zuordnung haengen an einem eigenen Eintrag in
# sys.modules (threemf_window.HOLDER); das Fenster wird beim Werkzeugstart mit neuem Code ersetzt.
threemf_text = importlib.reload(threemf_text)
threemf_geom = importlib.reload(threemf_geom)
threemf_model = importlib.reload(threemf_model)
threemf_loft = importlib.reload(threemf_loft)
threemf_writer = importlib.reload(threemf_writer)
threemf_reader = importlib.reload(threemf_reader)
threemf_session = importlib.reload(threemf_session)
threemf_allplan = importlib.reload(threemf_allplan)
threemf_filaments = importlib.reload(threemf_filaments)
threemf_printers = importlib.reload(threemf_printers)
threemf_window = importlib.reload(threemf_window)
threemf_slicer = importlib.reload(threemf_slicer)
threemf_bambu = importlib.reload(threemf_bambu)

SCRIPT_BUILD = "3MFStudio 0.9.6 (2026-11-08)"

FILE_FILTER = "3MF-Datei (*.3mf)|*.3mf|"
FILE_EXTENSION = "3mf"
PROGRAM_FILTER = "Programm (*.exe)|*.exe|"
HIGHLIGHT_COLOUR = 4                                       # Allplan kennt nur EINE Markierungsfarbe
PLATE_RGB = (60, 60, 60)                                   # Druckplatte dunkelgrau (naechste Allplan-Farbe)
VOLUME_RGB = (37, 99, 235)                                 # Bauraum-Linien blau
IMPORT_COLOURS = {1: 1, 2: 6, 3: 4, 4: 7}                 # Allplan-Farbe der importierten Koerper je Filament
HEADLESS_EDGE_MM = 1000.0


def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("threemfstudio.part")
    if not logger.handlers:
        # Ablage wie alle Parts des Workspace: ~/Documents/<Skript>_debug.log (Stage 3 liest dort).
        log_dir = os.path.join(os.path.expanduser("~"), "Documents")
        if not os.path.isdir(log_dir):
            log_dir = SCRIPT_DIR
        handler = logging.FileHandler(os.path.join(log_dir, "3MFStudio_debug.log"), "a", "utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


LOG = _setup_logging()
LOG.info("module loading, build %s", SCRIPT_BUILD)


def _allplan_language() -> str:
    """Allplans Sprache als zwei Buchstaben ("de", live 2026-11-07); ohne Antwort Deutsch."""
    try:
        return str(AllplanSettings.AllplanLocalisationService.Language())
    except Exception as exc:
        LOG.warning("Allplan-Sprache nicht lesbar, nehme Deutsch: %s", exc)
        return "de"


LOG.info("Sprache: %s", threemf_text.set_language(_allplan_language()))
tr = threemf_text.tr


def log_hint() -> str:
    return tr("Einzelheiten stehen in Dokumente\\3MFStudio_debug.log.")


def _is_headless() -> bool:
    """True, wenn der Test-Loop das Part treibt (Muster AnimationVR.py:121-131)."""
    try:
        if AllplanUtil.IsExecutedByUnitTest():
            return True
    except Exception as exc:
        LOG.warning("IsExecutedByUnitTest nicht abfragbar: %s", exc)
    if "unittest" in sys.modules:
        return True
    entry = os.path.basename(sys.argv[0]).lower() if sys.argv and sys.argv[0] else ""
    return entry.endswith(".py")


# Dialoge laufen ueber je EINE Funktion: eine Live-Probe ersetzt sie, sonst wartet Allplan auf einen Klick.

def ask_save_file(suggestion: str) -> str:
    return AllplanUtil.FileDialog.AskSaveFile(suggestion, tr("3MF-Datei speichern"), FILE_FILTER, FILE_EXTENSION,
                                              AllplanUtil.DefaultDirectories())


def ask_open_file() -> str:
    return AllplanUtil.FileDialog.AskOpenFile("", tr("3MF-Datei öffnen"), FILE_FILTER, FILE_EXTENSION,
                                              AllplanUtil.DefaultDirectories())


def ask_program() -> str:
    return AllplanUtil.FileDialog.AskOpenFile("", tr("Slicer-Programm wählen"), PROGRAM_FILTER, "exe",
                                              AllplanUtil.DefaultDirectories())


def ask_overwrite(path: str) -> bool:
    question = tr("Die Datei gibt es schon:\n{path}\n\nÜberschreiben?", path=path)
    return AllplanUtil.ShowMessageBox(question, AllplanUtil.MB_YESNO) == AllplanUtil.IDYES


def check_allplan_version(_build_ele: BuildingElement, _version: str) -> bool:
    """Check the current Allplan version

    Args:
        _build_ele: building element with the parameter properties
        _version:   the current Allplan version

    Returns:
        True
    """
    return True


def create_script_object(build_ele: BuildingElement, script_object_data: BaseScriptObjectData) -> BaseScriptObject:
    """Creation of the script object

    Args:
        build_ele:          building element with the parameter properties
        script_object_data: script object data

    Returns:
        created script object
    """
    return Studio3MF(build_ele, script_object_data)


class Studio3MF(BaseScriptObject):
    """Das Werkzeug: bedient das Fenster, die Auswahl im Modell und die Dialoge."""

    def __init__(self, build_ele: BuildingElement, script_object_data: BaseScriptObjectData):
        # Die Basis nimmt AUSSCHLIESSLICH script_object_data (brain 2026-07-28).
        super().__init__(script_object_data)
        self.build_ele = build_ele
        build_ele.InfoText.value = tr("Bedienung im 3MFStudio-Fenster")   # die Palette in Allplans Sprache
        self.selection_result = MultiElementSelectInteractorResult()
        self.point_result = PointInteractorResult()
        self._pending: tuple | None = None          # was nach dem laufenden Interactor geschieht
        self._armed = 0                             # Filament in Auswahl, 0 = keines
        self._alive = True                          # False, sobald das Werkzeug endet
        self._closing = False                       # das Kreuz im Fenster: ESC beendet dann das Werkzeug
        self._window = None
        self._import_elements: list = []
        self._import: tuple | None = None           # (Teile, Allplan-Farben, Farbtabelle, Leseergebnis) bis zum Absetzen
        self._headless = _is_headless()
        self._headless_elements: ModelEleList | None = None
        LOG.info("Werkzeug gestartet, headless=%s", self._headless)
        state = threemf_window.runtime()
        self.session = threemf_session.adopt(state.session)   # Koerper alter Fassungen bekommen neue Felder
        self.adapters: dict = state.adapters        # Kennung -> Bauteil, fuer die farbige Markierung
        state.session = self.session
        self.settings = threemf_slicer.load()       # Slicer-Programm; fehlt die Datei, gilt der Windows-Standard
        # Kein Fenster im Test-Loop und keines fuer die Vorschau der Bibliothek (is_only_update).
        if not self._headless and not self.is_only_update:
            try:
                self._window = threemf_window.open_window(self, self._view())
            except Exception:
                LOG.exception("Fenster liess sich nicht oeffnen")
                AllplanUtil.ShowMessageBox(tr("Das Fenster von 3MFStudio ließ sich nicht öffnen.") + "\n" + log_hint(),
                                           AllplanUtil.MB_OK)

    # ------------------------------------------------------------------ Rahmen

    def start_input(self):
        """Start ohne Eingabe: ausgewaehlt wird erst, wenn im Fenster ein Filament gewaehlt ist."""
        self.script_object_interactor = None

    def start_next_input(self):
        """Der laufende Interactor ist fertig. Steht danach wieder einer bereit, startet ihn der Rahmen."""
        self._finish_step()
        self._refresh()

    def execute(self) -> CreateElementResult:
        """Das Werkzeug legt hier nichts ab - nur der Import, per Klick. Der Test-Loop bekommt die Probewuerfel."""
        return self._headless_result() if self._headless else CreateElementResult()

    def on_control_event(self, event_id: int, *_args) -> bool:
        LOG.info("Palettenereignis %s uebergangen - die Bedienung ist das Fenster", event_id)
        return False

    def on_cancel_function(self) -> OnCancelFunctionResult:
        """ESC: eine laufende Auswahl endet und das Werkzeug bleibt; ohne Auswahl endet 3MFStudio."""
        if self._headless:
            return OnCancelFunctionResult.CREATE_ELEMENTS
        if self.script_object_interactor is not None and not self._closing:
            self._stop_input()
            LOG.info("Auswahl mit ESC beendet")
            self._refresh()
            return OnCancelFunctionResult.CONTINUE_INPUT
        self._stop_input()
        self._alive = False
        self._highlight(0)
        window, self._window = self._window, None
        if window is not None:
            window.detach()
            threemf_window.close_window()
        LOG.info("Werkzeug beendet")
        return OnCancelFunctionResult.CANCEL_INPUT

    # ------------------------------------------------------------------ Fenster -> Werkzeug

    def window_action(self, name: str, *values) -> None:
        """Ein Klick im Fenster (threemf_window). Laeuft ausserhalb eines Palettenereignisses."""
        if name == "closed":
            self._window = None
            if self._alive:
                # Das Kreuz beendet 3MFStudio: laufende Auswahl abraeumen, dann ESC an Allplan.
                self._closing = True
                self._stop_input()
                threemf_window.end_tool_soon(1.0)
            return
        if not self._alive:
            LOG.warning("Fensterklick %s nach dem Ende des Werkzeugs uebergangen", name)
            return
        LOG.info("Fenster: %s %s", name, list(values))
        self._run(lambda: self._act(name, values), f"Fensterklick {name}")
        self._refresh()

    def _act(self, name: str, values: tuple) -> None:
        if name == "pick":
            self._toggle_selection(int(values[0]))
        elif name == "clear":
            self._clear(int(values[0]))
        elif name == "rename":
            self.session.names[int(values[0])] = str(values[1])
        elif name == "scale":
            self.session.scale_on = bool(values[0])
        elif name == "reduction":
            self.session.reduction = float(values[0])
            self.session.scale_on = True
        elif name == "export":
            self._export()
        elif name == "slicer":
            self._open_in_slicer()
        elif name == "slicer_choose":
            self._choose_slicer()
        elif name == "slicer_reset":
            self.settings["slicer"] = ""
            threemf_slicer.save(self.settings)
        elif name == "universal":
            self.settings["universell"] = bool(values[0])
            threemf_slicer.save(self.settings)
        elif name == "import":
            self._start_import()
        elif name == "colour_open":
            self._open_colours(int(values[0]))
        elif name == "choose":
            self._choose(int(values[0]), self._listed_choice(str(values[1]), str(values[2]), int(values[3])))
        elif name == "choose_mine":
            self._choose(int(values[0]), self._mine()[int(values[1])])
        elif name == "choose_own":
            self._choose_own(int(values[0]), str(values[1]), str(values[2]), str(values[3]))
        elif name == "choose_auto":
            self.session.choose(int(values[0]), None)
        elif name == "swap":
            self._swap(int(values[0]), int(values[1]))
        elif name == "plate":
            self._place_plate(str(values[0]), bool(values[1]), values[2:5])
        elif name == "volume_save":
            self._save_volume(str(values[0]), bool(values[1]), values[2:5])
        else:
            LOG.warning("Unbekannter Fensterklick %s", name)

    def _run(self, step, label: str) -> None:
        """Fuehrt einen Bedienschritt aus; ein Fehler kommt als Meldung und steht im Protokoll."""
        try:
            step()
        except threemf_model.ThreeMfError as exc:
            self._tell(str(exc))
        except Exception:
            LOG.exception("%s gescheitert", label)
            self._tell(tr("Das hat nicht geklappt.") + " " + log_hint())

    # ------------------------------------------------------------------ Auswahl

    def _prompt(self, target: int) -> str:
        return tr("Körper für „{name}“ anklicken – „Fertig“ oder ESC beendet", name=self.session.name_of(target))

    def _stop_input(self) -> None:
        """Beendet eine laufende Auswahl oder Ablage; ohne laufende Eingabe geschieht nichts."""
        interactor, self.script_object_interactor = self.script_object_interactor, None
        self._pending = None
        self._armed = 0
        self._import_elements = []
        if isinstance(interactor, MultiElementSelectInteractor):
            interactor.close_selection()            # nimmt Allplans Auswahlfunktion wieder vom Stapel

    def _prepare_selection(self, target: int) -> None:
        self._pending = ("pick", target)
        self.selection_result = MultiElementSelectInteractorResult()
        self.script_object_interactor = MultiElementSelectInteractor(self.selection_result,
                                                                     prompt_msg=self._prompt(target))

    def _toggle_selection(self, target: int) -> None:
        """"Auswaehlen" startet die Auswahl; derselbe Knopf ("Fertig") beendet sie."""
        running = self._armed == target and self.script_object_interactor is not None
        self._stop_input()
        if running:
            self._highlight(0)
            return
        self._armed = target
        self._highlight(target)
        self._prepare_selection(target)
        interactor = self.script_object_interactor
        if interactor is None or interactor.start_input(self.coord_input) != StartFunctionResult.PRE_SELECTED_ELEMENTS:
            return
        # In Allplan war schon etwas markiert: der Interactor hat es sofort uebernommen, und niemand sonst
        # meldet das (MultiElementSelectInteractor.py:82-91).
        self._finish_step()
        interactor = self.script_object_interactor  # bleibt das Filament in Auswahl, steht hier der naechste
        if interactor is not None and interactor.start_input(self.coord_input) == StartFunctionResult.PRE_SELECTED_ELEMENTS:
            LOG.warning("Markierung blieb stehen - Auswahl beendet")
            self._stop_input()

    def _finish_step(self) -> None:
        """Der laufende Interactor ist fertig: Ergebnis uebernehmen; ein Filament in Auswahl bleibt in Auswahl."""
        self.script_object_interactor = None
        pending, self._pending = self._pending, None
        if pending is None:
            return
        if pending[0] == "place":
            self._run(self._place_import, "Ablegen")
            return
        self._run(lambda: self._take_selection(pending[1]), "Auswahl")
        if self._armed <= 0 or self._armed != pending[1]:
            self._armed = 0
        elif self._marking_left():
            # Sonst naehme die naechste Auswahl sofort wieder dieselben Bauteile - bei jeder Mausbewegung.
            LOG.warning("Markierung blieb stehen - Auswahl beendet")
            self._armed = 0
        else:
            self._prepare_selection(pending[1])

    def _marking_left(self) -> bool:
        """True, wenn in Allplan noch Bauteile markiert sind (oder sich das nicht feststellen laesst)."""
        try:
            return len(AllplanIFW.SelectElementsService.GetPreSelectedElements(self.document,
                                                                               AllplanIFW.SelectionQuery())) > 0
        except Exception:
            LOG.exception("Markierung nicht abfragbar")
            return True

    def _take_selection(self, target: int) -> None:
        elements = list(self.selection_result.sel_elements)
        # Die Markierung aufheben: sonst uebernimmt das naechste "Auswaehlen" sofort wieder dieselben Bauteile,
        # statt den Anwender klicken zu lassen (live gesehen 2026-11-06).
        try:
            AllplanIFW.SelectElementsService.PassivateAllElements(self.document)
        except Exception:
            LOG.exception("Markierung liess sich nicht aufheben")
        bodies, skipped = self._bodies_of(elements)
        added, removed = self.session.pick(target, bodies)
        for body in bodies if removed else []:
            self.adapters.pop(body.key, None)
        LOG.info("Filament %s: %s dazu, %s heraus", target, added, removed)
        if added:
            self._recolour(target)              # hat das Filament eine gewaehlte Farbe, bekommen die neuen sie auch
        self._highlight(target)
        if skipped:
            LOG.info("%s Bauteile ohne druckbaren Koerper uebergangen", skipped)

    def _bodies_of(self, elements: list) -> tuple[list, int]:
        """Die angeklickten Bauteile als Koerper; dazu die Zahl derer ohne druckbaren Koerper."""
        kinds = [threemf_allplan.type_name(element) for element in elements]
        # Liefert die Auswahl eine Wand UND ihre Schichten, zaehlen nur die Schichten - sonst stuende sie doppelt.
        layers_picked = any(kind in threemf_allplan.BODY_CHILDREN.values() for kind in kinds)
        help_layer = self._help_layer()
        bodies, skipped, helping = [], 0, 0
        with self._busy(tr("Körper werden gelesen")) as busy:
            for index, (element, kind) in enumerate(zip(elements, kinds)):
                busy.step(tr("Körper {done} von {total} wird gelesen …", done=index + 1, total=len(elements)))
                if layers_picked and kind in threemf_allplan.BODY_CHILDREN:
                    continue
                if threemf_allplan.on_layer(element, help_layer):
                    helping += 1                # Hilfskonstruktion (Druckplatte & Co.) kommt nie in die Datei
                    continue
                body = self._body_of(element)
                if body is None:
                    skipped += 1
                else:
                    bodies.append(body)
        LOG.info("Auswahl: %s Bauteile (%s), %s Koerper, %s uebergangen, %s auf %s", len(elements), sorted(set(kinds)),
                 len(bodies), skipped, helping, threemf_allplan.HELP_LAYER)
        return bodies, skipped

    def _body_of(self, element):
        """Ein angeklicktes Bauteil als Koerper (Netz dicht genaeht); None ohne druckbaren Koerper."""
        solids = threemf_allplan.solids_of(element)
        if not solids:
            return None
        label = element.GetDisplayName()
        try:
            part, failed_faces = threemf_allplan.part_from_solids(solids, label, 1)
        except threemf_model.ThreeMfError:
            return None
        if failed_faces:
            LOG.warning("%s: %s Flaechen nicht zerlegbar", label, failed_faces)
        colour, rgb = threemf_allplan.colour_of(element)
        group, group_name = threemf_allplan.group_of(element)
        key = str(element.GetElementUUID())
        self.adapters[key] = element
        return threemf_session.Body(key, label, colour, rgb, part, group=group, group_name=group_name)

    def _busy(self, title: str, text: str = ""):
        """Ladefenster fuer einen langen Schritt - erscheint erst nach 3 s; ohne Fenster (Test-Loop) unsichtbar."""
        return threemf_window.Busy(title, text, enabled=self._window is not None)

    def _clear(self, filament: int) -> None:
        for key in self.session.keys(filament):
            self.adapters.pop(key, None)
        LOG.info("Filament %s geleert (%s Koerper)", filament, self.session.clear(filament))
        self._highlight(self._armed if self._armed > 0 else 0)

    def _highlight(self, filament: int) -> None:
        """Markiert die Koerper EINES Filaments farbig; 0 hebt das auf. Reine Anzeige."""
        try:
            AllplanIFW.HighlightService.CancelAllHighlightedElements()
            adapters = AllplanElementAdapter.BaseElementAdapterList()
            for key in (self.session.keys(filament) if filament else []):
                if key in self.adapters:
                    adapters.append(self.adapters[key])
            if len(adapters):
                AllplanIFW.HighlightService.HighlightElements(adapters, HIGHLIGHT_COLOUR)
            AllplanBaseEle.ExecutePreviewDraw(self.document, True)
        except Exception:
            LOG.exception("Farbige Markierung gescheitert")

    # ------------------------------------------------------------------ Farbe und Sorte

    def _catalogue(self):
        """Die Farbliste - einmal je Allplan-Sitzung geladen (Laufzeit-Halter), Bambu Lab aus Bambu Studio, wenn da."""
        state = threemf_window.runtime()
        if state.catalogue is None:
            with self._busy(tr("Farbliste wird geladen")):
                program = threemf_slicer.slicer_program(self.settings["slicer"])
                found = threemf_filaments.bambu_colour_file(program)
                bases = threemf_bambu.base_profiles(os.path.dirname(found)) if found else {}
                state.catalogue = threemf_filaments.catalogue(threemf_text.language(), program,
                                                              {code: kind for code, (_stem, kind) in bases.items()})
            LOG.info("Farbliste %s: %s Hersteller, %s Farben, Bambu aus %s", state.catalogue.version,
                     len(state.catalogue.brands()), state.catalogue.count(), state.catalogue.bambu_file or "-")
        return state.catalogue

    def _mine(self) -> list:
        return threemf_session.mine_from_settings(self.settings)

    def _open_colours(self, filament: int) -> None:
        if self._window is not None:
            self._window.open_colours(filament, self._catalogue(), self.session.choices.get(filament), self._mine())

    def _listed_choice(self, brand: str, line_name: str, index: int):
        line = self._catalogue().line(brand, line_name)
        if line is None or not 0 <= index < len(line.swatches):
            raise threemf_model.ThreeMfError(tr("Diese Farbe gibt es in der Liste nicht mehr."))
        swatch = line.swatches[index]
        return threemf_session.Choice(swatch.hex, swatch.name, line.brand, line.name, line.material, line.code)

    def _choose_own(self, filament: int, text: str, brand: str, line_name: str) -> None:
        value = threemf_filaments.normal_hex(text)
        if not value:
            raise threemf_model.ThreeMfError(tr("„{text}“ ist kein Farbwert. Bitte so eingeben: #00AE42", text=text))
        line = self._catalogue().line(brand, line_name)
        choice = threemf_session.Choice(value, value, brand if line else "", line.name if line else "",
                                        line.material if line else "", line.code if line else "")
        threemf_session.remember_mine(self.settings, choice)
        threemf_slicer.save(self.settings)
        self._choose(filament, choice)

    def _choose(self, filament: int, choice) -> None:
        self.session.choose(filament, choice)
        LOG.info("Filament %s: Farbe %s (%s)", filament, choice.hex, choice.label() or "-")
        self._recolour(filament)
        self._highlight(self._armed)

    def _swap(self, first: int, second: int) -> None:
        moved = self.session.swap(first, second)
        LOG.info("Filament %s <-> %s getauscht (%s Koerper)", first, second, moved)
        self._recolour(first)
        self._recolour(second)
        self._highlight(self._armed)

    def _palette(self) -> dict:
        state = threemf_window.runtime()
        if not state.palette:
            state.palette = threemf_allplan.palette()
        return state.palette

    def _recolour(self, filament: int) -> None:
        """Die Koerper des Filaments bekommen in Allplan seine gewaehlte Farbe (naechste Allplan-Farbe).

        ElementsPropertyService.ModifyFormatProperties([(ModifyPropertyID, Wert)], Bauteile) - ein Rueckgaengig-
        Schritt; Farbe "von Layer" wird dabei ausgeschaltet, sonst zeigte Allplan weiter die Layerfarbe (beides wie
        AI ModelLink `_modify_format`, live belegt). Allplan kann den Bauteilen neue Kennungen geben - die
        Rueckgabe sind die Bauteile danach, die Zuordnung zieht mit."""
        palette = self._palette()
        number, keys = self.session.to_recolour(filament, palette)
        keys = [key for key in keys if key in self.adapters]
        if not number or not keys:
            return
        adapters = AllplanElementAdapter.BaseElementAdapterList()
        for key in keys:
            adapters.append(self.adapters[key])
        ids = AllplanBaseEle.ModifyPropertyID
        changes = [(ids.Color, number), (ids.ColorByLayer, 0)]
        try:
            # Der Stub nennt nur ein Argument; die Runtime nimmt (Aenderungen, Bauteile) - AI ModelLink A4 M13.
            after = list(AllplanBaseEle.ElementsPropertyService.ModifyFormatProperties(changes, adapters))  # type: ignore[call-arg]
        except Exception:
            LOG.exception("Umfaerben von %s Koerpern gescheitert", len(keys))
            self._tell(tr("Allplan hat die Farbe der Körper nicht übernommen.") + " " + log_hint())
            return
        if len(after) != len(keys):
            LOG.warning("Umfaerben: %s Bauteile zurueck fuer %s - Kennungen bleiben", len(after), len(keys))
            after = [self.adapters[key] for key in keys]
        rgb = palette.get(number, (0, 0, 0))
        for key, adapter in zip(keys, after):
            new_key = str(adapter.GetElementUUID())
            self.adapters.pop(key, None)
            self.adapters[new_key] = adapter
            self.session.recoloured(key, new_key, number, rgb)
        LOG.info("Filament %s: %s Koerper auf Allplan-Farbe %s", filament, len(keys), number)

    # ------------------------------------------------------------------ Druckplatte

    def _printers(self) -> list:
        """Die mitgelieferte Druckerliste (threemf_printers.json) - einmal je Allplan-Sitzung."""
        state = threemf_window.runtime()
        if not state.printers:
            try:
                state.printers = threemf_printers.load()
            except (OSError, ValueError, KeyError, TypeError):
                LOG.exception("Druckerliste nicht lesbar")
                state.printers = []
        return state.printers

    def _save_volume(self, name: str, with_volume: bool, sizes: tuple):
        """Bauraum-Karte: Drucker, Linien und eigene Masse sofort in die Einstellungen; liefert den Drucker."""
        printer = threemf_printers.find(self._printers(), name) if name else None
        if printer is None:
            printer = threemf_printers.custom(*sizes)        # meldet unbrauchbare Masse
            self.settings["eigene_masse"] = [printer.width, printer.depth, printer.height]
        self.settings["drucker"], self.settings["bauraum"] = (name if printer.name else ""), with_volume
        threemf_slicer.save(self.settings)
        return printer

    def _volume_note(self) -> str:
        """Die Zeile der Bauraum-Karte: was gerade gespeichert ist."""
        name = self.settings["drucker"]
        printer = threemf_printers.find(self._printers(), name) if name else None
        sizes = (printer.width, printer.depth, printer.height) if printer else self.settings["eigene_masse"]
        return tr("Gespeichert: {printer} · {size} mm", printer=name if printer else tr("Eigene Maße"),
                  size=" × ".join("%g" % float(value) for value in sizes))

    def _place_plate(self, name: str, with_volume: bool, sizes: tuple) -> None:
        """Druckplatte (1 mm, Oberseite Z = 0, Mitte X/Y = 0) und auf Wunsch den Bauraum als Linien ablegen."""
        printer = self._save_volume(name, with_volume, sizes)
        palette = self._palette()
        lines = threemf_printers.volume_lines(printer) if with_volume else []
        layer = self._help_layer()
        elements = threemf_allplan.plate_elements(threemf_printers.plate_box(printer), lines,
                                                  threemf_model.nearest_colour(PLATE_RGB, palette),
                                                  threemf_model.nearest_colour(VOLUME_RGB, palette), layer)
        created = list(AllplanBaseEle.CreateElements(self.document, AllplanGeo.Matrix3D(), elements, [], None))
        LOG.info("Druckplatte %s (%g x %g x %g mm, Bauraum %s, Layer-ID %s): %s Bauteile", printer.name or "eigene Masse",
                 printer.width, printer.depth, printer.height, with_volume, layer, len(created))
        if not layer:
            self._tell(tr("Den Layer „{layer}“ gibt es in diesem Projekt nicht. Die Druckplatte liegt deshalb auf dem "
                          "eingestellten Layer – beim Auswählen bitte nicht mit anklicken.",
                          layer=threemf_allplan.HELP_LAYER))

    def _help_layer(self) -> int:
        """ID des Hilfslayers KO_HK in diesem Projekt; 0, wenn es ihn nicht gibt."""
        try:
            return threemf_allplan.layer_id(threemf_allplan.HELP_LAYER, self.document)
        except Exception:
            LOG.exception("Layer %s nicht aufloesbar", threemf_allplan.HELP_LAYER)
            return 0

    def _release_help_layer(self) -> None:
        """Vor dem Schreiben: zugeordnete Koerper, die inzwischen auf dem Hilfslayer liegen, kommen nicht in die Datei."""
        layer = self._help_layer()
        if not layer:
            return
        keys = []
        for key, adapter in list(self.adapters.items()):
            try:
                if threemf_allplan.on_layer(adapter, layer):
                    keys.append(key)
            except Exception:
                LOG.exception("Layer von %s nicht lesbar - Koerper bleibt zugeordnet", key)
        released = self.session.release(keys)
        for key in keys:
            self.adapters.pop(key, None)
        if released:
            LOG.info("%s Koerper auf %s aus der Zuordnung genommen", released, threemf_allplan.HELP_LAYER)
            if released == 1:
                text = tr("Ein Körper liegt auf dem Layer „{layer}“ (Hilfskonstruktion) und kommt nicht in die Datei.",
                          layer=threemf_allplan.HELP_LAYER)
            else:
                text = tr("{number} Körper liegen auf dem Layer „{layer}“ (Hilfskonstruktion) und kommen nicht in "
                          "die Datei.", number=released, layer=threemf_allplan.HELP_LAYER)
            self._tell(text)

    # ------------------------------------------------------------------ Datei

    def _export(self) -> None:
        if self._armed:
            self._stop_input()
            self._highlight(0)
        self._release_help_layer()
        parts = self.session.parts()                # meldet "nichts zugeordnet" und einen unsinnigen Massstab
        chosen = ask_save_file("")
        if not chosen:
            LOG.info("Schreiben abgebrochen")
            return
        if not chosen.lower().endswith("." + FILE_EXTENSION):
            chosen += "." + FILE_EXTENSION
        if os.path.exists(chosen) and not ask_overwrite(chosen):
            LOG.info("Nicht ueberschrieben: %s", chosen)
            return
        with self._busy(tr("3MF wird geschrieben"), tr("Datei wird geschrieben …")):
            threemf_writer.write_3mf(chosen, parts)
        self.session.last_file = chosen
        self.session.last_colours = self.session.filament_colours()
        self.session.last_choices = self.session.filament_choices()
        self.session.last_is_project = False
        LOG.info("geschrieben: %s (%s Teile)", chosen, len(parts))
        self._bambu_project(chosen)

    def _bambu_project(self, written: str) -> None:
        """Ohne den Haken "universell" wird die Datei gleich Bambus Projekt mit Farben und Sorten - wenn Bambu
        Studio der Slicer ist. Scheitert Bambu, bleibt die universelle Datei liegen, mit Meldung."""
        program = threemf_slicer.slicer_program(self.settings["slicer"])
        if self.settings["universell"] or not threemf_bambu.is_bambu(program):
            return
        with self._busy(tr("Bambu-Projekt wird gebaut"), tr("Bambu Studio legt Farben und Sorten in die Datei …")):
            reason = threemf_bambu.coloured_project(program, written, self.session.last_colours, written,
                                                    choices=self.session.last_choices)
        if reason:
            LOG.warning("Bambu-Projekt nicht gebaut (%s) - die Datei bleibt die universelle 3MF", reason)
            self._tell(tr("Bambu Studio hat kein Projekt gebaut. Die Datei ist die universelle 3MF; "
                          "Farben und Sorten fehlen in Bambu Studio.") + " " + log_hint())
            return
        self.session.last_is_project = True
        LOG.info("Bambu-Projekt geschrieben: %s", written)

    def _open_in_slicer(self) -> None:
        """Oeffnet die zuletzt geschriebene Datei. Ist sie noch kein Bambu-Projekt und der Slicer Bambu Studio,
        baut Bambu vorher eins mit den Filamentfarben (threemf_bambu, Temp-Ordner); scheitert das, oeffnet
        die gewoehnliche Datei."""
        written, slicer = self.session.last_file, self.settings["slicer"]
        target = written
        program = threemf_slicer.slicer_program(slicer)
        if (written and os.path.isfile(written) and threemf_bambu.is_bambu(program) and self.session.last_colours
                and not self.session.last_is_project):
            project = threemf_slicer.project_path(written)
            with self._busy(tr("Slicer wird vorbereitet"), tr("Bambu Studio baut das Projekt mit den Filamentfarben …")):
                reason = threemf_bambu.coloured_project(program, written, self.session.last_colours, project,
                                                        choices=self.session.last_choices)
            if reason:
                LOG.warning("Farbiges Projekt nicht gebaut (%s) - oeffne die Datei ohne Farben", reason)
            else:
                LOG.info("farbiges Bambu-Projekt: %s %s", project, self.session.last_colours)
                target = project
        message = threemf_slicer.open_in_slicer(target, slicer)
        if message:
            self._tell(message)

    def _choose_slicer(self) -> None:
        chosen = ask_program()
        if not chosen:
            LOG.info("Slicer-Wahl abgebrochen")
            return
        problem = threemf_slicer.check_program(chosen)
        if problem:
            self._tell(problem)
            return
        self.settings["slicer"] = chosen
        threemf_slicer.save(self.settings)

    def _start_import(self) -> None:
        self._stop_input()
        self._highlight(0)
        chosen = ask_open_file()
        if not chosen:
            LOG.info("Import abgebrochen")
            return
        with self._busy(tr("3MF wird importiert"), tr("Datei wird gelesen …")) as busy:
            result = threemf_reader.read_file(chosen)
            low, _high = threemf_model.bounding_box(result.parts)
            parts = threemf_model.moved(result.parts, (-low[0], -low[1], -low[2]))  # untere linke Ecke am Cursor
            palette = threemf_allplan.palette()
            colours = [self._allplan_colour(part, palette) for part in parts]
            busy.step(tr("Vorschau wird vorbereitet …"))
            # Vorschau mit schnellen Flaechenkoerpern; die richtigen Koerper entstehen erst am Ablagepunkt.
            previews = [threemf_allplan.preview_element(part, colour) for part, colour in zip(parts, colours)]
        self._import_elements = [element for element in previews if element is not None]
        self._import = (parts, colours, palette, result)
        LOG.info("gelesen: %s (%s Koerper, %s Hilfskoerper uebergangen, %s bemalt, von %s)", chosen, len(parts),
                 result.skipped_helpers, result.painted_parts, result.application or "?")
        self._pending = ("place",)
        self.point_result = PointInteractorResult()
        interactor = PointInteractor(self.point_result, True, tr("Ablagepunkt für die importierten Körper anklicken"),
                                     self._draw_import_preview)
        self.script_object_interactor = interactor
        interactor.start_input(self.coord_input)

    def _placement_matrix(self) -> AllplanGeo.Matrix3D:
        point = self.point_result.input_point
        matrix = AllplanGeo.Matrix3D()
        matrix.SetTranslation(AllplanGeo.Vector3D(point.X, point.Y, point.Z))
        return matrix

    def _draw_import_preview(self) -> None:
        """Die Koerper haengen am Cursor, bis geklickt wird."""
        if self._import_elements:
            AllplanBaseEle.DrawElementPreview(self.document, self._placement_matrix(), self._import_elements,
                                              True, None)

    @staticmethod
    def _allplan_colour(part, palette: dict) -> int:
        """Die Allplan-Farbe, die der Filamentfarbe am naechsten kommt; ohne Farbe in der Datei feste Farben."""
        rgb = threemf_model.hex_rgb(part.colour)
        if rgb is None or not palette:
            return IMPORT_COLOURS.get(part.filament, 1)
        return threemf_model.nearest_colour(rgb, palette)

    def _place_import(self) -> None:
        self._import_elements = []
        imported, self._import = self._import, None
        if imported is None:
            return
        parts, colours, palette, result = imported
        point = self.point_result.input_point
        # Am Ablagepunkt bauen, nicht per Matrix verschieben: so verschoben speicherte Allplan ein Puzzleteil bei 6,4 m
        # um 0,9 % falsch, am Ablagepunkt gebaut exakt (live 2026-11-07).
        placed = threemf_model.moved(parts, (point.X, point.Y, point.Z))
        elements, pieces, faces_only = [], [], 0
        with self._busy(tr("3MF wird importiert")) as busy:
            for number, (part, colour) in enumerate(zip(placed, colours), start=1):
                busy.step(tr("Körper {part} von {parts} wird gebaut …", part=number, parts=len(placed)))

                def on_piece(piece: int, total: int, number=number) -> None:
                    busy.step(tr("Körper {part} von {parts} wird gebaut (Stück {piece} von {pieces}) …",
                                 part=number, parts=len(placed), piece=piece, pieces=total))

                made, faces = threemf_allplan.model_elements(part, colour, on_piece)
                faces_only += int(faces)
                for element, piece in made:
                    elements.append(element)
                    pieces.append((piece, colour))
            busy.step(tr("Allplan legt die Körper ab …"))
            created = list(AllplanBaseEle.CreateElements(self.document, AllplanGeo.Matrix3D(), elements, [], None))
        LOG.info("abgelegt: %s Koerper -> %s Allplan-Koerper (%s nur Flaechen), %s Bauteile entstanden",
                 len(parts), len(elements), faces_only, len(created))
        self._adopt_import(created, (pieces, palette, result, faces_only))

    def _adopt_import(self, created: list, imported: tuple) -> None:
        """Die abgelegten Koerper gleich ihrem Filament zuordnen - "3MF schreiben" ergibt dann wieder dieselbe Datei."""
        pieces, palette, result, faces_only = imported
        notes = []
        if result.painted_parts:
            notes.append(tr("{count} Körper sind in der Datei bemalt (Farbe auf der Oberfläche). Ein Allplan-Körper hat "
                            "genau eine Farbe – die Bemalung kommt nicht mit, der Körper schon.",
                            count=result.painted_parts))
        if faces_only:
            notes.append(tr("{count} Körper kamen nur als Flächenkörper an: ihr Netz ist in der Datei nicht geschlossen "
                            "oder für einen Allplan-Körper zu groß. Sie sehen gleich aus und lassen sich wieder "
                            "schreiben.", count=faces_only))
        if notes:
            self._tell("\n\n".join(notes))
        if len(created) != len(pieces):
            LOG.warning("Zuordnung nach dem Import uebersprungen: %s Bauteile fuer %s Koerper", len(created), len(pieces))
            return
        for element, (piece, colour) in zip(created, pieces):
            if piece is None:
                continue                            # Teilstueck eines Flaechenkoerpers - zeigt nur, das erste traegt
            part = piece
            key = str(element.GetElementUUID())
            self.adapters[key] = element
            rgb = threemf_model.hex_rgb(part.colour) or palette.get(colour, (0, 0, 0))
            self.session.assign(part.filament, [threemf_session.Body(key, part.name, colour, rgb, part)])
        if result.application.startswith(threemf_writer.APPLICATION):
            self.session.names.update(threemf_session.names_from_parts(result.parts))
        LOG.info("nach dem Import zugeordnet: %s", {n: self.session.count(n)
                                                    for n in range(1, threemf_model.MAX_FILAMENTS + 1)
                                                    if self.session.count(n)})

    # ------------------------------------------------------------------ Anzeige

    def _view(self) -> dict:
        view = self.session.view(self._armed)
        view["slicer_label"] = threemf_slicer.program_label(self.settings["slicer"])
        view["slicer_tip"] = threemf_slicer.open_tip(self.session.last_file, self.settings["slicer"])
        view["printers"] = [printer.name for printer in self._printers()]
        view["printer_sizes"] = [[printer.width, printer.depth, printer.height] for printer in self._printers()]
        view["volume_note"] = self._volume_note()
        view["printer"] = self.settings["drucker"]
        view["volume"] = self.settings["bauraum"]
        view["custom_size"] = self.settings["eigene_masse"]
        view["universal"] = bool(self.settings["universell"])
        view["file_kind"] = self._file_kind()
        return view

    def _file_kind(self) -> str:
        """Eine Zeile fuer das Zahnrad: was "3MF schreiben" gerade ablegen wuerde."""
        if self.settings["universell"]:
            return tr("Datei: universelle 3MF – ohne Farben und Sorten für Bambu Studio")
        program = threemf_slicer.slicer_program(self.settings["slicer"])
        if not threemf_bambu.is_bambu(program):
            return tr("Datei: universelle 3MF – Bambu Studio ist nicht der Slicer")
        machine = threemf_bambu.current_machine(program)
        if machine:
            return tr("Datei: Bambu-Projekt für {printer} (aus Bambu Studio)", printer=machine)
        return tr("Datei: Bambu-Projekt, Drucker offen – in Bambu Studio ist keiner eingestellt")

    def _refresh(self) -> None:
        if self._window is not None:
            try:
                self._window.update(self._view())
            except Exception:
                LOG.exception("Fenster liess sich nicht auffrischen")

    def _tell(self, text: str) -> None:
        LOG.info("Meldung: %s", text)
        if self._window is not None:
            self._window.show_message(text)

    # ------------------------------------------------------------------ Test-Loop

    def _headless_result(self) -> CreateElementResult:
        """Ohne Maus und Dialoge: drei Wuerfel durch Zuordnung, Schreiber, Leser und BRep-Bau schicken.

        Das Ergebnis geht als Elemente an den Test-Loop, damit sein Schnappschuss den ganzen Weg belegt.
        """
        if self._headless_elements is None:
            session = threemf_session.Session(names={1: tr("Grundkörper"), 2: "Text", 3: tr("Sockel")})
            for filament in (1, 2, 3):
                session.assign(filament, [threemf_session.Body(
                    f"headless-{filament}", tr("Würfel {number}", number=filament), filament, (0, 0, 0),
                    _headless_cube((filament - 1) * 1.5 * HEADLESS_EDGE_MM))])
            target = os.path.join(tempfile.gettempdir(), "3MFStudio_headless.3mf")
            threemf_writer.write_3mf(target, session.parts())
            parts = threemf_reader.read_3mf(target)
            LOG.info("Head-less: %s Teile geschrieben und gelesen (%s)", len(parts), target)
            elements = ModelEleList()
            for part in parts:
                elements.append(threemf_allplan.model_element(part, IMPORT_COLOURS.get(part.filament, 1)))
            self._headless_elements = elements
        return CreateElementResult(elements=self._headless_elements, placement_point=AllplanGeo.Point3D(0.0, 0.0, 0.0))


def _headless_cube(x0: float):
    """Ein Wuerfel als Teil (ohne Typangabe: `threemf_model` wird oben neu geladen, das vertraegt kein Typausdruck)."""
    edge = HEADLESS_EDGE_MM
    vertices = tuple((x0 + x * edge, y * edge, z * edge) for x, y, z in
                     ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)))
    triangles = ((0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
                 (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7))
    return threemf_model.Part(tr("Würfel"), 1, vertices, triangles)
