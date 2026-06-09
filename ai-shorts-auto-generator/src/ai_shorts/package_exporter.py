from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .compliance import AssetNote, DraftComplianceInput, SourceMaterial, evaluate_compliance
from .paths import PROJECTS_DIR
from .script_lab import ScriptDraft
from .state import ShortProject, write_json


def export_manual_upload_package(
    project: ShortProject,
    script: ScriptDraft,
    sources: list[SourceMaterial] | None = None,
    assets: list[AssetNote] | None = None,
) -> dict[str, Any]:
    project_dir = PROJECTS_DIR / project.id
    package_dir = project_dir / "exports" / "manual_upload_package"
    package_dir.mkdir(parents=True, exist_ok=True)

    source_list = sources or []
    asset_list = assets or []
    compliance = evaluate_compliance(
        DraftComplianceInput(
            title=script.title,
            narration=script.narration,
            description=script.description,
            tags=script.tags,
            sources=source_list,
            assets=asset_list,
            uses_realistic_synthetic_media=False,
            synthetic_disclosure_acknowledged=False,
            public_upload_requested=False,
        )
    )

    write_json(package_dir / "script.json", script.to_dict())
    write_json(package_dir / "compliance_report.json", compliance.to_dict())
    write_json(
        package_dir / "asset_source_notes.json",
        {
            "sources": [asdict(source) for source in source_list],
            "assets": [asdict(asset) for asset in asset_list],
        },
    )
    (package_dir / "title.txt").write_text(script.title, encoding="utf-8")
    (package_dir / "description.txt").write_text(script.description, encoding="utf-8")
    (package_dir / "tags.txt").write_text("\n".join(script.tags), encoding="utf-8")
    (package_dir / "pinned_comment.txt").write_text(script.pinned_comment, encoding="utf-8")
    (package_dir / "README_UPLOAD_REVIEW.txt").write_text(
        "\n".join(
            [
                "Manual upload package",
                "",
                "1. Review compliance_report.json.",
                "2. Confirm all asset/source rights notes.",
                "3. Render or attach the final video and thumbnail.",
                "4. Upload manually only after human approval.",
                "5. If realistic synthetic media is used, review YouTube altered-content disclosure.",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "package_dir": str(package_dir),
        "compliance_status": compliance.status.value,
        "finding_count": len(compliance.findings),
    }
