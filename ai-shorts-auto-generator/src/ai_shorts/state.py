from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import APP_STATE_PATH, PROJECTS_DIR, ensure_data_dirs


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AppState:
    schema_version: int = 1
    app_name: str = "AI Shorts Auto Generator"
    projects: list[dict[str, Any]] = field(default_factory=list)
    last_opened_project_id: str | None = None
    autosave: dict[str, bool] = field(default_factory=lambda: {"enabled": True, "save_on_every_step": True})


@dataclass
class ShortProject:
    id: str
    title: str
    status: str = "idea"
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    source_notes: str = ""
    script: dict[str, Any] = field(default_factory=dict)
    review: dict[str, Any] = field(default_factory=dict)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_app_state() -> AppState:
    ensure_data_dirs()
    data = read_json(APP_STATE_PATH, asdict(AppState()))
    return AppState(**data)


def save_app_state(state: AppState) -> Path:
    ensure_data_dirs()
    return write_json(APP_STATE_PATH, asdict(state))


def create_project(title: str, source_notes: str = "") -> ShortProject:
    ensure_data_dirs()
    project = ShortProject(id=str(uuid.uuid4()), title=title.strip() or "Untitled Short", source_notes=source_notes)
    project_dir = PROJECTS_DIR / project.id
    write_json(project_dir / "project.json", asdict(project))

    state = load_app_state()
    state.projects.append({"id": project.id, "title": project.title, "status": project.status, "updated_at": project.updated_at})
    state.last_opened_project_id = project.id
    save_app_state(state)
    return project


def update_project_review(project_id: str, status: str, reviewer_note: str = "") -> dict[str, Any]:
    ensure_data_dirs()
    project_path = PROJECTS_DIR / project_id / "project.json"
    project_data = read_json(project_path, {})
    if not project_data:
        raise FileNotFoundError(f"Project not found: {project_id}")

    timestamp = now_iso()
    project_data["status"] = status
    project_data["updated_at"] = timestamp
    project_data["review"] = {
        "status": status,
        "reviewer_note": reviewer_note.strip(),
        "reviewed_at": timestamp,
    }
    write_json(project_path, project_data)

    state = load_app_state()
    for item in state.projects:
        if item.get("id") == project_id:
            item["status"] = status
            item["updated_at"] = timestamp
            break
    save_app_state(state)
    return project_data
