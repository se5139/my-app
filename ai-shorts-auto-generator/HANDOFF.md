# Handoff Notes

## User Requirement

The user requires this program to autosave or save after each completed work unit, and to remain continuable from another PC at any time.

## Storage Address

```text
https://github.com/se5139/my-app.git
```

## Project Path In Repository

```text
ai-shorts-auto-generator/
```

## Working Policy

- Keep durable state in project files, not only in local temp files.
- After each completed implementation step, commit and push when Git is available.
- Do not overwrite unrelated root files in the repository.
- Update this handoff file when setup, run, or resume steps change.

## Current Machine Status

As of 2026-06-09, Git was not available from PowerShell PATH in this Codex session. The GitHub connector can save UTF-8 text files to the remote repository, but normal local `git commit` and `git push` require Git to be installed or exposed in PATH.

## 2026-06-09 Rebuild Start

Reviewed `shorts_auto_maker_v108_growth_learning.zip` as a reference package.

Decision:

- Use the old package only to understand product direction.
- Rebuild from scratch under `ai-shorts-auto-generator/`.
- Keep the first version focused on autosaved projects, script drafts, review, export packages, and growth learning imports.
- Do not copy the old many-launcher `.bat` structure.
- Do not rely on automatic upload in phase 1.

Current created files:

- `docs/REFERENCE_REVIEW.md`
- `docs/REBUILD_BLUEPRINT.md`
- `src/ai_shorts/paths.py`
- `src/ai_shorts/state.py`
- `tests/test_state.py`
- `pyproject.toml`
- `app_state.example.json`
- `docs/POLICY_SOURCES.md`
- `docs/PHASE1_REQUIREMENTS.md`
- `src/ai_shorts/compliance.py`
- `src/ai_shorts/weekly_planner.py`

Verification:

- Python compile check passed using Codex bundled Python.
- State smoke test passed after setting `PYTHONPATH=src`.
- Compliance and weekly planner smoke test passed after setting `PYTHONPATH=src`.

## 2026-06-09 First Workflow Step

Added the first local workflow after Git sync was repaired:

- `src/ai_shorts/script_lab.py`: creates a local Korean script draft without paid API calls.
- `src/ai_shorts/package_exporter.py`: exports a manual upload package with compliance report, title, description, tags, pinned comment, and asset/source notes.
- `src/ai_shorts/cli.py`: adds `new-draft` and `plan-week` commands.

Verification:

- Python compile check passed.
- Local script/planner smoke test passed.
- `python -m ai_shorts.cli new-draft "퇴근 후 시간 관리" ...` created a test package with compliance status `pass`.
- Test-generated `data/` and Python cache folders were removed after verification so sample artifacts are not committed.

## 2026-06-09 Local UI Step

Added a dependency-free local browser UI:

- `src/ai_shorts/workflow.py`: shared draft package workflow for CLI and web UI.
- `src/ai_shorts/web_app.py`: local HTTP UI at `http://127.0.0.1:8731`.
- `START_WEB_APP.ps1` and `START_WEB_APP.bat`: Windows launch helpers.

Verification:

- Python compile check passed.
- Web workflow smoke test passed.
- Local HTTP end-to-end check passed for page load, weekly plan form, and draft creation form.
- In-app Browser plugin connection failed in this sandbox, so HTTP checks were used instead.

Next recommended work:

- Add a project detail screen that opens saved drafts and shows compliance report contents.
- Then add actual video render placeholder generation.

## 2026-06-09 Project Detail Step

Added saved draft detail viewing:

- Recent drafts now link to `/project?id=<project_id>`.
- The detail screen reads `project.json`, `script_draft.json`, `compliance_report.json`, and package metadata.
- It shows script summary, scene list, compliance findings, source/asset counts, and upload package file paths.

Verification target:

- Compile `web_app.py`.
- Render unknown-project fallback.
- End-to-end create a draft through the web form and load its detail page.

Next recommended work after this:

- Add an edit/review action on the detail screen.
- Then add actual video render placeholder generation.

## 2026-06-09 Review Decision Step

Added human review decisions on the saved draft detail screen:

