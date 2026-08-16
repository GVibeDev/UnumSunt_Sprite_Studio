from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.runtime_paths import roaming_config_root


SUPPORTED_PROFILE_KINDS = ('chroma', 'alignment', 'generation', 'export', 'pipeline', 'prompt')


class ProfilesStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self.default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def default_path() -> Path:
        return roaming_config_root() / 'profiles.json'

    def _empty_data(self) -> dict[str, Any]:
        return {
            'version': 'R5c3',
            'profiles': {kind: {} for kind in SUPPORTED_PROFILE_KINDS},
            'last_used': {kind: None for kind in SUPPORTED_PROFILE_KINDS},
            'app_state': None,
        }

    def _load_data(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_data()
        try:
            payload = json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:
            return self._empty_data()
        data = self._empty_data()
        if isinstance(payload, dict):
            profiles = payload.get('profiles')
            if isinstance(profiles, dict):
                for kind in SUPPORTED_PROFILE_KINDS:
                    if isinstance(profiles.get(kind), dict):
                        data['profiles'][kind] = profiles[kind]
            last_used = payload.get('last_used')
            if isinstance(last_used, dict):
                for kind in SUPPORTED_PROFILE_KINDS:
                    if isinstance(last_used.get(kind), dict) or last_used.get(kind) is None:
                        data['last_used'][kind] = last_used.get(kind)
            app_state = payload.get('app_state')
            if isinstance(app_state, dict) or app_state is None:
                data['app_state'] = app_state
        return data

    def _save_data(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

    def list_profiles(self, kind: str) -> list[str]:
        data = self._load_data()
        profiles = data['profiles'].get(kind, {})
        if not isinstance(profiles, dict):
            return []
        return sorted(str(name) for name in profiles.keys())

    def get_profile(self, kind: str, name: str) -> dict[str, Any] | None:
        data = self._load_data()
        profiles = data['profiles'].get(kind, {})
        value = profiles.get(name)
        if isinstance(value, dict):
            return deepcopy(value)
        return None

    def set_profile(self, kind: str, name: str, value: dict[str, Any]) -> None:
        data = self._load_data()
        data['profiles'].setdefault(kind, {})[name] = deepcopy(value)
        self._save_data(data)

    def delete_profile(self, kind: str, name: str) -> None:
        data = self._load_data()
        profiles = data['profiles'].setdefault(kind, {})
        profiles.pop(name, None)
        self._save_data(data)

    def get_last_used(self, kind: str) -> dict[str, Any] | None:
        data = self._load_data()
        value = data['last_used'].get(kind)
        if isinstance(value, dict):
            return deepcopy(value)
        return None

    def set_last_used(self, kind: str, value: dict[str, Any]) -> None:
        data = self._load_data()
        data['last_used'][kind] = deepcopy(value)
        self._save_data(data)

    def get_app_state(self) -> dict[str, Any] | None:
        data = self._load_data()
        value = data.get('app_state')
        if isinstance(value, dict):
            return deepcopy(value)
        return None

    def set_app_state(self, value: dict[str, Any]) -> None:
        data = self._load_data()
        data['app_state'] = deepcopy(value)
        self._save_data(data)
