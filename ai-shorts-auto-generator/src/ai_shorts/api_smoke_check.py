from __future__ import annotations

from typing import Any

from . import api_keys
from .api_keys import API_CONNECTORS, api_connector_readiness
from .cost_guard import evaluate_api_call
from .paths import DATA_DIR
from .state import now_iso, read_json, write_json


SMOKE_CHECK_DIR = DATA_DIR / "api_smoke_checks"
SMOKE_CHECK_PATH = SMOKE_CHECK_DIR / "latest_smoke_checks.json"

KEY_SHAPE_RULES = {
    "gemini_api_key": {"min_length": 16, "hint": "Gemini key should be a non-empty API key string."},
    "youtube_api_key": {"min_length": 16, "hint": "YouTube Data API key should be a non-empty API key string."},
    "naver_client_id": {"min_length": 6, "hint": "Naver Client ID should be at least 6 characters."},
    "naver_client_secret": {"min_length": 8, "hint": "Naver Client Secret should be at least 8 characters."},
    "kakao_rest_api_key": {"min_length": 16, "hint": "Kakao REST API key should be a non-empty REST API key string."},
}

ENDPOINT_PLANS = {
    "gemini": "Plan only: prepare a zero-cost Gemini metadata/auth check after user approval.",
    "youtube": "Plan only: prepare a YouTube Data API key validation request after user approval.",
    "naver": "Plan only: prepare a Naver Search API credential validation request after user approval.",
    "kakao": "Plan only: prepare a Kakao REST API credential validation request after user approval.",
}


def run_api_smoke_check(connector_name: str) -> dict[str, Any]:
    connector = _connector_by_name(connector_name)
    readiness = {item["name"]: item for item in api_connector_readiness()}.get(connector["name"], {})
    guard = evaluate_api_call(connector["name"], 0, f"{connector['name']}_smoke_check")
    key_validation = _local_key_validation(connector)
    if readiness.get("status") != "ready":
        result_status = "missing_keys"
    elif any(item["status"] != "shape_ok" for item in key_validation):
        result_status = "invalid_key_shape"
    elif not guard.get("allowed"):
        result_status = "blocked_by_cost_guard"
    else:
        result_status = "ready_for_manual_network_test"
    result = {
        "connector": connector["name"],
        "label": connector["label"],
        "checked_at": now_iso(),
        "status": result_status,
        "cost_guard": guard,
        "local_key_validation": key_validation,
        "endpoint_plan": _endpoint_plan(connector["name"]),
        "network_call_executed": False,
        "next_step": _next_step(result_status),
    }
    _save_smoke_result(result)
    return result


def run_all_api_smoke_checks() -> dict[str, Any]:
    results = [run_api_smoke_check(connector["name"]) for connector in API_CONNECTORS]
    return {"checked_at": now_iso(), "results": results}


def _connector_by_name(connector_name: str) -> dict[str, Any]:
    for connector in API_CONNECTORS:
        if connector["name"] == connector_name:
            return connector
    raise ValueError("unknown API connector")


def _save_smoke_result(result: dict[str, Any]) -> None:
    SMOKE_CHECK_DIR.mkdir(parents=True, exist_ok=True)
    write_json(SMOKE_CHECK_PATH, result)


def _next_step(status: str) -> str:
    if status == "missing_keys":
        return "API 키 준비 섹션에서 필수 키를 먼저 저장하세요."
    if status == "invalid_key_shape":
        return "저장된 API 키 형식이 너무 짧거나 비어 있습니다. 실제 키를 다시 확인하세요."
    if status == "blocked_by_cost_guard":
        return "비용 차단 설정이 외부 API 호출을 막고 있습니다."
    return "차단기를 통과했습니다. 실제 네트워크 호출 구현 단계에서만 실행하세요."


def _local_key_validation(connector: dict[str, Any]) -> list[dict[str, Any]]:
    payload = read_json(api_keys.API_KEYS_PATH, {"keys": {}})
    keys = payload.get("keys", {})
    validations = []
    for field_name in connector.get("required", []):
        value = str(keys.get(field_name, "")).strip()
        rule = KEY_SHAPE_RULES.get(field_name, {"min_length": 1, "hint": "Required key should not be empty."})
        min_length = int(rule["min_length"])
        if not value:
            status = "missing"
        elif len(value) < min_length:
            status = "too_short"
        else:
            status = "shape_ok"
        validations.append(
            {
                "field": field_name,
                "status": status,
                "min_length": min_length,
                "configured": bool(value),
                "hint": rule["hint"],
            }
        )
    return validations


def _endpoint_plan(connector_name: str) -> dict[str, Any]:
    return {
        "network_call_enabled": False,
        "estimated_cost_units": 0,
        "description": ENDPOINT_PLANS.get(connector_name, "Plan only: prepare a zero-cost validation step after user approval."),
    }
