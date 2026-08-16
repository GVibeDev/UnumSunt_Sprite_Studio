from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.profile_store import ProfilesStore
from app.prompt_builder import (
    PromptProfileStore,
    background_rgb_for_state,
    build_prompt_profile,
    compose_negative_prompt,
    compose_prompt,
    default_builder_state,
    normalize_builder_state,
    starter_prompt_profiles,
)
from app.production_presets import sanitize_pipeline_state_for_preset


class PromptBuilderTests(unittest.TestCase):
    def test_default_walk_prompt_contains_core_blocks(self) -> None:
        state = default_builder_state('Walk')
        prompt = compose_prompt(state)
        self.assertIn('walk cycle', prompt.lower())
        self.assertIn('south-east', prompt.lower())
        self.assertIn('fixed isometric camera', prompt.lower())
        self.assertIn('green chroma background', prompt.lower())
        self.assertIn('sprite extraction', prompt.lower())

    def test_custom_action_is_visible_in_composed_prompt(self) -> None:
        state = default_builder_state('Custom')
        state['custom_action'] = 'Raises the left arm and points forward'
        prompt = compose_prompt(state)
        self.assertIn('Raises the left arm and points forward.', prompt)

    def test_custom_background_rgb_is_normalized_and_composed(self) -> None:
        state = default_builder_state('Idle')
        state['background'] = 'Custom'
        state['custom_background_rgb'] = [-5, 120, 999]
        normalized = normalize_builder_state(state)
        self.assertEqual(normalized['custom_background_rgb'], [0, 120, 255])
        self.assertEqual(background_rgb_for_state(normalized), [0, 120, 255])
        self.assertIn('RGB(0, 120, 255)', compose_prompt(normalized))

    def test_negative_prompt_reflects_enabled_constraints(self) -> None:
        state = default_builder_state('Run')
        negative = compose_negative_prompt(state)
        self.assertIn('camera movement', negative)
        self.assertIn('changed outfit', negative)
        self.assertIn('cropped body', negative)

    def test_disabling_constraint_removes_its_negative_terms(self) -> None:
        state = default_builder_state('Walk')
        state['constraints']['no_camera_movement'] = False
        negative = compose_negative_prompt(state)
        self.assertNotIn('pan', negative.split(', '))
        self.assertNotIn('dolly', negative.split(', '))

    def test_profile_preserves_manual_prompt_edits(self) -> None:
        state = default_builder_state('Attack')
        profile = build_prompt_profile(
            name='attack-custom',
            builder_state=state,
            positive_prompt='Manual positive prompt.',
            negative_prompt='Manual negative prompt.',
        )
        self.assertEqual(profile['positive_prompt'], 'Manual positive prompt.')
        self.assertEqual(profile['negative_prompt'], 'Manual negative prompt.')
        self.assertFalse(profile['builtin'])

    def test_starter_prompt_profiles_cover_required_defaults(self) -> None:
        names = set(starter_prompt_profiles())
        self.assertEqual(
            names,
            {'Default Idle', 'Default Walk', 'Default Run', 'Default Attack', 'Default Interaction'},
        )

    def test_prompt_profile_store_roundtrip_and_builtin_protection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profiles = ProfilesStore(Path(tmp) / 'profiles.json')
            store = PromptProfileStore(profiles)
            self.assertIn('Default Walk', store.list_names())
            with self.assertRaises(ValueError):
                store.delete('Default Walk')
            state = default_builder_state('Hurt')
            profile = build_prompt_profile(name='Hurt strict', builder_state=state)
            store.save('Hurt strict', profile)
            loaded = store.get('Hurt strict')
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded['builder_state']['action'], 'Hurt')
            store.delete('Hurt strict')
            self.assertIsNone(store.get('Hurt strict'))

    def test_production_preset_keeps_prompt_metadata_but_not_group_assets(self) -> None:
        state = default_builder_state('Walk')
        pipeline = {
            'generation': {
                'generation_profile': {
                    'reference_image': 'C:/subject.png',
                    'motion_video': 'C:/motion.mp4',
                    'positive_prompt': 'Final edited prompt',
                    'negative_prompt': 'Final negative',
                    'prompt_profile_name': 'Default Walk',
                    'prompt_builder_state': state,
                    'steps': 20,
                }
            }
        }
        clean = sanitize_pipeline_state_for_preset(pipeline, ['generation'])
        profile = clean['generation']['generation_profile']
        self.assertNotIn('reference_image', profile)
        self.assertNotIn('motion_video', profile)
        self.assertEqual(profile['prompt_profile_name'], 'Default Walk')
        self.assertEqual(profile['prompt_builder_state']['action'], 'Walk')
        self.assertEqual(profile['positive_prompt'], 'Final edited prompt')


if __name__ == '__main__':
    unittest.main()
