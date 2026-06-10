from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .audio_assets import build_audio_asset_manifest
from .audio_mixer import mix_audio_into_video
from .package_exporter import export_manual_upload_package
from .final_media_package import build_final_media_package
from .ffmpeg_renderer import ffmpeg_setup_guide, mp4_status, render_mp4_from_preview
from .paths import PROJECTS_DIR, ensure_data_dirs
from .render_export import build_render_export_status
from .render_placeholder import create_render_placeholders
from .render_preview import create_preview_media
from .script_lab import create_local_script_draft, normalize_target_duration, script_draft_from_dict
from .subtitle_burner import burn_subtitles_into_final_video
from .state import ShortProject, create_project, load_app_state, now_iso, read_json, save_app_state, write_json
from .subtitle_export import create_subtitle_files
from .upload_checklist import build_final_upload_checklist


def create_draft_package(topic: str, source_notes: str = "", target_duration_sec: int = 45) -> dict[str, Any]:
    ensure_data_dirs()
    project = create_project(topic, source_notes)
    script = create_local_script_draft(topic, source_notes, normalize_target_duration(target_duration_sec))
    project_dir = PROJECTS_DIR / project.id
    write_json(project_dir / "script_draft.json", script.to_dict())
    export = export_manual_upload_package(project, script)
    return {"project": asdict(project), "script": script.to_dict(), "export": export}


