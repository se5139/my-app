from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .state import read_json, write_json


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def ffmpeg_setup_guide(project_dir: Path) -> dict[str, Any]:
    preview_dir = project_dir / "renders" / "preview"
    guide = {
        "status": "guide_ready",
        "purpose": "Enable MP4 rendering from generated PNG preview frames.",
        "recommended_windows_command": "winget install --id Gyan.FFmpeg --exact",
        "manual_download_url": "https://www.ffmpeg.org/download.html",
        "windows_builds_url": "https://www.gyan.dev/ffmpeg/builds/",
        "verify_command": "ffmpeg -version",
        "after_install": [
            "Close and reopen PowerShell or this web app launcher.",
            "Run ffmpeg -version to confirm PATH can find ffmpeg.exe.",
            "Open the project detail screen and press ffmpeg 확인.",
            "Press MP4 변환 시도 after the status becomes ready.",
        ],
        "notes": [
            "The app does not auto-install system tools without explicit user action.",
            "FFmpeg provides the core command-line encoder; Windows builds are linked from the FFmpeg download page.",
            "WinGet is the standard Windows package-manager command on supported Windows systems.",
        ],
    }
    write_json(preview_dir / "ffmpeg_setup_guide.json", guide)
    markdown = "\n".join(
        [
            "# FFmpeg Setup Guide",
            "",
            "MP4 rendering needs `ffmpeg.exe` available in PATH.",
            "",
            "## Recommended Windows Install",
            "",
            "```powershell",
            guide["recommended_windows_command"],
            "```",
            "",
            "## Manual Download",
            "",
            f"- FFmpeg download page: {guide['manual_download_url']}",
            f"- Windows builds: {guide['windows_builds_url']}",
            "",
            "## Verify",
            "",
            "```powershell",
            guide["verify_command"],
            "```",
            "",
            "After installing, restart the app launcher and press `ffmpeg 확인` again.",
        ]
    )
    guide["markdown_path"] = str(preview_dir / "ffmpeg_setup_guide.md")
    (preview_dir / "ffmpeg_setup_guide.md").write_text(markdown, encoding="utf-8")
    write_json(preview_dir / "ffmpeg_setup_guide.json", guide)
    return guide


def mp4_status(project_dir: Path) -> dict[str, Any]:
    preview_dir = project_dir / "renders" / "preview"
    ffmpeg_path = find_ffmpeg()
    status = {
        "ffmpeg_available": bool(ffmpeg_path),
        "ffmpeg_path": ffmpeg_path or "",
        "mp4_path": str(preview_dir / "preview.mp4"),
        "status": "ready" if ffmpeg_path else "ffmpeg_missing",
        "install_hint": "Install ffmpeg and make sure ffmpeg.exe is available in PATH.",
        "setup_guide_path": str(preview_dir / "ffmpeg_setup_guide.json"),
    }
    if not ffmpeg_path:
        ffmpeg_setup_guide(project_dir)
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
