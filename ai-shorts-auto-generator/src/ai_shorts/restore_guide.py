from __future__ import annotations

from typing import Any


def restore_steps() -> list[dict[str, str]]:
    return [
        {
            "title": "1. Repository clone",
            "body": "Clone https://github.com/se5139/my-app.git, then open my-app/ai-shorts-auto-generator.",
            "command": "git clone https://github.com/se5139/my-app.git",
        },
        {
            "title": "2. Snapshot copy",
            "body": "Extract the latest operations_snapshot zip and copy the extracted data folder into ai-shorts-auto-generator/data.",
            "command": "Copy-Item -Recurse .\\data .\\ai-shorts-auto-generator\\data",
        },
        {
            "title": "3. Web app start",
            "body": "Start the local browser UI and confirm recent drafts, growth data, and snapshots are visible.",
            "command": "$env:PYTHONPATH='src'; python -m ai_shorts.web_app",
        },
        {
            "title": "4. Save after work",
            "body": "After each completed step, commit and push so another PC can continue without guessing.",
            "command": "git add .; git commit -m \"Save AI shorts progress\"; git push origin main",
        },
    ]


def restore_note() -> str:
    return "Extract the snapshot zip, copy its data folder into ai-shorts-auto-generator/data, then start the web app."


def new_pc_start_markdown(extra: dict[str, Any] | None = None) -> str:
    lines = [
        "# New PC Start Here",
        "",
        "Use this page when continuing the AI Shorts Auto Generator on another PC.",
        "",
        "## Required Repository",
        "",
        "```text",
        "https://github.com/se5139/my-app.git",
        "```",
        "",
        "## Steps",
        "",
    ]
    for step in restore_steps():
        lines.extend(
            [
                f"### {step['title']}",
                "",
                step["body"],
                "",
                "```powershell",
                step["command"],
                "```",
                "",
            ]
        )
    if extra:
        lines.extend(
            [
                "## Snapshot",
                "",
                f"- Created: {extra.get('created_at', '')}",
                f"- Projects: {extra.get('project_count', 0)}",
                f"- ZIP: {extra.get('zip_path', '')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Safety Rule",
            "",
            "Do not enable public upload automation until MP4, compliance, human review, metadata, and asset-source gates pass.",
            "",
        ]
    )
    return "\n".join(lines)
