from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class P2FFrameProjectContextContractTests(unittest.TestCase):
    def test_main_window_adopts_source_into_project_session(self) -> None:
        source = (ROOT / 'app' / 'main_window.py').read_text(encoding='utf-8')
        self.assertIn('self.project_session.set_current_source(', source)
        self.assertIn('self.project_session.set_current_frame(index)', source)
        self.assertIn('self.project_session.set_selected_frames(self.selected_frames)', source)

    def test_main_window_feeds_shared_create_frame_context(self) -> None:
        source = (ROOT / 'app' / 'main_window.py').read_text(encoding='utf-8')
        self.assertIn('self.workstation_shell.set_create_frame_context(', source)
        self.assertIn('CreateFrameContext(', source)
        self.assertIn('frame_count=metadata.frame_count', source)
        self.assertIn('source_label=metadata.path.name', source)

    def test_onion_uses_existing_pipeline_chroma_and_override_paths(self) -> None:
        source = (ROOT / 'app' / 'main_window.py').read_text(encoding='utf-8')
        self.assertIn('onion_target = self.workstation_shell.create_onion_target_index()', source)
        self.assertIn('onion_override = self.get_rgba_override(onion_target)', source)
        self.assertIn('onion_rgba, _onion_mask = apply_chroma_key(onion_rgb, self.chroma_settings)', source)
        self.assertNotIn('onion_pipeline_state', source)

    def test_create_shell_exposes_one_persistent_frame_strip(self) -> None:
        source = (ROOT / 'app' / 'create_workspace_shell.py').read_text(encoding='utf-8')
        self.assertEqual(source.count('self.frame_strip = CreateFrameStrip(self)'), 1)
        self.assertIn('self.frame_strip.frame_requested.connect(self.frame_requested.emit)', source)
        self.assertIn('self.frame_strip.selection_requested.connect(self.frame_selection_requested.emit)', source)

    def test_workstation_shell_forwards_frame_context_without_route_indices(self) -> None:
        source = (ROOT / 'app' / 'workstation_shell.py').read_text(encoding='utf-8')
        self.assertIn('create_frame_requested = Signal(int)', source)
        self.assertIn('create_frame_selection_requested = Signal(object)', source)
        self.assertIn('create_onion_mode_changed = Signal(str)', source)
        self.assertIn('def set_create_frame_context(self, context: CreateFrameContext)', source)

    def test_project_store_schema_is_not_modified_by_p2f_runtime_state(self) -> None:
        source = (ROOT / 'app' / 'project_store.py').read_text(encoding='utf-8')
        self.assertNotIn('onion_skin_mode', source)
        self.assertNotIn('current_frame_index', source)
        self.assertNotIn('CreateFrameContext', source)

    def test_main_window_method_count_stays_within_architecture_guard(self) -> None:
        source = (ROOT / 'app' / 'main_window.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'MainWindow')
        methods = [node.name for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.assertLessEqual(len(methods), 80)


if __name__ == '__main__':
    unittest.main()
