from __future__ import annotations

from ai_shorts.state import AppState, ShortProject, update_project_review
from ai_shorts.compliance import AssetNote, DraftComplianceInput, GateStatus, SourceMaterial, evaluate_compliance
from ai_shorts.script_lab import create_local_script_draft
from ai_shorts.weekly_planner import TopicInsight, clamp_weekly_count, create_weekly_plan
from ai_shorts.web_app import _render_page, _render_project_detail


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


def test_local_script_draft_has_transformation_note() -> None:
    draft = create_local_script_draft("퇴근 후 시간 관리", "인기 영상들의 주제 흐름만 참고")
    assert draft.title
    assert draft.scenes
    assert "복제하지 않고" in draft.transformation_note


def test_web_app_renders_korean_workspace() -> None:
    html = _render_page().decode("utf-8")
    assert "새 쇼츠 초안" in html
    assert "주간 2~3개 계획" in html


def test_project_detail_handles_unknown_project() -> None:
    html = _render_project_detail("missing-project-id")
    assert "초안을 찾을 수 없습니다" in html


def test_update_project_review_missing_project_raises() -> None:
    try:
        update_project_review("missing-project-id", "approved_for_export", "검토 완료")
    except FileNotFoundError:
        return
    raise AssertionError("missing project should raise FileNotFoundError")
