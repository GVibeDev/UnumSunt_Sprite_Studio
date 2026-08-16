from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

KREA_LICENSE_URL = "https://www.krea.ai/krea-2-licensing"
KREA_AUP_URL = "https://www.krea.ai/krea-2-use-policy"
KREA_REVIEW_FILENAME = "krea_safety_review.json"


def settings_model_type(settings_template: str | Path | None) -> str:
    if not settings_template:
        return ""
    path = Path(settings_template)
    if not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("model_type", "")).strip().lower()


def krea_policy_applies(settings_template: str | Path | None) -> bool:
    model_type = settings_model_type(settings_template)
    if model_type:
        return "krea" in model_type
    if not settings_template:
        return False
    return "krea" in Path(str(settings_template)).name.lower()


def review_record_path(manifest_path: str | Path | None) -> Path | None:
    if not manifest_path:
        return None
    manifest = Path(manifest_path)
    return manifest.parent / KREA_REVIEW_FILENAME


def write_review_record(*, manifest_path: str | Path | None, image_path: str | Path) -> Path | None:
    target = review_record_path(manifest_path)
    if target is None:
        return None
    payload: dict[str, Any] = {
        "schema": "unum-sunt-krea-manual-review-v1",
        "reviewed": True,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "image_path": str(Path(image_path).resolve()),
        "license_url": KREA_LICENSE_URL,
        "aup_url": KREA_AUP_URL,
        "note": "Local human review gate completed before promotion into the WAN reference pipeline.",
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def has_valid_review_record(*, manifest_path: str | Path | None, image_path: str | Path | None) -> bool:
    if not image_path:
        return False
    target = review_record_path(manifest_path)
    if target is None or not target.is_file():
        return False
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict) or payload.get("reviewed") is not True:
        return False
    try:
        recorded = Path(str(payload.get("image_path", ""))).resolve()
        expected = Path(str(image_path)).resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    return recorded == expected
