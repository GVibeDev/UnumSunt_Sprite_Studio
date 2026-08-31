from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal


MacroEnvironment = Literal['generate', 'create', 'manage']

ENVIRONMENT_ORDER: tuple[MacroEnvironment, ...] = ('generate', 'create', 'manage')
ENVIRONMENT_LABELS: dict[MacroEnvironment, str] = {
    'generate': 'GENERATE',
    'create': 'CREATE',
    'manage': 'MANAGE',
}


@dataclass(frozen=True, slots=True)
class WorkspaceRoute:
    route_id: str
    environment: MacroEnvironment
    label: str
    order: int
    tooltip: str
    legacy_index: int


WORKSPACE_ROUTES: tuple[WorkspaceRoute, ...] = (
    WorkspaceRoute(
        route_id='generation',
        environment='generate',
        label='Motion',
        order=10,
        tooltip='WAN / WanGP video generation',
        legacy_index=1,
    ),
    WorkspaceRoute(
        route_id='image_generation',
        environment='generate',
        label='Image',
        order=20,
        tooltip='Local image generation',
        legacy_index=11,
    ),
    WorkspaceRoute(
        route_id='prompt_builder',
        environment='generate',
        label='Prompt',
        order=30,
        tooltip='Prompt Builder and Prompt Profiles',
        legacy_index=9,
    ),
    WorkspaceRoute(
        route_id='calibration',
        environment='generate',
        label='Calibration',
        order=40,
        tooltip='Calibration Lab',
        legacy_index=8,
    ),
    WorkspaceRoute(
        route_id='spritesheet',
        environment='create',
        label='Import',
        order=10,
        tooltip='Sprite Sheet Import / Decompose / Reference Builder',
        legacy_index=10,
    ),
    WorkspaceRoute(
        route_id='extraction',
        environment='create',
        label='Extract',
        order=20,
        tooltip='R1 extraction and frame selection',
        legacy_index=2,
    ),
    WorkspaceRoute(
        route_id='smart_selection',
        environment='create',
        label='Select',
        order=30,
        tooltip='Smart frame selection',
        legacy_index=5,
    ),
    WorkspaceRoute(
        route_id='cleanup',
        environment='create',
        label='Clean-up',
        order=40,
        tooltip='Alpha and mask clean-up',
        legacy_index=3,
    ),
    WorkspaceRoute(
        route_id='alignment',
        environment='create',
        label='Align',
        order=50,
        tooltip='Alignment and output geometry',
        legacy_index=4,
    ),
    WorkspaceRoute(
        route_id='character_set',
        environment='create',
        label='Character Set',
        order=60,
        tooltip='Character Set / Layer Manager',
        legacy_index=13,
    ),
    WorkspaceRoute(
        route_id='export',
        environment='create',
        label='Export',
        order=70,
        tooltip='Export Studio',
        legacy_index=6,
    ),
    WorkspaceRoute(
        route_id='project',
        environment='manage',
        label='Projects',
        order=10,
        tooltip='Project and Project Groups',
        legacy_index=0,
    ),
    WorkspaceRoute(
        route_id='production_presets',
        environment='manage',
        label='Presets',
        order=20,
        tooltip='Production Presets',
        legacy_index=7,
    ),
    WorkspaceRoute(
        route_id='workflow',
        environment='manage',
        label='Workflows',
        order=30,
        tooltip='Guided Workflows / Workflow Router',
        legacy_index=12,
    ),
)

DEFAULT_ROUTE_ID = 'project'


def validate_route_registry(routes: Iterable[WorkspaceRoute]) -> tuple[WorkspaceRoute, ...]:
    normalized = tuple(routes)
    if not normalized:
        raise ValueError('The workstation route registry cannot be empty.')

    route_ids = [route.route_id for route in normalized]
    if any(not route_id.strip() for route_id in route_ids):
        raise ValueError('Every workstation route must declare a non-empty route_id.')
    if len(set(route_ids)) != len(route_ids):
        raise ValueError('Workstation route IDs must be unique.')

    legacy_indices = [route.legacy_index for route in normalized]
    if len(set(legacy_indices)) != len(legacy_indices):
        raise ValueError('Legacy workspace indices must be unique during migration.')
    if any(index < 0 for index in legacy_indices):
        raise ValueError('Legacy workspace indices cannot be negative.')

    for route in normalized:
        if route.environment not in ENVIRONMENT_ORDER:
            raise ValueError(f'Unsupported macro environment: {route.environment}')
        if not route.label.strip():
            raise ValueError(f'Route {route.route_id} must declare a visible label.')
        if route.order < 0:
            raise ValueError(f'Route {route.route_id} cannot have a negative order.')

    for environment in ENVIRONMENT_ORDER:
        orders = [route.order for route in normalized if route.environment == environment]
        if not orders:
            raise ValueError(f'Macro environment {environment} must contain at least one route.')
        if len(set(orders)) != len(orders):
            raise ValueError(f'Route order values must be unique inside {environment}.')

    return normalized


WORKSPACE_ROUTES = validate_route_registry(WORKSPACE_ROUTES)
WORKSPACE_ROUTES_BY_ID: dict[str, WorkspaceRoute] = {
    route.route_id: route for route in WORKSPACE_ROUTES
}


def route_by_id(route_id: str) -> WorkspaceRoute:
    normalized = str(route_id).strip()
    try:
        return WORKSPACE_ROUTES_BY_ID[normalized]
    except KeyError as exc:
        raise KeyError(f'Unknown workstation route: {route_id}') from exc


def routes_for_environment(environment: str) -> tuple[WorkspaceRoute, ...]:
    normalized = str(environment).strip().lower()
    if normalized not in ENVIRONMENT_ORDER:
        raise KeyError(f'Unknown workstation environment: {environment}')
    return tuple(
        sorted(
            (route for route in WORKSPACE_ROUTES if route.environment == normalized),
            key=lambda route: (route.order, route.route_id),
        )
    )


def routes_by_legacy_index() -> tuple[WorkspaceRoute, ...]:
    return tuple(sorted(WORKSPACE_ROUTES, key=lambda route: route.legacy_index))


def route_for_legacy_index(index: int) -> WorkspaceRoute:
    normalized = int(index)
    for route in WORKSPACE_ROUTES:
        if route.legacy_index == normalized:
            return route
    raise KeyError(f'Unknown legacy workspace index: {index}')


def default_route_for_environment(environment: str) -> WorkspaceRoute:
    return routes_for_environment(environment)[0]


def legacy_route_ids() -> tuple[str, ...]:
    return tuple(route.route_id for route in routes_by_legacy_index())
