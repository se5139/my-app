# Kakao Emoticon Maker

이 저장소는 카카오 이모티콘 제작 보조 프로그램입니다. 다른 PC에서도 이어서 실행하고 수정할 수 있도록 실행 파일, 검증 스크립트, 배포 ZIP, 동기화 도구를 함께 보관합니다.

## 5담당 운영 체계

이 프로젝트는 세영님이 최종 담당자에게 명령하고, 최종 담당자가 5개 통합 담당자 기준으로 작업을 분배하는 방식으로 운영합니다.

| 5담당자 | 담당 범위 | 기존 12담당자 업무 |
|---|---|---|
| 1. 기획/요구사항 담당 | 전체 방향, 기능 목록, 중복 기능, 빠진 기능, 개발 우선순위 관리 | 1. 기획/요구사항 정리 |
| 2. 이미지/품질/저작권 담당 | PNG/GIF/WebP 규격, 투명 배경, 파일명, 문구 품질, 캐릭터 일관성, 저작권 위험 점검 | 2. 이미지 규격 검사, 3. 캐릭터/문구/콘셉트 품질, 12. 저작권/카카오 제출 위험 |
| 3. 데이터/엑셀/DB/백업 담당 | 카카오 판매/발신 통계 엑셀, SQLite, JSON/CSV, 누적 학습, 백업/복구, 데이터 보존 | 4. 엑셀 통계 분석, 5. 데이터/DB/백업 |
| 4. 보안/비용/API 담당 | .env, API 키 마스킹, 하드코딩 방지, ZIP 내 비밀파일 검사, API 쿼터, 비용 차단 | 6. 보안/API 키, 7. 비용/API 쿼터 |
| 5. UI/문서/QA/릴리즈 담당 | 웹 UX, 초보자 설명, 한글화, 테스트, BAT/EXE/ZIP 패키징, 릴리즈 노트 | 8. UI/UX 웹 디자인, 9. 한글화/초보자 설명서, 10. 테스트/QA, 11. Windows 패키징/릴리즈 |

자세한 책임표와 보고 형식은 `TEAM_ROLES_5_KO.md`를 기준으로 합니다.

현재 기본 저장소:

```text
https://github.com/se5139/my-app.git
```

## 다른 PC에서 바로 실행

새 PC에서 Git과 Python 3.10 이상을 설치한 뒤 실행합니다.

```bat
git clone https://github.com/se5139/my-app.git kakao-emoticon
cd kakao-emoticon
START_HERE.bat
```

`START_HERE.bat`은 먼저 `VERIFY_PACKAGE.bat`으로 필수 파일을 확인하고, 문제가 없으면 `START_WINDOWS.bat`으로 앱을 실행합니다.

브라우저가 자동으로 열리지 않으면 아래 주소를 직접 엽니다.

```text
http://127.0.0.1:8520
```

## ZIP으로 실행

Git을 쓰기 어렵다면 GitHub의 `release` 폴더에서 최신 ZIP을 받습니다.

```text
release/kakao_emoticon_v100_clean_latest.zip
```

압축 해제 후:

```bat
START_HERE.bat
```

자동 다운로드를 쓰려면:

```bat
DOWNLOAD_LATEST_RELEASE.bat
```

자세한 안내:

```text
QUICK_START_OTHER_PC_KO.txt
DOWNLOAD_LATEST_FROM_GITHUB_KO.md
TROUBLESHOOTING_KO.md
```

## 다른 PC에서 개발 이어가기

처음 받은 뒤 개발 환경을 점검하려면:

```bat
SETUP_DEV_ENV_WINDOWS.bat
```

작업 전 최신 내용 받기:

```bat
PULL_LATEST_BEFORE_WORK.bat
```

작업 후 GitHub에 저장:

```bat
SAVE_WORK_TO_GITHUB.bat
```

앞으로 이 저장소에서 작업할 때는 항상 아래 상태를 유지합니다.

- 작업 시작 전 `PULL_LATEST_BEFORE_WORK.bat`으로 최신 상태를 받습니다.
- 작업 후 `VERIFY_PACKAGE.bat`으로 기본 검증을 통과시킵니다.
- 변경사항은 커밋하고 `origin/main`에 push해서 다른 PC에서도 바로 이어갈 수 있게 합니다.
- 로컬 전용 결과물, `.venv`, 캐시, API 키, 토큰은 저장소에 올리지 않습니다.

## 작업 상태 옮기기

최근 결과물과 로컬 메모리를 함께 옮기려면 기존 PC에서:

```bat
EXPORT_SYNC_STATE.bat
```

새 PC에서:

```bat
IMPORT_SYNC_STATE.bat
```

자세한 내용은 `SYNC_STATE_GUIDE_KO.md`를 확인합니다.

## 주요 기능

- 러프 스케치 기반 캐릭터 제작 보조
- PNG/GIF 이모티콘 후보 생성
- 카카오 제출 전 규격, 용량, 문구, 위험 표현 점검
- 사람 제작 증빙 패키지 생성
- 자료 URL/메모 기반 로컬 진화 메모리 저장
- API 키 없이 기본 작동
- API 사용 시 호출 한도 장부로 비용 방지
- 최근 결과물, 갤러리, ZIP, 리포트 확인 페이지 제공

주의: 이 프로그램은 제작 보조 도구입니다. 카카오 심사 통과, 수익, 법적 적합성을 보장하지 않습니다. 최종 제출 전 최신 카카오 공식 기준, 저작권, 상표권, 초상권, 생성형 AI 관련 정책을 직접 확인해야 합니다.

## v92 설치파일 보관

기존 v92 설치파일과 배포 ZIP은 `_deliverables_v92` 폴더에 보관되어 있습니다.

```text
_deliverables_v92/KakaoEmoticonSetup_v92_DirectCreationHotfix.exe
_deliverables_v92/kakao_emoticon_profit_system_v92_direct_creation_hotfix.zip
```

v92 소스에서 직접 실행:

```bat
cd _review_v92
START_WINDOWS.bat
```

v92 바탕화면 바로가기 복구:

```bat
cd _review_v92
00_STEP_5_CREATE_DESKTOP_SHORTCUTS.bat
```

## 검증

현재 폴더 검증:

```bat
VERIFY_PACKAGE.bat
```

Python으로 직접 검증:

```bat
python scripts\verify_package.py
```

검증이 통과하면 다른 PC에서 실행 가능한 기본 구성이 갖춰진 상태입니다.
