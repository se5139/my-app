from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass
class TopicInsight:
    topic: str
    growth_score: float = 50.0
    retention_score: float = 50.0
    ctr_score: float = 50.0
    originality_score: float = 50.0
    notes: str = ""


@dataclass
class WeeklyDraftSlot:
    slot_no: int
    topic: str
    reason: str
    target_status: str = "draft_only"
    required_gates: list[str] = field(default_factory=lambda: ["compliance", "originality", "human_review"])


@dataclass
class WeeklyPlan:
    week_start: str
    target_count: int
    slots: list[WeeklyDraftSlot]
    automation_note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "week_start": self.week_start,
            "target_count": self.target_count,
            "slots": [asdict(slot) for slot in self.slots],
            "automation_note": self.automation_note,
        }


def _score(insight: TopicInsight) -> float:
    return (
        insight.growth_score * 0.35
        + insight.retention_score * 0.25
        + insight.ctr_score * 0.20
        + insight.originality_score * 0.20
    )


def clamp_weekly_count(target_count: int) -> int:
    return max(2, min(3, int(target_count or 2)))


def create_weekly_plan(
    insights: list[TopicInsight],
    target_count: int = 2,
    week_start: date | None = None,
) -> WeeklyPlan:
    count = clamp_weekly_count(target_count)
    week = (week_start or date.today()).isoformat()

    ranked = sorted(insights, key=_score, reverse=True)
    if not ranked:
        ranked = [
            TopicInsight(topic="생활 문제 해결형 쇼츠", notes="기본 안전 주제"),
            TopicInsight(topic="직장/일상 공감형 쇼츠", notes="기본 안전 주제"),
            TopicInsight(topic="시간 절약 팁 쇼츠", notes="기본 안전 주제"),
        ]

    slots: list[WeeklyDraftSlot] = []
    for idx, insight in enumerate(ranked[:count], start=1):
        reason = (
            f"growth={insight.growth_score:.1f}, retention={insight.retention_score:.1f}, "
            f"ctr={insight.ctr_score:.1f}, originality={insight.originality_score:.1f}"
        )
        if insight.notes:
            reason = f"{reason}; {insight.notes}"
        slots.append(WeeklyDraftSlot(slot_no=idx, topic=insight.topic, reason=reason))

    return WeeklyPlan(
        week_start=week,
        target_count=count,
        slots=slots,
        automation_note="주간 자동화는 초안 패키지만 생성하며, 공개 업로드는 사람의 최종 승인 후에만 가능합니다.",
    )
