# Kakao Emoticon Maker

카카오톡 이모티콘 자동생성 및 분석 보조 프로그램입니다.  
다른 PC에서도 바로 이어서 실행할 수 있도록 실행 BAT, 검증 스크립트, 배포 ZIP, 동기화 도구를 함께 관리합니다.

## 5담당 운영 체계

세영님은 최종 담당자에게만 명령합니다. 최종 담당자는 작업을 5개 통합 담당자에게 나누고, 각 담당자의 점검 결과와 수정 결과를 취합해 보고합니다.

| 5담당자 | 담당 범위 |
|---|---|
| 1. 기획/요구사항 담당 | 전체 방향, 기능 목록, 중복/누락 기능, 다음 개발 우선순위 |
| 2. 이미지/품질/저작권 담당 | PNG/GIF/WebP 규격, 투명 배경, 파일명, 문구/캐릭터 품질, 저작권 위험 |
| 3. 데이터/엑셀/DB/백업 담당 | 카카오 판매/발신 통계 엑셀, JSON/CSV/SQLite, 누적 학습, 백업/복구 |
| 4. 보안/비용/API 담당 | `.env`, API 키 마스킹, ZIP 비밀파일 검사, API 쿼터와 비용 차단 |
| 5. UI/문서/QA/릴리즈 담당 | 웹 UX, 초보자 설명, 한글화, 테스트, BAT/ZIP 릴리즈 |

자세한 책임표는 `TEAM_ROLES_5_KO.md`를 기준으로 합니다.

## 저장소

```text
https://github.com/se5139/my-app.git
```

## 다른 PC에서 바로 실행

새 PC에 Git과 Python 3.10 이상이 설치되어 있으면 아래 순서로 실행합니다.

```bat
git clone https://github.com/se5139/my-app.git kakao-emoticon
cd kakao-emoticon
START_HERE.bat
```

`START_HERE.bat`는 먼저 `VERIFY_PACKAGE.bat`로 필수 파일을 검사한 뒤, 문제가 없으면 `START_WINDOWS.bat`로 앱을 실행합니다.

브라우저가 자동으로 열리지 않으면 아래 주소를 직접 엽니다.

```text
http://127.0.0.1:8520
```

## ZIP으로 실행

Git 사용이 어렵다면 GitHub의 `release` 폴더에서 최신 ZIP을 받습니다.

```text
release/kakao_emoticon_v100_clean_latest.zip
```

압축을 푼 뒤:

```bat
START_HERE.bat
```

자동 다운로드를 사용하려면:

```bat
DOWNLOAD_LATEST_RELEASE.bat
```

## 개발 환경 준비

처음 받은 뒤 개발 환경까지 준비하려면:

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

## 작업 상태 옮기기

기존 PC에서 최근 결과물과 로컬 메모리를 묶으려면:

```bat
EXPORT_SYNC_STATE.bat
```

새 PC에서 가져오려면:

```bat
IMPORT_SYNC_STATE.bat
```

자세한 내용은 `SYNC_STATE_GUIDE_KO.md`를 확인합니다.

## 주요 기능

- 스케치/텍스트 기반 이모티콘 후보 생성 보조
- 정지형/움직이는형/미니형 규격 검사
- 카카오 제출 전 ZIP, 용량, 파일명, 투명 배경 검수
- 카카오 판매내역/이모티콘 플러스 엑셀 분석
- 성과 대시보드와 다음 제작 방향 추천
- API 키 없이 기본 작동
- API 사용 시 허용 스위치와 호출 한도로 비용 발생 방지
- 결과물, 리포트, 백업/복구 도구 제공

주의: 이 프로그램은 제작과 검수를 돕는 도구입니다. 카카오 심사 통과, 수익, 법적 적합성을 보장하지 않습니다. 최종 제출 전에는 최신 카카오 공식 가이드, 저작권, 상표권, 초상권, 생성형 AI 관련 정책을 사람이 직접 확인해야 합니다.

## 검증

현재 폴더 검증:

```bat
VERIFY_PACKAGE.bat
```

Python으로 직접 검증:

```bat
python scripts\verify_package.py
```

성과 대시보드 웹 검증:

```bat
python scripts\v100_performance_dashboard_web_check.py
```
