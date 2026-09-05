from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class P2ECanvasConnectivityHotfixContractTests(unittest.TestCase):
    def test_canvas_has_wheel_zoom_and_drop_contract(self) -> None:
        source = (ROOT / 'app' / 'shared_create_canvas.py').read_text(encoding='utf-8')
        self.assertIn('def wheelEvent', source)
        self.assertIn('setAcceptDrops(True)', source)
        self.assertIn('source_files_dropped', source)
        self.assertIn('1.20 ** steps', source)

    def test_create_source_sector_reuses_qactions(self) -> None:
        source = (ROOT / 'app' / 'create_workspace_shell.py').read_text(encoding='utf-8')
        self.assertIn("self.left_tabs.addTab(self._source_page, 'Source')", source)
        self.assertIn('setDefaultAction(open_video_action)', source)
        self.assertIn('setDefaultAction(open_spritesheet_action)', source)

    def test_workstation_explicit_create_navigation_opens_controls(self) -> None:
        source = (ROOT / 'app' / 'workstation_shell.py').read_text(encoding='utf-8')
        self.assertIn("route.environment == 'create'", source)
        self.assertIn('page.show_workspace_controls()', source)

    def test_spritesheet_exposes_public_path_loader_and_canvas_preview(self) -> None:
        source = (ROOT / 'app' / 'spritesheet_workspace.py').read_text(encoding='utf-8')
        self.assertIn('def open_sheet_path', source)
        self.assertIn('source_preview_ready.emit', source)

    def test_main_window_method_guard_remains_within_existing_architecture_limit(self) -> None:
        tree = ast.parse((ROOT / 'app' / 'main_window.py').read_text(encoding='utf-8'))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'MainWindow')
        methods = [node.name for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.assertLessEqual(len(methods), 80)


if __name__ == '__main__':
    unittest.main()
