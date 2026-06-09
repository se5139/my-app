from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .paths import APP_STATE_PATH, PROJECTS_DIR, ensure_data_dirs
from .state import read_json, update_project_review
from .weekly_planner import TopicInsight, create_weekly_plan
from .workflow import create_draft_package, update_draft_script


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


def _latest_project_summary(limit: int = 8) -> str:
    state = _app_state()
    projects = list(reversed(state.get("projects", [])))[:limit]
    if not projects:
        return '<div class="empty">아직 저장된 초안이 없습니다.</div>'
    rows = []
    for item in projects:
        project_id = item.get("id", "")
        package_dir = PROJECTS_DIR / project_id / "exports" / "manual_upload_package"
        rows.append(
            "<tr>"
            f"<td><a href=\"/project?id={_escape(project_id)}\">{_escape(item.get('title'))}</a></td>"
            f"<td><span class=\"status\">{_escape(item.get('status'))}</span></td>"
            f"<td><code>{_escape(project_id[:8])}</code></td>"
            f"<td><code>{_escape(package_dir)}</code></td>"
            "</tr>"
        )
    return "<table><thead><tr><th>초안</th><th>상태</th><th>ID</th><th>패키지 위치</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _render_project_detail(project_id: str) -> str:
    if project_id not in _known_project_ids():
        return '<section class="band"><h2>초안을 찾을 수 없습니다</h2><p class="muted">저장된 프로젝트 목록에 없는 ID입니다.</p></section>'

    project = _read_project_file(project_id, "project.json", {})
    script = _read_project_file(project_id, "script_draft.json", {})
    package_dir = PROJECTS_DIR / project_id / "exports" / "manual_upload_package"
    compliance = read_json(package_dir / "compliance_report.json", {})
    asset_notes = read_json(package_dir / "asset_source_notes.json", {})

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
      <h2>정책 검사 리포트</h2>
      <p>상태 <span class="status">{_escape(compliance.get('status', 'unknown'))}</span> · 소스 {source_count}개 · 자산 {asset_count}개</p>
      <ol class="scenes">{findings}</ol>
    </section>

    <section class="band">
      <h2>업로드 패키지 파일</h2>
      <table><thead><tr><th>파일</th><th>경로</th></tr></thead><tbody>{file_rows}</tbody></table>
    </section>
    """


def _render_page(result: dict | None = None, plan: dict | None = None, error: str = "", detail_html: str = "") -> bytes:
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
            f"<li><strong>{_escape(slot.get('topic'))}</strong><br><span>{_escape(slot.get('reason'))}</span></li>"
            for slot in plan.get("slots", [])
        )
        plan_html = f"""
        <section class="band">
          <h2>주간 계획</h2>
          <p>{_escape(plan.get('automation_note'))}</p>
          <ol class="scenes">{slots}</ol>
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

    {result_html}
    {plan_html}

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
                plan = create_weekly_plan([TopicInsight(topic=topic) for topic in topics], count)
                self._send(_render_page(plan=plan.to_dict()))
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
