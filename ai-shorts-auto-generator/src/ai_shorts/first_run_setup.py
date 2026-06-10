from __future__ import annotations

from pathlib import Path
from typing import Any

from .environment_check import collect_environment_check
from .paths import DATA_DIR
from .state import now_iso, write_json


SETUP_GUIDES_DIR = DATA_DIR / "setup_guides"


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


def export_setup_guides(report: dict[str, Any] | None = None) -> dict[str, Any]:
    checklist = build_first_run_checklist(report)
    SETUP_GUIDES_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now_iso().replace(":", "").replace("+", "Z")
    exported = []
    for action in checklist["actions"]:
        path = SETUP_GUIDES_DIR / f"{action['id']}_{stamp}.md"
        path.write_text(_action_markdown(action), encoding="utf-8")
        exported.append(
            {
                "id": action["id"],
                "title": action["title"],
                "status": action["status"],
                "priority": action["priority"],
                "path": str(path),
            }
        )
    manifest = {
        "created_at": now_iso(),
        "overall_status": checklist["overall_status"],
        "guide_count": len(exported),
        "guides": exported,
    }
    manifest_path = SETUP_GUIDES_DIR / f"setup_guides_manifest_{stamp}.json"
    write_json(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)
    write_json(manifest_path, manifest)
    return manifest


def list_setup_guides() -> list[dict[str, str]]:
    if not SETUP_GUIDES_DIR.exists():
        return []
    guides = []
    for path in sorted(SETUP_GUIDES_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        guides.append(
            {
                "filename": path.name,
                "title": _read_markdown_title(path),
                "path": str(path),
            }
        )
    return guides


def read_setup_guide(filename: str) -> dict[str, str]:
    safe_name = Path(filename).name
    path = SETUP_GUIDES_DIR / safe_name
    if not safe_name or path.suffix.lower() != ".md" or not path.exists():
        raise FileNotFoundError("setup guide not found")
    return {
        "filename": safe_name,
        "title": _read_markdown_title(path),
        "path": str(path),
        "content": path.read_text(encoding="utf-8"),
    }


def _action_markdown(action: dict[str, str]) -> str:
    return "\n".join(
        [
            f"# {action.get('title', 'Setup Action')}",
            "",
            f"- Priority: {action.get('priority', '')}",
            f"- Status: {action.get('status', '')}",
            "",
            "## Why This Matters",
            "",
            str(action.get("body", "")),
            "",
            "## Command Or Action",
            "",
            "```powershell",
            str(action.get("command", "")),
            "```",
            "",
            "## After Completing",
            "",
            "Restart the local web app if a system PATH or tool installation changed, then refresh the home page.",
            "",
        ]
    )


def _read_markdown_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


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
