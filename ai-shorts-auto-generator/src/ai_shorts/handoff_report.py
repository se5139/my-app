from __future__ import annotations

from pathlib import Path
from typing import Any

from .environment_check import collect_environment_check
from .first_run_setup import build_first_run_checklist, list_setup_guides
from .operations_snapshot import SNAPSHOT_DIR
from .paths import DATA_DIR
from .state import now_iso, write_json


HANDOFF_REPORTS_DIR = DATA_DIR / "handoff_reports"


def create_handoff_report() -> dict[str, Any]:
    HANDOFF_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now_iso().replace(":", "").replace("+", "Z")
    report_path = HANDOFF_REPORTS_DIR / f"handoff_report_{stamp}.md"
    manifest_path = HANDOFF_REPORTS_DIR / f"handoff_report_{stamp}.json"

    environment = collect_environment_check()
    checklist = build_first_run_checklist(environment)
    latest_snapshot = _latest_file(SNAPSHOT_DIR, "operations_snapshot_*.zip")
    setup_guides = list_setup_guides()
    manifest = {
        "created_at": now_iso(),
        "environment_status": environment.get("overall_status", ""),
        "checklist_status": checklist.get("overall_status", ""),
        "latest_snapshot": str(latest_snapshot or ""),
        "setup_guide_count": len(setup_guides),
        "setup_guides": setup_guides,
        "report_path": str(report_path),
        "manifest_path": str(manifest_path),
    }
    report_path.write_text(_handoff_markdown(environment, checklist, latest_snapshot, setup_guides), encoding="utf-8")
    write_json(manifest_path, manifest)
    return manifest


def list_handoff_reports() -> list[dict[str, str]]:
    if not HANDOFF_REPORTS_DIR.exists():
        return []
    reports = []
    for path in sorted(HANDOFF_REPORTS_DIR.glob("handoff_report_*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        reports.append(
            {
                "filename": path.name,
                "title": _read_markdown_title(path),
                "path": str(path),
            }
        )
    return reports


def read_handoff_report(filename: str) -> dict[str, str]:
    safe_name = Path(filename).name
    path = HANDOFF_REPORTS_DIR / safe_name
    if not safe_name or path.suffix.lower() != ".md" or not path.exists():
        raise FileNotFoundError("handoff report not found")
    return {
        "filename": safe_name,
        "title": _read_markdown_title(path),
        "path": str(path),
        "content": path.read_text(encoding="utf-8"),
    }


def _latest_file(folder: Path, pattern: str) -> Path | None:
    if not folder.exists():
        return None
    matches = [path for path in folder.glob(pattern) if path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def _read_markdown_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def _handoff_markdown(
    environment: dict[str, Any],
    checklist: dict[str, Any],
    latest_snapshot: Path | None,
    setup_guides: list[dict[str, str]],
) -> str:
    lines = [
        "# AI Shorts Handoff Report",
        "",
        f"Created: {now_iso()}",
        "",
        "## Status",
        "",
        f"- Environment: {environment.get('overall_status', '')}",
        f"- First-run checklist: {checklist.get('overall_status', '')}",
        f"- Latest snapshot: {latest_snapshot or 'No operations snapshot found'}",
        "",
        "## Environment Checks",
        "",
    ]
    for item in environment.get("checks", []):
        lines.append(f"- {item.get('name')} [{item.get('status')}]: {item.get('message')} ({item.get('detail')})")
    lines.extend(["", "## First-Run Actions", ""])
    for action in checklist.get("actions", []):
        lines.append(
            f"- {action.get('priority')} / {action.get('status')}: {action.get('title')} - {action.get('command')}"
        )
    lines.extend(["", "## Setup Guides", ""])
    if setup_guides:
        for guide in setup_guides:
            lines.append(f"- {guide.get('title')}: {guide.get('path')}")
    else:
        lines.append("- No setup guides generated yet.")
    lines.extend(
        [
            "",
            "## Resume Rule",
            "",
            "Pull latest GitHub changes, restore the latest snapshot if needed, start the web app, and push after each completed unit of work.",
            "",
        ]
    )
    return "\n".join(lines)
