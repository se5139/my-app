from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .state import now_iso, read_json, write_json


def build_final_media_package(project_dir: Path) -> dict[str, Any]:
    preview_dir = project_dir / "renders" / "preview"
    subtitle_dir = project_dir / "renders" / "subtitles"
    audio_dir = project_dir / "renders" / "audio"
    package_dir = project_dir / "exports" / "manual_upload_package"
    media_dir = package_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    mp4_status = read_json(preview_dir / "mp4_status.json", {})
    subtitle_manifest = read_json(subtitle_dir / "subtitle_manifest.json", {})
    audio_manifest = read_json(audio_dir / "audio_manifest.json", {})

    copied: dict[str, str] = {}
    missing: list[str] = []

    mp4_path = Path(str(mp4_status.get("mp4_path") or preview_dir / "preview.mp4"))
    if mp4_status.get("status") == "mp4_ready" and mp4_path.exists():
        copied["mp4"] = _copy(mp4_path, media_dir / "preview.mp4")
    else:
        missing.append("mp4_ready")

    for key, filename in [("srt", "subtitles.srt"), ("vtt", "subtitles.vtt")]:
        source = Path(str(subtitle_manifest.get(f"{key}_path") or subtitle_dir / filename))
        if subtitle_manifest.get("status") == "subtitles_ready" and source.exists():
            copied[key] = _copy(source, media_dir / filename)
        else:
            missing.append(f"{key}_subtitle")

    if audio_manifest.get("status") == "audio_ready":
        audio_package_dir = media_dir / "audio"
        copied["audio_manifest"] = _copy(audio_dir / "audio_manifest.json", audio_package_dir / "audio_manifest.json")
        for role in ["voice", "bgm"]:
            track = audio_manifest.get(role, {})
            _copy_audio_track(track, audio_package_dir, copied, role)
        for idx, track in enumerate(audio_manifest.get("sfx", []), start=1):
            _copy_audio_track(track, audio_package_dir, copied, f"sfx_{idx}")
    else:
        missing.append("audio_ready")

    status = "final_media_ready" if not missing else "final_media_incomplete"
    manifest = {
        "status": status,
        "created_at": now_iso(),
        "media_dir": str(media_dir),
        "copied": copied,
        "missing": missing,
        "source_manifests": {
            "mp4_status": str(preview_dir / "mp4_status.json") if mp4_status else "",
            "subtitle_manifest": str(subtitle_dir / "subtitle_manifest.json") if subtitle_manifest else "",
            "audio_manifest": str(audio_dir / "audio_manifest.json") if audio_manifest else "",
        },
        "subtitle_mode": "sidecar",
        "next_step": _next_step(status),
    }
    write_json(package_dir / "final_media_package.json", manifest)
    return manifest


def _copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return str(destination)


def _copy_audio_track(track: Any, audio_package_dir: Path, copied: dict[str, str], role: str) -> None:
    if not isinstance(track, dict):
        return
    copied_path = str(track.get("copied_path") or "")
    if not copied_path:
        return
    source = Path(copied_path)
    if not source.exists():
        return
    copied[f"audio_{role}"] = _copy(source, audio_package_dir / source.name)


def _next_step(status: str) -> str:
    if status == "final_media_ready":
        return "수동 업로드 전 preview.mp4와 SRT/VTT sidecar 자막을 사람이 최종 확인하세요."
    return "최종 미디어 패키지를 만들기 전에 MP4 렌더, SRT/VTT 자막, 로컬 오디오 게이트를 완료하세요."
