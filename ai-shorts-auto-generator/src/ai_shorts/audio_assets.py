from __future__ import annotations

import shutil
import wave
from pathlib import Path
from typing import Any

from .state import now_iso, read_json, write_json


def build_audio_asset_manifest(project_dir: Path, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    inputs = inputs or {}
    audio_dir = project_dir / "renders" / "audio"
    source_dir = audio_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    timing_plan = read_json(project_dir / "renders" / "placeholder" / "timing_plan.json", {})
    target_duration_sec = float(timing_plan.get("total_duration_sec") or inputs.get("target_duration_sec") or 0)
    voice = _collect_track(
        source_dir,
        "voice",
        inputs.get("voice_path", ""),
        inputs.get("voice_source_note", ""),
        inputs.get("voice_duration_sec", ""),
        target_duration_sec,
        required=True,
    )
    bgm = _collect_track(
        source_dir,
        "bgm",
        inputs.get("bgm_path", ""),
        inputs.get("bgm_source_note", ""),
        inputs.get("bgm_duration_sec", ""),
        target_duration_sec,
        required=False,
        volume_pct=inputs.get("bgm_volume_pct", 18),
    )
    sfx_tracks = [
        _collect_track(
            source_dir,
            f"sfx_{idx + 1}",
            path,
            inputs.get("sfx_source_note", ""),
            "",
            target_duration_sec,
            required=False,
            volume_pct=inputs.get("sfx_volume_pct", 35),
        )
        for idx, path in enumerate(_split_paths(inputs.get("sfx_paths", "")))
    ]

    issues: list[str] = []
    issues.extend(voice["issues"])
    issues.extend(bgm["issues"])
    for track in sfx_tracks:
        issues.extend(track["issues"])

    master_volume_pct = _clamp_pct(inputs.get("master_volume_pct", 100), default=100)
    if not 60 <= master_volume_pct <= 100:
        issues.append("master_volume_outside_safe_range")

    manifest = {
        "status": "audio_ready" if not issues else "audio_needs_review",
        "created_at": now_iso(),
        "target_duration_sec": target_duration_sec,
        "voice": voice,
        "bgm": bgm,
        "sfx": sfx_tracks,
        "mix": {
            "mode": "local_files_only",
            "master_volume_pct": master_volume_pct,
            "duck_bgm_under_voice": True,
            "no_paid_api_calls": True,
            "public_upload_automation": "disabled",
        },
        "validation": {
            "valid": not issues,
            "issues": issues,
        },
        "next_step": _next_step(issues),
    }
    write_json(audio_dir / "audio_manifest.json", manifest)
    return manifest


def _collect_track(
    source_dir: Path,
    role: str,
    raw_path: Any,
    source_note: Any,
    raw_duration_sec: Any,
    target_duration_sec: float,
    *,
    required: bool,
    volume_pct: Any = 100,
) -> dict[str, Any]:
    path_text = str(raw_path or "").strip().strip('"')
    note = str(source_note or "").strip()
    issues: list[str] = []
    copied_path = ""
    source_path = ""
    duration_sec = 0.0

    if not path_text:
        if required:
            issues.append(f"{role}_file_missing")
        return {
            "role": role,
            "source_path": "",
            "copied_path": "",
            "source_note": note,
            "duration_sec": duration_sec,
            "volume_pct": _clamp_pct(volume_pct),
            "issues": issues,
        }

    path = Path(path_text).expanduser()
    source_path = str(path)
    if not path.exists() or not path.is_file():
        issues.append(f"{role}_file_not_found")
    else:
        copied_path = _copy_audio(path, source_dir, role)
        duration_sec = _duration_from_wav(path) or _float_value(raw_duration_sec)
        if duration_sec <= 0:
            issues.append(f"{role}_duration_unknown")

    if path_text and not note:
        issues.append(f"{role}_source_note_missing")
    if role == "voice" and target_duration_sec and duration_sec and abs(duration_sec - target_duration_sec) > 3:
        issues.append("voice_duration_mismatch")
    if role == "bgm" and not 5 <= _clamp_pct(volume_pct, default=18) <= 35:
        issues.append("bgm_volume_outside_safe_range")

    return {
        "role": role,
        "source_path": source_path,
        "copied_path": copied_path,
        "source_note": note,
        "duration_sec": round(duration_sec, 3),
        "volume_pct": _clamp_pct(volume_pct, default=18 if role == "bgm" else 100),
        "issues": issues,
    }


def _copy_audio(source: Path, source_dir: Path, role: str) -> str:
    suffix = source.suffix.lower() or ".audio"
    destination = source_dir / f"{role}{suffix}"
    shutil.copy2(source, destination)
    return str(destination)


def _duration_from_wav(path: Path) -> float:
    if path.suffix.lower() != ".wav":
        return 0.0
    try:
        with wave.open(str(path), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            return frames / float(rate) if rate else 0.0
    except (wave.Error, OSError):
        return 0.0


def _split_paths(raw_paths: Any) -> list[str]:
    return [item.strip() for item in str(raw_paths or "").replace(";", "\n").splitlines() if item.strip()]


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clamp_pct(value: Any, default: int = 100) -> int:
    try:
        numeric = int(float(value))
    except (TypeError, ValueError):
        numeric = default
    return max(0, min(100, numeric))


def _next_step(issues: list[str]) -> str:
    if not issues:
        return "오디오 파일, 출처 메모, 길이, 볼륨을 확인했습니다. 최종 렌더 전 사람이 한 번 더 들어보세요."
    if "voice_file_missing" in issues:
        return "로컬 음성 파일을 등록하고 출처/생성 방식 메모를 남기세요."
    if "voice_duration_mismatch" in issues:
        return "음성 길이를 목표 영상 길이에 맞게 조정하세요."
    return "오디오 검증 이슈를 해결한 뒤 다시 오디오 게이트를 실행하세요."
