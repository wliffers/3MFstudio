"""Das schwebende Fenster von 3MFStudio - WPF im Allplan-Prozess (pythonnet), Entwurf B mit Leiste.

Das Fenster IST die Bedienung (Auswahl und Einstellungen); die Allplan-Palette zeigt nur eine Info-Zeile. Es lebt,
solange das Werkzeug laeuft; das Kreuz beendet 3MFStudio (ESC an Allplans Hauptfenster, `end_tool_soon`, Muster
AI ModelLink `_selbst_beenden`). Lage und Zuordnung haengen an einem eigenen Eintrag in sys.modules (`HOLDER`)
und ueberleben Werkzeugende und Neuladen, solange Allplan laeuft. Technik und Fallen:
docs/wpf-dauerfenster-in-allplan.md; die Beschreibung der Oberflaeche steht als XAML-Text unten (in Allplan 2027
geprueft am 2026-11-06, .NET Framework 4.8).

Hier steckt KEINE Fachlogik und kein Allplan-Aufruf: das Fenster zeigt, was `update()` bekommt, und reicht jeden
Klick als `controller.window_action(name, ...)` weiter. Namen der Aktionen:
    pick(n)  clear(n)  rename(n, text)  scale(on)  reduction(wert)  export()  slicer()  import()  closed()
    slicer_choose()  slicer_reset()       (Einstellungen hinter dem Zahnrad)
    colour_open(n)  swap(a, b)            (Farbkachel antippen, Tauschen ⇅)
    plate(drucker, bauraum, breite, tiefe, hoehe)   (Druckplatte im Zahnrad-Menü; drucker "" = eigene Maße)
    choose(n, hersteller, sorte, farbe)  choose_mine(n, index)  choose_own(n, text, hersteller, sorte)  choose_auto(n)
Die Farbauswahl zeigt die Liste, die `open_colours` bekommt (threemf_filaments.Catalogue).

Alle Ereignisse laufen auf Allplans Bedienungs-Thread. Eine Python-Ausnahme, die nach .NET durchschlaegt,
kann Allplan mitreissen - deshalb laeuft jeder Rueckruf durch `_guard`.

`clr` und `System.*` werden erst beim Bauen geladen: der kopflose Test-Loop und die Tests importieren dieses
Modul ohne WPF. Was ohne WPF pruefbar ist (Farben, Texte, Sichtbarkeit), steht in den Funktionen ganz oben.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import traceback
import types

from threemf_filaments import normal_hex  # pyright: ignore[reportMissingImports]
from threemf_text import tr  # pyright: ignore[reportMissingImports]

LOG = logging.getLogger("threemfstudio.part")

HOLDER = "threemfstudio_laufzeit"          # Modulname in sys.modules: ueberlebt Werkzeugende und Neuladen
WINDOW_TITLE = "3MFStudio"
FILAMENTS = tuple(range(1, 17))            # wie threemf_model.MAX_FILAMENTS (Bambu-Projekte bis 16 Filamente)
ALWAYS_SHOWN = 3                           # Filament 1-3 stehen immer da, weitere bei Bedarf
CARD_LIST_MAX_HEIGHT = 420                 # danach Bildlauf - etwa sechs Karten
SCALE_PRESETS = (2, 10, 50, 100)
DEFAULT_LINE = "PLA Basic"                 # vorgewaehlte Sorte, wenn das Filament noch keine eigene Farbe hat
BOTTOM_ROW_HEIGHT = 96                     # untere Knopfreihe: links Schreiben + Importieren, rechts der Slicer
SLICER_BUTTON_WIDTH = 128
END_TOOL_MS = 400.0                        # Vorgabe fuer `end_tool_soon` (AI ModelLink: 400 ms)
_WPF_SUFFIX = ", Version=4.0.0.0, Culture=neutral, PublicKeyToken=31bf3856ad364e35"
_WM_KEYDOWN, _WM_KEYUP, _VK_ESCAPE = 0x0100, 0x0101, 0x1B

# Farben des Entwurfs B (helle Fassung)
CARD, CARD_ARMED = "#FFFFFF", "#EAF1FE"
LINE, LINE_ARMED = "#DDE3EC", "#2563EB"
SWATCH_RING, SUB = "#C4CBD8", "#566074"


# ---------------------------------------------------------------------------------------------- ohne WPF pruefbar

def hex_colour(rgb) -> str:
    """(255, 0, 0) -> "#FF0000"; Werte ausserhalb 0..255 werden begrenzt."""
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(value))) for value in rgb[:3])


def swatch_colours(colours: list) -> list[str]:
    """Die hoechstens zwei Farben des Farbfelds eines Filaments, haeufigste zuerst; leer = noch kein Koerper."""
    return [hex_colour(rgb) for rgb in colours[:2]]


def card_visible(entry: dict, shown_upto: int) -> bool:
    """Filament 1 bis `shown_upto` stehen da; weitere erst, wenn sie Koerper, einen Namen haben oder in Auswahl sind."""
    return (entry["number"] <= max(ALWAYS_SHOWN, shown_upto) or entry["count"] > 0
            or bool(entry["name"].strip()) or entry["armed"])


def next_hidden(filaments: list, shown_upto: int) -> int:
    """Die Nummer, die "＋ Filament hinzufügen" als naechste aufklappt; 0, wenn alle schon zu sehen sind."""
    return next((entry["number"] for entry in filaments if not card_visible(entry, shown_upto)), 0)


def sub_line(entry: dict) -> str:
    return entry["summary"] + (tr(" · läuft") if entry["armed"] else "")     # kurz: die Zeile ist schmal


def line_label(name: str, material: str) -> str:
    """Eintrag der Sortenliste: "PLA Basic"; steckt das Material nicht im Namen, in Klammern dahinter."""
    return name if not material or material.casefold() in name.casefold() else f"{name} ({material})"


def mine_label(choice) -> str:
    """Name einer eigenen Farbe beim Darueberfahren: "PLA Basic · #00AE42" bzw. nur der Farbwert."""
    return " · ".join(part for part in (choice.line, choice.hex) if part)


def bar_label(entry: dict) -> str:
    return "%s  %s" % (entry["shown"], entry["count"])


def scale_label(reduction: float) -> str:
    return "1:%g" % reduction



# ---------------------------------------------------------------------------------------------- Laufzeit

class Runtime:
    """Nur Daten - Methoden blieben beim Neuladen des Skripts auf altem Code stehen."""

    def __init__(self):
        self.window: object | None = None      # das offene StudioWindow oder None
        self.session: object | None = None     # die Zuordnung Koerper -> Filament; ueberlebt Werkzeugstarts
        self.adapters: dict = {}               # Kennung -> Bauteil in Allplan, fuer die Markierung
        self.timers: list = []                 # laufende Zeitgeber (festhalten, sonst raeumt sie der GC)
        self.position: tuple[float, float] | None = None   # (links, oben) in WPF-Einheiten, sobald es einmal stand
        self.collapsed = False                 # zur Leiste verkleinert
        self.shown_upto = ALWAYS_SHOWN         # Karten bis zu dieser Nummer ausdruecklich aufgeklappt
        self.catalogue: object | None = None   # Farbliste (threemf_filaments.Catalogue), einmal je Allplan-Sitzung
        self.palette: dict = {}                # Allplans Farbtabelle, fuer das Umfaerben
        self.printers: list = []               # Druckerliste (threemf_printers.Printer), einmal je Allplan-Sitzung


def runtime() -> Runtime:
    """Der Laufzeit-Halter. Stammt er aus einer aelteren Fassung, bekommt er die neuen Felder nachgetragen."""
    module = sys.modules.setdefault(HOLDER, types.ModuleType(HOLDER))
    state = getattr(module, "runtime", None)
    if state is None:
        state = module.runtime = Runtime()     # type: ignore[attr-defined]
    for name, value in vars(Runtime()).items():
        if not hasattr(state, name):
            setattr(state, name, value)
    return state                               # type: ignore[return-value]


def open_window(controller, view: dict) -> "StudioWindow":
    """Zeigt das Fenster fuer diese Steuerung; ein noch offenes altes wird ersetzt (Lage und Zuordnung bleiben)."""
    state = runtime()
    close_window()
    window = StudioWindow(controller, state)
    window.update(view)
    state.window = window
    window.show()
    return window


def close_window() -> None:
    """Schliesst das offene Fenster, ohne dass sein Schliessen noch bei der alten Steuerung ankommt."""
    state = runtime()
    window, state.window = state.window, None
    if window is None:
        return
    try:
        window.detach()                        # type: ignore[attr-defined]
        window.close()                         # type: ignore[attr-defined]
    except Exception:                          # pylint: disable=broad-except
        LOG.error("Altes Fenster liess sich nicht schliessen:\n%s", traceback.format_exc())


def later(delay_ms: float, action) -> None:
    """Fuehrt `action` nach `delay_ms` auf Allplans Bedienungs-Thread aus - nach dem laufenden Ereignis."""
    _wpf()
    from System import TimeSpan                                         # type: ignore  # pylint: disable=import-outside-toplevel
    from System.Windows.Threading import DispatcherTimer                # type: ignore  # pylint: disable=import-outside-toplevel
    state = runtime()
    timer = DispatcherTimer()
    timer.Interval = TimeSpan.FromMilliseconds(max(1.0, float(delay_ms)))

    def tick(_sender, _args) -> None:
        timer.Stop()
        state.timers[:] = [entry for entry in state.timers if entry[0] is not timer]
        try:
            action()
        except Exception:                                               # pylint: disable=broad-except
            LOG.error("Zeitgeber-Aufgabe gescheitert:\n%s", traceback.format_exc())

    timer.Tick += tick
    state.timers.append((timer, tick))
    timer.Start()


def end_tool_soon(delay_ms: float = END_TOOL_MS) -> None:
    """Beendet das laufende PythonPart selbst: ESC an Allplans Hauptfenster nach `delay_ms`.

    Muster AI ModelLink `_selbst_beenden` (gemessen 2026-10-31: das Werkzeug endet in 0,6-1,3 s). Der Zeitgeber
    wartet, bis der Rahmen mit dem laufenden Ereignis fertig ist.
    """
    _wpf()
    from System.Diagnostics import Process                              # type: ignore  # pylint: disable=import-outside-toplevel
    hwnd = int(Process.GetCurrentProcess().MainWindowHandle.ToInt64())

    def escape() -> None:
        post = ctypes.windll.user32.PostMessageW                        # type: ignore[attr-defined]
        post.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        if not (post(hwnd, _WM_KEYDOWN, _VK_ESCAPE, 0x00010001) and post(hwnd, _WM_KEYUP, _VK_ESCAPE, 0xC0010001)):
            LOG.warning("Selbstende per ESC nicht angenommen - Werkzeug mit ESC schliessen")

    later(delay_ms, escape)


# ---------------------------------------------------------------------------------------------- XAML

def _button_template(radius: int) -> str:
    return f"""
