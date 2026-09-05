from __future__ import annotations

from dataclasses import dataclass


Color = tuple[int, int, int]


@dataclass(frozen=True)
class WorkstationTheme:
    key: str
    label: str
    text_start: Color
    text_end: Color
    background_start: Color
    background_end: Color
    accent: Color


WORKSTATION_THEMES: dict[str, WorkstationTheme] = {
    'red': WorkstationTheme(
        key='red',
        label='Red',
        text_start=(34, 7, 12),
        text_end=(255, 224, 228),
        background_start=(170, 92, 103),
        background_end=(32, 8, 14),
        accent=(205, 92, 106),
    ),
    'green': WorkstationTheme(
        key='green',
        label='Green',
        text_start=(5, 28, 19),
        text_end=(219, 249, 234),
        background_start=(91, 154, 124),
        background_end=(6, 30, 21),
        accent=(91, 170, 128),
    ),
    'blue': WorkstationTheme(
        key='blue',
        label='Blue',
        text_start=(7, 22, 38),
        text_end=(220, 237, 255),
        background_start=(89, 126, 168),
        background_end=(7, 21, 36),
        accent=(93, 142, 196),
    ),
}

THEME_ORDER = ('red', 'green', 'blue')
DEFAULT_WORKSTATION_THEME = 'red'

# Compatibility aliases for older modules/plugins. P1-F application code uses
# the workstation terminology; these aliases avoid needless API breakage.
TabTheme = WorkstationTheme
TAB_THEMES = WORKSTATION_THEMES
DEFAULT_TAB_THEME = DEFAULT_WORKSTATION_THEME


def normalize_theme_name(value: str | None) -> str:
    key = str(value or '').strip().lower()
    return key if key in WORKSTATION_THEMES else DEFAULT_WORKSTATION_THEME


def _interpolate(start: Color, end: Color, count: int) -> list[Color]:
    count = max(0, int(count))
    if count == 0:
        return []
    if count == 1:
        return [tuple(int(v) for v in end)]
    colors: list[Color] = []
    for index in range(count):
        t = index / float(count - 1)
        colors.append(
            tuple(int(round(start[channel] + (end[channel] - start[channel]) * t)) for channel in range(3))
        )
    return colors


def workstation_theme_colors(theme_name: str, count: int) -> list[tuple[Color, Color]]:
    """Return legacy-compatible text/background gradient pairs for the theme."""
    theme = WORKSTATION_THEMES[normalize_theme_name(theme_name)]
    text = _interpolate(theme.text_start, theme.text_end, count)
    background = _interpolate(theme.background_start, theme.background_end, count)
    return list(zip(text, background))


def tab_theme_colors(theme_name: str, count: int) -> list[tuple[Color, Color]]:
    """Compatibility alias for the pre-workstation theme API."""
    return workstation_theme_colors(theme_name, count)


def next_theme_name(current: str) -> str:
    normalized = normalize_theme_name(current)
    index = THEME_ORDER.index(normalized)
    return THEME_ORDER[(index + 1) % len(THEME_ORDER)]


def theme_button_stylesheet(theme_name: str) -> str:
    theme = WORKSTATION_THEMES[normalize_theme_name(theme_name)]
    r, g, b = theme.accent
    return (
        'QToolButton { '
        f'background: rgb({max(0, r - 55)}, {max(0, g - 55)}, {max(0, b - 55)}); '
        'color: #f7f8fa; border: 1px solid rgba(255,255,255,70); '
        'padding: 4px 9px; border-radius: 4px; font-weight: 600; } '
        'QToolButton:hover { border: 1px solid rgba(255,255,255,150); }'
    )


def workstation_theme_stylesheet(theme_name: str) -> str:
    """Style the three-environment workstation navigation with one accent family."""
    theme = WORKSTATION_THEMES[normalize_theme_name(theme_name)]
    r, g, b = theme.accent
    deep = (max(0, r - 150), max(0, g - 150), max(0, b - 150))
    mid = (max(0, r - 95), max(0, g - 95), max(0, b - 95))
    soft = (min(255, r + 20), min(255, g + 20), min(255, b + 20))
    return (
        'QWidget[workstationRole="macroNavigation"] {'
        f' background: rgb({deep[0]}, {deep[1]}, {deep[2]});'
        ' border-bottom: 1px solid #353b44; }'
        'QWidget[workstationRole="subNavigation"] {'
        ' background: #171a1f; border-bottom: 1px solid #353b44; }'
        'QPushButton[workstationRole="macro"] {'
        ' color: #e7ebf1; background: transparent; border: 1px solid transparent;'
        ' padding: 7px 14px; border-radius: 5px; font-weight: 700; }'
        'QPushButton[workstationRole="macro"]:hover {'
        f' background: rgb({mid[0]}, {mid[1]}, {mid[2]}); border-color: rgba(255,255,255,55); }}'
        'QPushButton[workstationRole="macro"]:checked {'
        f' color: #ffffff; background: rgb({r}, {g}, {b}); border-color: rgb({soft[0]}, {soft[1]}, {soft[2]}); }}'
        'QPushButton[workstationRole="route"] {'
        ' color: #cbd2dc; background: #20242a; border: 1px solid #343a43;'
        ' padding: 5px 10px; border-radius: 4px; }'
        'QPushButton[workstationRole="route"]:hover {'
        f' border-color: rgb({r}, {g}, {b}); }}'
        'QPushButton[workstationRole="route"]:checked {'
        f' color: #ffffff; background: rgb({mid[0]}, {mid[1]}, {mid[2]}); border-color: rgb({r}, {g}, {b}); font-weight: 600; }}'
        'QWidget[workstationRole="createContextBar"] {'
        ' background: #1b1f24; border-bottom: 1px solid #353b44; color: #d7dce4; }'
        'QWidget[workstationRole="createToolbar"] {'
        ' background: #171a1f; border-bottom: 1px solid #353b44; }'
        'QFrame[workstationRole="createSidePanel"] {'
        ' background: #1b1f24; border-right: 1px solid #353b44; border-left: 1px solid #353b44; }'
        'QFrame[workstationRole="createProduction"] {'
        ' background: #111419; }'
        'QFrame[workstationRole="createFrameStrip"] {'
        ' background: #171a1f; border-top: 1px solid #353b44; color: #cbd2dc; }'
        'QLabel[workstationRole="createPanelHint"] {'
        ' color: #8f98a5; }'
        'QPushButton[workstationRole="panelToggle"] {'
        ' color: #cbd2dc; background: #20242a; border: 1px solid #343a43; padding: 5px 8px; border-radius: 4px; }'
        'QPushButton[workstationRole="panelToggle"]:checked {'
        f' border-color: rgb({r}, {g}, {b}); color: #ffffff; }}'
    )


STATUS_BAR_STYLESHEET = (
    'QStatusBar { color: #ffffff; background: #171a1f; border-top: 1px solid #353b44; } '
    'QStatusBar QLabel { color: #ffffff; }'
)
