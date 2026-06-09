# Phase 1 Requirements

## Goal

Build a reliable local workspace that creates compliant YouTube Shorts draft packages and saves progress after every step.

## Required Modules

- `state`: autosaved app and project state.
- `compliance`: legal, policy, originality, upload, and monetization risk checks.
- `weekly_planner`: chooses 2 to 3 weekly draft slots from performance insights and user goals.
- `script_lab`: creates structured script drafts.
- `package_exporter`: exports video package folders for manual upload.

## Compliance Gates

A draft cannot be marked `approved_for_export` if any of these are true:

- Missing transformation note when using external inspiration.
- Missing asset source/license note for third-party media.
- High reused-content risk.
- High copyright risk.
- Synthetic disclosure is required but not acknowledged.
- Claims imply guaranteed revenue, medical cure, financial certainty, or deception.
- Draft is marked made-for-kids without the correct review path.

## Weekly Automation Guardrails

- Weekly automation creates drafts, not public uploads.
- Default target: 2 drafts per week.
- Maximum default target: 3 drafts per week.
- Public upload requires explicit human approval.
- Paid API generation requires explicit cost confirmation.

## First Usable Version

The first usable version should let the user:

1. Create a project.
2. Enter a topic and source inspiration notes.
3. Generate or write a structured script draft.
4. Run compliance checks.
5. Save review results.
6. Export a manual upload package.
7. Import performance CSV later for growth learning.
