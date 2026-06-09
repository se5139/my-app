# AI Shorts Auto Generator

AI Shorts Auto Generator is a clean rebuild of the previous Shorts Auto Maker prototype.

The goal is to help one creator plan, produce, review, learn from, and safely publish short-form videos without losing progress between PCs.

## Canonical Repository

Use this GitHub repository for storage and cross-PC continuation:

```text
https://github.com/se5139/my-app.git
```

The project is stored under:

```text
ai-shorts-auto-generator/
```

## Save Rule

Every completed unit of work must be saved so another PC can continue at any time.

Required completion flow:

1. Save changed project files.
2. Commit the completed work.
3. Push to `origin/main`.
4. Keep setup and resume instructions current.

## Resume On Another PC

```powershell
git clone https://github.com/se5139/my-app.git
cd my-app\ai-shorts-auto-generator
```

Then follow the latest setup and run instructions in this folder.

## Rebuild Direction

The old reference package is kept only as a direction sample. The rebuild will focus on:

- A simple production pipeline: idea -> script -> assets -> video draft -> review -> publish package.
- Durable autosave state for every project and job.
- Clear Korean-first UI without broken text encoding.
- Local-first operation with optional AI/API integrations.
- Cost and upload safety gates before any paid API or public upload action.
- Growth learning from manually imported YouTube Studio metrics.
- Weekly 2 to 3 draft generation plans with human approval before upload.

See `docs/REFERENCE_REVIEW.md` and `docs/REBUILD_BLUEPRINT.md`.

## Current Foundation

- `src/ai_shorts/state.py`: autosaved app/project state.
- `src/ai_shorts/compliance.py`: legal, policy, originality, synthetic disclosure, and monetization risk gates.
- `src/ai_shorts/weekly_planner.py`: weekly 2 to 3 draft planning based on topic insights.
- `src/ai_shorts/script_lab.py`: local script draft creation without paid API calls.
- `src/ai_shorts/package_exporter.py`: manual upload package export with compliance report.
- `src/ai_shorts/cli.py`: local CLI for first workflow checks.
- `src/ai_shorts/web_app.py`: dependency-free local browser UI.

The app must generate compliant draft packages first. Public upload automation is intentionally not enabled in phase 1.

## Local CLI Smoke Workflow

From this folder:

```powershell
$env:PYTHONPATH='src'
python -m ai_shorts.cli new-draft "퇴근 후 시간 관리" --source-notes "인기 영상의 주제 흐름만 참고"
python -m ai_shorts.cli plan-week --count 3 --topic "생활 팁" --topic "직장 공감" --topic "시간 절약"
```

This creates autosaved local project data under `data/projects/`.

## Local Browser UI

From this folder:

```powershell
$env:PYTHONPATH='src'
python -m ai_shorts.web_app
```

Open:

```text
http://127.0.0.1:8731
```

On Windows, you can also run:

```bat
START_WEB_APP.bat
```

Saved drafts appear in the recent drafts table. Click a draft title to open its detail screen with:

- script summary
- scene list
- compliance report
- manual upload package file paths
- review decision controls: approve, needs revision, or block
- script edit controls for title, hook, thumbnail text, narration, and scene captions
- render placeholder generation with scene SVG files and `render_plan.json`
- render review package with `timeline.html` and `render_manifest.json`

## Local Git Setup For This PC

Git is required before local commits and pushes can run.

After Git is installed:

```powershell
git clone https://github.com/se5139/my-app.git
cd my-app\ai-shorts-auto-generator
```

If working from the existing OneDrive folder, initialize only after confirming how this local folder should sync with the remote repository.
