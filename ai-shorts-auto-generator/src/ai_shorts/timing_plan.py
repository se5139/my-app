from __future__ import annotations

from pathlib import Path
from typing import Any

from .script_lab import DEFAULT_TARGET_DURATION_SEC, ScriptDraft, normalize_target_duration
from .state import write_json


def build_timing_plan(project_id: str, script: ScriptDraft, project_dir: Path, render_plan_path: Path | None = None) -> dict[str, Any]:
    render_dir = project_dir / "renders" / "placeholder"
    target_duration_sec = normalize_target_duration(script.target_duration_sec)
    scenes = script.to_dict().get("scenes", [])
    scene_count = max(1, len(scenes))
    durations = _scene_durations(target_duration_sec, scene_count)

    timing_scenes = []
    cursor = 0.0
    for idx, scene in enumerate(scenes, start=1):
        duration = durations[idx - 1]
        start_sec = round(cursor, 2)
        end_sec = round(cursor + duration, 2)
        timing_scenes.append(
            {
                "scene_no": idx,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "duration_sec": duration,
                "caption": scene.get("caption", ""),
                "narration": scene.get("narration", ""),
                "subtitle_text": scene.get("caption", ""),
            }
        )
        cursor = end_sec

    plan = {
        "project_id": project_id,
        "status": "timing_ready",
        "target_duration_sec": target_duration_sec,
        "scene_count": len(timing_scenes),
        "total_duration_sec": round(sum(item["duration_sec"] for item in timing_scenes), 2),
        "source_script": str(project_dir / "script_draft.json"),
        "render_plan": str(render_plan_path or render_dir / "render_plan.json"),
        "scenes": timing_scenes,
        "next_step": "Use this plan for SRT/VTT subtitles, audio alignment, and final MP4 rendering.",
    }
    render_dir.mkdir(parents=True, exist_ok=True)
    write_json(render_dir / "timing_plan.json", plan)
    return plan


def _scene_durations(target_duration_sec: int, scene_count: int) -> list[float]:
    target_duration_sec = normalize_target_duration(target_duration_sec or DEFAULT_TARGET_DURATION_SEC)
    scene_count = max(1, scene_count)
    base = round(target_duration_sec / scene_count, 2)
    durations = [base for _ in range(scene_count)]
    drift = round(target_duration_sec - sum(durations), 2)
    durations[-1] = round(durations[-1] + drift, 2)
    return durations
