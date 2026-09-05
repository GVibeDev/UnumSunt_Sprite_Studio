from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PanelSection = Literal['source', 'tools', 'options', 'configurations', 'output']


@dataclass(frozen=True, slots=True)
class ControlPlacement:
    title: str
    section: PanelSection


@dataclass(frozen=True, slots=True)
class CreateRouteControlPlan:
    route_id: str
    source_file: str
    expected_widget_class: str | None
    placements: tuple[ControlPlacement, ...]
    preferred_left_section: Literal['Source', 'Tools', 'Options']
    preferred_right_section: Literal['Configurations', 'Output']
    collapse_legacy_control_columns: bool = False
    hidden_button_texts: tuple[str, ...] = ()

    def titles(self) -> tuple[str, ...]:
        return tuple(item.title for item in self.placements)

    def placements_for(self, section: PanelSection) -> tuple[ControlPlacement, ...]:
        return tuple(item for item in self.placements if item.section == section)


# P2-G audits the controls that exist in the validated P2-E/P2-F source and
# moves the same QWidget instances. Nothing in this registry creates a second
# implementation of an existing production command.
CREATE_ROUTE_CONTROL_PLANS: dict[str, CreateRouteControlPlan] = {
    'spritesheet': CreateRouteControlPlan(
        route_id='spritesheet',
        source_file='app/spritesheet_workspace.py',
        expected_widget_class='SpriteSheetWorkspace',
        placements=(
            ControlPlacement('Source', 'source'),
            ControlPlacement('Grid slicer', 'tools'),
            ControlPlacement('Irregular Atlas', 'options'),
            ControlPlacement('Decompose', 'configurations'),
            ControlPlacement('Existing Pipeline', 'output'),
            ControlPlacement('WAN Reference Sheet Builder', 'output'),
        ),
        preferred_left_section='Source',
        preferred_right_section='Output',
        collapse_legacy_control_columns=True,
        hidden_button_texts=('Open Spritesheet…',),
    ),
    'extraction': CreateRouteControlPlan(
        route_id='extraction',
        source_file='app/main_window.py',
        expected_widget_class=None,
        placements=(
            ControlPlacement('Video', 'source'),
            ControlPlacement('Background Extraction', 'tools'),
            ControlPlacement('Additional Background Colors · R5e5-A', 'options'),
            ControlPlacement('Structural Refinement · R5e5-B', 'options'),
            ControlPlacement('Alpha / Chroma Profiles', 'options'),
            ControlPlacement('Selected Frames', 'options'),
            ControlPlacement('R1 Export', 'output'),
        ),
        preferred_left_section='Tools',
        preferred_right_section='Output',
        collapse_legacy_control_columns=True,
        hidden_button_texts=(
            'Go to Project →',
            'Go to Generate →',
            'Go to Clean-up R3b →',
            'Go to R2 Alignment →',
            'Analyze and Try R3 Selection →',
            'Go to Export Studio R5e4 →',
        ),
    ),
    'smart_selection': CreateRouteControlPlan(
        route_id='smart_selection',
        source_file='app/smart_selection_studio.py',
        expected_widget_class='SmartSelectionStudio',
        placements=(
            ControlPlacement('Range and Profile', 'tools'),
        ),
        preferred_left_section='Tools',
        preferred_right_section='Configurations',
    ),
    'cleanup': CreateRouteControlPlan(
        route_id='cleanup',
        source_file='app/cleanup_studio.py',
        expected_widget_class='CleanupStudio',
        placements=(
            ControlPlacement('Clean-up alpha', 'tools'),
            ControlPlacement('Pixel painter', 'tools'),
            ControlPlacement('Selections and Propagation · R5e5-D', 'options'),
        ),
        preferred_left_section='Tools',
        preferred_right_section='Configurations',
        collapse_legacy_control_columns=True,
    ),
    'alignment': CreateRouteControlPlan(
        route_id='alignment',
        source_file='app/alignment_studio.py',
        expected_widget_class='AlignmentStudio',
        placements=(
            ControlPlacement('Current Frame Alignment', 'tools'),
            ControlPlacement('View and Onion Skin', 'options'),
            ControlPlacement('Output Geometry and Global Anchor · R5e2', 'configurations'),
            ControlPlacement('Alignment Profiles', 'configurations'),
            ControlPlacement('Animation and Export', 'output'),
        ),
        preferred_left_section='Tools',
        preferred_right_section='Configurations',
        collapse_legacy_control_columns=True,
    ),
    'character_set': CreateRouteControlPlan(
        route_id='character_set',
        source_file='app/character_set_workspace.py',
        expected_widget_class='CharacterSetWorkspace',
        placements=(
            ControlPlacement('Subject Logical Layers', 'tools'),
            ControlPlacement('Layer Assets by Direction', 'configurations'),
        ),
        preferred_left_section='Tools',
        preferred_right_section='Configurations',
    ),
    'export': CreateRouteControlPlan(
        route_id='export',
        source_file='app/export_studio.py',
        expected_widget_class='ExportStudio',
        placements=(
            ControlPlacement('Export Profiles', 'configurations'),
            ControlPlacement('Source and Destination', 'configurations'),
            ControlPlacement('Outputs to Generate', 'output'),
            ControlPlacement('Final Resolution and Background', 'output'),
        ),
        preferred_left_section='Source',
        preferred_right_section='Configurations',
    ),
}


def control_plan_for_route(route_id: str) -> CreateRouteControlPlan:
    normalized = str(route_id).strip()
    try:
        return CREATE_ROUTE_CONTROL_PLANS[normalized]
    except KeyError as exc:
        raise KeyError(f'No P2-G CREATE control plan for route: {route_id}') from exc


def validate_control_plans() -> tuple[str, ...]:
    expected_routes = {
        'spritesheet',
        'extraction',
        'smart_selection',
        'cleanup',
        'alignment',
        'character_set',
        'export',
    }
    actual_routes = set(CREATE_ROUTE_CONTROL_PLANS)
    if actual_routes != expected_routes:
        missing = sorted(expected_routes - actual_routes)
        extra = sorted(actual_routes - expected_routes)
        raise ValueError(f'Invalid P2-G route coverage; missing={missing}, extra={extra}')

    for route_id, plan in CREATE_ROUTE_CONTROL_PLANS.items():
        if route_id != plan.route_id:
            raise ValueError(f'P2-G route key mismatch for {route_id}')
        if not plan.placements:
            raise ValueError(f'P2-G route {route_id} has no audited controls.')
        titles = plan.titles()
        if len(set(titles)) != len(titles):
            raise ValueError(f'P2-G route {route_id} contains duplicate control titles.')
        if any(not title.strip() for title in titles):
            raise ValueError(f'P2-G route {route_id} contains an empty control title.')

    return tuple(sorted(actual_routes))


validate_control_plans()
