from __future__ import annotations

from typing import Any

from .paths import DATA_DIR
from .state import now_iso, read_json, write_json


COST_GUARD_DIR = DATA_DIR / "settings"
COST_GUARD_PATH = COST_GUARD_DIR / "cost_guard.json"

DEFAULT_COST_GUARD = {
    "enabled": True,
    "external_api_calls_allowed": False,
    "paid_api_calls_allowed": False,
    "max_daily_cost_krw": 0,
    "updated_at": "",
}


def load_cost_guard() -> dict[str, Any]:
    stored = read_json(COST_GUARD_PATH, {})
    guard = dict(DEFAULT_COST_GUARD)
    guard.update(stored)
    guard["enabled"] = bool(guard.get("enabled", True))
    guard["external_api_calls_allowed"] = bool(guard.get("external_api_calls_allowed", False))
    guard["paid_api_calls_allowed"] = bool(guard.get("paid_api_calls_allowed", False))
    guard["max_daily_cost_krw"] = int(guard.get("max_daily_cost_krw", 0) or 0)
    return guard


def save_cost_guard(values: dict[str, str]) -> dict[str, Any]:
    COST_GUARD_DIR.mkdir(parents=True, exist_ok=True)
    guard = load_cost_guard()
    guard["enabled"] = True
    guard["external_api_calls_allowed"] = values.get("external_api_calls_allowed", "") == "yes"
    guard["paid_api_calls_allowed"] = False
    guard["max_daily_cost_krw"] = 0
    guard["updated_at"] = now_iso()
    write_json(COST_GUARD_PATH, guard)
    return cost_guard_summary()


def evaluate_api_call(connector: str, estimated_cost_krw: int = 0, purpose: str = "") -> dict[str, Any]:
    guard = load_cost_guard()
    estimated_cost_krw = int(estimated_cost_krw or 0)
    if guard["enabled"] and not guard["external_api_calls_allowed"]:
        return _blocked(connector, estimated_cost_krw, purpose, "external_api_calls_blocked")
    if guard["enabled"] and estimated_cost_krw > 0 and not guard["paid_api_calls_allowed"]:
        return _blocked(connector, estimated_cost_krw, purpose, "paid_api_calls_blocked")
    if guard["enabled"] and estimated_cost_krw > guard["max_daily_cost_krw"]:
        return _blocked(connector, estimated_cost_krw, purpose, "daily_cost_limit_zero")
    return {
        "connector": connector,
        "allowed": True,
        "reason": "allowed_zero_cost_check",
        "estimated_cost_krw": estimated_cost_krw,
        "purpose": purpose,
    }


def cost_guard_summary() -> dict[str, Any]:
    guard = load_cost_guard()
    return {
        **guard,
        "mode": "zero_cost_only" if guard["external_api_calls_allowed"] else "local_only",
        "next_step": (
            "외부 연결 테스트는 허용됐지만 예상 비용 0원 작업만 허용됩니다."
            if guard["external_api_calls_allowed"]
            else "외부 API 호출이 차단되어 있습니다. 로컬 준비도 확인만 가능합니다."
        ),
    }


def _blocked(connector: str, estimated_cost_krw: int, purpose: str, reason: str) -> dict[str, Any]:
    return {
        "connector": connector,
        "allowed": False,
        "reason": reason,
        "estimated_cost_krw": estimated_cost_krw,
        "purpose": purpose,
    }
