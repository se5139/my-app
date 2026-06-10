from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .state import now_iso, read_json, write_json


MAX_SUBTITLE_LINE_CHARS = 24
MAX_SUBTITLE_LINES = 2


def create_subtitle_files(project_id: str, project_dir: Path) -> dict[str, Any]:
    render_dir = project_dir / "renders" / "placeholder"
    subtitle_dir = project_dir / "renders" / "subtitles"
    subtitle_dir.mkdir(parents=True, exist_ok=True)

    timing_plan = read_json(render_dir / "timing_plan.json", {})
    if not timing_plan:
        raise FileNotFoundError("timing_plan.json not found. Generate render placeholders first.")

    entries = [_subtitle_entry(scene) for scene in timing_plan.get("scenes", [])]
    validation = _validate_entries(entries, timing_plan)
    srt_path = subtitle_dir / "subtitles.srt"
    vtt_path = subtitle_dir / "subtitles.vtt"
    srt_path.write_text(_render_srt(entries), encoding="utf-8")
    vtt_path.write_text(_render_vtt(entries), encoding="utf-8")

    manifest = {
        "project_id": project_id,
        "status": "subtitles_ready" if validation["valid"] else "subtitles_need_review",
        "created_at": now_iso(),
        "source_timing_plan": str(render_dir / "timing_plan.json"),
        "srt_path": str(srt_path),
        "vtt_path": str(vtt_path),
        "format": ["srt", "vtt"],
        "line_limits": {
            "max_line_chars": MAX_SUBTITLE_LINE_CHARS,
            "max_lines": MAX_SUBTITLE_LINES,
        },
        "validation": validation,
        "entries": entries,
        "next_step": "Review subtitle sync and line breaks before render export.",
    }
    write_json(subtitle_dir / "subtitle_manifest.json", manifest)
    write_json(subtitle_dir / "subtitle_validation.json", validation)
    return manifest


def _subtitle_entry(scene: dict[str, Any]) -> dict[str, Any]:
    text = str(scene.get("subtitle_text") or scene.get("caption") or scene.get("narration") or "").strip()
    lines = _wrap_subtitle(text)
    return {
        "scene_no": int(scene.get("scene_no", 0) or 0),
        "start_sec": float(scene.get("start_sec", 0) or 0),
        "end_sec": float(scene.get("end_sec", 0) or 0),
        "duration_sec": float(scene.get("duration_sec", 0) or 0),
        "text": text,
        "lines": lines,
    }


def _wrap_subtitle(text: str) -> list[str]:
    compact = " ".join(str(text or "").split())
    lines = textwrap.wrap(compact, width=MAX_SUBTITLE_LINE_CHARS, break_long_words=False, replace_whitespace=True)
    if not lines and compact:
        lines = [compact]
    return lines[:MAX_SUBTITLE_LINES] or [""]


def _validate_entries(entries: list[dict[str, Any]], timing_plan: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    previous_end = 0.0
    for entry in entries:
        if entry["end_sec"] <= entry["start_sec"]:
            issues.append(f"scene_{entry['scene_no']}_invalid_time_range")
        if entry["start_sec"] < previous_end:
            issues.append(f"scene_{entry['scene_no']}_overlaps_previous")
        if len(entry["lines"]) > MAX_SUBTITLE_LINES:
            issues.append(f"scene_{entry['scene_no']}_too_many_lines")
        if any(len(line) > MAX_SUBTITLE_LINE_CHARS for line in entry["lines"]):
            issues.append(f"scene_{entry['scene_no']}_line_too_long")
        previous_end = entry["end_sec"]

    total_duration = round(sum(float(entry["duration_sec"]) for entry in entries), 2)
    target_duration = float(timing_plan.get("target_duration_sec", 0) or 0)
    if target_duration and abs(total_duration - target_duration) > 0.05:
        issues.append("subtitle_duration_mismatch")

    return {
        "valid": not issues,
        "issues": issues,
        "entry_count": len(entries),
        "total_duration_sec": total_duration,
        "target_duration_sec": target_duration,
    }


def _render_srt(entries: list[dict[str, Any]]) -> str:
    blocks = []
    for index, entry in enumerate(entries, start=1):
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{_format_srt_time(entry['start_sec'])} --> {_format_srt_time(entry['end_sec'])}",
                    "\n".join(entry["lines"]),
                ]
            )
        )
    return "\n\n".join(blocks) + "\n"


def _render_vtt(entries: list[dict[str, Any]]) -> str:
    blocks = ["WEBVTT", ""]
    for entry in entries:
        blocks.append(f"{_format_vtt_time(entry['start_sec'])} --> {_format_vtt_time(entry['end_sec'])}")
        blocks.append("\n".join(entry["lines"]))
        blocks.append("")
    return "\n".join(blocks)


def _format_srt_time(seconds: float) -> str:
    hours, minutes, secs, millis = _split_time(seconds)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_vtt_time(seconds: float) -> str:
    hours, minutes, secs, millis = _split_time(seconds)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _split_time(seconds: float) -> tuple[int, int, int, int]:
    total_millis = max(0, int(round(float(seconds) * 1000)))
    hours, remainder = divmod(total_millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return hours, minutes, secs, millis
