from __future__ import annotations

from typing import Any

from .paths import GROWTH_DIR, ensure_data_dirs
from .state import now_iso, read_json, write_json
from .weekly_planner import TopicInsight


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


def apply_growth_learning_to_topics(insights: list[TopicInsight]) -> list[TopicInsight]:
    records = recent_performance_records(limit=50)
    if not records:
        return insights

    adjusted: list[TopicInsight] = []
    for insight in insights:
        matches = _matching_records(insight.topic, records)
        if not matches:
            adjusted.append(insight)
            continue

        best = max(float(record.get("growth_score", 0.0)) for record in matches)
        retention = max(float(record.get("retention_pct", 0.0)) for record in matches)
        ctr = max(float(record.get("ctr_pct", 0.0)) for record in matches)
        boost = min(25.0, best * 0.20)
        notes = f"{insight.notes}; growth learning boost={boost:.1f}" if insight.notes else f"growth learning boost={boost:.1f}"
        adjusted.append(
            TopicInsight(
                topic=insight.topic,
                growth_score=min(100.0, insight.growth_score + boost),
                retention_score=max(insight.retention_score, min(100.0, retention)),
                ctr_score=max(insight.ctr_score, min(100.0, ctr * 10.0)),
                originality_score=insight.originality_score,
                notes=notes,
            )
        )
    return adjusted


def _growth_score(record: dict[str, Any]) -> float:
    view_score = min(100.0, float(record.get("views", 0)) / 1000.0 * 40.0)
    retention_score = float(record.get("retention_pct", 0.0)) * 0.35
    ctr_score = min(100.0, float(record.get("ctr_pct", 0.0)) * 10.0) * 0.20
    duration_score = min(100.0, float(record.get("avg_view_duration_sec", 0.0)) * 3.0) * 0.05
    return round(view_score + retention_score + ctr_score + duration_score, 2)


def _matching_records(topic: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    topic_tokens = _tokens(topic)
    if not topic_tokens:
        return []
    matches = []
    for record in records:
        record_text = f"{record.get('title', '')} {record.get('notes', '')}"
        if topic_tokens & _tokens(record_text):
            matches.append(record)
    return matches


def _tokens(text: str) -> set[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in str(text))
    return {token for token in normalized.split() if len(token) >= 2}
