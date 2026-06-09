from __future__ import annotations

from ai_shorts.state import AppState, ShortProject
from ai_shorts.compliance import AssetNote, DraftComplianceInput, GateStatus, SourceMaterial, evaluate_compliance
from ai_shorts.weekly_planner import TopicInsight, clamp_weekly_count, create_weekly_plan


def test_default_app_state_has_autosave_enabled() -> None:
    state = AppState()
    assert state.autosave["enabled"] is True
    assert state.autosave["save_on_every_step"] is True


def test_short_project_defaults_to_idea_status() -> None:
    project = ShortProject(id="p1", title="테스트 쇼츠")
    assert project.status == "idea"
    assert project.title == "테스트 쇼츠"


def test_compliance_blocks_missing_transformation_note() -> None:
    report = evaluate_compliance(
        DraftComplianceInput(
            title="새 쇼츠",
            narration="직접 해설과 새 장면으로 구성합니다.",
            sources=[SourceMaterial(kind="youtube", title="참고 영상", url="https://example.com")],
        )
    )
    assert report.status == GateStatus.BLOCK


def test_compliance_passes_original_generated_draft() -> None:
    report = evaluate_compliance(
        DraftComplianceInput(
            title="아침 시간을 아끼는 3가지 방법",
            narration="직접 작성한 대본과 생성 자산으로 만든 영상입니다.",
            assets=[AssetNote(kind="image", path_or_url="generated://scene-1", generated=True)],
        )
    )
    assert report.status == GateStatus.PASS


def test_weekly_plan_clamps_to_two_or_three() -> None:
    assert clamp_weekly_count(1) == 2
    assert clamp_weekly_count(4) == 3


def test_weekly_plan_selects_highest_scoring_topics() -> None:
    plan = create_weekly_plan(
        [
            TopicInsight(topic="낮은 점수", growth_score=20),
            TopicInsight(topic="높은 점수", growth_score=95, retention_score=90, ctr_score=88, originality_score=80),
        ],
        target_count=2,
    )
    assert plan.slots[0].topic == "높은 점수"
    assert plan.target_count == 2
