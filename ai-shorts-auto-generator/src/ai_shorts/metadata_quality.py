from __future__ import annotations

from pathlib import Path
from typing import Any

from .state import now_iso, read_json, write_json


MAX_TITLE_LEN = 100
MAX_DESCRIPTION_LEN = 5000
MAX_TAG_COUNT = 15
MAX_TAG_LEN = 30
CLICKBAIT_TERMS = ["100% 보장", "무조건", "절대 실패", "충격", "소름", "복붙", "그대로 따라"]


def build_metadata_quality_gate(project_dir: Path, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    inputs = inputs or {}
    package_dir = project_dir / "exports" / "manual_upload_package"
    script = read_json(project_dir / "script_draft.json", {})
    title = _text(inputs.get("title")) or _read_text(package_dir / "title.txt") or _text(script.get("title"))
    description = _text(inputs.get("description")) or _read_text(package_dir / "description.txt") or _text(script.get("description"))
    tags = _parse_tags(inputs.get("tags")) or _parse_tags(_read_text(package_dir / "tags.txt")) or [str(tag) for tag in script.get("tags", [])]
    pinned_comment = _text(inputs.get("pinned_comment")) or _read_text(package_dir / "pinned_comment.txt") or _text(script.get("pinned_comment"))
    reviewer_decision = _text(inputs.get("reviewer_decision")) or "needs_review"
    reviewer_note = _text(inputs.get("reviewer_note"))

    issues = _validate(title, description, tags, pinned_comment, reviewer_decision)
    status = "metadata_ready" if not issues else "metadata_needs_review"

    manifest = {
        "status": status,
        "created_at": now_iso(),
        "title": title,
        "description": description,
        "tags": tags,
        "pinned_comment": pinned_comment,
        "review": {
            "decision": reviewer_decision,
            "reviewer_note": reviewer_note,
            "human_review_required": True,
        },
        "validation": {
            "valid": not issues,
            "issues": issues,
            "title_length": len(title),
            "description_length": len(description),
            "tag_count": len(tags),
        },
        "policy_notes": [
            "No public upload automation is enabled.",
            "Avoid reused, misleading, sensational, or guaranteed-result metadata.",
            "Confirm that title, thumbnail, description, and tags match the actual final video.",
        ],
        "no_paid_api_calls": True,
        "public_upload_automation": "disabled",
        "next_step": _next_step(issues),
    }
    write_json(package_dir / "metadata_quality_report.json", manifest)
    if status == "metadata_ready":
        _write_metadata_files(package_dir, title, description, tags, pinned_comment)
    return manifest


def _validate(title: str, description: str, tags: list[str], pinned_comment: str, reviewer_decision: str) -> list[str]:
    issues: list[str] = []
    if not title:
        issues.append("title_missing")
    if len(title) > MAX_TITLE_LEN:
        issues.append("title_too_long")
    if not description:
        issues.append("description_missing")
    if len(description) > MAX_DESCRIPTION_LEN:
        issues.append("description_too_long")
    if len(tags) < 3:
        issues.append("tags_too_few")
    if len(tags) > MAX_TAG_COUNT:
        issues.append("tags_too_many")
    if len({tag.casefold() for tag in tags}) != len(tags):
        issues.append("duplicate_tags")
    if any(len(tag) > MAX_TAG_LEN for tag in tags):
        issues.append("tag_too_long")
    if not pinned_comment:
        issues.append("pinned_comment_missing")
    combined = " ".join([title, description, pinned_comment, " ".join(tags)])
    if any(term in combined for term in CLICKBAIT_TERMS):
        issues.append("misleading_or_clickbait_risk")
    if reviewer_decision != "approved":
        issues.append("human_metadata_review_required")
    return issues


def _write_metadata_files(package_dir: Path, title: str, description: str, tags: list[str], pinned_comment: str) -> None:
    (package_dir / "title.txt").write_text(title, encoding="utf-8")
    (package_dir / "description.txt").write_text(description, encoding="utf-8")
    (package_dir / "tags.txt").write_text("\n".join(tags), encoding="utf-8")
    (package_dir / "pinned_comment.txt").write_text(pinned_comment, encoding="utf-8")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_tags(value: Any) -> list[str]:
    raw = str(value or "")
    tags = [item.strip().lstrip("#") for item in raw.replace(",", "\n").splitlines()]
    return [tag for tag in tags if tag]


def _next_step(issues: list[str]) -> str:
    if not issues:
        return "메타데이터 품질 검토가 완료되었습니다. 최종 업로드 체크리스트를 실행하세요."
    if "human_metadata_review_required" in issues:
        return "제목, 설명, 태그, 고정댓글을 사람이 확인하고 승인하세요."
    if "misleading_or_clickbait_risk" in issues:
        return "과장, 보장, 충격형 표현을 줄이고 실제 영상 내용과 맞게 수정하세요."
    return "메타데이터 누락/길이/중복 항목을 수정하고 다시 점검하세요."
