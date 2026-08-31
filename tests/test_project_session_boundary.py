from __future__ import annotations

from pathlib import Path
import unittest


class ProjectSessionBoundarySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.main_source = (root / 'app' / 'main_window.py').read_text(encoding='utf-8')
        cls.workspace_source = (root / 'app' / 'project_workspace.py').read_text(encoding='utf-8')
        cls.session_source = (root / 'app' / 'project_session.py').read_text(encoding='utf-8')

    def test_main_window_owns_one_project_session(self) -> None:
        self.assertIn('self.project_session = ProjectSession(self)', self.main_source)
        self.assertIn(
            'self.project_workspace = ProjectWorkspace(project_session=self.project_session)',
            self.main_source,
        )

    def test_other_workspaces_get_project_context_from_session(self) -> None:
        self.assertIn('project_store_provider=lambda: self.project_session.store', self.main_source)
        self.assertIn('active_group_id_provider=lambda: self.project_session.active_group_id', self.main_source)
        self.assertNotIn('self.project_workspace.project_store', self.main_source)
        self.assertNotIn('self.project_workspace.active_group_id', self.main_source)

    def test_project_workspace_delegates_identity_to_session(self) -> None:
        self.assertIn('return self.project_session.store', self.workspace_source)
        self.assertIn('return self.project_session.project_path', self.workspace_source)
        self.assertIn('return self.project_session.active_group_id', self.workspace_source)
        self.assertIn('self.project_session.set_active_group(group_id)', self.workspace_source)

    def test_session_does_not_cache_duplicate_project_document(self) -> None:
        self.assertIn('self._store: ProjectStore | None = None', self.session_source)
        self.assertNotIn('self._document', self.session_source)
        self.assertNotIn('self._payload', self.session_source)
        self.assertIn('remains the single authoritative persistence', self.session_source)


if __name__ == '__main__':
    unittest.main()
