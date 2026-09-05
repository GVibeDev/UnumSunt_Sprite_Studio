from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import unittest

from app.create_control_rehousing import (
    CREATE_ROUTE_CONTROL_PLANS,
    control_plan_for_route,
    validate_control_plans,
)


ROOT = Path(__file__).resolve().parents[1]
PYSIDE6_AVAILABLE = importlib.util.find_spec('PySide6') is not None


class P2GControlAuditContractTests(unittest.TestCase):
    def test_every_create_route_has_one_control_plan(self) -> None:
        self.assertEqual(
            validate_control_plans(),
            (
                'alignment',
                'character_set',
                'cleanup',
                'export',
                'extraction',
                'smart_selection',
                'spritesheet',
            ),
        )

    def test_every_audited_group_title_exists_in_its_declared_source(self) -> None:
        for route_id, plan in CREATE_ROUTE_CONTROL_PLANS.items():
            source = (ROOT / plan.source_file).read_text(encoding='utf-8')
            for placement in plan.placements:
                with self.subTest(route=route_id, title=placement.title):
                    self.assertIn(placement.title, source)

    def test_alignment_is_split_across_local_panel_sections(self) -> None:
        plan = control_plan_for_route('alignment')
        by_section = {placement.title: placement.section for placement in plan.placements}
        self.assertEqual(by_section['Current Frame Alignment'], 'tools')
        self.assertEqual(by_section['View and Onion Skin'], 'options')
        self.assertEqual(by_section['Output Geometry and Global Anchor · R5e2'], 'configurations')
        self.assertEqual(by_section['Alignment Profiles'], 'configurations')
        self.assertEqual(by_section['Animation and Export'], 'output')
        self.assertTrue(plan.collapse_legacy_control_columns)

    def test_cleanup_keeps_tools_left_and_does_not_invent_output_controls(self) -> None:
        plan = control_plan_for_route('cleanup')
        self.assertEqual(
            tuple((item.title, item.section) for item in plan.placements),
            (
                ('Clean-up alpha', 'tools'),
                ('Pixel painter', 'tools'),
                ('Selections and Propagation · R5e5-D', 'options'),
            ),
        )

    def test_extraction_splits_nested_background_controls_instead_of_one_long_column(self) -> None:
        plan = control_plan_for_route('extraction')
        sections = {item.title: item.section for item in plan.placements}
        self.assertEqual(sections['Background Extraction'], 'tools')
        self.assertEqual(sections['Additional Background Colors · R5e5-A'], 'options')
        self.assertEqual(sections['Structural Refinement · R5e5-B'], 'options')
        self.assertEqual(sections['Alpha / Chroma Profiles'], 'options')
        self.assertEqual(sections['R1 Export'], 'output')

    def test_shell_reparents_existing_widgets_and_fails_on_audit_mismatch(self) -> None:
        source = (ROOT / 'app' / 'create_workspace_shell.py').read_text(encoding='utf-8')
        self.assertIn('self._rehouse_registered_route_controls(route_id, widget)', source)
        self.assertIn('P2-G control audit mismatch', source)
        self.assertIn('self._add_rehoused_control(route_id, placement.section', source)
        self.assertIn('column.hide()', source)

    def test_extraction_runtime_widget_is_marked_for_strict_audit(self) -> None:
        source = (ROOT / 'app' / 'main_window.py').read_text(encoding='utf-8')
        self.assertIn("page.setObjectName('extractionWorkspace')", source)


if PYSIDE6_AVAILABLE:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QGroupBox, QSplitter, QVBoxLayout, QWidget

    from app.create_workspace_shell import CreateWorkspaceShell
    from app.workstation_routes import routes_for_environment


@unittest.skipUnless(PYSIDE6_AVAILABLE, 'PySide6 is not installed in this test interpreter.')
class P2GControlRehousingQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_alignment_groups_are_moved_without_recreation_and_legacy_column_collapses(self) -> None:
        class AlignmentStudio(QWidget):
            def __init__(self) -> None:
                super().__init__()
                root = QVBoxLayout(self)
                splitter = QSplitter(self)
                root.addWidget(splitter)
                production = QWidget(splitter)
                splitter.addWidget(production)
                controls = QWidget(splitter)
                controls_layout = QVBoxLayout(controls)
                splitter.addWidget(controls)
                self.groups = {}
                for title in (
                    'Output Geometry and Global Anchor · R5e2',
                    'Alignment Profiles',
                    'Current Frame Alignment',
                    'View and Onion Skin',
                    'Animation and Export',
                ):
                    group = QGroupBox(title, controls)
                    controls_layout.addWidget(group)
                    self.groups[title] = group
                self.legacy_controls = controls

        shell = CreateWorkspaceShell(routes_for_environment('create'))
        workspace = AlignmentStudio()
        original_ids = {title: id(group) for title, group in workspace.groups.items()}
        shell.register_widget('alignment', workspace)
        shell.select_route('alignment')

        for title, group in workspace.groups.items():
            self.assertEqual(id(group), original_ids[title])
            self.assertIsNotNone(group.parentWidget())
            self.assertNotEqual(group.parentWidget(), workspace.legacy_controls)
        self.assertTrue(workspace.legacy_controls.isHidden())
        self.assertEqual(shell.left_tabs.tabText(shell.left_tabs.currentIndex()), 'Tools')
        self.assertEqual(shell.right_tabs.tabText(shell.right_tabs.currentIndex()), 'Configurations')


if __name__ == '__main__':
    unittest.main()
