from __future__ import annotations

from pathlib import Path
import unittest


class CanvasContextMenuSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.controller_source = (root / 'app' / 'canvas_context_menu.py').read_text(encoding='utf-8')
        cls.main_source = (root / 'app' / 'main_window.py').read_text(encoding='utf-8')
        cls.canvas_source = (root / 'app' / 'shared_canvas.py').read_text(encoding='utf-8')

    def test_controller_has_file_edit_and_three_macro_cascade_groups(self) -> None:
        self.assertIn("title='File'", self.controller_source)
        self.assertIn("title='Edit'", self.controller_source)
        self.assertIn('for environment in ENVIRONMENT_ORDER', self.controller_source)
        self.assertIn('routes_for_environment(environment)', self.controller_source)

    def test_file_edit_logic_is_reused_not_reimplemented(self) -> None:
        self.assertIn('submenu.addAction(action)', self.controller_source)
        self.assertIn('file_actions_provider=lambda: tuple(self.file_menu.actions())', self.main_source)
        self.assertIn('edit_actions_provider=lambda: tuple(self.edit_menu.actions())', self.main_source)
        self.assertNotIn("QAction('New Project'", self.controller_source)
        self.assertNotIn("QAction('Remove Selected'", self.controller_source)

    def test_shared_canvas_request_is_connected_to_general_context_controller(self) -> None:
        self.assertIn('create_canvas.context_menu_requested.connect(', self.main_source)
        self.assertIn('self.canvas_context_menu.show_for_canvas(canvas, x, y)', self.main_source)
        self.assertIn('context_menu_requested = Signal(float, float)', self.canvas_source)

    def test_context_menu_opening_does_not_mutate_canvas_state(self) -> None:
        self.assertNotIn('set_view_transform(', self.controller_source)
        self.assertNotIn('activate_tool(', self.controller_source)
        self.assertNotIn('set_project_context(', self.controller_source)
        self.assertNotIn('project_store', self.controller_source.lower())

    def test_macro_navigation_delegates_to_workstation_shell(self) -> None:
        self.assertIn('self._workstation.set_environment(env)', self.controller_source)
        self.assertIn('self._workstation.navigate(route_id)', self.controller_source)


if __name__ == '__main__':
    unittest.main()
