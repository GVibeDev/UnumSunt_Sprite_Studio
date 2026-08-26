from __future__ import annotations

from dataclasses import dataclass


TAB_ROUTES = (
    'project',
    'generation',
    'extraction',
    'cleanup',
    'alignment',
    'smart_selection',
    'export',
    'production_presets',
    'calibration',
    'prompt_builder',
    'spritesheet',
    'image_generation',
    'workflow',
    'character_set',
)

TAB_SHORT_LABELS = (
    '0 · Project',
    '1 · Generate',
    '2 · Extraction',
    '3 · Clean-up',
    '4 · Alignment',
    '5 · Selection',
    '6 · Export',
    '7 · Preset',
    '8 · Calibration',
    '9 · Prompt',
    '10 · Sprite Sheet',
    '11 · Image Gen',
    '12 · Workflow',
    '13 · Character Set',
)

TAB_TOOLTIPS = (
    'Project and Project Groups',
    'WAN / WanGP video generation',
    'R1 extraction and frame selection',
    'Alpha and mask clean-up',
    'Alignment and output geometry',
    'Smart frame selection',
    'Export Studio',
    'Production Presets',
    'Calibration Lab',
    'Prompt Builder and Prompt Profiles',
    'Sprite Sheet Import / Decompose / Reference Builder',
    'Local image generation',
    'Guided Workflows / Workflow Router',
    'Character Set / Layer Manager',
)


@dataclass(frozen=True)
class ToolbarCommandPolicy:
    contexts: frozenset[str]
    requires_video: bool = False


TOOLBAR_POLICIES: dict[str, ToolbarCommandPolicy] = {
    'new_project': ToolbarCommandPolicy(frozenset({'project'})),
    'save_project': ToolbarCommandPolicy(frozenset({'project', 'workflow', 'character_set'})),
    'open_video': ToolbarCommandPolicy(frozenset({'project', 'generation', 'extraction', 'workflow'})),
    'open_spritesheet': ToolbarCommandPolicy(frozenset({'spritesheet', 'workflow', 'character_set'})),
    'play': ToolbarCommandPolicy(frozenset({'extraction'}), requires_video=True),
    'prev_frame': ToolbarCommandPolicy(frozenset({'extraction'}), requires_video=True),
    'next_frame': ToolbarCommandPolicy(frozenset({'extraction'}), requires_video=True),
    'add_frame': ToolbarCommandPolicy(frozenset({'extraction'}), requires_video=True),
    'remove_frame': ToolbarCommandPolicy(frozenset({'extraction'}), requires_video=True),
    'export_r1': ToolbarCommandPolicy(frozenset({'extraction'}), requires_video=True),
}


def toolbar_command_state(command_id: str, context: str, *, video_open: bool) -> tuple[bool, bool]:
    """Return (visible_in_toolbar, enabled) for a contextual command."""
    policy = TOOLBAR_POLICIES.get(str(command_id))
    if policy is None:
        return False, False
    visible = str(context) in policy.contexts
    enabled = visible and (video_open or not policy.requires_video)
    return visible, enabled


def tab_gradient_colors(count: int, start: tuple[int, int, int] = (112, 126, 144), end: tuple[int, int, int] = (224, 234, 246)) -> list[tuple[int, int, int]]:
    """Generate a restrained dark-to-light RGB progression for tab labels."""
    count = max(0, int(count))
    if count == 0:
        return []
    if count == 1:
        return [tuple(int(v) for v in end)]
    colors: list[tuple[int, int, int]] = []
    for index in range(count):
        t = index / float(count - 1)
        colors.append(tuple(int(round(start[channel] + (end[channel] - start[channel]) * t)) for channel in range(3)))
    return colors
