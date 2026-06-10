from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .state import now_iso, read_json, write_json


def build_final_media_package(project_dir: Path) -> dict[str, Any]:
    preview_dir = project_dir / "renders" / "preview"
    subtitle_dir = project_dir / "renders" / "subtitles"
    package_dir = project_dir / "exports" / "manual_upload_package"
    media_dir = package_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    mp4_status = read_json(preview_dir / "mp4_status.json", {})
    subtitle_manifest = read_json(subtitle_dir / "subtitle_manifest.json", {})

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


def _next_step(status: str) -> str:
    if status == "final_media_ready":
        return "수동 업로드 전 preview.mp4와 SRT/VTT sidecar 자막을 사람이 최종 확인하세요."
    return "최종 미디어 패키지를 만들기 전에 MP4 렌더와 SRT/VTT 자막 생성을 완료하세요."