<Setter Property="Template"><Setter.Value><ControlTemplate TargetType="Button">
<Border x:Name="bd" CornerRadius="{radius}" Background="{{TemplateBinding Background}}" BorderBrush="{{TemplateBinding BorderBrush}}" BorderThickness="{{TemplateBinding BorderThickness}}" Padding="{{TemplateBinding Padding}}" SnapsToDevicePixels="True">
<ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center" RecognizesAccessKey="False"/>
</Border>
<ControlTemplate.Triggers>
<Trigger Property="IsMouseOver" Value="True"><Setter TargetName="bd" Property="Opacity" Value="0.82"/></Trigger>
<Trigger Property="IsPressed" Value="True"><Setter TargetName="bd" Property="Opacity" Value="0.66"/></Trigger>
<Trigger Property="IsKeyboardFocused" Value="True"><Setter TargetName="bd" Property="BorderBrush" Value="#1B2333"/></Trigger>
</ControlTemplate.Triggers>
</ControlTemplate></Setter.Value></Setter>"""


def _style(key: str, radius: int, background: str, border: str, foreground: str, disabled: bool = False) -> str:
    off = ("""<Style.Triggers><Trigger Property="IsEnabled" Value="False">
<Setter Property="Background" Value="#D5DBE6"/><Setter Property="BorderBrush" Value="#D5DBE6"/><Setter Property="Foreground" Value="#4A5366"/>
</Trigger></Style.Triggers>""" if disabled else "")
    return f"""
<Style x:Key="{key}" TargetType="Button">
<Setter Property="Background" Value="{background}"/><Setter Property="BorderBrush" Value="{border}"/>
<Setter Property="Foreground" Value="{foreground}"/><Setter Property="BorderThickness" Value="1"/>
<Setter Property="FontWeight" Value="SemiBold"/><Setter Property="Cursor" Value="Hand"/>
<Setter Property="FocusVisualStyle" Value="{{x:Null}}"/>{_button_template(radius)}{off}
</Style>"""


def _card(number: int) -> str:
    return f"""
<Border x:Name="Card{number}" Margin="0,0,0,8" Padding="10,8,4,8" CornerRadius="12" Background="{CARD}" BorderBrush="{LINE}" BorderThickness="1.5">
<DockPanel LastChildFill="True">
<Border DockPanel.Dock="Left" Width="26" Height="26" CornerRadius="13" Background="#FFFFFF" BorderBrush="#1B2333" BorderThickness="1" VerticalAlignment="Center">
<TextBlock Text="{number}" FontWeight="Bold" HorizontalAlignment="Center" VerticalAlignment="Center"/>
</Border>
<Button x:Name="ChipButton{number}" DockPanel.Dock="Left" Style="{{StaticResource Ghost}}" Margin="4,0,4,0" Padding="4,2,4,2" VerticalAlignment="Center" ToolTip="{T('Farbe und Sorte wählen')}" AutomationProperties.Name="{T('Farbe für Filament {number} wählen', number=number)}">
<Rectangle x:Name="Chip{number}" Width="18" Height="34" RadiusX="5" RadiusY="5" Stroke="{SWATCH_RING}" StrokeThickness="1" StrokeDashArray="3 2" Fill="Transparent"/>
</Button>
<Button x:Name="Clear{number}" DockPanel.Dock="Right" Style="{{StaticResource Ghost}}" Width="30" Height="40" Content="✕" ToolTip="{T('Filament {number} leeren', number=number)}" AutomationProperties.Name="{T('Filament {number} leeren', number=number)}"/>
<Button x:Name="Swap{number}" DockPanel.Dock="Right" Style="{{StaticResource Ghost}}" Width="30" Height="40" Content="⇅" FontSize="16" ToolTip="{T('Körper mit einem anderen Filament tauschen')}" AutomationProperties.Name="{T('Filament {number} tauschen', number=number)}"/>
<Button x:Name="Pick{number}" DockPanel.Dock="Right" Style="{{StaticResource Soft}}" Height="40" Width="90" Content="{T('Auswählen')}" AutomationProperties.Name="{T('Körper für Filament {number} auswählen', number=number)}"/>
<StackPanel VerticalAlignment="Center" Margin="0,0,8,0">
<Grid>
<TextBox x:Name="Name{number}" Height="26" Padding="3,2,3,2" BorderBrush="{LINE}" BorderThickness="1" Background="Transparent" Foreground="#1B2333" FontWeight="SemiBold" VerticalContentAlignment="Center" MaxLength="40" ToolTip="{T('Name des Filaments – kommt in Bambu Studio an')}" AutomationProperties.Name="{T('Name von Filament {number}', number=number)}"/>
<TextBlock x:Name="Hint{number}" Text="{T('Filament {number}', number=number)}" Margin="8,0,0,0" VerticalAlignment="Center" Foreground="#8A93A6" IsHitTestVisible="False"/>
</Grid>
<TextBlock x:Name="Sub{number}" Margin="7,1,0,0" FontSize="12" Foreground="{SUB}" TextTrimming="CharacterEllipsis" Text="{T('leer')}"/>
</StackPanel>
</DockPanel>
</Border>"""


def _bar_chip(number: int) -> str:
    return f"""
<Button x:Name="BarPick{number}" Style="{{StaticResource Pill}}" Height="40" Padding="7,0,12,0" Margin="0,0,6,0" AutomationProperties.Name="{T('Körper für Filament {number} auswählen', number=number)}">
<StackPanel Orientation="Horizontal">
<Border Width="24" Height="24" CornerRadius="12" Background="#FFFFFF" BorderBrush="#1B2333" BorderThickness="1" VerticalAlignment="Center">
<TextBlock Text="{number}" FontWeight="Bold" Foreground="#1B2333" HorizontalAlignment="Center" VerticalAlignment="Center"/>
</Border>
<Rectangle x:Name="BarChip{number}" Width="12" Height="24" Margin="6,0,6,0" RadiusX="4" RadiusY="4" Stroke="{SWATCH_RING}" StrokeThickness="1" StrokeDashArray="3 2" Fill="Transparent" VerticalAlignment="Center"/>
<TextBlock x:Name="BarText{number}" VerticalAlignment="Center" Foreground="#1B2333"/>
</StackPanel>
</Button>"""


_ICON_STROKE = ('Stroke="{Binding Foreground, RelativeSource={RelativeSource AncestorType=Button}}" '
                'StrokeThickness="2" StrokeStartLineCap="Round" StrokeEndLineCap="Round" StrokeLineJoin="Round"')
_PRINTER = "M3,3 H21 M8,3 V6 L10,9 H14 L16,6 V3 M11,9 V11 L12,12 L13,11 V9 M8,15 H16 M6,18 H18 M4,21 H20"
_OUTWARD = "M14,4 H20 V10 M20,4 L12,12 M18,14 V19 Q18,20 17,20 H5 Q4,20 4,19 V7 Q4,6 5,6 H10"


def _slicer_button() -> str:
    """Grosser Knopf "Im Slicer oeffnen" rechts neben Schreiben und Importieren (Entwurf des Anwenders,
    2026-11-07): Drucker oben, Text darunter, Pfeil nach aussen in der Ecke."""
    return f"""
