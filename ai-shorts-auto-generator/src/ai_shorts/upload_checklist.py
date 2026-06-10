from __future__ import annotations

from pathlib import Path
from typing import Any

from .state import now_iso, read_json, write_json


def build_final_upload_checklist(project_dir: Path, reviewer_note: str = "") -> dict[str, Any]:
    package_dir = project_dir / "exports" / "manual_upload_package"
    preview_dir = project_dir / "renders" / "preview"
    subtitle_dir = project_dir / "renders" / "subtitles"
    compliance = read_json(package_dir / "compliance_report.json", {})
    render_export = read_json(package_dir / "render_export_status.json", {})
    final_media_package = read_json(package_dir / "final_media_package.json", {})
    asset_notes = read_json(package_dir / "asset_source_notes.json", {})
    project = read_json(project_dir / "project.json", {})
    subtitle_manifest = read_json(subtitle_dir / "subtitle_manifest.json", {})

    checks = {
        "human_project_review": project.get("review", {}).get("status") == "approved_for_export",
        "compliance_passed": compliance.get("status") == "pass",
        "asset_source_notes_present": (package_dir / "asset_source_notes.json").exists() and isinstance(asset_notes, dict),
        "subtitles_ready": subtitle_manifest.get("status") == "subtitles_ready",
        "final_media_ready": final_media_package.get("status") == "final_media_ready",
        "render_export_ready": render_export.get("status") == "ready_for_manual_upload",
        "mp4_present": (preview_dir / "preview.mp4").exists(),
        "title_present": _has_text(package_dir / "title.txt"),
        "description_present": _has_text(package_dir / "description.txt"),
        "tags_present": _has_text(package_dir / "tags.txt"),
    }
    missing = [name for name, passed in checks.items() if not passed]
    status = "final_upload_ready" if not missing else "blocked_before_upload"
    checklist = {
        "status": status,
        "reviewer_note": reviewer_note.strip(),
        "checked_at": now_iso(),
        "checks": checks,
        "missing": missing,
        "manual_upload_allowed": status == "final_upload_ready",
        "public_upload_automation": "disabled",
        "next_step": _next_step(missing),
    }
    write_json(package_dir / "final_upload_checklist.json", checklist)
    return checklist


def _has_text(path: Path) -> bool:
    return path.exists() and bool(path.read_text(encoding="utf-8").strip())


def _next_step(missing: list[str]) -> str:
    if not missing:
        return "All gates passed. Manual upload may proceed after a final human check."
    if "mp4_present" in missing:
        return "Create preview.mp4 before final manual upload."
    if "subtitles_ready" in missing:
        return "Create and review SRT/VTT subtitles before final manual upload."
    if "final_media_ready" in missing:
        return "Package preview.mp4 with sidecar SRT/VTT subtitles before final manual upload."
    if "compliance_passed" in missing:
        return "Resolve compliance findings before final upload."
    if "human_project_review" in missing:
        return "Approve the project review before final upload."
    return "Complete every missing checklist item before manual upload."
