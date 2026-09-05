from __future__ import annotations

from pathlib import Path
import unittest


class Phase2RoadmapContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.source = (root / 'docs' / 'PHASE2_CREATE_WORKSPACE_CANVAS_CONTRACT.md').read_text(encoding='utf-8')

    def test_canvas_is_explicitly_dominant(self) -> None:
        self.assertIn('The canvas remains visually dominant', self.source)
        self.assertIn('Tools & Options / Canvas / Configurations & Output', self.source)

    def test_pan_is_neutral_behavior_not_a_tool(self) -> None:
        self.assertIn('PAN IS NOT A TOOL', self.source)
        self.assertIn('LMB drag → PAN', self.source)
        self.assertIn('RMB → general canvas context menu', self.source)

    def test_active_tool_has_priority_without_accidental_neutral_fallback(self) -> None:
        self.assertIn('TOOL ACTIVE > DEFAULT CANVAS INPUT', self.source)
        self.assertIn('unhandled   -> no action unless the tool explicitly delegates', self.source)

    def test_dense_panels_must_use_same_sector_stacked_or_tabbed_presentation(self) -> None:
        self.assertIn('Stacked/tabbed panel rule', self.source)
        self.assertIn('current Alignment UI demonstrates the failure mode', self.source)
        self.assertIn('only the active group/page needs to be visible at one time', self.source)
        self.assertIn('must not force primary/current-context fields below a useful size', self.source)


    def test_p2e_freezes_non_destructive_shared_canvas_layer_order(self) -> None:
        self.assertIn('Shared canvas layers & overlays — P2-E', self.source)
        self.assertIn('previous/next onion raster layers', self.source)
        self.assertIn('current frame raster layer', self.source)
        self.assertIn('Selections, guides, grid and pivot are overlays only', self.source)
        self.assertIn('must not mutate the underlying frame pixels', self.source)

    def test_final_grouping_and_panel_dimensions_remain_open(self) -> None:
        self.assertIn('final numeric panel dimensions', self.source)
        self.assertIn('exact Alignment/Clean-up/Export local tab names before audit', self.source)


if __name__ == '__main__':
    unittest.main()
