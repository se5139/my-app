from __future__ import annotations

from ai_shorts.state import AppState, ShortProject, update_project_review
from ai_shorts.compliance import AssetNote, DraftComplianceInput, GateStatus, SourceMaterial, evaluate_compliance
from ai_shorts.environment_check import collect_environment_check
from ai_shorts.first_run_setup import build_first_run_checklist, export_setup_guides, list_setup_guides, read_setup_guide
from ai_shorts.handoff_report import create_handoff_report, list_handoff_reports, read_handoff_report
from ai_shorts.script_lab import create_local_script_draft
from ai_shorts.weekly_planner import TopicInsight, clamp_weekly_count, create_weekly_plan
from ai_shorts.web_app import _render_page, _render_project_detail
from ai_shorts.script_lab import script_draft_from_dict
from ai_shorts.render_placeholder import create_render_placeholders
from ai_shorts.render_preview import create_preview_media
from ai_shorts.render_export import build_render_export_status
from ai_shorts.ffmpeg_renderer import ffmpeg_setup_guide, mp4_status
from ai_shorts.growth_learning import add_performance_record, apply_growth_learning_to_topics, import_performance_csv, recent_performance_records
from ai_shorts.operations_snapshot import create_operations_snapshot
from ai_shorts.project_dashboard import summarize_project_gate
from ai_shorts.restore_guide import new_pc_start_markdown, restore_steps
from ai_shorts.state import write_json
from ai_shorts.upload_checklist import build_final_upload_checklist
from ai_shorts.weekly_queue import mark_slot_promoted, save_weekly_plan_queue


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
    assert "로컬 환경 점검" in html
    assert "첫 실행 설정 체크리스트" in html
    assert "설정 가이드 생성" in html
    assert "생성된 가이드 보기" in html
    assert "handoff 보고서" in html
    assert "생성된 보고서 보기" in html


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


def test_final_upload_checklist_blocks_without_mp4(tmp_path) -> None:
    package_dir = tmp_path / "exports" / "manual_upload_package"
    package_dir.mkdir(parents=True)
    write_json(tmp_path / "project.json", {"review": {"status": "approved_for_export"}})
    write_json(package_dir / "compliance_report.json", {"status": "pass"})
    write_json(package_dir / "asset_source_notes.json", {"sources": [], "assets": []})
    write_json(package_dir / "render_export_status.json", {"status": "ready_for_upload_package_mp4_pending"})
    (package_dir / "title.txt").write_text("title", encoding="utf-8")
    (package_dir / "description.txt").write_text("description", encoding="utf-8")
    (package_dir / "tags.txt").write_text("tag", encoding="utf-8")

    checklist = build_final_upload_checklist(tmp_path, "final check")
    assert checklist["status"] == "blocked_before_upload"
    assert checklist["manual_upload_allowed"] is False
    assert "mp4_present" in checklist["missing"]
    assert "render_export_ready" in checklist["missing"]
    assert (package_dir / "final_upload_checklist.json").exists()


def test_project_dashboard_reports_first_blocking_gate(tmp_path) -> None:
    write_json(tmp_path / "project.json", {"status": "idea", "review": {"status": "needs_review"}})
    summary = summarize_project_gate(tmp_path)
    assert summary["blocking_gate"] == "project_review"
    assert "검토" in summary["next_step"]


def test_weekly_plan_queue_marks_promoted_slot(tmp_path, monkeypatch) -> None:
    from ai_shorts import weekly_queue

    monkeypatch.setattr(weekly_queue, "WEEKLY_PLAN_QUEUE_PATH", tmp_path / "weekly_plan_queue.json")
    plan = create_weekly_plan([TopicInsight(topic="큐 테스트")], target_count=2).to_dict()
    queue = save_weekly_plan_queue(plan)
    assert queue["slots"][0]["status"] == "queued"

    updated = mark_slot_promoted("큐 테스트", "project-1")
    assert updated["slots"][0]["status"] == "promoted_to_draft"
    assert updated["slots"][0]["promoted_project_id"] == "project-1"


