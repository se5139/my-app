from __future__ import annotations

from typing import Any

from .paths import GROWTH_DIR, ensure_data_dirs
from .state import now_iso, read_json, write_json


PERFORMANCE_RECORDS_PATH = GROWTH_DIR / "performance_records.json"


def add_performance_record(
    title: str,
    project_id: str = "",
    views: int = 0,
    retention_pct: float = 0.0,
    ctr_pct: float = 0.0,
    avg_view_duration_sec: float = 0.0,
    notes: str = "",
) -> dict[str, Any]:
    ensure_data_dirs()
    record = {
        "recorded_at": now_iso(),
        "project_id": project_id.strip(),
        "title": title.strip() or "Untitled performance record",
        "views": max(0, int(views or 0)),
        "retention_pct": max(0.0, min(100.0, float(retention_pct or 0.0))),
        "ctr_pct": max(0.0, min(100.0, float(ctr_pct or 0.0))),
        "avg_view_duration_sec": max(0.0, float(avg_view_duration_sec or 0.0)),
        "notes": notes.strip(),
    }
    record["growth_score"] = _growth_score(record)

    payload = read_json(PERFORMANCE_RECORDS_PATH, {"records": []})
    records = list(payload.get("records", []))
    records.append(record)
    payload = {
        "updated_at": now_iso(),
        "record_count": len(records),
        "records": records,
    }
    write_json(PERFORMANCE_RECORDS_PATH, payload)
    return record


def recent_performance_records(limit: int = 5) -> list[dict[str, Any]]:
    payload = read_json(PERFORMANCE_RECORDS_PATH, {"records": []})
    return list(reversed(payload.get("records", [])))[:limit]


def _growth_score(record: dict[str, Any]) -> float:
    view_score = min(100.0, float(record.get("views", 0)) / 1000.0 * 40.0)
    retention_score = float(record.get("retention_pct", 0.0)) * 0.35
    ctr_score = min(100.0, float(record.get("ctr_pct", 0.0)) * 10.0) * 0.20
    duration_score = min(100.0, float(record.get("avg_view_duration_sec", 0.0)) * 3.0) * 0.05
    return round(view_score + retention_score + ctr_score + duration_score, 2)
