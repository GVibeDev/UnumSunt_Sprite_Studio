from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import QTabBar

from app.ui_theme import TAB_THEMES, normalize_theme_name, tab_theme_colors


class ThemedTabBar(QTabBar):
    """Tab bar with per-tab inverse text/background gradients."""

    def __init__(self, parent=None, *, theme_name: str = 'red') -> None:
        super().__init__(parent)
        self._theme_name = normalize_theme_name(theme_name)
        self.setDrawBase(False)
        self.setExpanding(False)

    @property
    def theme_name(self) -> str:
        return self._theme_name

    def set_theme(self, theme_name: str) -> None:
        normalized = normalize_theme_name(theme_name)
        if normalized == self._theme_name:
            self.update()
            return
        self._theme_name = normalized
        self.updateGeometry()
        self.update()

    def tabSizeHint(self, index: int) -> QSize:  # noqa: N802 - Qt API
        base = super().tabSizeHint(index)
        return QSize(max(84, base.width() + 14), max(34, base.height() + 8))

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setClipRect(event.rect())
        color_pairs = tab_theme_colors(self._theme_name, self.count())
        theme = TAB_THEMES[self._theme_name]
        hover_index = self.tabAt(self.mapFromGlobal(QCursor.pos()))

        for index in range(self.count()):
            rect = self.tabRect(index)
            if not rect.intersects(event.rect()):
                continue
            text_rgb, background_rgb = color_pairs[index]
            background = QColor(*background_rgb)
            text = QColor(*text_rgb)

            if index == hover_index and index != self.currentIndex():
                background = background.lighter(112)
            if index == self.currentIndex():
                background = background.lighter(108)

            painter.fillRect(rect, background)
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
            painter.drawLine(rect.topRight(), rect.bottomRight())

            if index == self.currentIndex():
                painter.fillRect(rect.left(), rect.bottom() - 2, rect.width(), 3, QColor(*theme.accent))

            font = QFont(self.font())
            font.setBold(index == self.currentIndex())
            painter.setFont(font)
            painter.setPen(text if self.isTabEnabled(index) else QColor(145, 145, 145))

            text_rect = rect.adjusted(9, 0, -9, 0)
            elided = painter.fontMetrics().elidedText(self.tabText(index), self.elideMode(), text_rect.width())
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, elided)
