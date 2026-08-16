from __future__ import annotations

from dataclasses import dataclass


Color = tuple[int, int, int]


@dataclass(frozen=True)
class TabTheme:
    key: str
    label: str
    text_start: Color
    text_end: Color
    background_start: Color
    background_end: Color
    accent: Color


TAB_THEMES: dict[str, TabTheme] = {
    'red': TabTheme(
        key='red',
        label='Red',
        text_start=(34, 7, 12),
        text_end=(255, 224, 228),
        background_start=(170, 92, 103),
        background_end=(32, 8, 14),
        accent=(205, 92, 106),
    ),
    'green': TabTheme(
        key='green',
        label='Green',
        text_start=(5, 28, 19),
        text_end=(219, 249, 234),
        background_start=(91, 154, 124),
        background_end=(6, 30, 21),
        accent=(91, 170, 128),
    ),
    'blue': TabTheme(
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
DEFAULT_TAB_THEME = 'red'


def normalize_theme_name(value: str | None) -> str:
    key = str(value or '').strip().lower()
    return key if key in TAB_THEMES else DEFAULT_TAB_THEME


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


def tab_theme_colors(theme_name: str, count: int) -> list[tuple[Color, Color]]:
    """Return (text, background) pairs.

    Text becomes lighter from tab 0 to N while the background intentionally
    travels in the opposite direction, improving per-tab contrast.
    """
    theme = TAB_THEMES[normalize_theme_name(theme_name)]
    text = _interpolate(theme.text_start, theme.text_end, count)
    background = _interpolate(theme.background_start, theme.background_end, count)
    return list(zip(text, background))


def next_theme_name(current: str) -> str:
    normalized = normalize_theme_name(current)
    index = THEME_ORDER.index(normalized)
    return THEME_ORDER[(index + 1) % len(THEME_ORDER)]


def theme_button_stylesheet(theme_name: str) -> str:
    theme = TAB_THEMES[normalize_theme_name(theme_name)]
    r, g, b = theme.accent
    return (
        'QToolButton { '
        f'background: rgb({max(0, r - 55)}, {max(0, g - 55)}, {max(0, b - 55)}); '
        'color: #f7f8fa; border: 1px solid rgba(255,255,255,70); '
        'padding: 4px 9px; border-radius: 4px; font-weight: 600; } '
        'QToolButton:hover { border: 1px solid rgba(255,255,255,150); }'
    )


STATUS_BAR_STYLESHEET = (
    'QStatusBar { color: #ffffff; background: #171a1f; border-top: 1px solid #353b44; } '
    'QStatusBar QLabel { color: #ffffff; }'
)
