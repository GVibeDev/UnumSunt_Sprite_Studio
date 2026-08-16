from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from app.profile_store import ProfilesStore
from app.version import APP_VERSION


PROMPT_PROFILE_SCHEMA = 'unum-sunt-prompt-profile-v1'

ACTIONS = ('Idle', 'Walk', 'Run', 'Attack', 'Interaction', 'Hurt', 'Death', 'Custom')
DIRECTIONS = ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW')
MOTIONS = ('Static', 'Subtle', 'Moderate', 'Strong')
CAMERAS = ('Fixed', 'Fixed isometric', 'Fixed 3/4')
IDENTITY_LEVELS = ('Normal', 'Strict', 'Very strict')
BACKGROUNDS = ('Green chroma', 'Magenta chroma', 'Black', 'Custom')
OUTPUT_PURPOSES = ('Sprite extraction', 'Concept animation', 'Motion reference')

CONSTRAINT_KEYS = (
    'preserve_face',
    'preserve_hairstyle',
    'preserve_outfit',
    'preserve_equipment',
    'preserve_body_proportions',
    'keep_full_body_visible',
    'keep_subject_centered',
    'no_camera_movement',
    'no_scene_change',
    'no_additional_objects',
    'flat_background',
)

DEFAULT_CONSTRAINTS = {
    'preserve_face': True,
    'preserve_hairstyle': True,
    'preserve_outfit': True,
    'preserve_equipment': True,
    'preserve_body_proportions': True,
    'keep_full_body_visible': True,
    'keep_subject_centered': True,
    'no_camera_movement': True,
    'no_scene_change': True,
    'no_additional_objects': True,
    'flat_background': True,
}

_ACTION_BLOCKS = {
    'Idle': 'The character performs a controlled idle animation with minimal body motion and a stable stance.',
    'Walk': 'The character performs a clean, readable walk cycle at a steady pace.',
    'Run': 'The character performs a clean, readable run cycle with consistent stride and body orientation.',
    'Attack': 'The character performs one clear attack action, returning to a readable recovery pose.',
    'Interaction': 'The character performs one clear interaction action with controlled, readable movement.',
    'Hurt': 'The character performs a brief hurt reaction while preserving identity and body readability.',
    'Death': 'The character performs a readable death animation without camera or scene changes.',
}

_DIRECTION_BLOCKS = {
    'N': 'The character faces north.',
    'NE': 'The character faces north-east.',
    'E': 'The character faces east.',
    'SE': 'The character faces south-east.',
    'S': 'The character faces south.',
    'SW': 'The character faces south-west.',
    'W': 'The character faces west.',
    'NW': 'The character faces north-west.',
}

_MOTION_BLOCKS = {
    'Static': 'Motion amplitude is static or nearly static.',
    'Subtle': 'Motion amplitude is subtle and restrained.',
    'Moderate': 'Motion amplitude is moderate and clearly readable.',
    'Strong': 'Motion amplitude is strong but remains controlled and consistent.',
}

_CAMERA_BLOCKS = {
    'Fixed': 'Use a fixed camera with no reframing.',
    'Fixed isometric': 'Use a fixed isometric camera and preserve the same projection throughout.',
    'Fixed 3/4': 'Use a fixed three-quarter camera and preserve the same projection throughout.',
}

_IDENTITY_BLOCKS = {
    'Normal': 'Preserve the subject identity and overall visual design.',
    'Strict': 'Strictly preserve the subject identity, silhouette, clothing and proportions.',
    'Very strict': 'Preserve the subject identity with very strict consistency: face, hairstyle, outfit, equipment, silhouette and body proportions must not drift.',
}

_BACKGROUND_BLOCKS = {
    'Green chroma': 'Use a uniform flat green chroma background.',
    'Magenta chroma': 'Use a uniform flat magenta chroma background.',
    'Black': 'Use a uniform flat black background.',
}

_PURPOSE_BLOCKS = {
    'Sprite extraction': 'The output is intended for sprite extraction, so prioritize clean silhouette separation and frame-to-frame consistency.',
    'Concept animation': 'The output is intended as a concept animation, prioritizing readable motion while preserving identity.',
    'Motion reference': 'The output is intended as motion reference, prioritizing clear body mechanics and consistent framing.',
}

_CONSTRAINT_POSITIVE = {
    'preserve_face': 'Preserve the face.',
    'preserve_hairstyle': 'Preserve the hairstyle.',
    'preserve_outfit': 'Preserve the outfit.',
    'preserve_equipment': 'Preserve all equipment and carried items.',
    'preserve_body_proportions': 'Preserve body proportions.',
    'keep_full_body_visible': 'Keep the full body visible in every frame.',
    'keep_subject_centered': 'Keep the subject centered.',
    'no_camera_movement': 'Do not move the camera.',
    'no_scene_change': 'Do not change the scene.',
    'no_additional_objects': 'Do not introduce additional objects or characters.',
    'flat_background': 'Keep the background flat and uniform.',
}

