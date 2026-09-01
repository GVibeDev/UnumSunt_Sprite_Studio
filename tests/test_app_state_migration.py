from __future__ import annotations

import unittest

from app.app_state import (
    APP_STATE_SCHEMA_VERSION,
    app_state_needs_migration,
    navigation_state_for_route,
    resolve_navigation_state,
)


class AppStateMigrationTests(unittest.TestCase):
    def test_native_navigation_is_canonical(self) -> None:
        state = {
            'state_schema': APP_STATE_SCHEMA_VERSION,
            'navigation': {'environment': 'create', 'route': 'cleanup'},
            'preferences': {'workstation_theme': 'red'},
        }
        resolved = resolve_navigation_state(state)
        self.assertEqual(resolved.route_id, 'cleanup')
        self.assertEqual(resolved.environment, 'create')
        self.assertEqual(resolved.source, 'navigation')
        self.assertFalse(app_state_needs_migration(state))

    def test_mismatched_environment_is_repaired_from_route_registry(self) -> None:
        state = {
            'state_schema': APP_STATE_SCHEMA_VERSION,
            'navigation': {'environment': 'manage', 'route': 'cleanup'},
            'preferences': {'workstation_theme': 'blue'},
        }
        resolved = resolve_navigation_state(state)
        self.assertEqual(resolved.environment, 'create')
        self.assertTrue(app_state_needs_migration(state))

    def test_p1d_current_route_migrates_to_native_navigation(self) -> None:
        state = {'current_route': 'prompt_builder'}
        resolved = resolve_navigation_state(state)
        self.assertEqual((resolved.environment, resolved.route_id), ('generate', 'prompt_builder'))
        self.assertEqual(resolved.source, 'current_route')
        self.assertTrue(app_state_needs_migration(state))

    def test_r5c8_legacy_tab_index_migrates_to_native_navigation(self) -> None:
        state = {'current_tab': 3}
        resolved = resolve_navigation_state(state)
        self.assertEqual((resolved.environment, resolved.route_id), ('create', 'cleanup'))
        self.assertEqual(resolved.source, 'current_tab')
        self.assertTrue(app_state_needs_migration(state))

    def test_native_route_wins_over_legacy_fields(self) -> None:
        state = {
            'navigation': {'environment': 'generate', 'route': 'image_generation'},
            'current_route': 'cleanup',
            'current_tab': 0,
        }
        self.assertEqual(resolve_navigation_state(state).route_id, 'image_generation')

    def test_invalid_state_uses_canonical_fallback(self) -> None:
        resolved = resolve_navigation_state(
            {'navigation': {'route': 'missing'}, 'current_route': 'also_missing', 'current_tab': 999},
            fallback_route_id='workflow',
        )
        self.assertEqual((resolved.environment, resolved.route_id), ('manage', 'workflow'))
        self.assertEqual(resolved.source, 'fallback')

    def test_capture_helper_derives_environment_from_route(self) -> None:
        state = navigation_state_for_route('spritesheet')
        self.assertEqual(state.to_dict(), {'environment': 'create', 'route': 'spritesheet'})

    def test_legacy_theme_key_requires_one_way_migration(self) -> None:
        state = {
            'state_schema': APP_STATE_SCHEMA_VERSION,
            'navigation': {'environment': 'manage', 'route': 'project'},
            'preferences': {'tab_theme': 'green'},
        }
        self.assertTrue(app_state_needs_migration(state))


if __name__ == '__main__':
    unittest.main()
