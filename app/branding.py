from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.version import APP_LICENSE, APP_NAME, APP_VERSION, APP_BUILD_LABEL, APP_AUTHOR, APP_DEPENDENCIES
from app.runtime_paths import executable_dir

BRANDING_DIR = Path("assets") / "branding"
ICON_PNG_NAME = "app_icon.png"
ICON_ICO_NAME = "app_icon.ico"
SPLASH_NAME = "splash_screen.png"
INSTALLER_WIZARD_NAME = "installer_wizard.bmp"
INSTALLER_WIZARD_SMALL_NAME = "installer_wizard_small.bmp"


def branding_search_roots() -> list[Path]:
    project_root = Path(__file__).resolve().parents[1]
    roots: list[Path] = []
    for candidate in (executable_dir(), project_root):
        candidate = candidate.resolve()
        if candidate not in roots:
            roots.append(candidate)
    return roots


def resolve_branding_asset(filename: str, *, roots: Iterable[Path] | None = None) -> Path | None:
    search_roots = list(roots) if roots is not None else branding_search_roots()
    for root in search_roots:
        candidate = root / BRANDING_DIR / filename
        if candidate.exists():
            return candidate
    return None


def icon_png_path() -> Path | None:
    return resolve_branding_asset(ICON_PNG_NAME)


def icon_ico_path() -> Path | None:
    return resolve_branding_asset(ICON_ICO_NAME)


def splash_image_path() -> Path | None:
    return resolve_branding_asset(SPLASH_NAME)


def splash_metadata_lines() -> list[str]:
    return [
        f"Version: {APP_VERSION}",
        f"Build: {APP_BUILD_LABEL}",
        f"Author: {APP_AUTHOR}",
        f"Dependencies: {' · '.join(APP_DEPENDENCIES)}",
        f"License: {APP_LICENSE}",
    ]


def load_app_icon():
    from PySide6.QtGui import QIcon
    import sys

    path = None
    if sys.platform.startswith("win"):
        path = icon_ico_path() or icon_png_path()
    else:
        path = icon_png_path() or icon_ico_path()
    if path is None:
        return None
    icon = QIcon(str(path))
    if icon.isNull():
        return None
    return icon


def create_splash_screen():
    from PySide6.QtCore import Qt, QRect, QSize
    from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
    from PySide6.QtWidgets import QSplashScreen

    path = splash_image_path()
    if path is None:
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None

    max_size = QSize(1120, 620)
    pixmap = pixmap.scaled(max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    composed = QPixmap(pixmap)
    painter = QPainter(composed)
    try:
        width = composed.width()
        height = composed.height()
        panel_height = 112
        panel_rect = QRect(0, height - panel_height, width, panel_height)
        painter.fillRect(panel_rect, QColor(6, 10, 18, 196))
        painter.setPen(QColor(235, 223, 196))

        title_font = QFont("Segoe UI", 10)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(QRect(24, height - panel_height + 14, width - 48, 18), Qt.AlignLeft | Qt.AlignVCenter, APP_NAME)

        body_font = QFont("Segoe UI", 9)
        painter.setFont(body_font)
        text_y = height - panel_height + 38
        for line in splash_metadata_lines():
            painter.drawText(QRect(24, text_y, width - 48, 16), Qt.AlignLeft | Qt.AlignVCenter, line)
            text_y += 17
    finally:
        painter.end()

    splash = QSplashScreen(composed, Qt.WindowStaysOnTopHint)
    splash.setObjectName("BrandSplashScreen")
    splash.setWindowFlag(Qt.FramelessWindowHint, True)
    return splash
