from __future__ import annotations

import ast
import tempfile
import time
import unittest
from pathlib import Path

from app.background_rules_controller import BackgroundRulesController
from app.chroma_profile_controller import ChromaProfileController
from app.models import BackgroundColorRule, ChromaKeySettings
from app.performance_probe import PerformanceProbe
from app.profile_store import ProfilesStore


class FakeValueWidget:
    def __init__(self, value=0):
        self._value = value
        self._blocked = False
        self._enabled = True
        self._checked = False

    def blockSignals(self, value):
        previous = self._blocked
        self._blocked = bool(value)
        return previous

    def setValue(self, value):
        self._value = value

    def value(self):
        return self._value

    def setEnabled(self, value):
        self._enabled = bool(value)

    def isEnabled(self):
        return self._enabled

    def setChecked(self, value):
        self._checked = bool(value)

    def isChecked(self):
        return self._checked


class FakeCombo(FakeValueWidget):
    def __init__(self, data=None):
        super().__init__(0)
        self.items = []
        self.current = ''
        self.data = list(data or ['auto', 'global', 'edge_connected'])

    def clear(self):
        self.items = []
        self.current = ''

    def addItems(self, names):
        self.items.extend(names)
        if self.items and not self.current:
            self.current = self.items[0]

    def setCurrentText(self, name):
        self.current = name

    def currentText(self):
        return self.current

    def findData(self, value):
        try:
            return self.data.index(value)
        except ValueError:
            return -1

    def setCurrentIndex(self, index):
        self._value = index


class FakeList:
    def __init__(self):
        self.items = []
        self.row = -1

    def clear(self):
        self.items.clear()

    def addItem(self, text):
        self.items.append(text)

    def currentRow(self):
        return self.row


class R5e13aControllerTests(unittest.TestCase):
    def test_chroma_profile_roundtrip_and_store_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProfilesStore(Path(td) / 'profiles.json')
            settings = ChromaKeySettings(
                background_rgb=(12, 34, 56),
                tolerance=41,
                softness=17,
                cleanup_radius=3,
                edge_decontamination=52,
                keying_mode='edge_connected',
                additional_background_colors=[BackgroundColorRule((1, 2, 3), False, 9)],
                outer_border_mask_px=7,
                subject_edge_mask_expand_px=4,
            )
            profile_combo = FakeCombo()
            widgets = [FakeValueWidget() for _ in range(8)]
            key_combo = FakeCombo()
            events = []
            names = iter(['Profilo A'])
            controller = ChromaProfileController(
                store=store,
                settings=settings,
                profile_combo=profile_combo,
                tolerance_slider=widgets[0],
                softness_slider=widgets[1],
                cleanup_slider=widgets[2],
                decontam_slider=widgets[3],
                keying_mode_combo=key_combo,
                outer_border_checkbox=widgets[4],
                outer_border_spin=widgets[5],
                subject_expand_checkbox=widgets[6],
                subject_expand_spin=widgets[7],
                refresh_rules=lambda: events.append('rules'),
                update_swatch=lambda: events.append('swatch'),
                refresh_previews=lambda: events.append('preview'),
                has_current_frame=lambda: True,
                mark_alignment_dirty=lambda: events.append('alignment'),
                mark_smart_dirty=lambda: events.append('smart'),
                sync_cleanup_selection=lambda: events.append('cleanup'),
                ask_profile_name=lambda: next(names),
                confirm_delete=lambda _name: True,
                show_info=lambda _title, _text: events.append('info'),
                status=lambda text: events.append(text),
            )
            payload = controller.capture_profile_data()
            self.assertEqual(payload['background_rgb'], [12, 34, 56])
            self.assertEqual(payload['additional_background_colors'][0]['tolerance'], 9)
            controller.save_current_as()
            self.assertEqual(store.get_profile('chroma', 'Profilo A'), payload)
            self.assertEqual(profile_combo.currentText(), 'Profilo A')

            settings.background_rgb = (0, 0, 0)
            settings.additional_background_colors = []
            controller.load_selected()
            self.assertEqual(settings.background_rgb, (12, 34, 56))
            self.assertEqual(settings.additional_background_colors[0].rgb, (1, 2, 3))
            self.assertTrue(controller.has_saved_last)
            self.assertIn('preview', events)
            controller.delete_selected()
            self.assertIsNone(store.get_profile('chroma', 'Profilo A'))

    def test_background_rules_controller_sampling_toggle_tolerance_and_clear(self):
        settings = ChromaKeySettings(background_rgb=(0, 255, 0))
        list_widget = FakeList()
        events = []
        controller = BackgroundRulesController(
            settings=settings,
            list_widget=list_widget,
            has_current_frame=lambda: True,
            choose_color=lambda _rgb: (255, 0, 255),
            ask_tolerance=lambda _current: 31,
            show_warning=lambda title, text: events.append((title, text)),
            show_info=lambda title, text: events.append((title, text)),
            status=lambda text: events.append(text),
            changed=lambda: events.append('changed'),
        )
        controller.add_via_picker()
        self.assertEqual(settings.additional_background_colors[0].rgb, (255, 0, 255))
        list_widget.row = 0
        controller.toggle_selected()
        self.assertFalse(settings.additional_background_colors[0].enabled)
        controller.set_selected_tolerance()
        self.assertEqual(settings.additional_background_colors[0].tolerance, 31)
        controller.arm_sample()
        self.assertTrue(controller.sample_armed)
        self.assertTrue(controller.try_consume_sample((12, 13, 14), 4, 8))
        self.assertFalse(controller.sample_armed)
        self.assertEqual(settings.additional_background_colors[-1].rgb, (12, 13, 14))
        controller.clear()
        self.assertEqual(settings.additional_background_colors, [])
        self.assertGreaterEqual(events.count('changed'), 4)

    def test_performance_probe_is_opt_in_and_reports_metrics(self):
        disabled = PerformanceProbe(enabled=False)
        with disabled.measure('noop'):
            pass
        self.assertEqual(disabled.snapshot()['metrics'], {})

        probe = PerformanceProbe(enabled=True, sample_limit=32)
        with probe.measure('work'):
            time.sleep(0.001)
        probe.record('work', 2.5)
        metric = probe.snapshot()['metrics']['work']
        self.assertEqual(metric['count'], 2)
        self.assertEqual(metric['sample_count'], 2)
        self.assertGreater(metric['max_ms'], 0)
        self.assertGreater(metric['p95_ms'], 0)

    def test_main_window_no_longer_owns_extracted_profile_and_rule_methods(self):
        source = Path(__file__).resolve().parents[1] / 'app' / 'main_window.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        main = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'MainWindow')
        names = {node.name for node in main.body if isinstance(node, ast.FunctionDef)}
        extracted = {
            '_capture_chroma_profile_data',
            '_apply_chroma_profile_data',
            '_refresh_chroma_profiles_combo',
            '_load_last_used_chroma_profile',
            '_save_current_chroma_profile_as',
            '_load_selected_chroma_profile',
            '_delete_selected_chroma_profile',
            '_refresh_additional_background_colors_list',
            '_selected_additional_rule_index',
            '_additional_background_rules_changed',
            '_add_additional_background_color',
            '_arm_additional_background_sample',
            '_toggle_additional_background_color',
            '_set_additional_background_tolerance',
            '_remove_additional_background_color',
            '_clear_additional_background_colors',
        }
        self.assertTrue(extracted.isdisjoint(names))
        self.assertLessEqual(len(names), 80)


if __name__ == '__main__':
    unittest.main()
