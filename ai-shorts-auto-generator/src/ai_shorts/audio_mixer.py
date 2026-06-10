from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .ffmpeg_renderer import ffmpeg_setup_guide, find_ffmpeg
from .state import now_iso, read_json, write_json


def mix_audio_into_video(project_id: str, project_dir: Path) -> dict[str, Any]:
    audio_dir = project_dir / "renders" / "audio"
    preview_dir = project_dir / "renders" / "preview"
    final_dir = project_dir / "renders" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    audio_manifest = read_json(audio_dir / "audio_manifest.json", {})
    mp4_status = read_json(preview_dir / "mp4_status.json", {})
    if audio_manifest.get("status") != "audio_ready":
        return _write_status(audio_dir, {"status": "audio_not_ready", "next_step": "오디오 게이트를 먼저 통과시키세요."})
    if mp4_status.get("status") != "mp4_ready" or not Path(str(mp4_status.get("mp4_path") or "")).exists():
        return _write_status(audio_dir, {"status": "mp4_not_ready", "next_step": "MP4 렌더를 먼저 완료하세요."})

    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        ffmpeg_setup_guide(project_dir)
        return _write_status(audio_dir, {"status": "ffmpeg_missing", "next_step": "ffmpeg 설치 후 오디오 믹싱을 다시 실행하세요."})

    tracks = _audio_tracks(audio_manifest)
    if not tracks:
        return _write_status(audio_dir, {"status": "audio_tracks_missing", "next_step": "음성 파일을 등록한 뒤 다시 실행하세요."})

    mixed_audio = audio_dir / "mixed_audio.m4a"
    final_video = final_dir / "final_preview.mp4"
    mix_command = _mix_command(ffmpeg_path, tracks, mixed_audio)
    mix_result = subprocess.run(mix_command, capture_output=True, text=True, timeout=180)
    if mix_result.returncode != 0:
        return _write_status(
            audio_dir,
            {
                "status": "audio_mix_failed",
                "stderr": mix_result.stderr[-2000:],
                "mix_command": _redact_command(mix_command),
                "next_step": "오디오 파일 형식과 ffmpeg 설치 상태를 확인하세요.",
            },
        )

    mux_command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(mp4_status["mp4_path"]),
        "-i",
        str(mixed_audio),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(final_video),
    ]
    mux_result = subprocess.run(mux_command, capture_output=True, text=True, timeout=180)
    if mux_result.returncode != 0:
        return _write_status(
            audio_dir,
            {
                "status": "video_mux_failed",
                "stderr": mux_result.stderr[-2000:],
                "mix_command": _redact_command(mix_command),
                "mux_command": _redact_command(mux_command),
                "next_step": "MP4와 mixed_audio.m4a를 확인한 뒤 다시 실행하세요.",
            },
        )

    return _write_status(
        audio_dir,
        {
            "project_id": project_id,
            "status": "final_video_ready",
            "created_at": now_iso(),
            "mixed_audio_path": str(mixed_audio),
            "final_video_path": str(final_video),
            "source_video_path": str(mp4_status["mp4_path"]),
            "source_audio_manifest": str(audio_dir / "audio_manifest.json"),
            "mix_command": _redact_command(mix_command),
            "mux_command": _redact_command(mux_command),
            "no_paid_api_calls": True,
            "public_upload_automation": "disabled",
            "next_step": "final_preview.mp4를 사람이 들어보고 최종 미디어 패키지를 생성하세요.",
        },
    )


def _audio_tracks(audio_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    for role in ["voice", "bgm"]:
        track = audio_manifest.get(role, {})
        if isinstance(track, dict) and track.get("copied_path"):
            tracks.append(track)
    for track in audio_manifest.get("sfx", []):
        if isinstance(track, dict) and track.get("copied_path"):
            tracks.append(track)
    return tracks


def _mix_command(ffmpeg_path: str, tracks: list[dict[str, Any]], output_path: Path) -> list[str]:
    command = [ffmpeg_path, "-y"]
    filters: list[str] = []
    labels: list[str] = []
    for idx, track in enumerate(tracks):
        command.extend(["-i", str(track["copied_path"])])
        label = f"a{idx}"
        labels.append(f"[{label}]")
        volume = max(0.0, min(1.0, float(track.get("volume_pct", 100)) / 100.0))
        filters.append(f"[{idx}:a]volume={volume:.2f}[{label}]")
    if len(tracks) == 1:
        filters.append(f"{labels[0]}anull[mix]")
    else:
        filters.append("".join(labels) + f"amix=inputs={len(tracks)}:duration=first:dropout_transition=0[mix]")
    command.extend(["-filter_complex", ";".join(filters), "-map", "[mix]", "-c:a", "aac", "-b:a", "192k", str(output_path)])
    return command


def _write_status(audio_dir: Path, status: dict[str, Any]) -> dict[str, Any]:
    payload = {"created_at": now_iso(), **status}
    write_json(audio_dir / "audio_mix_status.json", payload)
    return payload


def _redact_command(command: list[str]) -> list[str]:
    return [str(item) for item in command]
