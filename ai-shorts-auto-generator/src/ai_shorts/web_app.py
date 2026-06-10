from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .growth_learning import add_performance_record, apply_growth_learning_to_topics, import_performance_csv, recent_performance_records
from .paths import APP_STATE_PATH, PROJECTS_DIR, ensure_data_dirs
from .project_dashboard import summarize_project_gate
from .state import read_json, update_project_review
from .weekly_planner import TopicInsight, create_weekly_plan
from .weekly_queue import mark_slot_promoted, save_weekly_plan_queue
from .workflow import (
    check_or_render_mp4,
    create_draft_package,
    create_ffmpeg_setup_guide,
    generate_placeholder_render,
    generate_preview_render,
    update_final_upload_checklist,
    update_render_export_review,
    update_draft_script,
)


HOST = "127.0.0.1"
PORT = 8731


def _escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _app_state() -> dict:
    ensure_data_dirs()
    return read_json(APP_STATE_PATH, {"projects": [], "last_opened_project_id": None})


def _known_project_ids() -> set[str]:
    return {str(item.get("id", "")) for item in _app_state().get("projects", [])}


def _read_project_file(project_id: str, filename: str, default: object) -> object:
    if project_id not in _known_project_ids():
        return default
    return read_json(PROJECTS_DIR / project_id / filename, default)