- `state.update_project_review(...)` updates `project.json` and `data/app_state.json`.
- Detail screen can mark a draft as `approved_for_export`, `needs_revision`, or `blocked`.
- Review note and timestamp are saved in the project record.
- Public upload remains disabled; approval only means the manual export package is ready for the next step.

Verification target:

- Compile `state.py`, `web_app.py`, and tests.
- End-to-end create a draft through the web form, submit review approval, and verify the detail page shows `approved_for_export`.

Next recommended work:

- Add simple edit controls for title, hook, narration, and scene captions.
- Then add actual video render placeholder generation.

## 2026-06-09 Script Edit Step

Added draft script editing on the saved draft detail screen:

- `script_lab.script_draft_from_dict(...)` restores saved script JSON into dataclasses.
- `workflow.update_draft_script(...)` updates title, hook, thumbnail text, narration, and scene captions.
- Editing regenerates the manual upload package and compliance report.
- Editing resets project status to `needs_review` with a review note.

Verification target:

- Compile `script_lab.py`, `workflow.py`, `web_app.py`, and tests.
- End-to-end create a draft through the web form, edit script fields, confirm `script_draft.json` changed, and confirm status returns to `needs_review`.

Next recommended work:

- Add actual video render placeholder generation.
- Then add a render review section to the detail page.

## 2026-06-09 Render Placeholder Step

Added render placeholder generation:

- `src/ai_shorts/render_placeholder.py` creates 1080x1920 SVG scene cards and `render_plan.json`.
- `workflow.generate_placeholder_render(...)` loads a saved project/script and creates render artifacts.
- Detail screen now has a "렌더 계획 생성" action and render artifact table.

Verification target:

- Compile `render_placeholder.py`, `workflow.py`, `web_app.py`, and tests.
- End-to-end create a draft through the web form, generate render placeholders, and verify `render_plan.json` plus scene SVG files exist.

Next recommended work:

- Add simple MP4 render from the generated SVG/placeholders.
- Then add render review and export status.

## 2026-06-09 Render Preview Step

Added a dependency-light render preview package:

- `src/ai_shorts/render_preview.py` creates scene PNG frames and `preview.gif` using Pillow.
- `preview_manifest.json` records GIF path, frame paths, dimensions, and MP4 availability status.
- Detail screen now has "GIF 미리보기 생성" and shows preview artifact paths.
- MP4 remains unavailable in the current bundled environment because `ffmpeg`, `moviepy`, and `imageio` are not present.

Verification target:

- Compile preview, workflow, web, and tests.
- Generate a draft, placeholder render, preview render, and verify `preview.gif`, frame PNGs, and `preview_manifest.json`.

Next recommended work:

- Add optional ffmpeg discovery/install guidance and MP4 conversion when ffmpeg is available.
- Then add render approval/export status.

## 2026-06-09 MP4 Conversion Readiness Step

Added ffmpeg readiness and optional MP4 conversion:

- `src/ai_shorts/ffmpeg_renderer.py` detects `ffmpeg` in PATH.
- If ffmpeg exists, it can convert preview PNG frames into `preview.mp4`.
- If ffmpeg is missing, it writes `mp4_status.json` with status `ffmpeg_missing` and install guidance.
- Detail screen now has "ffmpeg 확인" and "MP4 변환 시도" actions.

Current environment:

- `ffmpeg` was not found in PATH.
- `moviepy`, `imageio`, and `cv2` were not installed in the bundled Python.
- `PIL` was available, so PNG/GIF preview remains the working render path.

Verification target:

- Compile ffmpeg renderer, workflow, web, and tests.
- End-to-end create draft, generate placeholder, generate GIF preview, check MP4 status, and verify `mp4_status.json`.

Next recommended work:

- Add a guided ffmpeg install/download option if the user approves.
- Or add render approval/export status using GIF/timeline assets while MP4 waits.

## 2026-06-10 FFmpeg Setup Guide Step

Added guided ffmpeg setup output:

