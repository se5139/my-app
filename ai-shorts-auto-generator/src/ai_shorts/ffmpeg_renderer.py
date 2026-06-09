from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .state import read_json, write_json


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def mp4_status(project_dir: Path) -> dict[str, Any]:
    preview_dir = project_dir / "renders" / "preview"
    ffmpeg_path = find_ffmpeg()
    status = {
        "ffmpeg_available": bool(ffmpeg_path),
        "ffmpeg_path": ffmpeg_path or "",
        "mp4_path": str(preview_dir / "preview.mp4"),
        "status": "ready" if ffmpeg_path else "ffmpeg_missing",
        "install_hint": "Install ffmpeg and make sure ffmpeg.exe is available in PATH.",
    }
    write_json(preview_dir / "mp4_status.json", status)
    return status


def render_mp4_from_preview(project_id: str, project_dir: Path) -> dict[str, Any]:
    preview_dir = project_dir / "renders" / "preview"
    preview_manifest = read_json(preview_dir / "preview_manifest.json", {})
    if not preview_manifest:
        raise FileNotFoundError("preview_manifest.json not found. Generate GIF preview first.")

    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        return mp4_status(project_dir)

    output_path = preview_dir / "preview.mp4"
    frame_pattern = str(preview_dir / "frame_%02d.png")
    command = [
        ffmpeg_path,
        "-y",
        "-framerate",
        "1",
        "-i",
        frame_pattern,
        "-vf",
        "scale=1080:1920:flags=lanczos,format=yuv420p",
        "-r",
        "24",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if completed.returncode != 0:
        status = {
            "ffmpeg_available": True,
            "ffmpeg_path": ffmpeg_path,
            "mp4_path": str(output_path),
            "status": "failed",
            "stderr": completed.stderr[-2000:],
        }
        write_json(preview_dir / "mp4_status.json", status)
        return status

    status = {
        "project_id": project_id,
        "ffmpeg_available": True,
        "ffmpeg_path": ffmpeg_path,
        "mp4_path": str(output_path),
        "status": "mp4_ready",
        "source_manifest": str(preview_dir / "preview_manifest.json"),
    }
    write_json(preview_dir / "mp4_status.json", status)
    return status
