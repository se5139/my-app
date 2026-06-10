from __future__ import annotations

from typing import Any

from .paths import DATA_DIR
from .state import now_iso, read_json, write_json


SECRETS_DIR = DATA_DIR / "secrets"
API_KEYS_PATH = SECRETS_DIR / "api_keys.json"

API_KEY_FIELDS = [
    {"name": "gemini_api_key", "label": "Gemini 생성용 키"},
    {"name": "youtube_api_key", "label": "YouTube 수집용 키"},
    {"name": "naver_client_id", "label": "Naver Client ID"},
    {"name": "naver_client_secret", "label": "Naver Client Secret"},
    {"name": "kakao_rest_api_key", "label": "Kakao REST API 키"},
]


def save_api_keys(values: dict[str, str]) -> dict[str, Any]:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    current = read_json(API_KEYS_PATH, {"keys": {}})
    keys = dict(current.get("keys", {}))
    updated = []
    for field in API_KEY_FIELDS:
        name = field["name"]
        value = values.get(name, "").strip()
        if value:
            keys[name] = value
            updated.append(name)
    payload = {"updated_at": now_iso(), "keys": keys}
    write_json(API_KEYS_PATH, payload)
    return {"updated": updated, "status": api_key_status(payload)}


def api_key_status(payload: dict[str, Any] | None = None) -> list[dict[str, str]]:
    payload = payload or read_json(API_KEYS_PATH, {"keys": {}})
    keys = payload.get("keys", {})
    status = []
    for field in API_KEY_FIELDS:
        value = str(keys.get(field["name"], ""))
        status.append(
            {
                "name": field["name"],
                "label": field["label"],
                "configured": "yes" if bool(value) else "no",
                "masked": _mask_secret(value),
            }
        )
    return status


def configured_api_key_count() -> int:
    return sum(1 for item in api_key_status() if item["configured"] == "yes")


def _mask_secret(value: str) -> str:
    if not value:
        return "not configured"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"
