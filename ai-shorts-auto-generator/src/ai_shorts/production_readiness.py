from __future__ import annotations

from typing import Any

from .api_keys import api_key_status, configured_api_key_count
from .growth_learning import recent_performance_records
from .paths import APP_STATE_PATH, PROJECTS_DIR
from .project_dashboard import summarize_project_gate
from .state import read_json


def build_production_readiness() -> dict[str, Any]:
    app_state = read_json(APP_STATE_PATH, {"projects": []})
    projects = app_state.get("projects", [])
    gate_counts: dict[str, int] = {}
    ready_projects = 0
    for item in projects:
        project_id = str(item.get("id", ""))
        if not project_id:
            continue
        summary = summarize_project_gate(PROJECTS_DIR / project_id)
        gate = str(summary.get("blocking_gate", "unknown"))
        gate_counts[gate] = gate_counts.get(gate, 0) + 1
        if gate == "complete":
            ready_projects += 1

    growth_records = recent_performance_records(50)
    api_configured = configured_api_key_count()
    blockers = []
    if not projects:
        blockers.append("draft_projects_missing")
    if not growth_records:
        blockers.append("growth_data_missing")
    if api_configured < 5:
        blockers.append("api_keys_incomplete")

    return {
        "overall_status": "ready" if not blockers and ready_projects else "needs_work",
        "project_count": len(projects),
        "ready_project_count": ready_projects,
        "gate_counts": gate_counts,
        "growth_record_count": len(growth_records),
        "api_configured_count": api_configured,
        "api_total_count": 5,
        "api_keys": api_key_status(),
        "blockers": blockers,
        "next_step": _next_step(blockers, gate_counts),
    }


def _next_step(blockers: list[str], gate_counts: dict[str, int]) -> str:
    if "api_keys_incomplete" in blockers:
        return "API 키 준비 섹션에서 Gemini, YouTube, Naver, Kakao 키를 로컬에 저장하세요."
    if "draft_projects_missing" in blockers:
        return "새 쇼츠 초안을 만들거나 주간 계획에서 초안으로 승격하세요."
    if "growth_data_missing" in blockers:
        return "YouTube Studio CSV 또는 수동 성과 기록을 추가하세요."
    if gate_counts:
        first_gate = next(iter(gate_counts.keys()))
        return f"가장 먼저 막힌 제작 게이트를 처리하세요: {first_gate}"
    return "제작 준비도가 양호합니다. 다음 초안 제작 또는 렌더 검토로 진행하세요."
