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

API_CONNECTORS = [
    {
        "name": "gemini",
        "label": "Gemini 생성",
        "purpose": "대본, 장면 아이디어, 제목 후보 생성",
        "required": ["gemini_api_key"],
    },
    {
        "name": "youtube",
        "label": "YouTube 수집",
        "purpose": "YouTube Data API 기반 영상/채널/성과 수집 준비",
        "required": ["youtube_api_key"],
    },
    {
        "name": "naver",
        "label": "Naver 검색",
        "purpose": "Naver 검색 API 기반 트렌드/자료 조사 준비",
        "required": ["naver_client_id", "naver_client_secret"],
    },
    {
        "name": "kakao",
        "label": "Kakao API",
        "purpose": "Kakao REST API 기반 보조 연동 준비",
        "required": ["kakao_rest_api_key"],
    },
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


def api_connector_readiness(payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    status_by_name = {item["name"]: item for item in api_key_status(payload)}
    readiness = []
    for connector in API_CONNECTORS:
        required = connector["required"]
        missing = [name for name in required if status_by_name.get(name, {}).get("configured") != "yes"]
        readiness.append(
            {
                "name": connector["name"],
                "label": connector["label"],
                "purpose": connector["purpose"],
                "status": "ready" if not missing else "missing_keys",
                "required_keys": required,
                "missing_keys": missing,
                "network_check": "not_run",
                "next_step": "연결 테스트를 실행할 준비가 됐습니다." if not missing else "필수 키를 먼저 저장하세요.",
            }
        )
    return readiness


def _mask_secret(value: str) -> str:
    if not value:
        return "not configured"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"
