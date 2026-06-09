from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .package_exporter import export_manual_upload_package
from .paths import PROJECTS_DIR, ensure_data_dirs
from .script_lab import create_local_script_draft
from .state import create_project, write_json


def create_draft_package(topic: str, source_notes: str = "") -> dict[str, Any]:
    ensure_data_dirs()
    project = create_project(topic, source_notes)
    script = create_local_script_draft(topic, source_notes)
    project_dir = PROJECTS_DIR / project.id
    write_json(project_dir / "script_draft.json", script.to_dict())
    export = export_manual_upload_package(project, script)
    return {"project": asdict(project), "script": script.to_dict(), "export": export}
