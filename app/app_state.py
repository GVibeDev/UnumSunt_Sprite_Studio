from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.workstation_routes import DEFAULT_ROUTE_ID, route_by_id, route_for_legacy_index


APP_STATE_SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class NavigationState:
    """Normalized workstation navigation restored from any supported app-state era."""

    route_id: str
    environment: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {
            'environment': self.environment,
            'route': self.route_id,
        }


def navigation_state_for_route(route_id: str) -> NavigationState:
    route = route_by_id(route_id)
    return NavigationState(
        route_id=route.route_id,
        environment=route.environment,
        source='native',
    )


def resolve_navigation_state(
    state: dict[str, Any] | None,
    *,
    fallback_route_id: str = DEFAULT_ROUTE_ID,
) -> NavigationState:
    """Resolve P1-F, P1-D and pre-workstation navigation into one native route.

    Priority:
    1. P1-F ``navigation.route``;
    2. P1-D ``current_route``;
    3. R5c8/P1-C ``current_tab`` legacy index;
    4. canonical fallback.

    ``navigation.environment`` is intentionally advisory. The route registry is
    authoritative, so a stale/mismatched environment is repaired automatically.
    """
    payload = state if isinstance(state, dict) else {}

    navigation = payload.get('navigation')
    if isinstance(navigation, dict):
        route_id = navigation.get('route')
        if isinstance(route_id, str):
            try:
                route = route_by_id(route_id)
            except KeyError:
                pass
            else:
                return NavigationState(route.route_id, route.environment, 'navigation')

    current_route = payload.get('current_route')
    if isinstance(current_route, str):
        try:
            route = route_by_id(current_route)
        except KeyError:
            pass
        else:
            return NavigationState(route.route_id, route.environment, 'current_route')

    legacy_index = payload.get('current_tab')
    try:
        route = route_for_legacy_index(int(legacy_index))
    except (TypeError, ValueError, KeyError):
        route = route_by_id(fallback_route_id)
        return NavigationState(route.route_id, route.environment, 'fallback')
    return NavigationState(route.route_id, route.environment, 'current_tab')


def app_state_needs_migration(state: dict[str, Any] | None) -> bool:
    """Return True when a loaded profile should be rewritten in P1-F format."""
    if not isinstance(state, dict):
        return False
    if state.get('state_schema') != APP_STATE_SCHEMA_VERSION:
        return True
    if 'current_route' in state or 'current_tab' in state:
        return True

    navigation = state.get('navigation')
    if not isinstance(navigation, dict):
        return True
    resolved = resolve_navigation_state(state)
    if navigation.get('route') != resolved.route_id:
        return True
    if navigation.get('environment') != resolved.environment:
        return True

    preferences = state.get('preferences')
    if isinstance(preferences, dict):
        if 'tab_theme' in preferences or 'workstation_theme' not in preferences:
            return True
    return False
