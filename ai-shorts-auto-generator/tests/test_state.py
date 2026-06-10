from __future__ import annotations

import subprocess
import wave
import zipfile

from ai_shorts.audio_assets import build_audio_asset_manifest
from ai_shorts.audio_mixer import mix_audio_into_video
from ai_shorts.api_keys import api_connector_readiness, api_key_status, save_api_keys
from ai_shorts.api_smoke_check import run_api_smoke_check
from ai_shorts.cost_guard import cost_guard_summary, evaluate_api_call, save_cost_guard
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
from ai_shorts.ffmpeg_renderer import ffmpeg_setup_guide, mp4_status, render_mp4_from_preview
from ai_shorts.final_media_package import build_final_media_package
from ai_shorts.subtitle_export import create_subtitle_files
from ai_shorts.growth_learning import add_performance_record, apply_growth_learning_to_topics, import_performance_csv, recent_performance_records
from ai_shorts.operations_snapshot import create_operations_snapshot
from ai_shorts.production_readiness import build_production_readiness
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
    assert "제작 준비도" in html
    assert "API 키 준비" in html
    assert "API별 연결 준비" in html
    assert "API 비용 차단" in html
    assert "콘텐츠 제작 흐름" in html


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
    draft = create_local_script_draft("대본 수정 테스트", "주제만 참고", target_duration_sec=60)
    loaded = script_draft_from_dict(draft.to_dict())
    assert loaded.title == draft.title
    assert loaded.scenes[0].caption == draft.scenes[0].caption
    assert loaded.target_duration_sec == 60
    assert script_draft_from_dict({"scenes": []}).target_duration_sec == 45


def test_render_placeholder_plan_shape(tmp_path) -> None:
    draft = create_local_script_draft("렌더 테스트", "주제만 참고", target_duration_sec=30)
    plan = create_render_placeholders("p1", draft, tmp_path)
    assert plan["status"] == "placeholder_ready"
    assert plan["target_duration_sec"] == 30
    assert plan["total_duration_sec"] == 30
    assert plan["scene_count"] == len(draft.scenes)
    assert (tmp_path / "renders" / "placeholder" / "render_plan.json").exists()
    assert (tmp_path / "renders" / "placeholder" / "render_manifest.json").exists()
    assert (tmp_path / "renders" / "placeholder" / "timing_plan.json").exists()
    assert (tmp_path / "renders" / "placeholder" / "timeline.html").exists()
    assert sum(scene["duration_sec"] for scene in plan["scenes"]) == 30


def test_preview_media_creates_gif_and_manifest(tmp_path) -> None:
    draft = create_local_script_draft("미리보기 테스트", "주제만 참고", target_duration_sec=60)
    create_render_placeholders("p1", draft, tmp_path)
    manifest = create_preview_media("p1", tmp_path)
    assert manifest["status"] == "preview_ready"
    assert manifest["target_duration_sec"] == 60
    assert sum(frame["duration_ms"] for frame in manifest["frames"]) == 60000
    assert (tmp_path / "renders" / "preview" / "preview.gif").exists()
    assert (tmp_path / "renders" / "preview" / "preview_manifest.json").exists()


def test_subtitle_export_creates_srt_vtt_and_manifest(tmp_path) -> None:
    draft = create_local_script_draft("자막 테스트", "주제만 참고", target_duration_sec=30)
    create_render_placeholders("p1", draft, tmp_path)
    manifest = create_subtitle_files("p1", tmp_path)
    assert manifest["status"] == "subtitles_ready"
    assert manifest["validation"]["valid"] is True
    assert manifest["validation"]["entry_count"] == len(draft.scenes)
    assert manifest["validation"]["total_duration_sec"] == 30
    assert (tmp_path / "renders" / "subtitles" / "subtitles.srt").exists()
    assert (tmp_path / "renders" / "subtitles" / "subtitles.vtt").exists()
    assert (tmp_path / "renders" / "subtitles" / "subtitle_manifest.json").exists()
    assert "WEBVTT" in (tmp_path / "renders" / "subtitles" / "subtitles.vtt").read_text(encoding="utf-8")


def test_mp4_status_records_ffmpeg_state(tmp_path) -> None:
    (tmp_path / "renders" / "preview").mkdir(parents=True)
    status = mp4_status(tmp_path)
    assert "ffmpeg_available" in status
    assert (tmp_path / "renders" / "preview" / "mp4_status.json").exists()


