from __future__ import annotations

import importlib.util
import os
import unittest

PYSIDE6_AVAILABLE = importlib.util.find_spec('PySide6') is not None

if PYSIDE6_AVAILABLE:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QAction, QWheelEvent
    from PySide6.QtWidgets import QApplication, QLabel

    from app.create_workspace_state import CreateWorkspaceState
    from app.shared_create_canvas import SharedCreateCanvas
    from app.workstation_routes import route_by_id
    from app.workstation_shell import WorkstationShell


@unittest.skipUnless(PYSIDE6_AVAILABLE, 'PySide6 is not installed in this test interpreter.')
class P2ECanvasConnectivityQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_neutral_wheel_changes_zoom(self) -> None:
        state = CreateWorkspaceState()
        canvas = SharedCreateCanvas(state=state)
        canvas.resize(800, 600)
        event = QWheelEvent(
            QPointF(400, 300),
            QPointF(400, 300),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        canvas.wheelEvent(event)
        self.assertGreater(state.view.zoom, 1.0)

    def test_source_buttons_reuse_existing_actions(self) -> None:
        shell = WorkstationShell()
        video_action = QAction('Open Video…', shell)
        sheet_action = QAction('Open Spritesheet…', shell)
        shell.bind_create_source_actions(
            open_video_action=video_action,
            open_spritesheet_action=sheet_action,
        )
        create = shell.create_workspace_shell()
        self.assertIs(create.open_video_source_button.defaultAction(), video_action)
        self.assertIs(create.open_spritesheet_source_button.defaultAction(), sheet_action)

    def test_explicit_create_navigation_opens_route_controls(self) -> None:
        shell = WorkstationShell()
        for route_id in ('spritesheet', 'cleanup'):
            shell.register_route(route_by_id(route_id), QLabel(route_id))
        create = shell.create_workspace_shell()
        create.show_canvas()
        self.assertEqual(create.production_tabs.currentIndex(), 0)
        shell.navigate('cleanup')
        self.assertEqual(create.production_tabs.currentIndex(), 1)


if __name__ == '__main__':
    unittest.main()
