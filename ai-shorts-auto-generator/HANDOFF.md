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
