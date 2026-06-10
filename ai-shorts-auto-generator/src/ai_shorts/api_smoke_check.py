from __future__ import annotations

from typing import Any

from .api_keys import API_CONNECTORS, api_connector_readiness
from .cost_guard import evaluate_api_call
from .paths import DATA_DIR
from .state import now_iso, write_json


SMOKE_CHECK_DIR = DATA_DIR / "api_smoke_checks"
SMOKE_CHECK_PATH = SMOKE_CHECK_DIR / "latest_smoke_checks.json"


def run_api_smoke_check(connector_name: str) -> dict[str, Any]:
    connector = _connector_by_name(connector_name)
    readiness = {item["name"]: item for item in api_connector_readiness()}.get(connector["name"], {})
    guard = evaluate_api_call(connector["name"], 0, f"{connector['name']}_smoke_check")
    if readiness.get("status") != "ready":
        result_status = "missing_keys"
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
    if status == "blocked_by_cost_guard":
        return "비용 차단 설정이 외부 API 호출을 막고 있습니다."
    return "차단기를 통과했습니다. 실제 네트워크 호출 구현 단계에서만 실행하세요."