_CONSTRAINT_NEGATIVE = {
    'preserve_face': 'changed face, altered facial features',
    'preserve_hairstyle': 'changed hairstyle, hair drift',
    'preserve_outfit': 'changed outfit, clothing drift',
    'preserve_equipment': 'missing equipment, changed equipment, extra equipment',
    'preserve_body_proportions': 'body proportion drift, anatomy drift',
    'keep_full_body_visible': 'cropped body, body out of frame, missing feet',
    'keep_subject_centered': 'off-center subject, framing drift',
    'no_camera_movement': 'camera movement, pan, tilt, zoom, dolly, orbit',
    'no_scene_change': 'scene cuts, scene change, background transition',
    'no_additional_objects': 'additional objects, extra characters, background props',
    'flat_background': 'textured background, scenery, gradients, shadows on background',
}

_BASE_NEGATIVE = (
    'identity drift',
    'inconsistent character design',
    'duplicate limbs',
    'extra limbs',
    'missing limbs',
    'motion blur',
    'heavy blur',
)


def _now() -> str:
    return datetime.now().isoformat(timespec='seconds')


def default_builder_state(action: str = 'Walk') -> dict[str, Any]:
    action = action if action in ACTIONS else 'Walk'
    return {
        'action': action,
        'custom_action': '',
        'direction': 'SE',
        'motion': 'Moderate' if action not in {'Idle'} else 'Subtle',
        'camera': 'Fixed isometric',
        'identity_preservation': 'Very strict',
        'background': 'Green chroma',
        'custom_background_rgb': [0, 255, 0],
        'output_purpose': 'Sprite extraction',
        'identity_description': '',
        'constraints': deepcopy(DEFAULT_CONSTRAINTS),
    }


def normalize_builder_state(value: dict[str, Any] | None) -> dict[str, Any]:
    result = default_builder_state()
    if not isinstance(value, dict):
        return result
    for key, allowed in (
        ('action', ACTIONS),
        ('direction', DIRECTIONS),
        ('motion', MOTIONS),
        ('camera', CAMERAS),
        ('identity_preservation', IDENTITY_LEVELS),
        ('background', BACKGROUNDS),
        ('output_purpose', OUTPUT_PURPOSES),
    ):
        candidate = str(value.get(key) or result[key])
        if candidate in allowed:
            result[key] = candidate
    result['custom_action'] = str(value.get('custom_action') or '')
    result['identity_description'] = str(value.get('identity_description') or '')
    rgb = value.get('custom_background_rgb')
    if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
        result['custom_background_rgb'] = [max(0, min(255, int(v))) for v in rgb]
    constraints = value.get('constraints')
    if isinstance(constraints, dict):
        for key in CONSTRAINT_KEYS:
            if key in constraints:
                result['constraints'][key] = bool(constraints[key])
    return result


def background_rgb_for_state(state: dict[str, Any]) -> list[int]:
    normalized = normalize_builder_state(state)
    background = normalized['background']
    if background == 'Green chroma':
        return [0, 255, 0]
    if background == 'Magenta chroma':
        return [255, 0, 255]
    if background == 'Black':
        return [0, 0, 0]
    return list(normalized['custom_background_rgb'])


def compose_prompt(state: dict[str, Any]) -> str:
    s = normalize_builder_state(state)
    blocks: list[str] = []
    identity_description = s['identity_description'].strip()
    if identity_description:
        blocks.append(identity_description.rstrip('. ') + '.')
    blocks.append(_IDENTITY_BLOCKS[s['identity_preservation']])
    if s['action'] == 'Custom':
        custom = s['custom_action'].strip()
        if custom:
            blocks.append(custom.rstrip('. ') + '.')
        else:
            blocks.append('The character performs one clear, controlled custom action.')
    else:
        blocks.append(_ACTION_BLOCKS[s['action']])
    blocks.append(_DIRECTION_BLOCKS[s['direction']])
    blocks.append(_MOTION_BLOCKS[s['motion']])
    blocks.append(_CAMERA_BLOCKS[s['camera']])
    if s['background'] == 'Custom':
        r, g, b = background_rgb_for_state(s)
        blocks.append(f'Use a uniform flat custom background color RGB({r}, {g}, {b}).')
    else:
        blocks.append(_BACKGROUND_BLOCKS[s['background']])
    blocks.append(_PURPOSE_BLOCKS[s['output_purpose']])
    active_constraints = [
        _CONSTRAINT_POSITIVE[key]
        for key in CONSTRAINT_KEYS
        if s['constraints'].get(key, False)
    ]
    if active_constraints:
        blocks.append('Technical constraints: ' + ' '.join(active_constraints))
    return '\n\n'.join(blocks).strip()