<Button x:Name="Slicer" Grid.Column="2" Style="{{StaticResource Slicer}}" Padding="6" ToolTipService.ShowOnDisabled="True" AutomationProperties.Name="{T('Im Slicer öffnen')}">
<Grid Width="{SLICER_BUTTON_WIDTH - 16}" Height="{BOTTOM_ROW_HEIGHT - 16}"><!-- feste Groesse: die Knopf-Vorlage zentriert ihren Inhalt -->
<Viewbox Width="16" Height="16" HorizontalAlignment="Right" VerticalAlignment="Top"><Canvas Width="24" Height="24"><Path Data="{_OUTWARD}" {_ICON_STROKE}/></Canvas></Viewbox>
<StackPanel HorizontalAlignment="Center" VerticalAlignment="Center">
<Viewbox Width="30" Height="30" HorizontalAlignment="Center"><Canvas Width="24" Height="24"><Path Data="{_PRINTER}" {_ICON_STROKE}/></Canvas></Viewbox>
<TextBlock Text="{T('Im Slicer öffnen')}" Margin="0,8,0,0" FontSize="14" FontWeight="SemiBold" TextAlignment="Center" TextWrapping="Wrap"/>
</StackPanel>
</Grid>
</Button>"""


COLOUR_TILE = 22                           # Kantenlaenge einer Farbkachel
COLOUR_TILES_MAX_HEIGHT = 156              # danach Bildlauf - etwa sechs Reihen


def _colour_panel() -> str:
    """Farbauswahl fuer EIN Filament (Wunsch 2026-11-07): Hersteller, Sorte, Farbkacheln, eigene Farbe."""
    return f"""
<Border x:Name="ColourPanel" Visibility="Collapsed" Margin="12,0,12,10" Padding="12,8,8,12" CornerRadius="12" Background="{CARD}" BorderBrush="{LINE_ARMED}" BorderThickness="1.5">
<StackPanel>
<DockPanel>
<Button x:Name="ColourClose" DockPanel.Dock="Right" Style="{{StaticResource Ghost}}" Width="30" Height="30" Content="✕" ToolTip="{T('Farbauswahl schließen')}" AutomationProperties.Name="{T('Farbauswahl schließen')}"/>
<TextBlock x:Name="ColourTitle" FontWeight="SemiBold" VerticalAlignment="Center"/>
</DockPanel>
<Grid Margin="0,6,4,0">
<Grid.ColumnDefinitions><ColumnDefinition Width="*"/><ColumnDefinition Width="8"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
<StackPanel Grid.Column="0"><TextBlock Text="{T('Hersteller')}" FontSize="12" Foreground="{SUB}"/><ComboBox x:Name="ColourBrand" Height="28" Margin="0,2,0,0" MaxDropDownHeight="320" AutomationProperties.Name="{T('Hersteller')}"/></StackPanel>
<StackPanel Grid.Column="2"><TextBlock Text="{T('Sorte')}" FontSize="12" Foreground="{SUB}"/><ComboBox x:Name="ColourLine" Height="28" Margin="0,2,0,0" MaxDropDownHeight="320" AutomationProperties.Name="{T('Sorte')}"/></StackPanel>
</Grid>
<TextBlock x:Name="ColourMineTitle" Text="{T('Meine Farben')}" Margin="0,8,0,0" FontSize="12" Foreground="{SUB}"/>
<WrapPanel x:Name="ColourMine" Margin="0,2,0,0"/>
<ScrollViewer MaxHeight="{COLOUR_TILES_MAX_HEIGHT}" Margin="0,8,0,0" VerticalScrollBarVisibility="Auto" HorizontalScrollBarVisibility="Disabled">
<WrapPanel x:Name="ColourTiles"/>
</ScrollViewer>
<TextBlock x:Name="ColourHover" Margin="0,4,0,0" FontSize="12" Foreground="{SUB}" TextTrimming="CharacterEllipsis"/>
<DockPanel Margin="0,8,4,0">
<Button x:Name="ColourAuto" DockPanel.Dock="Left" Style="{{StaticResource Soft}}" Height="30" Padding="10,0,10,0" Content="{T('Allplan-Farbe')}" ToolTip="{T('Keine eigene Wahl: das Filament hat die Farbe seiner Körper in Allplan')}"/>
<Button x:Name="ColourOwn" DockPanel.Dock="Right" Style="{{StaticResource Soft}}" Height="30" Padding="10,0,10,0" Content="{T('Eigene Farbe')}" ToolTip="{T('Farbwert links eintippen, Sorte wie oben gewählt')}"/>
<TextBox x:Name="ColourHex" Height="30" Margin="8,0,6,0" Padding="4,0,4,0" VerticalContentAlignment="Center" MaxLength="9" Text="#" BorderBrush="{LINE}" ToolTip="{T('Farbwert als #RRGGBB, z. B. #00AE42')}" AutomationProperties.Name="{T('Eigener Farbwert')}"/>
</DockPanel>
<TextBlock Text="{T('Bildschirmfarbe – das gedruckte Filament kann etwas anders aussehen.')}" Margin="0,6,0,0" FontSize="11" Foreground="{SUB}" TextWrapping="Wrap"/>
</StackPanel>
</Border>"""


def build_xaml() -> str:
    """Die ganze Oberflaeche als XAML-Text: Karte (Entwurf B) und Leiste (Entwurf A) in einem Rahmen."""
    cards = "".join(_card(number) for number in FILAMENTS)
    chips = "".join(_bar_chip(number) for number in FILAMENTS)
    presets = "".join(
        f'<Button x:Name="Scale{value}" Style="{{StaticResource Soft}}" Height="32" MinWidth="56" Margin="0,0,6,0" '
        f'Content="1:{value}" AutomationProperties.Name="{T("Maßstab 1:{value}", value=value)}"/>' for value in SCALE_PRESETS)
    return f"""
<Border xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        x:Name="Shell" Margin="16" CornerRadius="14" Background="#F4F6FA" BorderBrush="#C3CBD9" BorderThickness="1" SnapsToDevicePixels="True"
        TextElement.FontFamily="Segoe UI" TextElement.FontSize="13" TextElement.Foreground="#1B2333">
<Border.Effect><DropShadowEffect BlurRadius="18" ShadowDepth="4" Opacity="0.38" Color="#000000"/></Border.Effect>
<Border.Resources>
{_style("Soft", 10, "#FFFFFF", "#C7D7FB", "#1E40AF")}
{_style("Primary", 10, "#2563EB", "#2563EB", "#FFFFFF", disabled=True)}
{_style("Ghost", 10, "Transparent", "Transparent", SUB)}
{_style("Pill", 20, "#FFFFFF", LINE, "#1B2333")}
{_style("PillArmed", 20, CARD_ARMED, LINE_ARMED, "#1B2333")}
{_style("Slicer", 10, "#FFFFFF", "#AEB7C7", "#1B2333", disabled=True)}
</Border.Resources>
<StackPanel>

<StackPanel x:Name="CardPanel" Width="400">
<DockPanel x:Name="Header" Background="Transparent" Margin="12,8,6,10" Cursor="SizeAll" ToolTip="{T('Hier anfassen und verschieben')}">
<Button x:Name="Close" DockPanel.Dock="Right" Style="{{StaticResource Ghost}}" Width="36" Height="36" VerticalAlignment="Top" Content="✕" ToolTip="{T('3MFStudio schließen')}" AutomationProperties.Name="{T('3MFStudio schließen')}"/>
<Button x:Name="Settings" DockPanel.Dock="Right" Style="{{StaticResource Ghost}}" Width="36" Height="36" VerticalAlignment="Top" Content="⚙" FontSize="16" ToolTip="{T('Einstellungen')}" AutomationProperties.Name="{T('Einstellungen')}"/>
<Button x:Name="Collapse" DockPanel.Dock="Right" Style="{{StaticResource Ghost}}" Width="36" Height="36" VerticalAlignment="Top" Content="—" ToolTip="{T('Zur Leiste verkleinern')}" AutomationProperties.Name="{T('Zur Leiste verkleinern')}"/>
<TextBlock DockPanel.Dock="Left" Text="⋮⋮" Foreground="{SUB}" Width="14" Margin="0,3,6,0" VerticalAlignment="Top"/>
<StackPanel VerticalAlignment="Center">
<TextBlock Text="{T('3MFStudio · Filamente')}" FontSize="14" FontWeight="SemiBold"/>
<TextBlock Margin="0,2,0,0" FontSize="12" Foreground="{SUB}" TextWrapping="Wrap" Text="{T('Farbkachel antippen: Farbe und Sorte wählen')}"/>
</StackPanel>
</DockPanel>