def test_growth_learning_records_performance(tmp_path, monkeypatch) -> None:
    from ai_shorts import growth_learning

    monkeypatch.setattr(growth_learning, "PERFORMANCE_RECORDS_PATH", tmp_path / "performance_records.json")
    record = add_performance_record("성과 테스트", views=1200, retention_pct=62.5, ctr_pct=7.2, avg_view_duration_sec=18, notes="hook good")
    assert record["growth_score"] > 0
    records = recent_performance_records()
    assert records[0]["title"] == "성과 테스트"
    assert (tmp_path / "performance_records.json").exists()


def test_growth_learning_boosts_matching_weekly_topics(tmp_path, monkeypatch) -> None:
    from ai_shorts import growth_learning

    monkeypatch.setattr(growth_learning, "PERFORMANCE_RECORDS_PATH", tmp_path / "performance_records.json")
    add_performance_record("출근 루틴 성공 영상", views=2500, retention_pct=72, ctr_pct=8.1, avg_view_duration_sec=22)
    insights = apply_growth_learning_to_topics(
        [
            TopicInsight(topic="출근 루틴 정리", growth_score=50),
            TopicInsight(topic="저녁 식단 기록", growth_score=50),
        ]
    )
    plan = create_weekly_plan(insights, target_count=2)
    assert plan.slots[0].topic == "출근 루틴 정리"
    assert "growth learning boost" in plan.slots[0].reason


def test_growth_learning_imports_csv_rows(tmp_path, monkeypatch) -> None:
    from ai_shorts import growth_learning

    monkeypatch.setattr(growth_learning, "PERFORMANCE_RECORDS_PATH", tmp_path / "performance_records.json")
    result = import_performance_csv(
        "Title,Views,Average percentage viewed,Impressions click-through rate,Average view duration,Notes\n"
        "CSV Topic,\"1,500\",66.5,7.4,21,good hook\n"
    )
    assert result["imported_count"] == 1
    records = recent_performance_records()
    assert records[0]["title"] == "CSV Topic"
    assert records[0]["views"] == 1500
    assert records[0]["growth_score"] > 0


def test_web_app_renders_growth_import_result() -> None:
    html = _render_page(growth_import={"imported_count": 2, "skipped_count": 1, "skipped": [{"row": 4, "reason": "missing_title"}]}).decode("utf-8")
    assert "CSV 가져오기 결과" in html
    assert "missing_title" in html


