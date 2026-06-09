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