<Border x:Name="SettingsPanel" Visibility="Collapsed" Margin="12,0,12,10" Padding="12,10,12,12" CornerRadius="12" Background="{CARD}" BorderBrush="{LINE}" BorderThickness="1.5">
<StackPanel>
<TextBlock Text="{T('Einstellungen')}" FontWeight="SemiBold"/>
<TextBlock Text="{T('Slicer-Programm')}" Margin="0,8,0,0"/>
<TextBlock x:Name="SlicerName" Margin="0,2,0,0" FontSize="12" Foreground="{SUB}" TextTrimming="CharacterEllipsis"/>
<StackPanel Orientation="Horizontal" Margin="0,8,0,0">
<Button x:Name="SlicerChoose" Style="{{StaticResource Soft}}" Height="34" Padding="12,0,12,0" Margin="0,0,8,0" Content="{T('Programm wählen…')}" ToolTip="{T('Die .exe deines Slicers wählen (Bambu Studio, OrcaSlicer, PrusaSlicer …)')}"/>
<Button x:Name="SlicerReset" Style="{{StaticResource Soft}}" Height="34" Padding="12,0,12,0" Content="{T('Windows-Standard')}" ToolTip="{T('Kein eigenes Programm: Windows öffnet die Datei mit dem Programm, das für 3MF eingestellt ist')}"/>
</StackPanel>
<CheckBox x:Name="UniversalCheck" Margin="0,10,0,0" Content="{T('Universelle 3MF schreiben')}" Foreground="#1B2333" ToolTip="{T('Aus: Ist Bambu Studio der Slicer, wird die Datei gleich das Bambu-Projekt mit Farben, Sorten und dem Drucker aus Bambu Studio. An: neutrale 3MF für jeden Slicer, ohne Bambu-Daten.')}"/>
<TextBlock x:Name="FileKind" Margin="0,4,0,0" FontSize="11" Foreground="{SUB}" TextWrapping="Wrap"/>
<TextBlock Text="{T('Druckplatte')}" Margin="0,14,0,0"/>
<ComboBox x:Name="PlatePrinter" Height="28" Margin="0,4,0,0" MaxDropDownHeight="320" AutomationProperties.Name="{T('Drucker für die Druckplatte')}"/>
<StackPanel x:Name="PlateCustom" Orientation="Horizontal" Margin="0,6,0,0" Visibility="Collapsed">
<TextBlock Text="{T('B')}" VerticalAlignment="Center" Margin="0,0,4,0"/><TextBox x:Name="PlateWidth" Width="56" Height="26" VerticalContentAlignment="Center" AutomationProperties.Name="{T('Breite in mm')}"/>
<TextBlock Text="{T('T')}" VerticalAlignment="Center" Margin="10,0,4,0"/><TextBox x:Name="PlateDepth" Width="56" Height="26" VerticalContentAlignment="Center" AutomationProperties.Name="{T('Tiefe in mm')}"/>
<TextBlock Text="{T('H')}" VerticalAlignment="Center" Margin="10,0,4,0"/><TextBox x:Name="PlateHeight" Width="56" Height="26" VerticalContentAlignment="Center" AutomationProperties.Name="{T('Höhe in mm')}"/>
<TextBlock Text="mm" VerticalAlignment="Center" Margin="6,0,0,0" Foreground="{SUB}"/>
</StackPanel>
<DockPanel Margin="0,8,0,0">
<Button x:Name="PlatePlace" DockPanel.Dock="Right" Style="{{StaticResource Soft}}" Height="34" Padding="12,0,12,0" Content="{T('Druckplatte ablegen')}" ToolTip="{T('Legt die Platte ins Modell: Oberseite auf Z = 0, Mitte auf X = 0 / Y = 0')}"/>
<CheckBox x:Name="PlateVolume" Content="{T('Bauraum als Linien')}" VerticalAlignment="Center" Foreground="#1B2333"/>
</DockPanel>
<TextBlock Text="{T('Oberseite auf Z = 0, Mitte auf X/Y = 0 · kommt nicht in die 3MF-Datei')}" Margin="0,4,0,0" FontSize="11" Foreground="{SUB}" TextWrapping="Wrap"/>
</StackPanel>
</Border>

{_colour_panel()}

<StackPanel Margin="12,0,12,2">
<TextBlock x:Name="SwapHint" Visibility="Collapsed" Margin="4,0,4,8" FontSize="12" Foreground="{LINE_ARMED}" TextWrapping="Wrap"/>
<ScrollViewer x:Name="CardList" MaxHeight="{CARD_LIST_MAX_HEIGHT}" VerticalScrollBarVisibility="Auto" HorizontalScrollBarVisibility="Disabled" Padding="0,0,2,0">
<StackPanel>
{cards}
</StackPanel>
</ScrollViewer>
<Button x:Name="AddMore" Style="{{StaticResource Soft}}" Height="38" Margin="0,0,0,8" Content="{T('＋  Filament hinzufügen')}"/>
</StackPanel>

<StackPanel Margin="14,12,14,0">
<DockPanel>
<CheckBox x:Name="ScaleOn" DockPanel.Dock="Right" Content="{T('Verkleinern')}" VerticalAlignment="Center" Foreground="#1B2333" ToolTip="{T('Aus: Originalgröße in mm')}"/>
<TextBlock Text="{T('Größe')}" FontWeight="SemiBold" VerticalAlignment="Center"/>
</DockPanel>
<StackPanel x:Name="ScaleRow" Orientation="Horizontal" Margin="0,6,0,0" Visibility="Collapsed">
<TextBlock Text="{T('Maßstab')}" VerticalAlignment="Center" Margin="0,0,10,0"/>
{presets}
<TextBlock x:Name="ScaleFree" VerticalAlignment="Center" Foreground="{SUB}" FontSize="12"/>
</StackPanel>
<TextBlock x:Name="SizeText" Margin="0,6,0,0" FontSize="12" Foreground="{SUB}" TextWrapping="Wrap"/>
</StackPanel>

<Grid Margin="12,12,12,14" Height="{BOTTOM_ROW_HEIGHT}">
<Grid.ColumnDefinitions><ColumnDefinition Width="*"/><ColumnDefinition Width="10"/><ColumnDefinition Width="{SLICER_BUTTON_WIDTH}"/></Grid.ColumnDefinitions>
<Grid Grid.Column="0">
<Grid.RowDefinitions><RowDefinition Height="*"/><RowDefinition Height="8"/><RowDefinition Height="*"/></Grid.RowDefinitions>
<Button x:Name="Export" Grid.Row="0" Style="{{StaticResource Primary}}" FontSize="14" FontWeight="Bold" Content="{T('3MF schreiben')}" ToolTip="{T('Schreibt die Druckdatei für den Slicer')}"/>
<Button x:Name="Import" Grid.Row="2" Style="{{StaticResource Soft}}" FontSize="14" Content="{T('3MF importieren')}" ToolTip="{T('Datei wählen, dann die Körper per Mausklick in Allplan absetzen')}"/>
</Grid>
{_slicer_button()}
</Grid>
</StackPanel>

<StackPanel x:Name="BarPanel" Orientation="Horizontal" Background="Transparent" Margin="8,6,6,6" Visibility="Collapsed" Cursor="SizeAll" ToolTip="{T('Hier anfassen und verschieben')}">
<TextBlock Text="⋮⋮" Foreground="{SUB}" VerticalAlignment="Center" Margin="2,0,8,0"/>
{chips}
<TextBlock x:Name="BarScale" VerticalAlignment="Center" Foreground="{SUB}" Margin="4,0,10,0"/>
<Button x:Name="BarExport" Style="{{StaticResource Primary}}" Height="40" Padding="16,0,16,0" FontWeight="Bold" Content="3MF" ToolTip="{T('3MF schreiben')}" AutomationProperties.Name="{T('3MF schreiben')}"/>
<Button x:Name="Expand" Style="{{StaticResource Ghost}}" Width="36" Height="40" Content="▾" ToolTip="{T('Fenster aufklappen')}" AutomationProperties.Name="{T('Fenster aufklappen')}"/>
</StackPanel>

