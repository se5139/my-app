from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .ffmpeg_renderer import ffmpeg_setup_guide, find_ffmpeg
from .state import now_iso, read_json, write_json


def burn_subtitles_into_final_video(project_id: str, project_dir: Path) -> dict[str, Any]:
    subtitle_dir = project_dir / "renders" / "subtitles"
    audio_dir = project_dir / "renders" / "audio"
    final_dir = project_dir / "renders" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    subtitle_manifest = read_json(subtitle_dir / "subtitle_manifest.json", {})
    audio_mix_status = read_json(audio_dir / "audio_mix_status.json", {})
    source_video = Path(str(audio_mix_status.get("final_video_path") or final_dir / "final_preview.mp4"))
    subtitle_path = Path(str(subtitle_manifest.get("srt_path") or subtitle_dir / "subtitles.srt"))

    if audio_mix_status.get("status") != "final_video_ready" or not source_video.exists():
        return _write_status(final_dir, {"status": "final_video_missing", "next_step": "오디오 합성으로 final_preview.mp4를 먼저 생성하세요."})
    if subtitle_manifest.get("status") != "subtitles_ready" or not subtitle_path.exists():
        return _write_status(final_dir, {"status": "subtitles_missing", "next_step": "SRT/VTT 자막을 먼저 생성하고 검토하세요."})

    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        ffmpeg_setup_guide(project_dir)
        return _write_status(final_dir, {"status": "ffmpeg_missing", "next_step": "ffmpeg 설치 후 자막 번인을 다시 실행하세요."})

    output_path = final_dir / "final_burned_subtitles.mp4"
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(source_video),
        "-vf",
        f"subtitles='{_escape_subtitle_filter_path(subtitle_path)}':force_style='Fontsize=48,Outline=2,Shadow=1,Alignment=2,MarginV=110'",
        "-c:a",
        "copy",
        str(output_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if completed.returncode != 0:
        return _write_status(
            final_dir,
            {
                "status": "subtitle_burn_failed",
                "stderr": completed.stderr[-2000:],
                "command": _redact_command(command),
                "next_step": "SRT 경로, 한글 글꼴, ffmpeg subtitles 필터 지원 여부를 확인하세요.",
            },
        )

    return _write_status(
        final_dir,
        {
            "project_id": project_id,
            "status": "subtitle_burn_ready",
            "created_at": now_iso(),
            "source_video_path": str(source_video),
            "subtitle_path": str(subtitle_path),
            "burned_video_path": str(output_path),
            "subtitle_mode": "burned",
            "sidecar_fallback": True,
            "no_paid_api_calls": True,
            "public_upload_automation": "disabled",
            "command": _redact_command(command),
            "next_step": "final_burned_subtitles.mp4를 사람이 확인하고 최종 미디어 패키지를 생성하세요.",
        },
    )


def _write_status(final_dir: Path, status: dict[str, Any]) -> dict[str, Any]:
    payload = {"created_at": now_iso(), **status}
    write_json(final_dir / "subtitle_burn_status.json", payload)
    return payload


def _escape_subtitle_filter_path(path: Path) -> str:
    text = str(path.resolve()).replace("\\", "/")
    return text.replace(":", "\\:").replace("'", "\\'")


def _redact_command(command: list[str]) -> list[str]:
    return [str(item) for item in command]
