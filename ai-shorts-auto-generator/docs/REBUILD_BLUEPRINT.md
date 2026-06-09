# Rebuild Blueprint

## Product Shape

Build a Korean-first desktop/web app for one creator producing YouTube Shorts.

The first screen should be the actual workspace:

- Project list and current production queue.
- One clear "new short" workflow.
- Autosaved draft state.
- Review checklist before export or upload.
- Growth insights from imported metrics.

## Core Workflow

1. Idea
   - Enter a topic manually.
   - Optionally import trend notes or competitor inspiration.
   - Store source notes so the draft can be audited later.

2. Script
   - Generate or manually write hook, narration, scenes, title candidates, thumbnail text, hashtags, and pinned comment.
   - Keep every draft revision.

3. Assets
   - Attach images/video clips/audio or generate placeholder assets.
   - Track license/source notes for each asset.

4. Draft Video
   - Create a vertical 1080x1920 draft.
   - Add Korean subtitles first, English optional later.
   - Save render settings and output paths.

5. Review
   - Check policy risk, copyright/source notes, readability, length, and upload metadata.
   - Require explicit approval before export/upload.

6. Publish Package
   - Export video, thumbnail, description, tags, checklist, and source notes into a package folder.
   - Direct YouTube upload can be added only after the approval and OAuth flow is reliable.

7. Growth Learning
   - Import YouTube Studio CSV manually first.
   - Score topics, hooks, retention, CTR, comments, and upload timing.
   - Feed insights into the next idea/script workflow.

## User-Requested Capabilities

1. Legal and policy collection, review, and inspection
   - Store official policy source URLs and the date they were reviewed.
   - Check copyright/source risk, reused-content risk, synthetic-content disclosure needs, advertiser suitability, and YouTube monetization fit.
   - Mark risky drafts as blocked until the user reviews them.

2. Analyze videos and content without copying
   - Collect public metadata and creator-entered notes for inspiration.
   - Extract patterns such as topic, hook style, pacing, comment themes, title structure, and upload timing.
   - Do not download, reupload, clone, imitate, or minimally modify other creators' assets.
   - Require a transformation note that explains what is original in the new draft.

3. Compliant generation
   - The app must not help bypass YouTube policies.
   - The app should search for compliant production methods and choose safer defaults.
   - Public upload must stay disabled until review gates pass.

4. Full video production
   - Generate or assemble script, voice, subtitles, BGM/music, visuals, thumbnail, description, tags, and final vertical video.
   - Track asset source and license notes for every non-generated asset.

5. Weekly revenue-oriented production
   - Create 2 to 3 draft packages per week by default.
   - Use imported performance data to prioritize topic families, hooks, and upload windows.
   - Never guarantee revenue. Optimize for eligibility, consistency, retention, CTR, and originality.

## Data Model

Use local durable files first:

- `data/app_state.json`: global app state.
- `data/projects/<project_id>/project.json`: one short or series project.
- `data/projects/<project_id>/revisions/*.json`: script and metadata revisions.
- `data/projects/<project_id>/assets/`: user-provided or generated assets.
- `data/projects/<project_id>/renders/`: rendered draft outputs.
- `data/growth/metrics_imports/`: imported CSV files.
- `data/growth/insights.json`: computed learning memory.

Later, add SQLite if file-based state becomes awkward. Start simple.

## Technical Stack

Phase 1 should use Python with a small local web UI:

- Streamlit for fast UI iteration.
- Pydantic-style validation if available, otherwise dataclasses plus explicit checks.
- MoviePy/Pillow only when video rendering is needed.
- No auto-upload in the first version.

## Phase 1 Scope

- Clean project skeleton.
- Autosave state manager.
- Manual new-short workflow.
- Script draft editor.
- Review checklist.
- Export package generator.
- Growth CSV import stub.
- Policy/legal checker stub with deterministic gates.
- Weekly 2 to 3 draft planner.

## Non-Goals For Phase 1

- Android APK.
- Windows installer.
- Automatic public upload.
- Complex background worker.
- Dozens of one-click `.bat` commands.
- Paid API calls without explicit cost confirmation.
- Policy evasion or scraping that violates site/API terms.
