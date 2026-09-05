from __future__ import annotations

from pathlib import Path
import unittest


class P2DGeneralCanvasContextMenuContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.menu = (root / 'app' / 'canvas_context_menu.py').read_text(encoding='utf-8')
        cls.create_shell = (root / 'app' / 'create_workspace_shell.py').read_text(encoding='utf-8')
        cls.workstation = (root / 'app' / 'workstation_shell.py').read_text(encoding='utf-8')
        cls.main = (root / 'app' / 'main_window.py').read_text(encoding='utf-8')
        cls.doc = (root / 'docs' / 'P2D_GENERAL_CANVAS_CONTEXT_MENU.md').read_text(encoding='utf-8')

    def test_context_request_is_forwarded_from_canvas_to_main_window(self) -> None:
        self.assertIn('general_canvas_context_menu_requested = Signal(QPoint)', self.create_shell)
        self.assertIn('general_canvas_context_menu_requested = Signal(QPoint)', self.workstation)
        self.assertIn('self.canvas_context_menu.show', self.main)

    def test_file_and_edit_actions_are_reused_not_reimplemented(self) -> None:
        self.assertIn('file_actions=tuple(self.file_menu.actions())', self.main)
        self.assertIn('edit_actions=tuple(self.edit_menu.actions())', self.main)
        self.assertIn('submenu.addAction(action)', self.menu)

    def test_macro_and_route_navigation_use_workstation_callbacks(self) -> None:
        self.assertIn('self.set_environment(env)', self.menu)
        self.assertIn('self.navigate_route(route_id)', self.menu)
        self.assertIn('WORKSPACE_ROUTES', self.menu)

    def test_menu_builder_has_no_project_or_view_state_dependency(self) -> None:
        self.assertNotIn('ProjectStore', self.menu)
        self.assertNotIn('ProjectSession', self.menu)
        self.assertNotIn('CreateWorkspaceState', self.menu)
        self.assertNotIn('pan_x', self.menu)
        self.assertNotIn('zoom', self.menu)

    def test_p2d_document_freezes_no_mutation_and_tool_priority(self) -> None:
        self.assertIn('Opening the menu does not mutate project, selection, pan, zoom or tool state.', self.doc)
        self.assertIn('An active tool cannot open this general menu unless it explicitly delegates', self.doc)
        self.assertIn('same QAction instances', self.doc)


if __name__ == '__main__':
    unittest.main()
