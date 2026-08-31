from __future__ import annotations

import unittest

from app.ui_commands import TAB_ROUTES
from app.workstation_routes import (
    DEFAULT_ROUTE_ID,
    ENVIRONMENT_ORDER,
    WORKSPACE_ROUTES,
    default_route_for_environment,
    legacy_route_ids,
    route_by_id,
    route_for_legacy_index,
    routes_for_environment,
    validate_route_registry,
    WorkspaceRoute,
)


class WorkstationRouteTests(unittest.TestCase):
    def test_registry_maps_all_r5c8_legacy_routes_once(self) -> None:
        self.assertEqual(len(WORKSPACE_ROUTES), 14)
        self.assertEqual(len({route.route_id for route in WORKSPACE_ROUTES}), 14)
        self.assertEqual(len({route.legacy_index for route in WORKSPACE_ROUTES}), 14)
        self.assertEqual(set(route.legacy_index for route in WORKSPACE_ROUTES), set(range(14)))
        self.assertEqual(legacy_route_ids(), TAB_ROUTES)

    def test_environment_mapping_is_exact(self) -> None:
        self.assertEqual(
            tuple(route.route_id for route in routes_for_environment('generate')),
            ('generation', 'image_generation', 'prompt_builder', 'calibration'),
        )
        self.assertEqual(
            tuple(route.route_id for route in routes_for_environment('create')),
            (
                'spritesheet',
                'extraction',
                'smart_selection',
                'cleanup',
                'alignment',
                'character_set',
                'export',
            ),
        )
        self.assertEqual(
            tuple(route.route_id for route in routes_for_environment('manage')),
            ('project', 'production_presets', 'workflow'),
        )

    def test_legacy_index_lookup_preserves_r5c8_order(self) -> None:
        for index, route_id in enumerate(TAB_ROUTES):
            route = route_for_legacy_index(index)
            self.assertEqual(route.route_id, route_id)
            self.assertEqual(route_by_id(route_id), route)

    def test_default_route_preserves_r5c8_project_start(self) -> None:
        self.assertEqual(DEFAULT_ROUTE_ID, 'project')
        self.assertEqual(route_by_id(DEFAULT_ROUTE_ID).environment, 'manage')

    def test_environment_defaults_are_deterministic(self) -> None:
        self.assertEqual(tuple(ENVIRONMENT_ORDER), ('generate', 'create', 'manage'))
        self.assertEqual(default_route_for_environment('generate').route_id, 'generation')
        self.assertEqual(default_route_for_environment('create').route_id, 'spritesheet')
        self.assertEqual(default_route_for_environment('manage').route_id, 'project')

    def test_unknown_route_and_environment_are_rejected(self) -> None:
        with self.assertRaises(KeyError):
            route_by_id('missing')
        with self.assertRaises(KeyError):
            routes_for_environment('missing')
        with self.assertRaises(KeyError):
            route_for_legacy_index(99)

    def test_registry_validation_rejects_duplicate_route_ids(self) -> None:
        duplicate = WorkspaceRoute('generation', 'generate', 'Duplicate', 99, 'x', 99)
        with self.assertRaises(ValueError):
            validate_route_registry((*WORKSPACE_ROUTES, duplicate))

    def test_registry_validation_rejects_duplicate_orders_in_one_environment(self) -> None:
        routes = list(WORKSPACE_ROUTES)
        original = routes[1]
        routes[1] = WorkspaceRoute(
            original.route_id,
            original.environment,
            original.label,
            routes[0].order,
            original.tooltip,
            original.legacy_index,
        )
        with self.assertRaises(ValueError):
            validate_route_registry(routes)


if __name__ == '__main__':
    unittest.main()
