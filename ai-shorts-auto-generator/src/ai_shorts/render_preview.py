from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .state import read_json, write_json


WIDTH = 540
HEIGHT = 960


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _wrap(text: str, width: int, max_lines: int) -> list[str]:
    lines = textwrap.wrap(" ".join(str(text or "").split()), width=width, break_long_words=False)
    return lines[:max_lines] or [""]


def _draw_lines(draw: ImageDraw.ImageDraw, lines: list[str], xy: tuple[int, int], font: ImageFont.ImageFont, fill: str, line_gap: int = 10) -> None:
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap


def _scene_frame(scene: dict[str, Any], title: str, scene_no: int, total: int) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), "#111827")
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        r = int(15 + (29 - 15) * y / HEIGHT)
        g = int(118 + (78 - 118) * y / HEIGHT)
        b = int(110 + (216 - 110) * y / HEIGHT)
        draw.line((0, y, WIDTH, y), fill=(r, g, b))

    draw.rounded_rectangle((34, 42, WIDTH - 34, HEIGHT - 42), radius=24, outline="#dbeafe", width=2)
    draw.text((48, 72), f"SCENE {scene_no}/{total}", font=_font(20, True), fill="#dbeafe")
    _draw_lines(draw, _wrap(title, 20, 2), (48, 122), _font(28, True), "#ffffff", 8)

    box_top = 292
    draw.rounded_rectangle((48, box_top, WIDTH - 48, box_top + 210), radius=20, fill="#0f172a")
    _draw_lines(draw, _wrap(str(scene.get("caption", "")), 12, 4), (70, box_top + 50), _font(38, True), "#ffffff", 8)

    draw.text((48, 570), "Narration", font=_font(19, True), fill="#ccfbf1")
    _draw_lines(draw, _wrap(str(scene.get("narration", "")), 24, 4), (48, 612), _font(22), "#f8fafc", 8)
    return img


def create_preview_media(project_id: str, project_dir: Path) -> dict[str, Any]:
    render_dir = project_dir / "renders" / "placeholder"
    preview_dir = project_dir / "renders" / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    render_plan = read_json(render_dir / "render_plan.json", {})
    if not render_plan:
        raise FileNotFoundError("render_plan.json not found. Generate render placeholders first.")

    title = str(render_plan.get("title", "Untitled"))
    scenes = render_plan.get("scenes", [])
    total = max(1, len(scenes))
    frames: list[Image.Image] = []
    outputs: list[dict[str, Any]] = []

    for idx, scene in enumerate(scenes, start=1):
        duration_sec = float(scene.get("duration_sec", 1.2) or 1.2)
        duration_ms = max(100, int(round(duration_sec * 1000)))
        frame = _scene_frame(scene, title, idx, total)
        frame_path = preview_dir / f"frame_{idx:02d}.png"
        frame.save(frame_path)
        frames.append(frame)
        outputs.append(
            {
                "scene_no": idx,
                "frame_png": str(frame_path),
                "duration_sec": duration_sec,
                "duration_ms": duration_ms,
            }
        )

    gif_path = preview_dir / "preview.gif"
    if frames:
        frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=[frame["duration_ms"] for frame in outputs], loop=0)

    manifest = {
        "project_id": project_id,
        "status": "preview_ready",
        "format": "gif_preview",
        "width": WIDTH,
        "height": HEIGHT,
        "target_duration_sec": render_plan.get("target_duration_sec", 0),
        "total_duration_sec": render_plan.get("total_duration_sec", render_plan.get("target_duration_sec", 0)),
        "source_timing_plan": render_plan.get("timing_plan", ""),
        "preview_gif": str(gif_path),
        "frames": outputs,
        "mp4_status": "not_available_without_ffmpeg",
        "next_step": "Install or bundle ffmpeg/moviepy to convert frames into MP4.",
    }
    write_json(preview_dir / "preview_manifest.json", manifest)
    return manifest