def _growth_learning_summary(limit: int = 5) -> str:
    records = recent_performance_records(limit)
    if not records:
        return '<div class="empty">아직 입력된 성과 기록이 없습니다.</div>'
    rows = []
    for record in records:
        rows.append(
            "<tr>"
            f"<td>{_escape(record.get('title'))}</td>"
            f"<td>{int(record.get('views', 0))}</td>"
            f"<td>{_escape(record.get('retention_pct'))}%</td>"
            f"<td>{_escape(record.get('ctr_pct'))}%</td>"
            f"<td>{_escape(record.get('growth_score'))}</td>"
            f"<td>{_escape(record.get('notes'))}</td>"
            "</tr>"
        )
    return "<table><thead><tr><th>콘텐츠</th><th>조회수</th><th>유지율</th><th>CTR</th><th>성장 점수</th><th>메모</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _latest_project_summary(limit: int = 8) -> str:
    state = _app_state()
    projects = list(reversed(state.get("projects", [])))[:limit]
    if not projects:
        return '<div class="empty">아직 저장된 초안이 없습니다.</div>'
    rows = []
    for item in projects:
        project_id = item.get("id", "")
        package_dir = PROJECTS_DIR / project_id / "exports" / "manual_upload_package"
        summary = summarize_project_gate(PROJECTS_DIR / project_id)
        rows.append(
            "<tr>"
            f"<td><a href=\"/project?id={_escape(project_id)}\">{_escape(item.get('title'))}</a></td>"
            f"<td><span class=\"status\">{_escape(item.get('status'))}</span></td>"
            f"<td>{_escape(summary.get('blocking_gate'))}</td>"
            f"<td>{_escape(summary.get('next_step'))}</td>"
            f"<td><code>{_escape(project_id[:8])}</code></td>"
            f"<td><code>{_escape(package_dir)}</code></td>"
            "</tr>"
        )
    return "<table><thead><tr><th>초안</th><th>상태</th><th>현재 막힌 단계</th><th>다음 작업</th><th>ID</th><th>패키지 위치</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _render_project_detail(project_id: str) -> str:
    if project_id not in _known_project_ids():
        return '<section class="band"><h2>초안을 찾을 수 없습니다</h2><p class="muted">저장된 프로젝트 목록에 없는 ID입니다.</p></section>'

    project = _read_project_file(project_id, "project.json", {})
    script = _read_project_file(project_id, "script_draft.json", {})
    package_dir = PROJECTS_DIR / project_id / "exports" / "manual_upload_package"
    render_dir = PROJECTS_DIR / project_id / "renders" / "placeholder"
    preview_dir = PROJECTS_DIR / project_id / "renders" / "preview"
    compliance = read_json(package_dir / "compliance_report.json", {})
    render_export_status = read_json(package_dir / "render_export_status.json", {})
    final_upload_checklist = read_json(package_dir / "final_upload_checklist.json", {})
    asset_notes = read_json(package_dir / "asset_source_notes.json", {})
    render_plan = read_json(render_dir / "render_plan.json", {})
    preview_manifest = read_json(preview_dir / "preview_manifest.json", {})
    mp4_info = read_json(preview_dir / "mp4_status.json", {})
    ffmpeg_guide = read_json(preview_dir / "ffmpeg_setup_guide.json", {})

    scenes = "".join(
        "<tr>"
        f"<td>{int(scene.get('order', idx + 1))}</td>"
        f"<td>{_escape(scene.get('caption'))}</td>"
        f"<td>{_escape(scene.get('narration'))}</td>"
        f"<td>{_escape(scene.get('visual_direction'))}</td>"
        "</tr>"
        for idx, scene in enumerate(script.get("scenes", []))
    )
    if not scenes:
        scenes = '<tr><td colspan="4" class="muted">저장된 장면이 없습니다.</td></tr>'

    findings = "".join(
        "<li>"
        f"<strong>{_escape(finding.get('severity'))}</strong> "
        f"{_escape(finding.get('message'))}<br>"
        f"<span>{_escape(finding.get('recommendation'))}</span>"
        "</li>"
        for finding in compliance.get("findings", [])
    )
    if not findings:
        findings = '<li><strong>pass</strong> 차단 또는 검토 항목이 없습니다.</li>'

    files = [
        "script.json",
        "compliance_report.json",
        "asset_source_notes.json",
        "title.txt",
        "description.txt",
        "tags.txt",
        "pinned_comment.txt",
        "README_UPLOAD_REVIEW.txt",
    ]
    file_rows = "".join(
        "<tr>"
        f"<td>{_escape(name)}</td>"
        f"<td><code>{_escape(package_dir / name)}</code></td>"
        "</tr>"
        for name in files
    )

    source_count = len(asset_notes.get("sources", [])) if isinstance(asset_notes, dict) else 0
    asset_count = len(asset_notes.get("assets", [])) if isinstance(asset_notes, dict) else 0
    review = project.get("review", {}) if isinstance(project, dict) else {}
    reviewer_note = review.get("reviewer_note", "") if isinstance(review, dict) else ""
    reviewed_at = review.get("reviewed_at", "") if isinstance(review, dict) else ""
    scene_inputs = "".join(
        f"""
        <label for="scene_caption_{idx}">장면 {idx + 1} 자막</label>
        <input id="scene_caption_{idx}" name="scene_caption_{idx}" value="{_escape(scene.get('caption'))}">
        """
        for idx, scene in enumerate(script.get("scenes", []))
    )
    render_rows = "".join(
        "<tr>"
        f"<td>{int(scene.get('scene_no', idx + 1))}</td>"
        f"<td>{_escape(scene.get('caption'))}</td>"
        f"<td>{_escape(scene.get('duration_sec'))}s</td>"
        f"<td><code>{_escape(scene.get('placeholder_svg'))}</code></td>"
        "</tr>"
        for idx, scene in enumerate(render_plan.get("scenes", []))
    )
    if not render_rows:
        render_rows = '<tr><td colspan="4" class="muted">아직 렌더 placeholder가 없습니다.</td></tr>'
    timeline_html = render_plan.get("timeline_html", "") if isinstance(render_plan, dict) else ""
    render_manifest = render_plan.get("render_manifest", "") if isinstance(render_plan, dict) else ""
    preview_gif = preview_manifest.get("preview_gif", "") if isinstance(preview_manifest, dict) else ""
    preview_rows = "".join(
        "<tr>"
        f"<td>{int(frame.get('scene_no', idx + 1))}</td>"
        f"<td><code>{_escape(frame.get('frame_png'))}</code></td>"
        f"<td>{_escape(frame.get('duration_ms'))}ms</td>"
        "</tr>"
        for idx, frame in enumerate(preview_manifest.get("frames", []))
    )
    if not preview_rows:
        preview_rows = '<tr><td colspan="3" class="muted">아직 미리보기 프레임이 없습니다.</td></tr>'
    mp4_status = mp4_info.get("status", "not_checked") if isinstance(mp4_info, dict) else "not_checked"
    mp4_path = mp4_info.get("mp4_path", "") if isinstance(mp4_info, dict) else ""
    ffmpeg_path = mp4_info.get("ffmpeg_path", "") if isinstance(mp4_info, dict) else ""
    install_hint = mp4_info.get("install_hint", "") if isinstance(mp4_info, dict) else ""
    setup_guide_path = ""
    setup_command = ""
    verify_command = ""
    if isinstance(ffmpeg_guide, dict):
        setup_guide_path = str(ffmpeg_guide.get("markdown_path") or ffmpeg_guide.get("json_path") or "")
        setup_command = str(ffmpeg_guide.get("recommended_windows_command") or "")
        verify_command = str(ffmpeg_guide.get("verify_command") or "")
    if not setup_guide_path and isinstance(mp4_info, dict):
        setup_guide_path = str(mp4_info.get("setup_guide_path") or "")
    render_export_decision = render_export_status.get("decision", "not_reviewed") if isinstance(render_export_status, dict) else "not_reviewed"
    render_export_package_status = render_export_status.get("status", "not_reviewed") if isinstance(render_export_status, dict) else "not_reviewed"
    render_export_note = render_export_status.get("reviewer_note", "") if isinstance(render_export_status, dict) else ""
    render_export_next_step = render_export_status.get("next_step", "렌더 미리보기와 업로드 가능 여부를 검토하세요.") if isinstance(render_export_status, dict) else "렌더 미리보기와 업로드 가능 여부를 검토하세요."
    render_export_assets = render_export_status.get("assets", {}) if isinstance(render_export_status, dict) else {}
    render_export_blockers = render_export_status.get("blockers", []) if isinstance(render_export_status, dict) else []
    render_export_blocker_text = ", ".join(str(item) for item in render_export_blockers) if render_export_blockers else "없음"
    final_upload_status = final_upload_checklist.get("status", "not_checked") if isinstance(final_upload_checklist, dict) else "not_checked"
    final_upload_note = final_upload_checklist.get("reviewer_note", "") if isinstance(final_upload_checklist, dict) else ""
    final_upload_missing = final_upload_checklist.get("missing", []) if isinstance(final_upload_checklist, dict) else []
    final_upload_missing_text = ", ".join(str(item) for item in final_upload_missing) if final_upload_missing else "없음"
    final_upload_next_step = final_upload_checklist.get("next_step", "최종 업로드 전 체크리스트를 실행하세요.") if isinstance(final_upload_checklist, dict) else "최종 업로드 전 체크리스트를 실행하세요."
    final_upload_allowed = final_upload_checklist.get("manual_upload_allowed", False) if isinstance(final_upload_checklist, dict) else False

    return f"""
    <section class="band detail-head">
      <div>
        <a class="back" href="/">← 작업 화면으로</a>
        <h2>{_escape(project.get('title'))}</h2>
        <p class="muted">ID <code>{_escape(project_id)}</code> · 상태 <span class="status">{_escape(project.get('status'))}</span></p>
      </div>
      <div>
        <label>패키지 위치</label>
        <p><code>{_escape(package_dir)}</code></p>
        <label>검토 메모</label>
        <p>{_escape(reviewer_note or '아직 검토 메모가 없습니다.')}</p>
        <p class="muted">{_escape(reviewed_at)}</p>
      </div>
    </section>

    <section class="band">
      <h2>검토 결정</h2>
      <p class="muted">정책 리포트와 소스/자산 메모를 확인한 뒤 상태를 바꿉니다. 공개 업로드는 별도 최종 승인 전까지 자동 실행하지 않습니다.</p>
      <form method="post" action="/review">
        <input type="hidden" name="project_id" value="{_escape(project_id)}">
        <label for="reviewer_note">검토 메모</label>
        <textarea id="reviewer_note" name="reviewer_note" placeholder="예: 정책 리포트 확인, 외부 자산 없음, 수동 업로드 패키지 생성 가능">{_escape(reviewer_note)}</textarea>
        <div class="actions">
          <button type="submit" name="decision" value="approved_for_export">승인</button>
          <button class="secondary" type="submit" name="decision" value="needs_revision">수정 필요</button>
          <button class="warning" type="submit" name="decision" value="blocked">차단</button>
        </div>
      </form>
    </section>

    <section class="band">
      <h2>대본 요약</h2>
      <div class="grid two">
        <div>
          <label>제목</label>
          <p class="big">{_escape(script.get('title'))}</p>
          <label>후킹</label>
          <p>{_escape(script.get('hook'))}</p>
          <label>썸네일 문구</label>
          <p>{_escape(script.get('thumbnail_text'))}</p>
        </div>
        <div>
          <label>창작 변형 메모</label>
          <p>{_escape(script.get('transformation_note'))}</p>
          <label>참고/수집 메모</label>
          <p>{_escape(project.get('source_notes'))}</p>
        </div>
      </div>
      <label>전체 내레이션</label>
      <p class="narration">{_escape(script.get('narration'))}</p>
    </section>

    <section class="band">
      <h2>대본 수정</h2>
      <p class="muted">저장하면 정책 검사 리포트와 수동 업로드 패키지가 새 내용으로 다시 생성되고, 상태는 재검토 필요로 바뀝니다.</p>
      <form method="post" action="/edit-script">
        <input type="hidden" name="project_id" value="{_escape(project_id)}">
        <div class="grid two">
          <div>
            <label for="edit_title">제목</label>
            <input id="edit_title" name="title" value="{_escape(script.get('title'))}">
          </div>
          <div>
            <label for="edit_thumbnail">썸네일 문구</label>
            <input id="edit_thumbnail" name="thumbnail_text" value="{_escape(script.get('thumbnail_text'))}">
          </div>
        </div>
        <label for="edit_hook">후킹</label>
        <input id="edit_hook" name="hook" value="{_escape(script.get('hook'))}">
        <label for="edit_narration">전체 내레이션</label>
        <textarea id="edit_narration" name="narration">{_escape(script.get('narration'))}</textarea>
        <div class="grid two">{scene_inputs}</div>
        <div class="actions">
          <button type="submit">수정 저장</button>
        </div>
      </form>
    </section>

    <section class="band">
      <h2>장면 구성</h2>
      <table>
        <thead><tr><th>#</th><th>자막</th><th>내레이션</th><th>비주얼 방향</th></tr></thead>
        <tbody>{scenes}</tbody>
      </table>
    </section>

    <section class="band">
      <h2>렌더 placeholder</h2>
      <p class="muted">실제 영상 생성 전, 장면별 1080x1920 SVG와 render_plan.json을 만들어 영상 구조를 확인합니다.</p>
      <form method="post" action="/render-placeholder">
        <input type="hidden" name="project_id" value="{_escape(project_id)}">
        <div class="actions">
          <button type="submit">렌더 계획 생성</button>
          <span class="muted">상태: {_escape(render_plan.get('status', 'not_created'))}</span>
        </div>
      </form>
      <div class="grid two">
        <div>
          <label>타임라인 HTML</label>
          <p><code>{_escape(timeline_html or '아직 생성되지 않았습니다.')}</code></p>
        </div>
        <div>
          <label>렌더 manifest</label>
          <p><code>{_escape(render_manifest or '아직 생성되지 않았습니다.')}</code></p>
        </div>
      </div>
      <table><thead><tr><th>#</th><th>자막</th><th>길이</th><th>SVG 파일</th></tr></thead><tbody>{render_rows}</tbody></table>
    </section>

    <section class="band">
      <h2>렌더 미리보기</h2>
      <p class="muted">MP4 전 단계로 PNG 프레임과 애니메이션 GIF를 생성합니다. 현재 환경에는 ffmpeg가 없어 MP4 변환은 다음 단계입니다.</p>
      <form method="post" action="/render-preview">
        <input type="hidden" name="project_id" value="{_escape(project_id)}">
        <div class="actions">
          <button type="submit">GIF 미리보기 생성</button>
          <span class="muted">상태: {_escape(preview_manifest.get('status', 'not_created') if isinstance(preview_manifest, dict) else 'not_created')}</span>
        </div>
      </form>
      <label>미리보기 GIF</label>
      <p><code>{_escape(preview_gif or '아직 생성되지 않았습니다.')}</code></p>
      <table><thead><tr><th>#</th><th>PNG 프레임</th><th>길이</th></tr></thead><tbody>{preview_rows}</tbody></table>
    </section>

    <section class="band">
      <h2>MP4 변환</h2>
      <p class="muted">ffmpeg가 PATH에 있으면 PNG 프레임을 MP4로 변환합니다. 없으면 설치 안내 상태를 저장합니다.</p>
      <form method="post" action="/mp4-status">
        <input type="hidden" name="project_id" value="{_escape(project_id)}">
        <div class="actions">
          <button type="submit" name="render" value="false">ffmpeg 확인</button>
          <button class="secondary" type="submit" name="render" value="true">MP4 변환 시도</button>
          <span class="muted">상태: {_escape(mp4_status)}</span>
        </div>
      </form>
      <div class="grid two">
        <div>
          <label>MP4 경로</label>
          <p><code>{_escape(mp4_path or '아직 생성되지 않았습니다.')}</code></p>
        </div>
        <div>
          <label>ffmpeg</label>
          <p><code>{_escape(ffmpeg_path or install_hint or '아직 확인하지 않았습니다.')}</code></p>
        </div>
      </div>
      <form method="post" action="/ffmpeg-guide">
        <input type="hidden" name="project_id" value="{_escape(project_id)}">
        <div class="actions">
          <button type="submit">ffmpeg 설치 안내 생성</button>
          <span class="muted">안내: <code>{_escape(setup_guide_path or '아직 생성되지 않았습니다.')}</code></span>
        </div>
      </form>
      <div class="grid two">
        <div>
          <label>설치 명령</label>
          <p><code>{_escape(setup_command or 'winget install --id Gyan.FFmpeg --exact')}</code></p>
        </div>
        <div>
          <label>설치 확인</label>
          <p><code>{_escape(verify_command or 'ffmpeg -version')}</code></p>
        </div>
      </div>
    </section>

    <section class="band">
      <h2>정책 검사 리포트</h2>
      <p>상태 <span class="status">{_escape(compliance.get('status', 'unknown'))}</span> · 소스 {source_count}개 · 자산 {asset_count}개</p>
      <ol class="scenes">{findings}</ol>
    </section>

    <section class="band">
      <h2>렌더 승인/export 상태</h2>
      <p class="muted">timeline, GIF 미리보기, MP4 준비 상태를 확인하고 수동 업로드 패키지로 보낼 수 있는지 결정합니다.</p>
      <form method="post" action="/render-export-review">
        <input type="hidden" name="project_id" value="{_escape(project_id)}">
        <label for="render_export_note">렌더 검토 메모</label>
        <textarea id="render_export_note" name="reviewer_note" placeholder="예: timeline 확인, GIF 미리보기 승인, MP4는 ffmpeg 설치 후 생성">{_escape(render_export_note)}</textarea>
        <div class="actions">
          <button type="submit" name="decision" value="ready_for_upload_package">업로드 패키지 가능</button>
          <button class="secondary" type="submit" name="decision" value="needs_render_revision">수정 필요</button>
          <button class="warning" type="submit" name="decision" value="render_blocked">차단</button>
          <span class="muted">상태: {_escape(render_export_package_status)} · 결정: {_escape(render_export_decision)}</span>
        </div>
      </form>
      <div class="grid two">
        <div>
          <label>준비 상태</label>
          <p>timeline: {_escape(render_export_assets.get('timeline_ready', False))} · GIF: {_escape(render_export_assets.get('gif_ready', False))} · MP4: {_escape(render_export_assets.get('mp4_ready', False))}</p>
          <label>차단 항목</label>
          <p>{_escape(render_export_blocker_text)}</p>
        </div>
        <div>
          <label>다음 작업</label>
          <p>{_escape(render_export_next_step)}</p>
          <label>상태 파일</label>
          <p><code>{_escape(package_dir / 'render_export_status.json')}</code></p>
        </div>
      </div>
    </section>

    <section class="band">
      <h2>업로드 패키지 파일</h2>
      <form method="post" action="/final-upload-checklist">
        <input type="hidden" name="project_id" value="{_escape(project_id)}">
        <label for="final_upload_note">최종 체크 메모</label>
        <textarea id="final_upload_note" name="reviewer_note" placeholder="예: MP4, 정책, 제목/설명/태그 확인">{_escape(final_upload_note)}</textarea>
        <div class="actions">
          <button type="submit">최종 업로드 체크리스트 실행</button>
          <span class="muted">상태: {_escape(final_upload_status)} · 수동 업로드 허용: {_escape(final_upload_allowed)}</span>
        </div>
      </form>
      <div class="grid two">
        <div>
          <label>미충족 항목</label>
          <p>{_escape(final_upload_missing_text)}</p>
        </div>
        <div>
          <label>다음 작업</label>
          <p>{_escape(final_upload_next_step)}</p>
          <label>체크리스트 파일</label>
          <p><code>{_escape(package_dir / 'final_upload_checklist.json')}</code></p>
        </div>
      </div>
      <table><thead><tr><th>파일</th><th>경로</th></tr></thead><tbody>{file_rows}</tbody></table>
    </section>
    """


