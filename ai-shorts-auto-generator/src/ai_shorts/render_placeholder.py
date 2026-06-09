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


def _timeline_html(render_plan: dict[str, Any]) -> str:
    title = escape(str(render_plan.get("title", "")))
    target_duration = escape(str(render_plan.get("target_duration_sec", "")))
    cards = []
    for scene in render_plan.get("scenes", []):
        svg_path = Path(str(scene.get("placeholder_svg", "")))
        cards.append(
            f"""
            <article class="scene">
              <div class="frame">
                <img src="{escape(svg_path.name)}" alt="Scene {int(scene.get('scene_no', 0))} placeholder">
              </div>
              <div class="meta">
                <div class="eyebrow">Scene {int(scene.get('scene_no', 0))} · {escape(str(scene.get('duration_sec', '')))}s</div>
                <h2>{escape(str(scene.get('caption', '')))}</h2>
                <p>{escape(str(scene.get('visual_direction', '')))}</p>
              </div>
            </article>
            """
        )
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} · Render Timeline</title>
  <style>
    body {{
      margin: 0;
      background: #f6f7f9;
      color: #1c2430;
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", system-ui, sans-serif;
      letter-spacing: 0;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: #ffffff;
      border-bottom: 1px solid #d9dee7;
      padding: 18px 22px;
    }}
    h1 {{ margin: 0 0 6px; font-size: 22px; }}
    .muted {{ color: #5d6675; font-size: 14px; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 22px; }}
    .scene {{
      display: grid;
      grid-template-columns: 270px minmax(0, 1fr);
      gap: 18px;
      background: #ffffff;
      border: 1px solid #d9dee7;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
    }}
    .frame {{
      width: 100%;
      aspect-ratio: 9 / 16;
      background: #111827;
      border-radius: 6px;
      overflow: hidden;
      border: 1px solid #d9dee7;
    }}
    .frame img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
    .eyebrow {{ color: #0f766e; font-weight: 700; font-size: 13px; margin-bottom: 8px; }}
    h2 {{ margin: 0 0 10px; font-size: 20px; }}
    p {{ margin: 0; line-height: 1.6; }}
    @media (max-width: 720px) {{
      .scene {{ grid-template-columns: 1fr; }}
      .frame {{ max-width: 280px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <div class="muted">Placeholder timeline · {len(render_plan.get("scenes", []))} scenes · target {target_duration}s</div>
  </header>
  <main>
    {"".join(cards)}
  </main>
</body>
</html>
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
        "timeline_html": str(render_dir / "timeline.html"),
        "render_manifest": str(render_dir / "render_manifest.json"),
        "next_step": "Replace SVG placeholders with generated/attached images, then render MP4.",
    }
    write_json(render_dir / "render_plan.json", render_plan)
    write_json(
        render_dir / "render_manifest.json",
        {
            "project_id": project_id,
            "title": script.title,
            "review_entry": str(render_dir / "timeline.html"),
            "render_plan": str(render_dir / "render_plan.json"),
            "assets": [scene["placeholder_svg"] for scene in scene_outputs],
            "status": "review_package_ready",
        },
    )
    (render_dir / "timeline.html").write_text(_timeline_html(render_plan), encoding="utf-8")
    return render_plan
