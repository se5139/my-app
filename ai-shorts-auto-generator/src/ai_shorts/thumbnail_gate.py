from __future__ import annotations

import html
import struct
import zlib
from pathlib import Path
from typing import Any

from .state import now_iso, read_json, write_json


THUMBNAIL_SIZE = (1280, 720)


def build_thumbnail_gate(project_dir: Path, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    inputs = inputs or {}
    package_dir = project_dir / "exports" / "manual_upload_package"
    thumbnail_dir = package_dir / "thumbnail"
    thumbnail_dir.mkdir(parents=True, exist_ok=True)

    script = read_json(project_dir / "script_draft.json", {})
    title = str(inputs.get("title") or script.get("title") or "").strip()
    thumbnail_text = str(inputs.get("thumbnail_text") or script.get("thumbnail_text") or title).strip()
    source_note = str(inputs.get("source_note") or "로컬 자동 생성 썸네일, 외부 이미지/브랜드/인물 사용 없음").strip()
    reviewer_decision = str(inputs.get("reviewer_decision") or "needs_review").strip()
    reviewer_note = str(inputs.get("reviewer_note") or "").strip()

    png_path = thumbnail_dir / "thumbnail.png"
    svg_path = thumbnail_dir / "thumbnail_review.svg"
    _write_thumbnail_png(png_path)
    _write_thumbnail_svg(svg_path, title, thumbnail_text)

    issues = _validate(title, thumbnail_text, source_note, reviewer_decision, png_path)
    status = "thumbnail_ready" if not issues else "thumbnail_needs_review"
    manifest = {
        "status": status,
        "created_at": now_iso(),
        "thumbnail_png": str(png_path),
        "thumbnail_svg": str(svg_path),
        "size": {"width": THUMBNAIL_SIZE[0], "height": THUMBNAIL_SIZE[1]},
        "title": title,
        "thumbnail_text": thumbnail_text,
        "source_note": source_note,
        "review": {
            "decision": reviewer_decision,
            "reviewer_note": reviewer_note,
            "human_review_required": True,
        },
        "validation": {
            "valid": not issues,
            "issues": issues,
        },
        "no_paid_api_calls": True,
        "public_upload_automation": "disabled",
        "next_step": _next_step(issues),
    }
    write_json(thumbnail_dir / "thumbnail_manifest.json", manifest)
    if status == "thumbnail_ready":
        _copy_for_upload(package_dir, png_path, svg_path, thumbnail_dir / "thumbnail_manifest.json")
    return manifest


def _validate(title: str, thumbnail_text: str, source_note: str, reviewer_decision: str, png_path: Path) -> list[str]:
    issues: list[str] = []
    if not title:
        issues.append("title_missing")
    if not thumbnail_text:
        issues.append("thumbnail_text_missing")
    if len(thumbnail_text) > 28:
        issues.append("thumbnail_text_too_long")
    if not source_note:
        issues.append("source_note_missing")
    if reviewer_decision != "approved":
        issues.append("human_thumbnail_review_required")
    if not png_path.exists():
        issues.append("thumbnail_png_missing")
    return issues


def _copy_for_upload(package_dir: Path, png_path: Path, svg_path: Path, manifest_path: Path) -> None:
    (package_dir / "thumbnail.png").write_bytes(png_path.read_bytes())
    (package_dir / "thumbnail_review.svg").write_text(svg_path.read_text(encoding="utf-8"), encoding="utf-8")
    (package_dir / "thumbnail_manifest.json").write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")


def _write_thumbnail_png(path: Path) -> None:
    width, height = THUMBNAIL_SIZE
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            if x < width * 0.34:
                rgb = (18, 101, 89)
            elif y < height * 0.42:
                rgb = (235, 241, 237)
            else:
                rgb = (246, 184, 84)
            if 70 < x < width - 70 and 70 < y < height - 70:
                rgb = tuple(min(255, value + 12) for value in rgb)
            row.extend(rgb)
        rows.append(bytes(row))
    raw = b"".join(rows)
    png = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += _png_chunk(b"IDAT", zlib.compress(raw, 6))
    png += _png_chunk(b"IEND", b"")
    path.write_bytes(png)


def _write_thumbnail_svg(path: Path, title: str, thumbnail_text: str) -> None:
    safe_title = html.escape(title[:70])
    safe_text = html.escape(thumbnail_text[:40])
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#126559"/>
  <rect x="435" width="845" height="720" fill="#f6b854"/>
  <rect x="72" y="72" width="1136" height="576" rx="0" fill="#f7f8f5" opacity="0.92"/>
  <text x="112" y="228" font-family="Arial, sans-serif" font-size="46" font-weight="700" fill="#126559">{safe_title}</text>
  <text x="112" y="410" font-family="Arial, sans-serif" font-size="94" font-weight="900" fill="#1e1e1e">{safe_text}</text>
  <text x="112" y="540" font-family="Arial, sans-serif" font-size="34" font-weight="700" fill="#8a4f00">Shorts Auto Maker</text>
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def _next_step(issues: list[str]) -> str:
    if not issues:
        return "썸네일 파일과 검토 승인이 준비되었습니다. 최종 업로드 체크리스트를 실행하세요."
    if "human_thumbnail_review_required" in issues:
        return "thumbnail_review.svg를 확인한 뒤 썸네일을 승인하세요."
    if "thumbnail_text_too_long" in issues:
        return "썸네일 문구를 28자 이하로 줄이세요."
    return "썸네일 누락 항목을 보완하고 다시 생성하세요."