def compose_negative_prompt(state: dict[str, Any]) -> str:
    s = normalize_builder_state(state)
    terms: list[str] = list(_BASE_NEGATIVE)
    for key in CONSTRAINT_KEYS:
        if s['constraints'].get(key, False):
            terms.extend(part.strip() for part in _CONSTRAINT_NEGATIVE[key].split(',') if part.strip())
    # preserve order while removing duplicates
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        lowered = term.casefold()
        if lowered not in seen:
            seen.add(lowered)
            unique.append(term)
    return ', '.join(unique)


def build_prompt_profile(
    *,
    name: str,
    builder_state: dict[str, Any],
    positive_prompt: str | None = None,
    negative_prompt: str | None = None,
    builtin: bool = False,
    description: str = '',
) -> dict[str, Any]:
    state = normalize_builder_state(builder_state)
    positive = compose_prompt(state) if positive_prompt is None else str(positive_prompt).strip()
    negative = compose_negative_prompt(state) if negative_prompt is None else str(negative_prompt).strip()
    now = _now()
    return {
        'schema': PROMPT_PROFILE_SCHEMA,
        'application_version': APP_VERSION,
        'name': str(name).strip() or 'Prompt profile',
        'description': str(description).strip(),
        'builder_state': state,
        'positive_prompt': positive,
        'negative_prompt': negative,
        'requested_background_rgb': background_rgb_for_state(state),
        'builtin': bool(builtin),
        'created_at': now,
        'updated_at': now,
    }


def normalize_prompt_profile(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return build_prompt_profile(name='Prompt profile', builder_state=default_builder_state())
    state = normalize_builder_state(value.get('builder_state') if isinstance(value.get('builder_state'), dict) else {})
    return {
        'schema': PROMPT_PROFILE_SCHEMA,
        'application_version': APP_VERSION,
        'name': str(value.get('name') or 'Prompt profile'),
        'description': str(value.get('description') or ''),
        'builder_state': state,
        'positive_prompt': str(value.get('positive_prompt') or compose_prompt(state)),
        'negative_prompt': str(value.get('negative_prompt') or compose_negative_prompt(state)),
        'requested_background_rgb': background_rgb_for_state(state),
        'builtin': bool(value.get('builtin', False)),
        'created_at': str(value.get('created_at') or _now()),
        'updated_at': str(value.get('updated_at') or _now()),
    }


def starter_prompt_profiles() -> dict[str, dict[str, Any]]:
    specs = (
        ('Default Idle', 'Idle', 'Subtle'),
        ('Default Walk', 'Walk', 'Moderate'),
        ('Default Run', 'Run', 'Strong'),
        ('Default Attack', 'Attack', 'Moderate'),
        ('Default Interaction', 'Interaction', 'Moderate'),
    )
    result: dict[str, dict[str, Any]] = {}
    for name, action, motion in specs:
        state = default_builder_state(action)
        state['motion'] = motion
        result[name] = build_prompt_profile(
            name=name,
            builder_state=state,
            builtin=True,
            description='Starter modificabile come punto di partenza; non è un prompt universale.',
        )
    return result


class PromptProfileStore:
    def __init__(self, profiles_store: ProfilesStore | None = None) -> None:
        self.profiles_store = profiles_store or ProfilesStore()
        self.ensure_starters()

    def ensure_starters(self) -> None:
        for name, profile in starter_prompt_profiles().items():
            existing = self.profiles_store.get_profile('prompt', name)
            if existing is None or existing.get('builtin') is True:
                self.profiles_store.set_profile('prompt', name, profile)

    def list_names(self) -> list[str]:
        return self.profiles_store.list_profiles('prompt')

    def get(self, name: str) -> dict[str, Any] | None:
        value = self.profiles_store.get_profile('prompt', name)
        return normalize_prompt_profile(value) if value is not None else None

    def save(self, name: str, profile: dict[str, Any]) -> None:
        clean = normalize_prompt_profile(profile)
        clean['name'] = str(name).strip() or clean['name']
        clean['builtin'] = False
        clean['updated_at'] = _now()
        self.profiles_store.set_profile('prompt', clean['name'], clean)

    def delete(self, name: str) -> None:
        profile = self.get(name)
        if profile and profile.get('builtin'):
            raise ValueError('I profili Prompt Starter integrati non possono essere eliminati.')
        self.profiles_store.delete_profile('prompt', name)
