from __future__ import annotations

from pathlib import Path
from typing import Any

from .state import read_json


def summarize_project_gate(project_dir: Path) -> dict[str, Any]:
    project = read_json(project_dir / "project.json", {})
    package_dir = project_dir / "exports" / "manual_upload_package"
    render_dir = project_dir / "renders" / "placeholder"
    preview_dir = project_dir / "renders" / "preview"

    compliance = read_json(package_dir / "compliance_report.json", {})
    render_export = read_json(package_dir / "render_export_status.json", {})
    final_upload = read_json(package_dir / "final_upload_checklist.json", {})
    preview_manifest = read_json(preview_dir / "preview_manifest.json", {})
    mp4_status = read_json(preview_dir / "mp4_status.json", {})

    gates = {
        "project_review": project.get("review", {}).get("status") == "approved_for_export",
        "compliance": compliance.get("status") == "pass",
        "render_plan": (render_dir / "render_manifest.json").exists(),
        "gif_preview": preview_manifest.get("status") == "preview_ready" and (preview_dir / "preview.gif").exists(),
        "mp4": mp4_status.get("status") == "mp4_ready" and (preview_dir / "preview.mp4").exists(),
        "render_export": render_export.get("status") == "ready_for_manual_upload",
        "final_upload": final_upload.get("status") == "final_upload_ready",
    }
    order = ["project_review", "compliance", "render_plan", "gif_preview", "mp4", "render_export", "final_upload"]
    blocking_gate = next((name for name in order if not gates[name]), "complete")
    return {
        "project_status": project.get("status", "unknown"),
        "blocking_gate": blocking_gate,
        "gates": gates,
        "next_step": _next_step(blocking_gate, render_export, final_upload),
    }


def _next_step(blocking_gate: str, render_export: dict[str, Any], final_upload: dict[str, Any]) -> str:
    if blocking_gate == "project_review":
        return "검토 결정에서 초안을 승인하거나 수정하세요."
    if blocking_gate == "compliance":
        return "정책 검토 리포트와 출처/자산 메모를 확인하세요."
    if blocking_gate == "render_plan":
        return "렌더 계획을 생성하세요."
    if blocking_gate == "gif_preview":
        return "GIF 미리보기를 생성하세요."
    if blocking_gate == "mp4":
        return "ffmpeg 설치 후 MP4 변환을 완료하세요."
    if blocking_gate == "render_export":
        return str(render_export.get("next_step") or "렌더 승인/export 상태를 검토하세요.")
    if blocking_gate == "final_upload":
        return str(final_upload.get("next_step") or "최종 업로드 체크리스트를 실행하세요.")
    return "모든 게이트가 통과되었습니다."
