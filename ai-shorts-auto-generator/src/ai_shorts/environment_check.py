from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from .ffmpeg_renderer import find_ffmpeg
from .paths import APP_STATE_PATH, DATA_DIR, PROJECT_ROOT, PROJECTS_DIR
from .state import read_json


def collect_environment_check() -> dict[str, Any]:
    git_path = shutil.which("git")
    git_root = _find_git_root(PROJECT_ROOT)
    ffmpeg_path = find_ffmpeg()
    app_state = read_json(APP_STATE_PATH, {"projects": []}) if APP_STATE_PATH.exists() else {"projects": []}
    project_dirs = [path for path in PROJECTS_DIR.iterdir() if path.is_dir()] if PROJECTS_DIR.exists() else []

    checks = [
        {
            "name": "Python",
            "status": "pass",
            "message": f"{platform.python_implementation()} {platform.python_version()}",
            "detail": sys.executable,
        },
        {
            "name": "Git",
            "status": "pass" if git_path and git_root else "warn" if git_root else "fail",
            "message": "Git is available in PATH." if git_path else "Git command is not available in PATH.",
            "detail": git_path or str(git_root or "Repository root not found"),
        },
        {
            "name": "Data folder",
            "status": "pass" if DATA_DIR.exists() else "warn",
            "message": "Local autosave data folder is present." if DATA_DIR.exists() else "No local data folder yet.",
            "detail": str(DATA_DIR),
        },
        {
            "name": "Projects",
            "status": "pass" if project_dirs or app_state.get("projects") else "warn",
            "message": f"{len(app_state.get('projects', []))} saved projects in app state, {len(project_dirs)} project folders.",
            "detail": str(PROJECTS_DIR),
        },
        {
            "name": "FFmpeg",
            "status": "pass" if ffmpeg_path else "warn",
            "message": "FFmpeg is ready for MP4 rendering." if ffmpeg_path else "FFmpeg is missing; GIF/timeline review can continue.",
            "detail": ffmpeg_path or "Install ffmpeg and restart the app before MP4 rendering.",
        },
    ]
    return {
        "overall_status": _overall_status(checks),
        "project_root": str(PROJECT_ROOT),
        "git_root": str(git_root or ""),
        "checks": checks,
    }


def _find_git_root(start: Path) -> Path | None:
    for path in [start, *start.parents]:
        if (path / ".git").exists():
            return path
    return None


def _overall_status(checks: list[dict[str, str]]) -> str:
    if any(item.get("status") == "fail" for item in checks):
        return "needs_setup"
    if any(item.get("status") == "warn" for item in checks):
        return "usable_with_warnings"
    return "ready"
