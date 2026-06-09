# Reference Review: shorts_auto_maker_v108_growth_learning

## What The Old Program Was Trying To Become

The reference ZIP is an all-in-one YouTube Shorts production suite. Its direction is useful:

- Discover or enter topics.
- Generate Korean short-form scripts.
- Create vertical video drafts with subtitles, narration, BGM, thumbnails, and metadata.
- Queue drafts for human approval.
- Prepare YouTube uploads and policy checks.
- Track performance after upload.
- Learn which topics, hooks, formats, upload times, and production modes perform better.
- Support backup, restore, installer, local mode, cost guard, and PC optimization.

In short: the intended product is a creator operating system for Shorts, not just a video generator.

## What To Keep

- The pipeline idea: topic -> script -> scene plan -> audio/video draft -> review -> publish package.
- Human approval before upload.
- Local-first mode so the program remains useful without API keys.
- Growth learning from CSV/manual metrics.
- Cost guard and policy guard as first-class features.
- Cross-PC continuation as a hard requirement.

## What To Avoid

- Too many `.bat` launchers for every tiny feature.
- Version pileup where v60, v68, v71, v108 concepts coexist in the same app.
- Broken Korean text encoding in UI, config, and docs.
- A single huge Streamlit app importing every feature at startup.
- Hidden state scattered across outputs, data folders, and generated reports.
- Pipeline steps that depend on variables before they are created.
- Features that imply automatic upload or revenue guarantees.

## Key Technical Findings

- The package contains hundreds of command files and version-specific checks, which makes the real user workflow hard to understand.
- `app.py` has broken Korean labels and very broad imports, making startup fragile.
- `config.yaml` includes useful settings but also broken Korean strings and stale model/version names.
- The main pipeline is conceptually rich but tightly coupled to many modules.
- The growth learning system has a useful scoring direction, but it should be rewritten with clear schemas and test data.

## Rebuild Decision

Do not repair this package directly. Use it as a product-direction reference and rebuild from a small, testable core.