</StackPanel>
</Border>"""


# ---------------------------------------------------------------------------------------------- Ladefenster

BUSY_DELAY_S = 3                           # erst nach so vielen Sekunden Arbeit erscheint das Ladefenster


def busy_xaml(title: str, text: str) -> str:
    """Kleines Ladefenster: drehender Ring, Titel, eine Zeile Fortschritt. Es ist sofort da, aber durchsichtig
    und blendet sich erst nach BUSY_DELAY_S ein - das macht WPF selbst (Storyboard), ohne Python-Rueckruf:
    waehrend Allplan rechnet, laeuft kein Python-Code im Ladefenster."""
    return f"""
<Border xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        x:Name="Shell" Margin="16" Width="330" Padding="18,16,18,16" CornerRadius="14" Background="#F4F6FA" BorderBrush="#C3CBD9" BorderThickness="1"
        Opacity="0" TextElement.FontFamily="Segoe UI" TextElement.FontSize="13" TextElement.Foreground="#1B2333">
<Border.Effect><DropShadowEffect BlurRadius="18" ShadowDepth="4" Opacity="0.38" Color="#000000"/></Border.Effect>
<Border.Triggers><EventTrigger RoutedEvent="FrameworkElement.Loaded"><BeginStoryboard><Storyboard>
<DoubleAnimation Storyboard.TargetProperty="Opacity" From="0" To="1" BeginTime="0:0:{BUSY_DELAY_S}" Duration="0:0:0.25"/>
</Storyboard></BeginStoryboard></EventTrigger></Border.Triggers>
<DockPanel>
<Grid DockPanel.Dock="Left" Width="34" Height="34" Margin="0,0,14,0" VerticalAlignment="Center" RenderTransformOrigin="0.5,0.5">
<Grid.RenderTransform><RotateTransform x:Name="Spin"/></Grid.RenderTransform>
<Grid.Triggers><EventTrigger RoutedEvent="FrameworkElement.Loaded"><BeginStoryboard><Storyboard>
<DoubleAnimation Storyboard.TargetName="Spin" Storyboard.TargetProperty="Angle" From="0" To="360" Duration="0:0:1" RepeatBehavior="Forever"/>
</Storyboard></BeginStoryboard></EventTrigger></Grid.Triggers>
<Ellipse Stroke="#DDE3EC" StrokeThickness="4"/>
<Path Data="M17,2 A15,15 0 0 1 32,17" Stroke="#2563EB" StrokeThickness="4" StrokeStartLineCap="Round" StrokeEndLineCap="Round"/>
</Grid>
<StackPanel VerticalAlignment="Center">
<TextBlock Text="{_xml(title)}" FontWeight="SemiBold" FontSize="14"/>
<TextBlock x:Name="Detail" Margin="0,3,0,0" Foreground="{SUB}" TextWrapping="Wrap" Text="{_xml(text)}"/>
</StackPanel>
</DockPanel>
</Border>"""


def _xml(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def T(message: str, /, **values) -> str:                 # pylint: disable=invalid-name
    """Uebersetzter Text, fertig fuer ein XAML-Attribut."""
    return _xml(tr(message, **values))


class Busy:
    """Ladefenster fuer lange Schritte (Import: glatte Koerper brauchen einige Sekunden je Teil).

    Laeuft in einem eigenen WPF-Faden mit eigenem Dispatcher: Allplans Bedienungs-Thread ist waehrend der Arbeit
    belegt und koennte nichts zeichnen. `step` setzt die Fortschrittszeile, `close` beendet den Faden. Ohne WPF
    (Test-Loop, Tests) tut die Klasse nichts. Benutzung: `with Busy(titel, text, aktiv) as busy: busy.step(...)`.
    """

    def __init__(self, title: str, text: str = "", enabled: bool = True):
        self.title, self.text, self.enabled = title, text, enabled
        self._dispatcher = None
        self._detail = None
        self._closed = False

    def __enter__(self) -> "Busy":
        if self.enabled:
            try:
                self._start()
            except Exception:                                   # pylint: disable=broad-except
                LOG.error("Ladefenster liess sich nicht starten:\n%s", traceback.format_exc())
                self.enabled = False
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def _start(self) -> None:
        """Startet den Faden und kehrt sofort zurueck - die Arbeit wartet nicht auf das Fenster."""
        _wpf()
        from System.Diagnostics import Process                              # type: ignore  # pylint: disable=import-outside-toplevel
        from System.Threading import ApartmentState, Thread, ThreadStart    # type: ignore  # pylint: disable=import-outside-toplevel
        owner = Process.GetCurrentProcess().MainWindowHandle
        thread = Thread(ThreadStart(lambda: self._run(owner)))
        thread.SetApartmentState(ApartmentState.STA)
        thread.IsBackground = True
        thread.Start()

    def _run(self, owner) -> None:
        """Im eigenen Faden: Fenster bauen, zeigen, Dispatcher laufen lassen bis `close`.

        Reihenfolge gegen ein sehr fruehes `close`: erst den Dispatcher eintragen, dann `_closed` pruefen. `close`
        setzt erst `_closed` und liest dann den Dispatcher - eins von beiden sieht das andere immer."""
        try:
            from System.Windows import (ResizeMode, SizeToContent, Window,  # type: ignore  # pylint: disable=import-outside-toplevel
                                        WindowStartupLocation, WindowStyle)
            from System.Windows.Interop import WindowInteropHelper          # type: ignore  # pylint: disable=import-outside-toplevel
            from System.Windows.Markup import XamlReader                    # type: ignore  # pylint: disable=import-outside-toplevel
            from System.Windows.Media import Brushes                        # type: ignore  # pylint: disable=import-outside-toplevel
            from System.Windows.Threading import Dispatcher                 # type: ignore  # pylint: disable=import-outside-toplevel
            root = XamlReader.Parse(busy_xaml(self.title, self.text))
            window = Window()
            window.Title = WINDOW_TITLE
            window.WindowStyle = getattr(WindowStyle, "None")
            window.AllowsTransparency = True
            window.Background = Brushes.Transparent
            window.ResizeMode = ResizeMode.NoResize
            window.ShowInTaskbar = False
            window.ShowActivated = False
            window.Topmost = True
            window.SizeToContent = SizeToContent.WidthAndHeight
            window.WindowStartupLocation = WindowStartupLocation.CenterOwner
            window.Content = root
            WindowInteropHelper(window).Owner = owner
            detail = root.FindName("Detail")
            detail.Text = self.text                             # die zuletzt gemeldete Zeile
            self._detail = detail
            self._dispatcher = Dispatcher.CurrentDispatcher
            if self._closed:
                return                                          # Arbeit war schneller fertig als das Fenster
            window.Show()
        except Exception:                                       # pylint: disable=broad-except
            LOG.error("Ladefenster liess sich nicht bauen:\n%s", traceback.format_exc())
            return
        Dispatcher.Run()                                        # gibt Pythons Sperre frei, solange nichts zu tun ist

    def step(self, text: str) -> None:
        """Neue Fortschrittszeile (wird angezeigt, sobald das Fenster eingeblendet ist)."""
        self.text = text
        dispatcher, detail = self._dispatcher, self._detail
        if dispatcher is None or detail is None:
            return
        try:
            from System import Action                           # type: ignore  # pylint: disable=import-outside-toplevel
            dispatcher.BeginInvoke(Action(lambda: setattr(detail, "Text", text)))
        except Exception:                                       # pylint: disable=broad-except
            LOG.info("Ladefenster: Zeile nicht gesetzt (%s)", text)

    def close(self) -> None:
        self._closed = True
        dispatcher, self._dispatcher = self._dispatcher, None
        if dispatcher is None:
            return
        try:
            from System.Windows.Threading import DispatcherPriority  # type: ignore  # pylint: disable=import-outside-toplevel
            dispatcher.BeginInvokeShutdown(DispatcherPriority.Normal)
        except Exception:                                       # pylint: disable=broad-except
            LOG.error("Ladefenster liess sich nicht schliessen:\n%s", traceback.format_exc())


# ---------------------------------------------------------------------------------------------- Fenster

def _wpf() -> None:
    """WPF-Assemblies vollqualifiziert laden - der Kurzname scheitert (docs/wpf-dauerfenster-in-allplan.md 4.1)."""
    import clr                                              # type: ignore  # pylint: disable=import-outside-toplevel
    for name in ("WindowsBase", "PresentationCore", "PresentationFramework"):
        clr.AddReference(name + _WPF_SUFFIX)                # type: ignore


class StudioWindow:
    """Baut das Fenster, zeigt den Stand und reicht Klicks an `controller.window_action` weiter."""

    def __init__(self, controller, state: Runtime):
        _wpf()
        from System.Diagnostics import Process                                  # type: ignore  # pylint: disable=import-outside-toplevel
        from System.Windows import (ResizeMode, SizeToContent, Window,          # type: ignore  # pylint: disable=import-outside-toplevel
                                    WindowStartupLocation, WindowStyle)
        from System.Windows.Interop import WindowInteropHelper                  # type: ignore  # pylint: disable=import-outside-toplevel
        from System.Windows.Markup import XamlReader                            # type: ignore  # pylint: disable=import-outside-toplevel
        from System.Windows.Media import Brushes                                # type: ignore  # pylint: disable=import-outside-toplevel

        self.controller = controller
        self.state = state
        self.closed = False
        self._updating = False
        self._keep: list = []               # Rueckrufe festhalten: ein vom GC geraeumtes Delegate reisst Allplan mit
        self._names: dict[int, str] = {}    # der zuletzt uebernommene Name je Filament
        self._next_hidden = 0               # was "＋ Filament hinzufügen" als naechstes aufklappt
        self._swap_from = 0                 # Filament, dessen ⇅ gedrueckt ist (0 = keins)
        self._colour_for = 0                # Filament, fuer das die Farbauswahl offen ist (0 = zu)
        self._catalogue = None              # threemf_filaments.Catalogue, solange die Farbauswahl offen ist
        self._choice = None                 # die gewaehlte Farbe des Filaments (threemf_session.Choice) oder None
        self._lines: list = []              # Sorten des gewaehlten Herstellers, Reihenfolge wie in der Liste
        self._mine: list = []               # "Meine Farben" (threemf_session.Choice)
        self._printers: list[str] = []      # Druckernamen der Liste "Druckplatte"; danach kommt "Eigene Maße"
        self._tile_keep: list = []          # Rueckrufe der Farbkacheln - beim Neubau der Kacheln freigegeben
        self._mine_keep: list = []

        self.root = XamlReader.Parse(build_xaml())
        window = Window()
        window.Title = WINDOW_TITLE
        window.WindowStyle = getattr(WindowStyle, "None")   # None ist in Python ein Schluesselwort
        window.AllowsTransparency = True
        window.Background = Brushes.Transparent
        window.ResizeMode = ResizeMode.NoResize
        window.ShowInTaskbar = False
        window.ShowActivated = False        # Allplan behaelt den Vordergrund: der naechste Klick gilt dem Modell
        window.SizeToContent = SizeToContent.WidthAndHeight
        window.Content = self.root
        # Allplans Hauptfenster ist kein WPF-Fenster: Besitzer ueber das Handle setzen.
        self._owner = Process.GetCurrentProcess().MainWindowHandle
        WindowInteropHelper(window).Owner = self._owner
        if state.position:
            window.WindowStartupLocation = WindowStartupLocation.Manual
            window.Left, window.Top = float(state.position[0]), float(state.position[1])
        else:
            window.WindowStartupLocation = WindowStartupLocation.CenterOwner
        self.window = window
        self._wire()
        self._apply_collapsed()

    # -- Verdrahtung ---------------------------------------------------------------------------

    def _part(self, name: str):
        part = self.root.FindName(name)
        if part is None:
            raise LookupError("Fensterteil %s fehlt in der Beschreibung" % name)
        return part

    def _guard(self, handler, quiet_ok: bool = False, keep: list | None = None):
        """.NET-Ereignis -> Python, ohne dass eine Ausnahme nach Allplan durchschlaegt."""
        def wrapped(_sender, args):
            if self._updating and not quiet_ok:
                return
            try:
                handler(args)
            except Exception as exc:                        # pylint: disable=broad-except
                LOG.error("Fensterereignis %s gescheitert:\n%s", getattr(handler, "__name__", "?"),
                          traceback.format_exc())
                self.show_message(tr("Das hat nicht geklappt: {error}", error=exc))
        (self._keep if keep is None else keep).append(wrapped)
        return wrapped

    def _send(self, name: str, *values, focus_model: bool = True) -> None:
        if self.controller is not None:
            self.controller.window_action(name, *values)
        if focus_model:
            self.focus_allplan()

    def _click(self, part: str, action) -> None:
        self._part(part).Click += self._guard(lambda _args: action())

    def _wire(self) -> None:
        for number in FILAMENTS:
            self._click(f"Pick{number}", lambda n=number: self._send("pick", n))
            self._click(f"BarPick{number}", lambda n=number: self._send("pick", n))
            self._click(f"Clear{number}", lambda n=number: self._send("clear", n))
            self._click(f"Swap{number}", lambda n=number: self._swap_click(n))
            self._click(f"ChipButton{number}", lambda n=number: self._chip_click(n))
            box = self._part(f"Name{number}")
            box.LostKeyboardFocus += self._guard(lambda _args, n=number: self._commit_name(n))
            box.KeyDown += self._guard(lambda args, n=number: self._name_key(n, args))
            box.TextChanged += self._guard(lambda _args, n=number: self._show_hint(n), quiet_ok=True)
            box.GotKeyboardFocus += self._guard(lambda _args, n=number: self._show_hint(n), quiet_ok=True)
        for value in SCALE_PRESETS:
            self._click(f"Scale{value}", lambda v=value: self._send("reduction", float(v)))
        self._click("AddMore", self._add_more)
        self._click("ScaleOn", lambda: self._send("scale", bool(self._part("ScaleOn").IsChecked)))
        self._click("Export", lambda: self._send("export", focus_model=False))
        self._click("BarExport", lambda: self._send("export", focus_model=False))
        self._click("Slicer", lambda: self._send("slicer", focus_model=False))
        self._click("Settings", self._toggle_settings)
        self._click("SlicerChoose", lambda: self._send("slicer_choose", focus_model=False))
        self._click("SlicerReset", lambda: self._send("slicer_reset", focus_model=False))
        self._click("UniversalCheck", lambda: self._send("universal", bool(self._part("UniversalCheck").IsChecked),
                                                         focus_model=False))
        self._click("PlatePlace", self._place_plate)
        self._part("PlatePrinter").SelectionChanged += self._guard(lambda _args: self._show_plate_custom())
        self._click("Import", lambda: self._send("import"))
        self._click("Collapse", lambda: self._set_collapsed(True))
        self._click("Expand", lambda: self._set_collapsed(False))
        self._click("Close", self.close)
        self._click("ColourClose", self.close_colours)
        self._click("ColourAuto", lambda: self._chosen("choose_auto"))
        self._click("ColourOwn", self._own_colour)
        self._part("ColourHex").KeyDown += self._guard(self._hex_key)
        self._part("ColourBrand").SelectionChanged += self._guard(lambda _args: self._fill_lines())
        self._part("ColourLine").SelectionChanged += self._guard(lambda _args: self._fill_tiles())
        for grip in ("Header", "BarPanel"):
            self._part(grip).MouseLeftButtonDown += self._guard(lambda _args: self._drag())
        self.window.Closed += self._guard(lambda _args: self._on_closed(), quiet_ok=True)

    # -- Ereignisse ----------------------------------------------------------------------------

    def _drag(self) -> None:
        try:
            self.window.DragMove()
        except Exception:                                   # pylint: disable=broad-except
            LOG.info("Verschieben abgebrochen (DragMove ist waehlerisch)")
        self._remember_position()

    def _add_more(self) -> None:
        number = self._next_hidden
        if number:
            self.state.shown_upto = number
            self._send("pick", number)

    def _swap_click(self, number: int) -> None:
        """Erstes ⇅ merkt das Filament, das zweite ⇅ tauscht; dasselbe ⇅ nochmal bricht ab."""
        first, self._swap_from = self._swap_from, 0
        if first == 0:
            self._swap_from = number
        elif first != number:
            self._send("swap", first, number, focus_model=False)
        self._show_swap()

    def _show_swap(self) -> None:
        from System.Windows import Visibility                # type: ignore  # pylint: disable=import-outside-toplevel
        hint = self._part("SwapHint")
        hint.Visibility = Visibility.Visible if self._swap_from else Visibility.Collapsed
        hint.Text = tr("Tauschen: jetzt ⇅ beim anderen Filament drücken (nochmal ⇅ bricht ab).") if self._swap_from else ""
        for number in FILAMENTS:
            self._part(f"Swap{number}").Style = self.root.FindResource("Primary" if number == self._swap_from else "Ghost")

    def _chip_click(self, number: int) -> None:
        if self._colour_for == number:
            self.close_colours()
        else:
            self._send("colour_open", number, focus_model=False)

    def _plate_name(self) -> str:
        """Gewaehlter Drucker; "" = eigene Masse (letzter Eintrag)."""
        index = int(self._part("PlatePrinter").SelectedIndex)
        return self._printers[index] if 0 <= index < len(self._printers) else ""

    def _show_plate_custom(self) -> None:
        from System.Windows import Visibility                # type: ignore  # pylint: disable=import-outside-toplevel
        custom = int(self._part("PlatePrinter").SelectedIndex) == len(self._printers)
        self._part("PlateCustom").Visibility = Visibility.Visible if custom else Visibility.Collapsed

    def _place_plate(self) -> None:
        sizes = [str(self._part(name).Text or "") for name in ("PlateWidth", "PlateDepth", "PlateHeight")]
        self._send("plate", self._plate_name(), bool(self._part("PlateVolume").IsChecked), *sizes)

    def _fill_plate(self, view: dict) -> None:
        """Druckerliste einmal fuellen; danach behaelt die Liste die Wahl des Anwenders."""
        if self._printers or not view.get("printers"):
            return
        self._printers = list(view["printers"])
        combo = self._part("PlatePrinter")
        for name in self._printers + [tr("Eigene Maße")]:
            combo.Items.Add(name)
        chosen = view.get("printer", "")
        combo.SelectedIndex = self._printers.index(chosen) if chosen in self._printers else len(self._printers)
        self._part("PlateVolume").IsChecked = bool(view.get("volume", True))
        for name, value in zip(("PlateWidth", "PlateDepth", "PlateHeight"), view.get("custom_size", [])):
            self._part(name).Text = "%g" % float(value)
        self._show_plate_custom()

    def _toggle_settings(self) -> None:
        from System.Windows import Visibility                # type: ignore  # pylint: disable=import-outside-toplevel
        panel = self._part("SettingsPanel")
        panel.Visibility = Visibility.Collapsed if panel.Visibility == Visibility.Visible else Visibility.Visible

    def _set_collapsed(self, collapsed: bool) -> None:
        self.state.collapsed = collapsed
        self._apply_collapsed()
        self.focus_allplan()

    def _apply_collapsed(self) -> None:
        from System.Windows import Visibility                # type: ignore  # pylint: disable=import-outside-toplevel
        self._part("CardPanel").Visibility = Visibility.Collapsed if self.state.collapsed else Visibility.Visible
        self._part("BarPanel").Visibility = Visibility.Visible if self.state.collapsed else Visibility.Collapsed

    def _commit_name(self, number: int) -> None:
        self._show_hint(number)
        text = str(self._part(f"Name{number}").Text or "")
        if text != self._names.get(number, ""):
            self._names[number] = text
            self._send("rename", number, text, focus_model=False)

    def _name_key(self, number: int, args) -> None:
        from System.Windows.Input import Key                 # type: ignore  # pylint: disable=import-outside-toplevel
        if args.Key == Key.Enter:
            args.Handled = True
            self._commit_name(number)
            self.focus_allplan()
        elif args.Key == Key.Escape:
            args.Handled = True
            self._part(f"Name{number}").Text = self._names.get(number, "")
            self.focus_allplan()

    def _show_hint(self, number: int) -> None:
        """Der graue Platzhalter "Filament n" steht nur da, solange das Feld leer ist und niemand tippt."""
        from System.Windows import Visibility                # type: ignore  # pylint: disable=import-outside-toplevel
        box = self._part(f"Name{number}")
        empty = not str(box.Text or "") and not bool(box.IsKeyboardFocused)
        self._part(f"Hint{number}").Visibility = Visibility.Visible if empty else Visibility.Collapsed

    def _on_closed(self) -> None:
        self.closed = True
        self._remember_position()
        if self.state.window is self:
            self.state.window = None
        controller, self.controller = self.controller, None
        if controller is not None:
            controller.window_action("closed")

    def _remember_position(self) -> None:
        try:
            self.state.position = (float(self.window.Left), float(self.window.Top))
        except Exception:                                   # pylint: disable=broad-except
            LOG.info("Fensterlage nicht lesbar")

    # -- Meldung -------------------------------------------------------------------------------

    def show_message(self, text: str) -> None:
        """Meldung an den Anwender - nur fuer das, was er wissen muss (Fehler)."""
        try:
            from System.Windows import MessageBox             # type: ignore  # pylint: disable=import-outside-toplevel
            MessageBox.Show(self.window, text, WINDOW_TITLE)
        except Exception:                                   # pylint: disable=broad-except
            LOG.error("Meldung liess sich nicht zeigen (%s):\n%s", text, traceback.format_exc())

    # -- Farbauswahl ---------------------------------------------------------------------------

    def open_colours(self, number: int, catalogue, choice, mine: list) -> None:
        """Zeigt die Farbauswahl fuer ein Filament: Liste `catalogue`, aktuelle Wahl `choice`, "Meine Farben"."""
        from System.Windows import Visibility                # type: ignore  # pylint: disable=import-outside-toplevel
        self._colour_for, self._catalogue, self._choice, self._mine = number, catalogue, choice, list(mine)
        self._part("ColourTitle").Text = tr("Farbe für Filament {number}", number=number)
        self._part("ColourHex").Text = choice.hex if choice else "#"
        brands = catalogue.brands()
        brand = choice.brand if choice is not None and choice.brand in brands else (brands[0] if brands else "")
        combo = self._part("ColourBrand")
        self._updating = True
        try:
            combo.Items.Clear()
            for name in brands:
                combo.Items.Add(name)
            combo.SelectedIndex = brands.index(brand) if brand else -1
        finally:
            self._updating = False
        self._fill_lines()
        self._fill_mine()
        self._part("ColourPanel").Visibility = Visibility.Visible

    def close_colours(self) -> None:
        from System.Windows import Visibility                # type: ignore  # pylint: disable=import-outside-toplevel
        self._part("ColourPanel").Visibility = Visibility.Collapsed
        self._part("ColourTiles").Children.Clear()
        self._part("ColourMine").Children.Clear()
        self._colour_for, self._catalogue, self._choice, self._lines = 0, None, None, []
        self._tile_keep, self._mine_keep = [], []

    def _fill_lines(self) -> None:
        """Sorten des gewaehlten Herstellers; vorgewaehlt die Sorte der aktuellen Wahl, sonst PLA Basic."""
        brand = str(self._part("ColourBrand").SelectedItem or "")
        self._lines = self._catalogue.lines(brand) if self._catalogue is not None else []
        choice = self._choice
        names = [line.name for line in self._lines]
        prefer = choice.line if choice is not None and choice.brand == brand else DEFAULT_LINE
        combo = self._part("ColourLine")
        self._updating = True
        try:
            combo.Items.Clear()
            for line in self._lines:
                combo.Items.Add(line_label(line.name, line.material))
            combo.SelectedIndex = names.index(prefer) if prefer in names else (0 if names else -1)
        finally:
            self._updating = False
        self._fill_tiles()

    def _fill_tiles(self) -> None:
        panel = self._part("ColourTiles")
        panel.Children.Clear()
        self._tile_keep = []
        index = int(self._part("ColourLine").SelectedIndex)
        line = self._lines[index] if 0 <= index < len(self._lines) else None
        self._part("ColourHover").Text = (tr("{count} Farben – Name beim Darüberfahren", count=len(line.swatches))
                                          if line is not None else tr("Keine Farben für diesen Hersteller"))
        if line is None:
            return
        choice = self._choice
        for position, swatch in enumerate(line.swatches):
            selected = (choice is not None and choice.brand == line.brand and choice.line == line.name
                        and choice.name == swatch.name)
            panel.Children.Add(self._tile(swatch.name, (swatch.hex,) + tuple(swatch.more), selected,
                                          lambda p=position, l=line: self._chosen("choose", l.brand, l.name, p),
                                          self._tile_keep))

    def _fill_mine(self) -> None:
        from System.Windows import Visibility                # type: ignore  # pylint: disable=import-outside-toplevel
        panel = self._part("ColourMine")
        panel.Children.Clear()
        self._mine_keep = []
        for index, choice in enumerate(self._mine):
            panel.Children.Add(self._tile(mine_label(choice), (choice.hex,), choice == self._choice,
                                          lambda i=index: self._chosen("choose_mine", i), self._mine_keep))
        shown = Visibility.Visible if self._mine else Visibility.Collapsed
        panel.Visibility = shown
        self._part("ColourMineTitle").Visibility = shown

    def _tile(self, name: str, tones: tuple, selected: bool, action, keep: list):
        """Eine Farbkachel; mehrfarbiges Filament als Streifen. Klick waehlt, Darueberfahren nennt den Namen."""
        from System.Windows import CornerRadius, Point, Thickness             # type: ignore  # pylint: disable=import-outside-toplevel
        from System.Windows.Controls import Border                           # type: ignore  # pylint: disable=import-outside-toplevel
        from System.Windows.Input import Cursors                             # type: ignore  # pylint: disable=import-outside-toplevel
        from System.Windows.Media import ColorConverter, GradientStop, LinearGradientBrush   # type: ignore  # pylint: disable=import-outside-toplevel
        tile = Border()
        tile.Width = tile.Height = float(COLOUR_TILE)
        tile.Margin = Thickness(2.0)
        tile.CornerRadius = CornerRadius(5.0)
        if len(tones) == 1:
            tile.Background = self._brush(tones[0])
        else:
            stripes = LinearGradientBrush()
            stripes.StartPoint, stripes.EndPoint = Point(0.0, 0.0), Point(1.0, 0.0)
            for index, tone in enumerate(tones):
                colour = ColorConverter.ConvertFromString(tone)
                stripes.GradientStops.Add(GradientStop(colour, index / len(tones)))
                stripes.GradientStops.Add(GradientStop(colour, (index + 1) / len(tones)))
            tile.Background = stripes
        tile.BorderBrush = self._brush("#1B2333" if selected else SWATCH_RING)
        tile.BorderThickness = Thickness(2.5 if selected else 1.0)
        tile.ToolTip = name
        tile.Cursor = Cursors.Hand
        hover = self._part("ColourHover")
        tile.MouseLeftButtonUp += self._guard(lambda _args: action(), keep=keep)
        tile.MouseEnter += self._guard(lambda _args: setattr(hover, "Text", name), quiet_ok=True, keep=keep)
        return tile

    def _chosen(self, action: str, *values) -> None:
        number = self._colour_for
        self.close_colours()
        if number:
            self._send(action, number, *values, focus_model=False)

    def _own_colour(self) -> None:
        text = str(self._part("ColourHex").Text or "").strip()
        if not normal_hex(text):
            self.show_message(tr("„{text}“ ist kein Farbwert. Bitte so eingeben: #00AE42", text=text))
            return
        index = int(self._part("ColourLine").SelectedIndex)
        line = self._lines[index] if 0 <= index < len(self._lines) else None
        self._chosen("choose_own", text, line.brand if line else "", line.name if line else "")

    def _hex_key(self, args) -> None:
        from System.Windows.Input import Key                 # type: ignore  # pylint: disable=import-outside-toplevel
        if args.Key == Key.Enter:
            args.Handled = True
            self._own_colour()
        elif args.Key == Key.Escape:
            args.Handled = True
            self.close_colours()

    # -- Anzeige -------------------------------------------------------------------------------

    def update(self, view: dict) -> None:
        """Zeigt den Stand der Zuordnung; loest dabei keine Ereignisse aus."""
        if self.closed:
            return
        self._updating = True
        try:
            self._show(view)
        finally:
            self._updating = False

    def _brush(self, colour: str):
        from System.Windows.Media import ColorConverter, SolidColorBrush   # type: ignore  # pylint: disable=import-outside-toplevel
        return SolidColorBrush(ColorConverter.ConvertFromString(colour))

    def _swatch(self, shape, colours: list) -> None:
        from System.Windows import Point                                    # type: ignore  # pylint: disable=import-outside-toplevel
        from System.Windows.Media import (ColorConverter, DoubleCollection,  # type: ignore  # pylint: disable=import-outside-toplevel
                                          GradientStop, LinearGradientBrush)
        tones = swatch_colours(colours)
        if not tones:
            shape.Fill = self._brush("#00FFFFFF")
            dashes = DoubleCollection()
            dashes.Add(3.0)
            dashes.Add(2.0)
            shape.StrokeDashArray = dashes
            return
        shape.StrokeDashArray = DoubleCollection()
        if len(tones) == 1:
            shape.Fill = self._brush(tones[0])
            return
        split = LinearGradientBrush()
        split.StartPoint, split.EndPoint = Point(0.0, 0.0), Point(0.0, 1.0)
        for tone, offset in ((tones[0], 0.0), (tones[0], 0.5), (tones[1], 0.5), (tones[1], 1.0)):
            split.GradientStops.Add(GradientStop(ColorConverter.ConvertFromString(tone), offset))
        shape.Fill = split

    def _show(self, view: dict) -> None:
        from System.Windows import Visibility                # type: ignore  # pylint: disable=import-outside-toplevel
        shown = lambda flag: Visibility.Visible if flag else Visibility.Collapsed
        for entry in view["filaments"]:
            number, armed = entry["number"], entry["armed"]
            visible = card_visible(entry, self.state.shown_upto)
            card = self._part(f"Card{number}")
            card.Visibility = shown(visible)
            card.Background = self._brush(CARD_ARMED if armed else CARD)
            card.BorderBrush = self._brush(LINE_ARMED if armed else LINE)
            self._swatch(self._part(f"Chip{number}"), entry["colours"])
            self._swatch(self._part(f"BarChip{number}"), entry["colours"])
            box = self._part(f"Name{number}")
            if not bool(box.IsKeyboardFocused) and str(box.Text or "") != entry["name"]:
                box.Text = entry["name"]
            if not bool(box.IsKeyboardFocused):
                self._names[number] = entry["name"]
            self._part(f"Hint{number}").Text = entry["hint"]
            self._show_hint(number)
            self._part(f"Sub{number}").Text = sub_line(entry)
            pick = self._part(f"Pick{number}")
            pick.Content = tr("Fertig") if armed else tr("Auswählen")
            pick.Style = self.root.FindResource("Primary" if armed else "Soft")
            bar = self._part(f"BarPick{number}")
            bar.Visibility = shown(visible)
            bar.Style = self.root.FindResource("PillArmed" if armed else "Pill")
            self._part(f"BarText{number}").Text = bar_label(entry)
        self._next_hidden = next_hidden(view["filaments"], self.state.shown_upto)
        add = self._part("AddMore")
        add.Visibility = shown(bool(self._next_hidden))
        add.Content = tr("＋  Filament {number} hinzufügen", number=self._next_hidden)

        self._part("ScaleOn").IsChecked = bool(view["scale_on"])
        self._part("ScaleRow").Visibility = shown(view["scale_on"])
        for value in SCALE_PRESETS:
            chosen = view["scale_on"] and abs(view["reduction"] - value) < 1e-9
            self._part(f"Scale{value}").Style = self.root.FindResource("Primary" if chosen else "Soft")
        preset = any(abs(view["reduction"] - value) < 1e-9 for value in SCALE_PRESETS)
        self._part("ScaleFree").Text = "" if preset else tr("aktuell {scale}", scale=scale_label(view["reduction"]))
        self._part("BarScale").Text = scale_label(view["reduction"]) if view["scale_on"] else tr("Originalgröße")
        self._part("SizeText").Text = view["size"]
        self._part("Export").IsEnabled = bool(view["can_export"])
        self._part("BarExport").IsEnabled = bool(view["can_export"])
        slicer = self._part("Slicer")
        slicer.IsEnabled = bool(view.get("last_file"))
        slicer.ToolTip = view.get("slicer_tip", "")
        self._part("SlicerName").Text = view.get("slicer_label", "")
        universal = self._part("UniversalCheck")
        if bool(universal.IsChecked) != bool(view.get("universal")):
            universal.IsChecked = bool(view.get("universal"))
        self._part("FileKind").Text = view.get("file_kind", "")
        self._fill_plate(view)

    # -- Lebenszyklus --------------------------------------------------------------------------

    def show(self) -> None:
        self.window.Show()
        if not self.state.position:
            self._place_top_right()
        self._remember_position()

    def _place_top_right(self) -> None:
        """Erster Start: oben rechts ueber dem Modell statt mitten darauf."""
        try:
            from System.Windows import Point, PresentationSource             # type: ignore  # pylint: disable=import-outside-toplevel
            rect = (ctypes.c_long * 4)()
            user32 = ctypes.windll.user32                                    # type: ignore[attr-defined]
            user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            if not user32.GetWindowRect(ctypes.c_void_p(self._owner.ToInt64()), ctypes.byref(rect)):
                return
            to_wpf = PresentationSource.FromVisual(self.window).CompositionTarget.TransformFromDevice
            corner = to_wpf.Transform(Point(float(rect[2]), float(rect[1])))
            self.window.Left = corner.X - float(self.window.ActualWidth) - 30.0
            self.window.Top = corner.Y + 190.0
        except Exception:                                   # pylint: disable=broad-except
            LOG.info("Startlage nicht bestimmbar - Fenster bleibt mittig:\n%s", traceback.format_exc())

    def focus_allplan(self) -> None:
        """Gibt die Tastatur an Allplan zurueck: der naechste Klick soll im Modell ankommen."""
        try:
            user32 = ctypes.windll.user32                                    # type: ignore[attr-defined]
            user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
            user32.SetForegroundWindow(ctypes.c_void_p(self._owner.ToInt64()))
        except Exception:                                   # pylint: disable=broad-except
            LOG.info("Fokus liess sich nicht an Allplan zurueckgeben")

    def detach(self) -> None:
        """Loest das Fenster von seiner Steuerung: sein Schliessen kommt dort nicht mehr an."""
        self.controller = None

    def close(self) -> None:
        if not self.closed:
            self.window.Close()