def update_draft_script(project_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    ensure_data_dirs()
    project_dir = PROJECTS_DIR / project_id
    project_data = read_json(project_dir / "project.json", {})
    if not project_data:
        raise FileNotFoundError(f"Project not found: {project_id}")
    script_data = read_json(project_dir / "script_draft.json", {})
    if not script_data:
        raise FileNotFoundError(f"Script draft not found: {project_id}")

    script = script_draft_from_dict(script_data)
    script.title = str(updates.get("title", script.title)).strip() or script.title
    script.hook = str(updates.get("hook", script.hook)).strip() or script.hook
    script.thumbnail_text = str(updates.get("thumbnail_text", script.thumbnail_text)).strip() or script.thumbnail_text
    script.narration = str(updates.get("narration", script.narration)).strip() or script.narration
    script.target_duration_sec = normalize_target_duration(updates.get("target_duration_sec", script.target_duration_sec))

    scene_captions = updates.get("scene_captions", [])
    for idx, caption in enumerate(scene_captions):
        if idx < len(script.scenes):
            script.scenes[idx].caption = str(caption).strip() or script.scenes[idx].caption

    timestamp = now_iso()
    project_data["title"] = script.title
    project_data["status"] = "needs_review"
    project_data["updated_at"] = timestamp
    project_data["review"] = {
        "status": "needs_review",
        "reviewer_note": "대본이 수정되어 다시 검토가 필요합니다.",
        "reviewed_at": timestamp,
    }

    write_json(project_dir / "project.json", project_data)
    write_json(project_dir / "script_draft.json", script.to_dict())

    project = ShortProject(**project_data)
    export = export_manual_upload_package(project, script)

    state = load_app_state()
    for item in state.projects:
        if item.get("id") == project_id:
            item["title"] = script.title
            item["status"] = "needs_review"
            item["updated_at"] = timestamp
            break
    save_app_state(state)

    return {"project": project_data, "script": script.to_dict(), "export": export}


def generate_placeholder_render(project_id: str) -> dict[str, Any]:
    ensure_data_dirs()
    project_dir = PROJECTS_DIR / project_id
    project_data = read_json(project_dir / "project.json", {})
    if not project_data:
        raise FileNotFoundError(f"Project not found: {project_id}")
    script_data = read_json(project_dir / "script_draft.json", {})
    if not script_data:
        raise FileNotFoundError(f"Script draft not found: {project_id}")
    script = script_draft_from_dict(script_data)
    return create_render_placeholders(project_id, script, project_dir)


def generate_preview_render(project_id: str) -> dict[str, Any]:
    ensure_data_dirs()
    project_dir = PROJECTS_DIR / project_id
    if not read_json(project_dir / "project.json", {}):
        raise FileNotFoundError(f"Project not found: {project_id}")
    if not (project_dir / "renders" / "placeholder" / "render_plan.json").exists():
        generate_placeholder_render(project_id)
    return create_preview_media(project_id, project_dir)


def generate_subtitle_export(project_id: str) -> dict[str, Any]:
    ensure_data_dirs()
    project_dir = PROJECTS_DIR / project_id
    if not read_json(project_dir / "project.json", {}):
        raise FileNotFoundError(f"Project not found: {project_id}")
    if not (project_dir / "renders" / "placeholder" / "timing_plan.json").exists():
        generate_placeholder_render(project_id)
    return create_subtitle_files(project_id, project_dir)


def prepare_audio_assets(project_id: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_data_dirs()
    project_dir = PROJECTS_DIR / project_id
    if not read_json(project_dir / "project.json", {}):
        raise FileNotFoundError(f"Project not found: {project_id}")
    if not (project_dir / "renders" / "placeholder" / "timing_plan.json").exists():
        generate_placeholder_render(project_id)
    return build_audio_asset_manifest(project_dir, inputs)


def check_or_render_mp4(project_id: str, render: bool = False) -> dict[str, Any]:
    ensure_data_dirs()
    project_dir = PROJECTS_DIR / project_id
    if not read_json(project_dir / "project.json", {}):
        raise FileNotFoundError(f"Project not found: {project_id}")
    if not (project_dir / "renders" / "preview" / "preview_manifest.json").exists():
        generate_preview_render(project_id)
    if render:
        if not (project_dir / "renders" / "subtitles" / "subtitle_manifest.json").exists():
            generate_subtitle_export(project_id)
        return render_mp4_from_preview(project_id, project_dir)
    return mp4_status(project_dir)


def mix_audio_for_video(project_id: str) -> dict[str, Any]:
    ensure_data_dirs()
    project_dir = PROJECTS_DIR / project_id
    if not read_json(project_dir / "project.json", {}):
        raise FileNotFoundError(f"Project not found: {project_id}")
    return mix_audio_into_video(project_id, project_dir)


def burn_subtitles_for_video(project_id: str) -> dict[str, Any]:
    ensure_data_dirs()
    project_dir = PROJECTS_DIR / project_id
    if not read_json(project_dir / "project.json", {}):
        raise FileNotFoundError(f"Project not found: {project_id}")
    return burn_subtitles_into_final_video(project_id, project_dir)


def package_final_media(project_id: str) -> dict[str, Any]:
    ensure_data_dirs()
    project_dir = PROJECTS_DIR / project_id
    if not read_json(project_dir / "project.json", {}):
        raise FileNotFoundError(f"Project not found: {project_id}")
    return build_final_media_package(project_dir)


def create_ffmpeg_setup_guide(project_id: str) -> dict[str, Any]:
    ensure_data_dirs()
    project_dir = PROJECTS_DIR / project_id
    if not read_json(project_dir / "project.json", {}):
        raise FileNotFoundError(f"Project not found: {project_id}")
    return ffmpeg_setup_guide(project_dir)


def update_render_export_review(project_id: str, decision: str, reviewer_note: str = "") -> dict[str, Any]:
    ensure_data_dirs()
    project_dir = PROJECTS_DIR / project_id
    project_path = project_dir / "project.json"
    project_data = read_json(project_path, {})
    if not project_data:
        raise FileNotFoundError(f"Project not found: {project_id}")

    status = build_render_export_status(project_dir, decision, reviewer_note)
    timestamp = now_iso()
    project_data["render_review"] = status
    project_data["updated_at"] = timestamp
    if status["status"] in {"ready_for_manual_upload", "ready_for_upload_package_mp4_pending", "blocked", "needs_revision"}:
        project_data["status"] = status["status"]
    write_json(project_path, project_data)

    state = load_app_state()
    for item in state.projects:
        if item.get("id") == project_id:
            item["status"] = project_data["status"]
            item["updated_at"] = timestamp
            break
    save_app_state(state)
    return status


def update_final_upload_checklist(project_id: str, reviewer_note: str = "") -> dict[str, Any]:
    ensure_data_dirs()
    project_dir = PROJECTS_DIR / project_id
    project_path = project_dir / "project.json"
    project_data = read_json(project_path, {})
    if not project_data:
        raise FileNotFoundError(f"Project not found: {project_id}")

    checklist = build_final_upload_checklist(project_dir, reviewer_note)
    timestamp = now_iso()
    project_data["final_upload_checklist"] = checklist
    project_data["updated_at"] = timestamp
    project_data["status"] = checklist["status"]
    write_json(project_path, project_data)

    state = load_app_state()
    for item in state.projects:
        if item.get("id") == project_id:
            item["status"] = checklist["status"]
            item["updated_at"] = timestamp
            break
    save_app_state(state)
    return checklist
