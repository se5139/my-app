# 다른 PC에서 이어서 작업하기

이 문서는 `https://github.com/se5139/my-app.git` 저장소를 다른 Windows PC에서 받아서 실행하고, 수정한 뒤 다시 GitHub에 저장하는 순서를 정리한 안내입니다.

## 1. 새 PC에서 처음 한 번만 준비

1. Git for Windows를 설치합니다.
2. Python 3.10 이상을 설치합니다.
3. Python 설치 화면에서 `Add Python to PATH`를 체크합니다.
4. 작업할 폴더에서 PowerShell 또는 명령 프롬프트를 엽니다.
5. 저장소를 받습니다.

```bat
git clone https://github.com/se5139/my-app.git kakao-emoticon
cd kakao-emoticon
```

6. 실행 전 패키지를 점검합니다.

```bat
VERIFY_PACKAGE.bat
```

7. 개발 환경을 준비합니다.

```bat
SETUP_DEV_ENV_WINDOWS.bat
```

8. 프로그램을 실행합니다.

```bat
START_HERE.bat
```

브라우저가 자동으로 열리지 않으면 아래 주소를 직접 엽니다.

```text
http://127.0.0.1:8520
```

## 2. 작업 시작 전 최신 내용 받기

다른 PC에서 작업을 시작하기 전에는 항상 최신 내용을 먼저 받습니다.

```bat
PULL_LATEST_BEFORE_WORK.bat
```

이 파일은 현재 PC에 저장하지 않은 변경이 있으면 자동으로 멈춥니다. 그 경우 먼저 작업을 저장하거나 백업한 뒤 다시 실행합니다.

## 3. 작업 후 GitHub에 저장하기

수정이 끝나면 아래 파일을 실행합니다.

```bat
SAVE_WORK_TO_GITHUB.bat
```

실행 중 커밋 메시지를 물어보면 짧게 입력합니다.

예:

```text
Fix shortcut creation
Update other PC guide
Improve preview validation
```

이 스크립트는 아래 순서로 처리합니다.

1. 변경 파일 확인
2. 전체 변경 파일 stage
3. commit 생성
4. GitHub 최신 내용 rebase
5. GitHub push

## 4. 최근 결과물과 로컬 메모리 옮기기

GitHub에는 보통 `outputs/`, `.venv/`, 로컬 캐시를 올리지 않습니다. 최근 결과물과 로컬 메모리까지 옮기려면 동기화 ZIP을 사용합니다.

기존 PC에서:

```bat
EXPORT_SYNC_STATE.bat
```

새 PC에서:

```bat
IMPORT_SYNC_STATE.bat
```

자세한 내용은 `SYNC_STATE_GUIDE_KO.md`를 확인합니다.

## 5. 충돌이 생겼을 때

여러 PC에서 같은 파일을 동시에 고치면 Git 충돌이 날 수 있습니다.

초보자 기준 권장 순서:

1. 오류 창을 닫지 말고 메시지를 확인합니다.
2. `git status`를 실행해서 충돌 파일명을 확인합니다.
3. 충돌 파일에서 `<<<<<<<`, `=======`, `>>>>>>>` 표시를 정리합니다.
4. 정리 후 아래 명령을 실행합니다.

```bat
git add .
git rebase --continue
git push origin main
```

해결이 어렵다면 충돌 파일명과 오류 메시지를 그대로 복사해서 Codex에 요청하면 됩니다.

## 6. 기본 작업 규칙

- 작업 시작 전 `PULL_LATEST_BEFORE_WORK.bat`을 먼저 실행합니다.
- 작업 종료 후 `SAVE_WORK_TO_GITHUB.bat`으로 저장합니다.
- API 키, 비밀번호, 개인 토큰이 들어간 파일은 GitHub에 올리지 않습니다.
- `outputs/`, `.venv/`, 캐시 폴더는 GitHub에 올리지 않습니다.
- 제출용 결과물은 필요할 때 `EXPORT_SYNC_STATE.bat`으로 별도 이동합니다.

## 7. 기준 정보

- 기본 저장소: `https://github.com/se5139/my-app.git`
- 기본 브랜치: `main`
- 첫 실행 파일: `START_HERE.bat`
- 실행 전 검증 파일: `VERIFY_PACKAGE.bat`
- 작업 전 최신화 파일: `PULL_LATEST_BEFORE_WORK.bat`
- 작업 후 저장 파일: `SAVE_WORK_TO_GITHUB.bat`
- 다른 PC용 ZIP: `release/kakao_emoticon_v100_clean_latest.zip`