def _render_page(
    result: dict | None = None,
    plan: dict | None = None,
    growth_import: dict | None = None,
    error: str = "",
    detail_html: str = "",
) -> bytes:
    result_html = ""
    if result:
        script = result.get("script", {})
        export = result.get("export", {})
        scenes = "".join(
            f"<li><strong>{_escape(scene.get('caption'))}</strong><br><span>{_escape(scene.get('visual_direction'))}</span></li>"
            for scene in script.get("scenes", [])
        )
        result_html = f"""
        <section class="band">
          <h2>생성 결과</h2>
          <div class="grid two">
            <div>
              <label>제목</label>
              <p class="big">{_escape(script.get('title'))}</p>
              <label>후킹</label>
              <p>{_escape(script.get('hook'))}</p>
              <label>썸네일 문구</label>
              <p>{_escape(script.get('thumbnail_text'))}</p>
            </div>
            <div>
              <label>정책 검사</label>
              <p><span class="status">{_escape(export.get('compliance_status'))}</span> · findings {int(export.get('finding_count', 0))}</p>
              <label>패키지 위치</label>
              <p><code>{_escape(export.get('package_dir'))}</code></p>
            </div>
          </div>
          <label>장면 구성</label>
          <ol class="scenes">{scenes}</ol>
        </section>
        """

    plan_html = ""
    if plan:
        slots = "".join(
            f"""
            <li>
              <strong>{_escape(slot.get('topic'))}</strong><br>
              <span>{_escape(slot.get('reason'))}</span>
              <form method="post" action="/promote-plan-slot">
                <input type="hidden" name="topic" value="{_escape(slot.get('topic'))}">
                <input type="hidden" name="reason" value="{_escape(slot.get('reason'))}">
                <div class="actions">
                  <button type="submit">저장된 초안으로 승격</button>
                </div>
              </form>
            </li>
            """
            for slot in plan.get("slots", [])
        )
        plan_html = f"""
        <section class="band">
          <h2>주간 계획</h2>
          <p>{_escape(plan.get('automation_note'))}</p>
          <p class="muted">선택한 슬롯은 즉시 autosave 프로젝트로 저장되고 최근 초안 목록에 나타납니다.</p>
          <ol class="scenes">{slots}</ol>
        </section>
        """

    growth_import_html = ""
    if growth_import:
        skipped_rows = "".join(
            f"<li>row {_escape(item.get('row'))}: {_escape(item.get('reason'))}</li>"
            for item in growth_import.get("skipped", [])
        )
        if not skipped_rows:
            skipped_rows = "<li>없음</li>"
        growth_import_html = f"""
        <section class="band">
          <h2>CSV 가져오기 결과</h2>
          <p>성공 <span class="status">{int(growth_import.get('imported_count', 0))}</span> · 스킵 {int(growth_import.get('skipped_count', 0))}</p>
          <label>스킵된 행</label>
          <ol class="scenes">{skipped_rows}</ol>
        </section>
        """

    error_html = f'<div class="error">{_escape(error)}</div>' if error else ""
    body = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Shorts Auto Generator</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --ink: #1c2430;
      --muted: #5d6675;
      --line: #d9dee7;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-2: #1d4ed8;
      --danger: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", system-ui, sans-serif;
      letter-spacing: 0;
    }}
    header {{
      padding: 22px 28px 14px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    h1 {{ margin: 0 0 8px; font-size: 24px; line-height: 1.25; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 22px; }}
    .band {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 16px;
    }}
    .grid {{ display: grid; gap: 14px; }}
    .two {{ grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }}
    label {{ display: block; font-weight: 700; font-size: 13px; color: var(--muted); margin-bottom: 7px; }}
    input, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 11px 12px;
      font: inherit;
      background: #fff;
    }}
    textarea {{ min-height: 118px; resize: vertical; }}
    button {{
      border: 0;
      border-radius: 6px;
      padding: 11px 14px;
      background: var(--accent);
      color: #fff;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    button.secondary {{ background: var(--accent-2); }}
    button.warning {{ background: #b42318; }}
    a {{ color: var(--accent-2); font-weight: 700; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .back {{ display: inline-block; margin-bottom: 10px; font-size: 14px; }}
    .actions {{ display: flex; gap: 10px; align-items: center; margin-top: 12px; flex-wrap: wrap; }}
    .muted {{ color: var(--muted); font-size: 14px; }}
    .big {{ font-size: 18px; font-weight: 700; }}
    code {{
      word-break: break-all;
      background: #eef2f7;
      border-radius: 4px;
      padding: 2px 5px;
      font-size: 13px;
    }}
    .status {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 999px;
      background: #e6f4f1;
      color: #09645c;
      font-size: 13px;
      font-weight: 700;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 13px; }}
    .scenes {{ margin: 8px 0 0; padding-left: 22px; }}
    .scenes li {{ margin: 10px 0; }}
    .scenes span {{ color: var(--muted); }}
    .detail-head {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(260px, 0.7fr); gap: 18px; }}
    .narration {{ white-space: pre-wrap; line-height: 1.65; }}
    .empty {{ color: var(--muted); padding: 10px 0; }}
    .error {{ border: 1px solid #fecdca; color: var(--danger); background: #fff3f1; padding: 12px; border-radius: 6px; margin-bottom: 16px; }}
    @media (max-width: 760px) {{
      header {{ padding: 18px; }}
      main {{ padding: 14px; }}
      .two {{ grid-template-columns: 1fr; }}
      .detail-head {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AI Shorts Auto Generator</h1>
    <div class="muted">초안 생성, 정책 검사, 수동 업로드 패키지까지 로컬에 자동저장합니다.</div>
  </header>
  <main>
    {error_html}
    {detail_html}
    <section class="band">
      <h2>새 쇼츠 초안</h2>
      <form method="post" action="/create">
        <div class="grid two">
          <div>
            <label for="topic">주제</label>
            <input id="topic" name="topic" required placeholder="예: 퇴근 후 시간 관리">
          </div>
          <div>
            <label for="source_notes">참고/수집 메모</label>
            <input id="source_notes" name="source_notes" placeholder="복제하지 않고 주제 흐름만 참고">
          </div>
        </div>
        <div class="actions">
          <button type="submit">초안 생성</button>
          <span class="muted">생성 즉시 data/projects 아래에 저장됩니다.</span>
        </div>
      </form>
    </section>

    <section class="band">
      <h2>주간 2~3개 계획</h2>
      <form method="post" action="/plan">
        <div class="grid two">
          <div>
            <label for="topics">후보 주제</label>
            <textarea id="topics" name="topics" placeholder="생활 팁&#10;직장 공감&#10;시간 절약"></textarea>
          </div>
          <div>
            <label for="count">생성 개수</label>
            <input id="count" name="count" type="number" min="2" max="3" value="2">
          </div>
        </div>
        <div class="actions">
          <button class="secondary" type="submit">주간 계획 만들기</button>
          <span class="muted">공개 업로드가 아니라 검토용 초안 계획입니다.</span>
        </div>
      </form>
    </section>

    <section class="band">
      <h2>성장 학습 데이터</h2>
      <form method="post" action="/growth-record">
        <div class="grid two">
          <div>
            <label for="growth_title">콘텐츠 제목</label>
            <input id="growth_title" name="title" required placeholder="예: 출근 전 5분 정리법">
          </div>
          <div>
            <label for="growth_project_id">프로젝트 ID</label>
            <input id="growth_project_id" name="project_id" placeholder="선택 사항">
          </div>
          <div>
            <label for="growth_views">조회수</label>
            <input id="growth_views" name="views" type="number" min="0" value="0">
          </div>
          <div>
            <label for="growth_retention">평균 유지율 %</label>
            <input id="growth_retention" name="retention_pct" type="number" min="0" max="100" step="0.1" value="0">
          </div>
          <div>
            <label for="growth_ctr">CTR %</label>
            <input id="growth_ctr" name="ctr_pct" type="number" min="0" max="100" step="0.1" value="0">
          </div>
          <div>
            <label for="growth_duration">평균 시청 시간 초</label>
            <input id="growth_duration" name="avg_view_duration_sec" type="number" min="0" step="0.1" value="0">
          </div>
        </div>
        <label for="growth_notes">성과 메모</label>
        <textarea id="growth_notes" name="notes" placeholder="예: 초반 3초 이탈이 많음, 제목은 잘 먹힘"></textarea>
        <div class="actions">
          <button type="submit">성과 기록 저장</button>
          <span class="muted">저장된 기록은 다음 주간 계획 점수 개선에 사용할 수 있습니다.</span>
        </div>
      </form>
      <form method="post" action="/growth-csv-import">
        <label for="growth_csv">YouTube Studio CSV 붙여넣기</label>
        <textarea id="growth_csv" name="csv_text" placeholder="Title,Views,Average percentage viewed,Impressions click-through rate,Average view duration&#10;출근 루틴,1200,64,7.2,18"></textarea>
        <div class="actions">
          <button class="secondary" type="submit">CSV 성과 가져오기</button>
          <span class="muted">열 이름은 Title/Views/Retention/CTR 계열을 자동 인식합니다.</span>
        </div>
      </form>
      {_growth_learning_summary()}
    </section>

    {result_html}
    {plan_html}
    {growth_import_html}

    <section class="band">
      <h2>최근 저장 초안</h2>
      {_latest_project_summary()}
    </section>
  </main>
</body>
</html>"""
    return body.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/project":
            query = parse_qs(parsed.query)
            detail_html = _render_project_detail(query.get("id", [""])[0])
            self._send(_render_page(detail_html=detail_html))
            return
        self._send(_render_page())

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        params = parse_qs(self.rfile.read(length).decode("utf-8"))
        try:
            if self.path == "/create":
                topic = params.get("topic", [""])[0]
                source_notes = params.get("source_notes", [""])[0]
                result = create_draft_package(topic, source_notes)
                self._send(_render_page(result=result))
                return
            if self.path == "/plan":
                topics_text = params.get("topics", [""])[0]
                count = int(params.get("count", ["2"])[0] or 2)
                topics = [line.strip() for line in topics_text.splitlines() if line.strip()]
                insights = apply_growth_learning_to_topics([TopicInsight(topic=topic) for topic in topics])
                plan = create_weekly_plan(insights, count)
                save_weekly_plan_queue(plan.to_dict())
                self._send(_render_page(plan=plan.to_dict()))
                return
            if self.path == "/promote-plan-slot":
                topic = params.get("topic", [""])[0]
                reason = params.get("reason", [""])[0]
                result = create_draft_package(topic, f"Weekly plan promotion: {reason}")
                project_id = result.get("project", {}).get("id", "")
                if project_id:
                    mark_slot_promoted(topic, project_id)
                self._send(_render_page(result=result))
                return
            if self.path == "/growth-record":
                add_performance_record(
                    title=params.get("title", [""])[0],
                    project_id=params.get("project_id", [""])[0],
                    views=int(params.get("views", ["0"])[0] or 0),
                    retention_pct=float(params.get("retention_pct", ["0"])[0] or 0),
                    ctr_pct=float(params.get("ctr_pct", ["0"])[0] or 0),
                    avg_view_duration_sec=float(params.get("avg_view_duration_sec", ["0"])[0] or 0),
                    notes=params.get("notes", [""])[0],
                )
                self._send(_render_page())
                return
            if self.path == "/growth-csv-import":
                growth_import = import_performance_csv(params.get("csv_text", [""])[0])
                self._send(_render_page(growth_import=growth_import))
                return
            if self.path == "/review":
                project_id = params.get("project_id", [""])[0]
                decision = params.get("decision", ["needs_revision"])[0]
                reviewer_note = params.get("reviewer_note", [""])[0]
                if decision not in {"approved_for_export", "needs_revision", "blocked"}:
                    raise ValueError("알 수 없는 검토 상태입니다.")
                update_project_review(project_id, decision, reviewer_note)
                detail_html = _render_project_detail(project_id)
                self._send(_render_page(detail_html=detail_html))
                return
            if self.path == "/edit-script":
                project_id = params.get("project_id", [""])[0]
                scene_captions: list[str] = []
                index = 0
                while f"scene_caption_{index}" in params:
                    scene_captions.append(params.get(f"scene_caption_{index}", [""])[0])
                    index += 1
                update_draft_script(
                    project_id,
                    {
                        "title": params.get("title", [""])[0],
                        "hook": params.get("hook", [""])[0],
                        "thumbnail_text": params.get("thumbnail_text", [""])[0],
                        "narration": params.get("narration", [""])[0],
                        "scene_captions": scene_captions,
                    },
                )
                detail_html = _render_project_detail(project_id)
                self._send(_render_page(detail_html=detail_html))
                return
            if self.path == "/render-placeholder":
                project_id = params.get("project_id", [""])[0]
                generate_placeholder_render(project_id)
                detail_html = _render_project_detail(project_id)
                self._send(_render_page(detail_html=detail_html))
                return
            if self.path == "/render-preview":
                project_id = params.get("project_id", [""])[0]
                generate_preview_render(project_id)
                detail_html = _render_project_detail(project_id)
                self._send(_render_page(detail_html=detail_html))
                return
            if self.path == "/mp4-status":
                project_id = params.get("project_id", [""])[0]
                should_render = params.get("render", ["false"])[0] == "true"
                check_or_render_mp4(project_id, should_render)
                detail_html = _render_project_detail(project_id)
                self._send(_render_page(detail_html=detail_html))
                return
            if self.path == "/ffmpeg-guide":
                project_id = params.get("project_id", [""])[0]
                create_ffmpeg_setup_guide(project_id)
                detail_html = _render_project_detail(project_id)
                self._send(_render_page(detail_html=detail_html))
                return
            if self.path == "/render-export-review":
                project_id = params.get("project_id", [""])[0]
                decision = params.get("decision", ["needs_render_revision"])[0]
                reviewer_note = params.get("reviewer_note", [""])[0]
                if decision not in {"ready_for_upload_package", "needs_render_revision", "render_blocked"}:
                    raise ValueError("알 수 없는 렌더 승인 상태입니다.")
                update_render_export_review(project_id, decision, reviewer_note)
                detail_html = _render_project_detail(project_id)
                self._send(_render_page(detail_html=detail_html))
                return
            if self.path == "/final-upload-checklist":
                project_id = params.get("project_id", [""])[0]
                reviewer_note = params.get("reviewer_note", [""])[0]
                update_final_upload_checklist(project_id, reviewer_note)
                detail_html = _render_project_detail(project_id)
                self._send(_render_page(detail_html=detail_html))
                return
            self._send(_render_page(error="알 수 없는 요청입니다."), status=404)
        except Exception as exc:
            self._send(_render_page(error=str(exc)), status=500)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, body: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    ensure_data_dirs()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"AI Shorts Auto Generator running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
