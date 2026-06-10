# New PC Start Here

Use this page when continuing the AI Shorts Auto Generator on another PC.

## Required Repository

```text
https://github.com/se5139/my-app.git
```

## 1. Repository Clone

```powershell
git clone https://github.com/se5139/my-app.git
cd my-app\ai-shorts-auto-generator
```

## 2. Snapshot Restore

If an operations snapshot zip exists, extract it and copy the extracted `data` folder into:

```text
my-app\ai-shorts-auto-generator\data
```

The snapshot zip is created from the web app with `운영 스냅샷 생성`.

## 3. Start The Web App

```powershell
$env:PYTHONPATH='src'
python -m ai_shorts.web_app
```

Open:

```text
http://127.0.0.1:8731
```

Confirm that recent drafts, growth learning records, weekly queue, and snapshots are visible.

## 4. Save After Every Completed Step

```powershell
git add .
git commit -m "Save AI shorts progress"
git push origin main
```

## Safety Rule

Do not enable public upload automation until MP4, compliance, human review, metadata, and asset-source gates pass.