def test_operations_snapshot_creates_zip(tmp_path, monkeypatch) -> None:
    from ai_shorts import operations_snapshot, paths

    data_dir = tmp_path / "data"
    projects_dir = data_dir / "projects"
    monkeypatch.setattr(paths, "DATA_DIR", data_dir)
    monkeypatch.setattr(paths, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(operations_snapshot, "DATA_DIR", data_dir)
    monkeypatch.setattr(operations_snapshot, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(operations_snapshot, "SNAPSHOT_DIR", data_dir / "snapshots")
    write_json(data_dir / "app_state.json", {"projects": [{"id": "p1", "title": "Snapshot Test", "status": "idea"}]})
    write_json(projects_dir / "p1" / "project.json", {"status": "idea", "review": {"status": "needs_review"}})

    snapshot = create_operations_snapshot()
    assert snapshot["project_count"] == 1
    assert snapshot["zip_path"].endswith(".zip")
    assert snapshot["restore_steps"]
    assert (data_dir / "snapshots").exists()


def test_restore_guide_has_repo_and_snapshot_steps() -> None:
    steps = restore_steps()
    markdown = new_pc_start_markdown({"project_count": 1})
    assert any("github.com/se5139/my-app.git" in step["command"] for step in steps)
    assert any("data folder" in step["body"] for step in steps)
    assert "New PC Start Here" in markdown


def test_environment_check_reports_core_items() -> None:
    report = collect_environment_check()
    names = {item["name"] for item in report["checks"]}
    assert {"Python", "Git", "Data folder", "Projects", "FFmpeg"}.issubset(names)
    assert report["overall_status"] in {"ready", "usable_with_warnings", "needs_setup"}


def test_first_run_setup_turns_environment_into_actions() -> None:
    checklist = build_first_run_checklist(
        {
            "checks": [
                {"name": "Python", "status": "pass"},
                {"name": "Git", "status": "warn"},
                {"name": "Data folder", "status": "warn"},
                {"name": "Projects", "status": "warn"},
                {"name": "FFmpeg", "status": "warn"},
            ]
        }
    )
    action_ids = {item["id"] for item in checklist["actions"]}
    assert {"clone_or_pull_repo", "restore_snapshot_data", "start_web_app", "enable_mp4_rendering"}.issubset(action_ids)
    assert checklist["overall_status"] in {"blocked", "needs_attention", "ready"}


def test_first_run_setup_exports_markdown_guides(tmp_path, monkeypatch) -> None:
    from ai_shorts import first_run_setup

    monkeypatch.setattr(first_run_setup, "SETUP_GUIDES_DIR", tmp_path / "setup_guides")
    manifest = export_setup_guides(
        {
            "checks": [
                {"name": "Python", "status": "pass"},
                {"name": "Git", "status": "warn"},
                {"name": "Data folder", "status": "warn"},
                {"name": "Projects", "status": "warn"},
                {"name": "FFmpeg", "status": "warn"},
            ]
        }
    )
    assert manifest["guide_count"] == 4
    assert (tmp_path / "setup_guides").exists()
    assert all(pathlib_path_exists(item["path"]) for item in manifest["guides"])


def test_first_run_setup_lists_and_reads_guides(tmp_path, monkeypatch) -> None:
    from ai_shorts import first_run_setup

    monkeypatch.setattr(first_run_setup, "SETUP_GUIDES_DIR", tmp_path / "setup_guides")
    export_setup_guides(
        {
            "checks": [
                {"name": "Python", "status": "pass"},
                {"name": "Git", "status": "warn"},
                {"name": "Data folder", "status": "warn"},
                {"name": "Projects", "status": "warn"},
                {"name": "FFmpeg", "status": "warn"},
            ]
        }
    )
    guides = list_setup_guides()
    assert guides
    detail = read_setup_guide(guides[0]["filename"])
    assert detail["filename"] == guides[0]["filename"]
    assert "Command Or Action" in detail["content"]


def test_handoff_report_creates_markdown_and_manifest(tmp_path, monkeypatch) -> None:
    from ai_shorts import first_run_setup, handoff_report, operations_snapshot

    monkeypatch.setattr(first_run_setup, "SETUP_GUIDES_DIR", tmp_path / "setup_guides")
    monkeypatch.setattr(operations_snapshot, "SNAPSHOT_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(handoff_report, "SNAPSHOT_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(handoff_report, "HANDOFF_REPORTS_DIR", tmp_path / "handoff_reports")
    (tmp_path / "snapshots").mkdir(parents=True)
    (tmp_path / "snapshots" / "operations_snapshot_test.zip").write_text("zip placeholder", encoding="utf-8")
    export_setup_guides(
        {
            "checks": [
                {"name": "Python", "status": "pass"},
                {"name": "Git", "status": "warn"},
                {"name": "Data folder", "status": "warn"},
                {"name": "Projects", "status": "warn"},
                {"name": "FFmpeg", "status": "warn"},
            ]
        }
    )

    report = create_handoff_report()
    assert report["latest_snapshot"].endswith("operations_snapshot_test.zip")
    assert report["setup_guide_count"] == 4
    assert pathlib_path_exists(report["report_path"])
    assert pathlib_path_exists(report["manifest_path"])


def test_handoff_report_lists_and_reads_reports(tmp_path, monkeypatch) -> None:
    from ai_shorts import handoff_report, operations_snapshot

    monkeypatch.setattr(operations_snapshot, "SNAPSHOT_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(handoff_report, "SNAPSHOT_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(handoff_report, "HANDOFF_REPORTS_DIR", tmp_path / "handoff_reports")
    create_handoff_report()
    reports = list_handoff_reports()
    assert reports
    detail = read_handoff_report(reports[0]["filename"])
    assert detail["filename"] == reports[0]["filename"]
    assert "Resume Rule" in detail["content"]


def pathlib_path_exists(path: str) -> bool:
    from pathlib import Path

    return Path(path).exists()
