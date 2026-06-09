from __future__ import annotations

from ai_shorts.state import AppState, ShortProject, update_project_review
from ai_shorts.compliance import AssetNote, DraftComplianceInput, GateStatus, SourceMaterial, evaluate_compliance
from ai_shorts.script_lab import create_local_script_draft
from ai_shorts.weekly_planner import TopicInsight, clamp_weekly_count, create_weekly_plan
from ai_shorts.web_app import _render_page, _render_project_detail
from ai_shorts.script_lab import script_draft_from_dict
from ai_shorts.render_placeholder import create_render_placeholders
from ai_shorts.render_preview import create_preview_media
from ai_shorts.render_export import build_render_export_status
from ai_shorts.ffmpeg_renderer import ffmpeg_setup_guide, mp4_status


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


def test_script_draft_round_trips_from_dict() -> None:
    draft = create_local_script_draft("대본 수정 테스트", "주제만 참고")
    loaded = script_draft_from_dict(draft.to_dict())
    assert loaded.title == draft.title
    assert loaded.scenes[0].caption == draft.scenes[0].caption


def test_render_placeholder_plan_shape(tmp_path) -> None:
    draft = create_local_script_draft("렌더 테스트", "주제만 참고")
    plan = create_render_placeholders("p1", draft, tmp_path)
    assert plan["status"] == "placeholder_ready"
    assert plan["scene_count"] == len(draft.scenes)
    assert (tmp_path / "renders" / "placeholder" / "render_plan.json").exists()
    assert (tmp_path / "renders" / "placeholder" / "render_manifest.json").exists()
    assert (tmp_path / "renders" / "placeholder" / "timeline.html").exists()


def test_preview_media_creates_gif_and_manifest(tmp_path) -> None:
    draft = create_local_script_draft("미리보기 테스트", "주제만 참고")
    create_render_placeholders("p1", draft, tmp_path)
    manifest = create_preview_media("p1", tmp_path)
    assert manifest["status"] == "preview_ready"
    assert (tmp_path / "renders" / "preview" / "preview.gif").exists()
    assert (tmp_path / "renders" / "preview" / "preview_manifest.json").exists()


def test_mp4_status_records_ffmpeg_state(tmp_path) -> None:
    (tmp_path / "renders" / "preview").mkdir(parents=True)
    status = mp4_status(tmp_path)
    assert "ffmpeg_available" in status
    assert (tmp_path / "renders" / "preview" / "mp4_status.json").exists()


def test_ffmpeg_setup_guide_creates_json_and_markdown(tmp_path) -> None:
    guide = ffmpeg_setup_guide(tmp_path)
    assert guide["status"] == "guide_ready"
    assert "winget" in guide["recommended_windows_command"]
    assert (tmp_path / "renders" / "preview" / "ffmpeg_setup_guide.json").exists()
    assert (tmp_path / "renders" / "preview" / "ffmpeg_setup_guide.md").exists()


def test_render_export_status_records_review_assets(tmp_path) -> None:
    draft = create_local_script_draft("렌더 승인 테스트", "주제만 참고")
    create_render_placeholders("p1", draft, tmp_path)
    create_preview_media("p1", tmp_path)
    status = build_render_export_status(tmp_path, "ready_for_upload_package", "GIF 확인 완료")
    assert status["status"] == "ready_for_upload_package_mp4_pending"
    assert status["assets"]["timeline_ready"] is True
    assert status["assets"]["gif_ready"] is True
    assert status["assets"]["mp4_ready"] is False
    assert (tmp_path / "exports" / "manual_upload_package" / "render_export_status.json").exists()