- `ffmpeg_setup_guide.json` and `ffmpeg_setup_guide.md` are generated under each project's preview render folder.
- The guide records a Windows WinGet install command, official/manual download links, and `ffmpeg -version` verification.
- The project detail screen now includes an `ffmpeg setup guide` action plus install and verify commands.
- The app still does not auto-install system tools without explicit user action.

Verification target:

- Compile ffmpeg renderer, workflow, web, and tests.
- Generate a setup guide from the web route and verify both guide files exist.

Next recommended work:

- Add render approval/export status using GIF/timeline assets while MP4 waits, or add a user-approved ffmpeg downloader/installer wrapper.

## 2026-06-10 Render Export Review Step

Added render export review status:

- `src/ai_shorts/render_export.py` writes `render_export_status.json` under `exports/manual_upload_package`.
- The status records timeline, GIF preview, and MP4 readiness plus blockers and next-step guidance.
- The project detail screen now has render export decisions: upload package possible, needs revision, or blocked.
- If GIF/timeline are approved but MP4 is still missing, status becomes `ready_for_upload_package_mp4_pending` instead of pretending final video upload is complete.

Verification target:

- Compile render export, workflow, web, and tests.
- End-to-end create draft, generate placeholder, generate GIF preview, approve render export, and verify `render_export_status.json`.

Next recommended work:

- Add final package checklist that requires MP4 before actual manual YouTube upload.

## 2026-06-10 Final Upload Checklist Step

Added final manual upload checklist:

- `src/ai_shorts/upload_checklist.py` writes `final_upload_checklist.json` under `exports/manual_upload_package`.
- The checklist verifies human project approval, compliance pass, asset/source notes, render export readiness, MP4 presence, title, description, and tags.
- Manual upload readiness stays blocked unless every gate passes.
- Public upload automation remains disabled; this only prepares a human-reviewed manual upload handoff.

Verification target:

- Compile upload checklist, workflow, web, and tests.
- End-to-end create draft, approve project review, generate render assets, approve render export, run final checklist, and verify it blocks without MP4.

Next recommended work:

- Add a dashboard summary that shows all projects and their current blocking gate.

## 2026-06-10 Project Dashboard Gate Summary Step

Added home dashboard gate summary:

- `src/ai_shorts/project_dashboard.py` computes the first blocking gate for each project.
- The home page recent-project table now shows current blocking gate and next action.
- Gate order is project review, compliance, render plan, GIF preview, MP4, render export, and final upload checklist.

Verification target:

- Compile project dashboard, web, and tests.
- Create a draft through the web route and verify the home page shows the blocking gate summary.

Next recommended work:

- Add weekly planner-to-draft queue so 2 to 3 planned topics can be promoted into saved drafts.

## 2026-06-10 Weekly Plan Queue Step

Added weekly plan promotion queue:

- `src/ai_shorts/weekly_queue.py` saves the latest weekly plan to `data/weekly_plan_queue.json`.
- Weekly plan results now show a "저장된 초안으로 승격" action for each planned topic.
- Promoting a slot creates a normal autosaved draft package and marks the queue slot as `promoted_to_draft`.

Verification target:

- Compile weekly queue, web, and tests.
- End-to-end create a weekly plan, promote a slot, and verify `app_state.json` contains the new draft.

Next recommended work:

- Add a lightweight growth-learning import form so uploaded performance notes can feed future weekly scores.

## 2026-06-10 Growth Learning Input Step

Added lightweight growth-learning performance records:

- `src/ai_shorts/growth_learning.py` stores records in `data/growth/performance_records.json`.
- Home page now has a growth-learning form for title, project ID, views, retention, CTR, average watch time, and notes.
- Each record receives a computed `growth_score` for future weekly planning.
- Recent performance records are shown on the home page.

Verification target:

- Compile growth learning, web, and tests.
- End-to-end submit the growth form and verify `performance_records.json` contains the record.

Next recommended work:

- Connect growth records to weekly planning so matching topics receive score boosts automatically.

## 2026-06-10 Growth Learning Weekly Score Step

Connected growth records to weekly planning:

- `apply_growth_learning_to_topics(...)` boosts candidate topic scores when words match prior performance record titles or notes.
- The web weekly plan route now applies growth learning before ranking slots.
- Boosted slots include `growth learning boost=...` in their reason text.

