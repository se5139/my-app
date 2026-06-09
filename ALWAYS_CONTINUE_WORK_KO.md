# 항상 이어서 작업하기

앞으로 이 프로젝트의 기준 저장소는 아래 주소입니다.

```text
https://github.com/se5139/my-app.git
```

## 다른 PC에서 시작할 때

```powershell
git clone https://github.com/se5139/my-app.git kakao-emoticon
cd kakao-emoticon
START_HERE.bat
```

이미 받아 둔 폴더가 있으면 작업 전에 먼저 실행합니다.

```powershell
PULL_LATEST_BEFORE_WORK.bat
```

## 작업을 끝낼 때

작업 후에는 항상 GitHub에 저장합니다.

```powershell
SAVE_WORK_TO_GITHUB.bat
```

Codex가 작업할 때도 원칙은 같습니다.

1. 작업 전 `origin/main` 최신 상태 확인
2. 필요한 변경만 커밋
3. `pull --rebase` 또는 `fetch` 후 충돌 확인
4. `https://github.com/se5139/my-app.git`의 `main` 브랜치로 푸시

이렇게 유지하면 다른 PC에서도 같은 저장소를 받아 바로 이어서 작업할 수 있습니다.
