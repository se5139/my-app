from __future__ import annotations

from typing import Any

from .environment_check import collect_environment_check


def build_first_run_checklist(report: dict[str, Any] | None = None) -> dict[str, Any]:
    report = report or collect_environment_check()
    check_by_name = {str(item.get("name")): item for item in report.get("checks", [])}
    actions = [
        {
            "id": "clone_or_pull_repo",
            "priority": "required",
            "status": _action_status(check_by_name.get("Git")),
            "title": "Repository access",
            "body": "Make sure this folder is inside the GitHub repository and Git can pull/push progress.",
            "command": "git pull --rebase origin main",
        },
        {
            "id": "restore_snapshot_data",
            "priority": "recommended",
            "status": _data_action_status(check_by_name.get("Data folder"), check_by_name.get("Projects")),
            "title": "Restore autosave data",
            "body": "If this is a new PC, restore the latest operations snapshot before continuing work.",
            "command": "Extract snapshot zip, then copy its data folder into ai-shorts-auto-generator/data.",
        },
        {
            "id": "start_web_app",
            "priority": "required",
            "status": "ready" if check_by_name.get("Python", {}).get("status") == "pass" else "blocked",
            "title": "Start local web app",
            "body": "Open the local UI and confirm recent drafts, growth records, and setup warnings.",
            "command": "$env:PYTHONPATH='src'; python -m ai_shorts.web_app",
        },
        {
            "id": "enable_mp4_rendering",
            "priority": "optional",
            "status": "ready" if check_by_name.get("FFmpeg", {}).get("status") == "pass" else "todo",
            "title": "Enable MP4 rendering",
            "body": "Install ffmpeg only when you are ready to render final MP4 files. GIF/timeline review can continue without it.",
            "command": "winget install --id Gyan.FFmpeg --exact",
        },
    ]
    return {
        "overall_status": _overall_action_status(actions),
        "actions": actions,
    }


def _action_status(check: dict[str, Any] | None) -> str:
    if not check:
        return "blocked"
    if check.get("status") == "pass":
        return "ready"
    if check.get("status") == "warn":
        return "todo"
    return "blocked"


def _data_action_status(data_check: dict[str, Any] | None, project_check: dict[str, Any] | None) -> str:
    if data_check and data_check.get("status") == "pass" and project_check and project_check.get("status") == "pass":
        return "ready"
    if data_check and data_check.get("status") in {"pass", "warn"}:
        return "todo"
    return "blocked"


def _overall_action_status(actions: list[dict[str, str]]) -> str:
    required = [item for item in actions if item.get("priority") == "required"]
    if any(item.get("status") == "blocked" for item in required):
        return "blocked"
    if any(item.get("status") == "todo" for item in actions):
        return "needs_attention"
    return "ready"