Verification target:

- Compile growth learning, web, and tests.
- Add a performance record, create a weekly plan with a matching candidate, and verify the matching topic ranks first.

Next recommended work:

- Add a CSV import path for YouTube Studio exports so performance rows can be added in bulk.

## 2026-06-10 YouTube Studio CSV Import Step

Added bulk CSV import for growth learning:

- `import_performance_csv(...)` accepts pasted CSV text and maps common YouTube Studio style columns.
- The growth learning section now has a CSV paste form.
- Imported rows are stored as normal performance records and immediately become available for weekly score boosts.

Verification target:

- Compile growth learning, web, and tests.
- End-to-end paste CSV data, verify records are stored, then create a weekly plan and confirm the imported topic can boost ranking.

Next recommended work:

- Add CSV import result feedback on the page so the user can see imported/skipped row counts.

## 2026-06-10 CSV Import Result Feedback Step

Added CSV import result feedback:

- The CSV import route now passes `imported_count`, `skipped_count`, and skipped row details back to the page.
- The home page displays a `CSV 가져오기 결과` section after import.

Verification target:

- Compile web and tests.
- End-to-end paste CSV data and verify the page shows imported/skipped counts.

Next recommended work:

- Add an operations snapshot/export button so the whole local project state can be backed up as a handoff bundle.

## 2026-06-10 Operations Snapshot Export Step

Added operations snapshot export:

- `src/ai_shorts/operations_snapshot.py` creates JSON, Markdown, and ZIP handoff files under `data/snapshots`.
- The snapshot summarizes saved projects, blocking gates, next actions, included files, and restore guidance.
- The home page now includes an `운영 스냅샷 생성` action and shows the generated ZIP/Markdown paths.

Verification target:

- Compile operations snapshot, web, and tests.
- End-to-end create a snapshot from the web action and verify the ZIP and handoff files exist.

Next recommended work:

- Add snapshot restore guidance UI and a one-page "new PC start here" document.

## 2026-06-10 Snapshot Restore Guide Step

Added new-PC continuation guidance:

- `src/ai_shorts/restore_guide.py` centralizes repository clone, snapshot copy, web start, and save-after-work steps.
- The home page now shows a `새 PC에서 이어하기` guide below the operations snapshot action.
- Operations snapshot Markdown now includes restore steps and a generated new-PC start section.
- `docs/NEW_PC_START_HERE.md` gives a one-page handoff guide for another PC.

Verification target:

- Compile restore guide, operations snapshot, web app, and tests.
- Smoke-test snapshot creation to confirm restore steps are included.

Next recommended work:

- Add a local environment check panel that shows Git, Python, data folder, and ffmpeg readiness from inside the web UI.

## 2026-06-09 Render Review Package Step

Extended placeholder rendering into a reviewable render package:

- `timeline.html` shows all generated scene SVGs in order with durations and visual directions.
- `render_manifest.json` records the review entry point, render plan, assets, and package status.
- Detail screen now shows timeline and manifest paths alongside scene SVG files.

Verification target:

- Compile render and web modules.
- Generate placeholders and verify `render_plan.json`, `render_manifest.json`, `timeline.html`, and `scene_01.svg` exist.

Next recommended work:

- Add simple MP4 render from the generated SVG/placeholders.
- Then add render review and export status.

## User Feature Direction Captured

The user wants:

1. Legal/policy collection, review, and inspection.
2. YouTube and other content analysis for original creation, not copying.
3. Automatic generation methods that avoid YouTube policy violations.
4. Combined video production: video, script, music, subtitles, and voice.
5. Weekly 2 to 3 automatically generated draft videos optimized using collected data and performance learning.

Implementation stance:

- Build compliance-first generation, not policy evasion.
- Automatic weekly work creates draft packages first.
- Public upload requires human approval and passing compliance gates.

Known blocker:

- Git is still unavailable on this PC from PowerShell PATH.
- GitHub connector write attempts returned `403 Resource not accessible by integration`.
- Remote commit/push still needs Git installed/exposed or GitHub app content-write permission fixed.
