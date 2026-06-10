from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from .paths import DATA_DIR, PROJECTS_DIR, ensure_data_dirs
from .project_dashboard import summarize_project_gate
from .state import now_iso, read_json, write_json


SNAPSHOT_DIR = DATA_DIR / "snapshots"


def create_operations_snapshot() -> dict[str, Any]:
    ensure_data_dirs()
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now_iso().replace(":", "").replace("+", "Z")
    base_name = f"operations_snapshot_{stamp}"
    manifest_path = SNAPSHOT_DIR / f"{base_name}.json"
    readme_path = SNAPSHOT_DIR / f"{base_name}.md"
    zip_path = SNAPSHOT_DIR / f"{base_name}.zip"

    manifest = {
        "created_at": now_iso(),
        "data_dir": str(DATA_DIR),
        "project_count": 0,
        "projects": [],
        "included_files": [],
        "zip_path": str(zip_path),
        "readme_path": str(readme_path),
        "restore_note": "Copy the extracted data folder into ai-shorts-auto-generator/data on another PC, then start the web app.",
    }

    app_state = read_json(DATA_DIR / "app_state.json", {"projects": []})
    for item in app_state.get("projects", []):
        project_id = str(item.get("id", ""))
        project_dir = PROJECTS_DIR / project_id
        if not project_id or not project_dir.exists():
            continue
        summary = summarize_project_gate(project_dir)
        manifest["projects"].append(
            {
                "id": project_id,
                "title": item.get("title", ""),
                "status": item.get("status", ""),
                "blocking_gate": summary.get("blocking_gate", ""),
                "next_step": summary.get("next_step", ""),
            }
        )
    manifest["project_count"] = len(manifest["projects"])

    write_json(manifest_path, manifest)
    readme_path.write_text(_snapshot_readme(manifest), encoding="utf-8")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in _iter_snapshot_files():
            arcname = file_path.relative_to(DATA_DIR.parent)
            archive.write(file_path, arcname.as_posix())
            manifest["included_files"].append(arcname.as_posix())
        archive.write(manifest_path, manifest_path.relative_to(DATA_DIR.parent).as_posix())
        archive.write(readme_path, readme_path.relative_to(DATA_DIR.parent).as_posix())

    write_json(manifest_path, manifest)
    return manifest


def _iter_snapshot_files() -> list[Path]:
    if not DATA_DIR.exists():
        return []
    files = []
    for file_path in DATA_DIR.rglob("*"):
        if not file_path.is_file():
            continue
        if SNAPSHOT_DIR in file_path.parents:
            continue
        files.append(file_path)
    return files


def _snapshot_readme(manifest: dict[str, Any]) -> str:
    project_lines = [
        f"- {project.get('title') or project.get('id')} [{project.get('status')}] blocked at {project.get('blocking_gate')}: {project.get('next_step')}"
        for project in manifest.get("projects", [])
    ]
    if not project_lines:
        project_lines = ["- No saved projects were found."]
    return "\n".join(
        [
            "# AI Shorts Operations Snapshot",
            "",
            f"Created: {manifest.get('created_at')}",
            f"Project count: {manifest.get('project_count')}",
            "",
            "## Projects",
            "",
            *project_lines,
            "",
            "## Restore",
            "",
            str(manifest.get("restore_note")),
            "",
        ]
    )
