from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from .script_lab import ScriptDraft
from .state import write_json


WIDTH = 1080
HEIGHT = 1920


def _wrap_text(text: str, width: int = 18, max_lines: int = 5) -> list[str]:
    compact = " ".join(str(text or "").split())
    lines = textwrap.wrap(compact, width=width, break_long_words=False, replace_whitespace=True)
    return lines[:max_lines] or [""]


def _svg_text_block(lines: list[str], x: int, y: int, size: int, color: str = "#ffffff", weight: str = "700") -> str:
    tspans = []
    for idx, line in enumerate(lines):
        dy = 0 if idx == 0 else int(size * 1.35)
        tspans.append(f'<tspan x="{x}" dy="{dy}">{escape(line)}</tspan>')
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" font-family="Malgun Gothic, Arial, sans-serif">{"".join(tspans)}</text>'


def _scene_svg(scene: dict[str, Any], title: str, scene_no: int, total: int) -> str:
    caption_lines = _wrap_text(str(scene.get("caption", "")), width=14, max_lines=4)
    direction_lines = _wrap_text(str(scene.get("visual_direction", "")), width=26, max_lines=5)
    narration_lines = _wrap_text(str(scene.get("narration", "")), width=24, max_lines=4)
    title_lines = _wrap_text(title, width=20, max_lines=2)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f766e"/>
      <stop offset="54%" stop-color="#1d4ed8"/>
      <stop offset="100%" stop-color="#111827"/>
    </linearGradient>
  </defs>
  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>
  <rect x="72" y="84" width="936" height="1752" rx="42" fill="rgba(255,255,255,0.10)" stroke="rgba(255,255,255,0.28)" stroke-width="3"/>
  <text x="92" y="150" font-size="36" font-weight="700" fill="#dbeafe" font-family="Malgun Gothic, Arial, sans-serif">SCENE {scene_no}/{total}</text>
  {_svg_text_block(title_lines, 92, 244, 52, "#ffffff", "700")}
  <rect x="92" y="552" width="896" height="420" rx="32" fill="rgba(0,0,0,0.32)"/>
  {_svg_text_block(caption_lines, 132, 674, 74, "#ffffff", "800")}
  <text x="92" y="1110" font-size="34" font-weight="700" fill="#bfdbfe" font-family="Malgun Gothic, Arial, sans-serif">Visual direction</text>
  {_svg_text_block(direction_lines, 92, 1172, 36, "#e5e7eb", "500")}
  <text x="92" y="1490" font-size="34" font-weight="700" fill="#ccfbf1" font-family="Malgun Gothic, Arial, sans-serif">Narration</text>
  {_svg_text_block(narration_lines, 92, 1552, 34, "#f8fafc", "500")}
</svg>
"""


def create_render_placeholders(project_id: str, script: ScriptDraft, project_dir: Path) -> dict[str, Any]:
    render_dir = project_dir / "renders" / "placeholder"
    render_dir.mkdir(parents=True, exist_ok=True)
    scenes = script.to_dict().get("scenes", [])
    total = max(1, len(scenes))
    duration_per_scene = round(45 / total, 2)

    scene_outputs: list[dict[str, Any]] = []
    for idx, scene in enumerate(scenes, start=1):
        svg_path = render_dir / f"scene_{idx:02d}.svg"
        svg_path.write_text(_scene_svg(scene, script.title, idx, total), encoding="utf-8")
        scene_outputs.append(
            {
                "scene_no": idx,
                "caption": scene.get("caption", ""),
                "duration_sec": duration_per_scene,
                "placeholder_svg": str(svg_path),
                "visual_direction": scene.get("visual_direction", ""),
            }
        )

    render_plan = {
        "project_id": project_id,
        "title": script.title,
        "width": WIDTH,
        "height": HEIGHT,
        "target_duration_sec": 45,
        "scene_count": len(scene_outputs),
        "status": "placeholder_ready",
        "scenes": scene_outputs,
        "next_step": "Replace SVG placeholders with generated/attached images, then render MP4.",
    }
    write_json(render_dir / "render_plan.json", render_plan)
    return render_plan
