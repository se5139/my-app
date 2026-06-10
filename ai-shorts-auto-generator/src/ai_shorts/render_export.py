from __future__ import annotations

from pathlib import Path
from typing import Any

from .state import now_iso, read_json, write_json


VALID_RENDER_DECISIONS = {"ready_for_upload_package", "needs_render_revision", "render_blocked"}


def build_render_export_status(project_dir: Path, decision: str = "needs_render_revision", reviewer_note: str = "") -> dict[str, Any]:
    if decision not in VALID_RENDER_DECISIONS:
        raise ValueError(f"Unknown render export decision: {decision}")

    render_dir = project_dir / "renders" / "placeholder"
    preview_dir = project_dir / "renders" / "preview"
    package_dir = project_dir / "exports" / "manual_upload_package"
    render_manifest = read_json(render_dir / "render_manifest.json", {})
    preview_manifest = read_json(preview_dir / "preview_manifest.json", {})
    mp4_status = read_json(preview_dir / "mp4_status.json", {})
    subtitle_manifest = read_json(project_dir / "renders" / "subtitles" / "subtitle_manifest.json", {})

    timeline_ready = (render_dir / "timeline.html").exists()
    gif_ready = (preview_dir / "preview.gif").exists() and preview_manifest.get("status") == "preview_ready"
    mp4_ready = (preview_dir / "preview.mp4").exists() and mp4_status.get("status") == "mp4_ready"
    timing_plan_ready = (render_dir / "timing_plan.json").exists()
    subtitles_ready = subtitle_manifest.get("status") == "subtitles_ready"

    blockers: list[str] = []
    if not timeline_ready:
        blockers.append("timeline_missing")
    if not gif_ready:
        blockers.append("gif_preview_missing")
    if decision == "ready_for_upload_package" and not gif_ready:
        blockers.append("preview_required_before_upload_package")
    if decision == "ready_for_upload_package" and timing_plan_ready and not subtitles_ready:
        blockers.append("subtitles_required_before_export")
    if decision == "render_blocked":
        blockers.append("human_blocked_render")

    if decision == "ready_for_upload_package" and not blockers:
        package_status = "ready_for_manual_upload" if mp4_ready else "ready_for_upload_package_mp4_pending"
    elif decision == "render_blocked":
        package_status = "blocked"
    else:
        package_status = "needs_revision"

    status = {
        "status": package_status,
        "decision": decision,
        "reviewer_note": reviewer_note.strip(),
        "reviewed_at": now_iso(),
        "assets": {
            "timeline_ready": timeline_ready,
            "gif_ready": gif_ready,
            "mp4_ready": mp4_ready,
            "subtitles_ready": subtitles_ready,
            "timeline_html": str(render_dir / "timeline.html"),
            "preview_gif": str(preview_dir / "preview.gif"),
            "preview_mp4": str(preview_dir / "preview.mp4"),
            "subtitle_manifest": str(project_dir / "renders" / "subtitles" / "subtitle_manifest.json"),
        },
        "source_manifests": {
            "render_manifest": str(render_dir / "render_manifest.json") if render_manifest else "",
            "preview_manifest": str(preview_dir / "preview_manifest.json") if preview_manifest else "",
            "mp4_status": str(preview_dir / "mp4_status.json") if mp4_status else "",
            "subtitle_manifest": str(project_dir / "renders" / "subtitles" / "subtitle_manifest.json") if subtitle_manifest else "",
        },
        "blockers": blockers,
        "next_step": _next_step(package_status, mp4_ready),
    }
    write_json(package_dir / "render_export_status.json", status)
    return status


def _next_step(package_status: str, mp4_ready: bool) -> str:
    if package_status == "ready_for_manual_upload":
        return "Attach the MP4 and complete the manual YouTube upload review."
    if package_status == "ready_for_upload_package_mp4_pending":
        return "GIF/timeline review is approved; install ffmpeg and render MP4 before final upload."
    if package_status == "blocked":
        return "Resolve the render issue before export."
    return "Revise the render or generate missing preview assets before approval."