def test_mp4_render_uses_timing_concat_and_subtitle_sidecars(tmp_path, monkeypatch) -> None:
    from ai_shorts import ffmpeg_renderer

    draft = create_local_script_draft("MP4 타이밍 테스트", "주제만 참고", target_duration_sec=30)
    create_render_placeholders("p1", draft, tmp_path)
    create_preview_media("p1", tmp_path)
    create_subtitle_files("p1", tmp_path)

    def fake_run(command, capture_output, text, timeout):
        output_path = tmp_path / "renders" / "preview" / "preview.mp4"
        output_path.write_bytes(b"mp4")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(ffmpeg_renderer, "find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(ffmpeg_renderer.subprocess, "run", fake_run)

    status = render_mp4_from_preview("p1", tmp_path)
    concat_path = tmp_path / "renders" / "preview" / "ffmpeg_concat_frames.txt"
    concat_text = concat_path.read_text(encoding="utf-8")
    assert status["status"] == "mp4_ready"
    assert status["target_duration_sec"] == 30
    assert status["subtitle_mode"] == "sidecar"
    assert status["subtitle_sidecars"]["srt"].endswith("subtitles.srt")
    assert "duration 7.500" in concat_text
    assert concat_path.exists()


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
    create_subtitle_files("p1", tmp_path)
    voice_path = _write_silent_wav(tmp_path / "voice.wav", 45)
    build_audio_asset_manifest(tmp_path, {"voice_path": str(voice_path), "voice_source_note": "직접 녹음"})
    status = build_render_export_status(tmp_path, "ready_for_upload_package", "GIF 확인 완료")
    assert status["status"] == "ready_for_upload_package_mp4_pending"
    assert status["assets"]["timeline_ready"] is True
    assert status["assets"]["gif_ready"] is True
    assert status["assets"]["subtitles_ready"] is True
    assert status["assets"]["audio_ready"] is True
    assert status["assets"]["mp4_ready"] is False
    assert (tmp_path / "exports" / "manual_upload_package" / "render_export_status.json").exists()


def test_render_export_blocks_without_subtitles_when_timing_exists(tmp_path) -> None:
    draft = create_local_script_draft("자막 누락 테스트", "주제만 참고")
    create_render_placeholders("p1", draft, tmp_path)
    create_preview_media("p1", tmp_path)
    status = build_render_export_status(tmp_path, "ready_for_upload_package", "자막 전 검토")
    assert status["status"] == "needs_revision"
    assert "subtitles_required_before_export" in status["blockers"]


def test_audio_asset_manifest_validates_local_voice_and_bgm(tmp_path) -> None:
    draft = create_local_script_draft("오디오 테스트", "주제만 참고", target_duration_sec=30)
    create_render_placeholders("p1", draft, tmp_path)
    voice_path = _write_silent_wav(tmp_path / "voice.wav", 30)
    bgm_path = _write_silent_wav(tmp_path / "bgm.wav", 30)

    manifest = build_audio_asset_manifest(
        tmp_path,
        {
            "voice_path": str(voice_path),
            "voice_source_note": "직접 녹음",
            "bgm_path": str(bgm_path),
            "bgm_source_note": "직접 제작",
            "bgm_volume_pct": 18,
        },
    )

    assert manifest["status"] == "audio_ready"
    assert manifest["mix"]["no_paid_api_calls"] is True
    assert (tmp_path / "renders" / "audio" / "source" / "voice.wav").exists()
    assert (tmp_path / "renders" / "audio" / "audio_manifest.json").exists()


def test_audio_mixer_creates_mixed_audio_and_final_video(tmp_path, monkeypatch) -> None:
    from ai_shorts import audio_mixer

    voice_path = _write_silent_wav(tmp_path / "voice.wav", 1)
    build_audio_asset_manifest(
        tmp_path,
        {"voice_path": str(voice_path), "voice_source_note": "직접 녹음", "target_duration_sec": 1},
    )
    preview_dir = tmp_path / "renders" / "preview"
    preview_dir.mkdir(parents=True)
    preview_mp4 = preview_dir / "preview.mp4"
    preview_mp4.write_bytes(b"mp4")
    write_json(preview_dir / "mp4_status.json", {"status": "mp4_ready", "mp4_path": str(preview_mp4)})

    def fake_run(command, capture_output, text, timeout):
        output_path = tmp_path / command[-1] if not str(command[-1]).startswith(str(tmp_path)) else command[-1]
        output_path = tmp_path / "renders" / "audio" / "mixed_audio.m4a" if str(output_path).endswith(".m4a") else tmp_path / "renders" / "final" / "final_preview.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"media")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(audio_mixer, "find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(audio_mixer.subprocess, "run", fake_run)

    status = mix_audio_into_video("p1", tmp_path)

    assert status["status"] == "final_video_ready"
    assert (tmp_path / "renders" / "audio" / "mixed_audio.m4a").exists()
    assert (tmp_path / "renders" / "final" / "final_preview.mp4").exists()
    assert status["no_paid_api_calls"] is True


def test_final_media_package_copies_mp4_and_sidecar_subtitles(tmp_path) -> None:
    package_dir = tmp_path / "exports" / "manual_upload_package"
    preview_dir = tmp_path / "renders" / "preview"
    subtitle_dir = tmp_path / "renders" / "subtitles"
    preview_dir.mkdir(parents=True)
    subtitle_dir.mkdir(parents=True)
    mp4_path = preview_dir / "preview.mp4"
    srt_path = subtitle_dir / "subtitles.srt"
    vtt_path = subtitle_dir / "subtitles.vtt"
    mp4_path.write_bytes(b"mp4")
    srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\n테스트\n", encoding="utf-8")
    vtt_path.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\n테스트\n", encoding="utf-8")
    voice_path = _write_silent_wav(tmp_path / "voice.wav", 1)
    write_json(preview_dir / "mp4_status.json", {"status": "mp4_ready", "mp4_path": str(mp4_path)})
    write_json(
        subtitle_dir / "subtitle_manifest.json",
        {"status": "subtitles_ready", "srt_path": str(srt_path), "vtt_path": str(vtt_path)},
    )
    build_audio_asset_manifest(
        tmp_path,
        {"voice_path": str(voice_path), "voice_source_note": "직접 녹음", "target_duration_sec": 1},
    )
    mixed_audio = tmp_path / "renders" / "audio" / "mixed_audio.m4a"
    final_video = tmp_path / "renders" / "final" / "final_preview.mp4"
    mixed_audio.write_bytes(b"audio")
    final_video.parent.mkdir(parents=True)
    final_video.write_bytes(b"mp4")
    write_json(
        tmp_path / "renders" / "audio" / "audio_mix_status.json",
        {"status": "final_video_ready", "mixed_audio_path": str(mixed_audio), "final_video_path": str(final_video)},
    )

    manifest = build_final_media_package(tmp_path)

    assert manifest["status"] == "final_media_ready"
    assert (package_dir / "media" / "preview_silent.mp4").exists()
    assert (package_dir / "media" / "final_preview.mp4").exists()
    assert (package_dir / "media" / "subtitles.srt").exists()
    assert (package_dir / "media" / "subtitles.vtt").exists()
    assert (package_dir / "media" / "audio" / "audio_manifest.json").exists()
    assert (package_dir / "media" / "audio" / "mixed_audio.m4a").exists()
    assert manifest["subtitle_mode"] == "sidecar"


def test_final_upload_checklist_blocks_without_mp4(tmp_path) -> None:
    package_dir = tmp_path / "exports" / "manual_upload_package"
    package_dir.mkdir(parents=True)
    write_json(tmp_path / "project.json", {"review": {"status": "approved_for_export"}})
    write_json(package_dir / "compliance_report.json", {"status": "pass"})
    write_json(package_dir / "asset_source_notes.json", {"sources": [], "assets": []})
    write_json(package_dir / "render_export_status.json", {"status": "ready_for_upload_package_mp4_pending"})
    write_json(tmp_path / "renders" / "subtitles" / "subtitle_manifest.json", {"status": "subtitles_ready"})
    (package_dir / "title.txt").write_text("title", encoding="utf-8")
    (package_dir / "description.txt").write_text("description", encoding="utf-8")
    (package_dir / "tags.txt").write_text("tag", encoding="utf-8")

    checklist = build_final_upload_checklist(tmp_path, "final check")
    assert checklist["status"] == "blocked_before_upload"
    assert checklist["manual_upload_allowed"] is False
    assert "mp4_present" in checklist["missing"]
    assert "audio_ready" in checklist["missing"]
    assert "audio_mix_ready" in checklist["missing"]
    assert "final_media_ready" in checklist["missing"]
    assert "render_export_ready" in checklist["missing"]
    assert (package_dir / "final_upload_checklist.json").exists()


def test_project_dashboard_reports_first_blocking_gate(tmp_path) -> None:
    write_json(tmp_path / "project.json", {"status": "idea", "review": {"status": "needs_review"}})
    summary = summarize_project_gate(tmp_path)
    assert summary["blocking_gate"] == "project_review"
    assert "검토" in summary["next_step"]


def test_project_dashboard_reports_subtitle_gate(tmp_path) -> None:
    write_json(tmp_path / "project.json", {"status": "idea", "review": {"status": "approved_for_export"}})
    write_json(tmp_path / "exports" / "manual_upload_package" / "compliance_report.json", {"status": "pass"})
    write_json(tmp_path / "renders" / "placeholder" / "render_manifest.json", {"status": "review_package_ready"})
    summary = summarize_project_gate(tmp_path)
    assert summary["blocking_gate"] == "subtitles"
    assert "SRT/VTT" in summary["next_step"]


def _write_silent_wav(path, duration_sec: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 8000
    frame_count = sample_rate * duration_sec
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * frame_count)
    return path


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


def test_operations_snapshot_excludes_local_secrets(tmp_path, monkeypatch) -> None:
    from ai_shorts import operations_snapshot, paths

    data_dir = tmp_path / "data"
    projects_dir = data_dir / "projects"
    monkeypatch.setattr(paths, "DATA_DIR", data_dir)
    monkeypatch.setattr(paths, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(operations_snapshot, "DATA_DIR", data_dir)
    monkeypatch.setattr(operations_snapshot, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(operations_snapshot, "SNAPSHOT_DIR", data_dir / "snapshots")
    monkeypatch.setattr(operations_snapshot, "SECRETS_DIR", data_dir / "secrets")
    write_json(data_dir / "app_state.json", {"projects": []})
    write_json(data_dir / "secrets" / "api_keys.json", {"keys": {"gemini_api_key": "secret"}})

    snapshot = create_operations_snapshot()
    with zipfile.ZipFile(snapshot["zip_path"]) as archive:
        names = archive.namelist()
    assert not any("secrets" in name for name in names)


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


def test_api_keys_save_and_mask_status(tmp_path, monkeypatch) -> None:
    from ai_shorts import api_keys

    monkeypatch.setattr(api_keys, "SECRETS_DIR", tmp_path / "secrets")
    monkeypatch.setattr(api_keys, "API_KEYS_PATH", tmp_path / "secrets" / "api_keys.json")
    result = save_api_keys(
        {
            "gemini_api_key": "gemini-secret-1234",
            "youtube_api_key": "youtube-secret-1234",
            "naver_client_id": "naver-client-id",
            "naver_client_secret": "naver-client-secret",
            "kakao_rest_api_key": "kakao-secret-1234",
        }
    )
    status = api_key_status()
    assert len(result["updated"]) == 5
    assert all(item["configured"] == "yes" for item in status)
    assert all("secret-1234" not in item["masked"] for item in status)


def test_api_connector_readiness_groups_required_keys(tmp_path, monkeypatch) -> None:
    from ai_shorts import api_keys

    monkeypatch.setattr(api_keys, "API_KEYS_PATH", tmp_path / "secrets" / "api_keys.json")
    missing = api_connector_readiness()
    assert {item["name"] for item in missing} == {"gemini", "youtube", "naver", "kakao"}
    assert all(item["status"] == "missing_keys" for item in missing)

    save_api_keys(
        {
            "gemini_api_key": "gemini-secret-1234",
            "youtube_api_key": "youtube-secret-1234",
            "naver_client_id": "naver-client-id",
            "naver_client_secret": "naver-client-secret",
            "kakao_rest_api_key": "kakao-secret-1234",
        }
    )
    ready = api_connector_readiness()
    assert all(item["status"] == "ready" for item in ready)
    assert all(item["network_check"] == "not_run" for item in ready)


def test_api_smoke_check_uses_cost_guard_before_network(tmp_path, monkeypatch) -> None:
    from ai_shorts import api_keys, api_smoke_check, cost_guard

    monkeypatch.setattr(api_keys, "API_KEYS_PATH", tmp_path / "secrets" / "api_keys.json")
    monkeypatch.setattr(cost_guard, "COST_GUARD_DIR", tmp_path / "settings")
    monkeypatch.setattr(cost_guard, "COST_GUARD_PATH", tmp_path / "settings" / "cost_guard.json")
    monkeypatch.setattr(api_smoke_check, "SMOKE_CHECK_DIR", tmp_path / "api_smoke_checks")
    monkeypatch.setattr(api_smoke_check, "SMOKE_CHECK_PATH", tmp_path / "api_smoke_checks" / "latest_smoke_checks.json")
    save_api_keys({"gemini_api_key": "gemini-secret-1234"})

    result = run_api_smoke_check("gemini")
    assert result["status"] == "blocked_by_cost_guard"
    assert result["network_call_executed"] is False
    assert result["cost_guard"]["reason"] == "external_api_calls_blocked"
    assert result["local_key_validation"][0]["status"] == "shape_ok"
    assert result["endpoint_plan"]["network_call_enabled"] is False
    assert result["endpoint_plan"]["estimated_cost_units"] == 0
    assert pathlib_path_exists(str(tmp_path / "api_smoke_checks" / "latest_smoke_checks.json"))


def test_api_smoke_check_flags_short_key_shape_without_network(tmp_path, monkeypatch) -> None:
    from ai_shorts import api_keys, api_smoke_check, cost_guard

    monkeypatch.setattr(api_keys, "API_KEYS_PATH", tmp_path / "secrets" / "api_keys.json")
    monkeypatch.setattr(cost_guard, "COST_GUARD_DIR", tmp_path / "settings")
    monkeypatch.setattr(cost_guard, "COST_GUARD_PATH", tmp_path / "settings" / "cost_guard.json")
    monkeypatch.setattr(api_smoke_check, "SMOKE_CHECK_DIR", tmp_path / "api_smoke_checks")
    monkeypatch.setattr(api_smoke_check, "SMOKE_CHECK_PATH", tmp_path / "api_smoke_checks" / "latest_smoke_checks.json")
    save_api_keys({"gemini_api_key": "short"})

    result = run_api_smoke_check("gemini")
    assert result["status"] == "invalid_key_shape"
    assert result["network_call_executed"] is False
    assert result["local_key_validation"][0]["status"] == "too_short"
    assert result["cost_guard"]["reason"] == "external_api_calls_blocked"


def test_cost_guard_blocks_external_and_paid_calls(tmp_path, monkeypatch) -> None:
    from ai_shorts import cost_guard

    monkeypatch.setattr(cost_guard, "COST_GUARD_DIR", tmp_path / "settings")
    monkeypatch.setattr(cost_guard, "COST_GUARD_PATH", tmp_path / "settings" / "cost_guard.json")
    blocked = evaluate_api_call("gemini", 0, "smoke")
    assert blocked["allowed"] is False
    assert blocked["reason"] == "external_api_calls_blocked"

    save_cost_guard({"external_api_calls_allowed": "yes"})
    free_check = evaluate_api_call("gemini", 0, "smoke")
    paid_check = evaluate_api_call("gemini", 1, "generation")
    summary = cost_guard_summary()
    assert free_check["allowed"] is True
    assert paid_check["allowed"] is False
    assert paid_check["reason"] == "paid_api_calls_blocked"
    assert summary["mode"] == "zero_cost_only"


def test_production_readiness_reports_api_and_growth_state(tmp_path, monkeypatch) -> None:
    from ai_shorts import api_keys, growth_learning, paths, production_readiness

    data_dir = tmp_path / "data"
    monkeypatch.setattr(paths, "APP_STATE_PATH", data_dir / "app_state.json")
    monkeypatch.setattr(paths, "PROJECTS_DIR", data_dir / "projects")
    monkeypatch.setattr(api_keys, "API_KEYS_PATH", data_dir / "secrets" / "api_keys.json")
    monkeypatch.setattr(production_readiness, "APP_STATE_PATH", data_dir / "app_state.json")
    monkeypatch.setattr(production_readiness, "PROJECTS_DIR", data_dir / "projects")
    monkeypatch.setattr(growth_learning, "PERFORMANCE_RECORDS_PATH", data_dir / "growth" / "performance_records.json")
    write_json(data_dir / "app_state.json", {"projects": []})

    report = build_production_readiness()
    assert report["overall_status"] == "needs_work"
    assert "api_keys_incomplete" in report["blockers"]
    assert {item["stage"] for item in report["workflow"]} == {"초안", "검토", "렌더", "업로드 게이트", "성장 데이터"}


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
