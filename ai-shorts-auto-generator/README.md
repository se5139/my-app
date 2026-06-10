# 쇼츠 자동 생성 프로그램

이 프로젝트는 세영님이 다른 PC에서도 이어서 작업할 수 있도록 만든 로컬 우선형 Shorts Auto Maker입니다.

현재 목표는 바로 공개 업로드하는 자동화가 아니라, 안전한 쇼츠 제작 흐름을 만드는 것입니다.

```text
주제 선정 -> 대본 초안 -> 장면 구성 -> 정책 검토 -> 렌더 미리보기 -> 업로드 패키지 -> 사람 승인
```

## 저장소

항상 아래 GitHub 저장소를 기준으로 저장하고 이어서 작업합니다.

```text
https://github.com/se5139/my-app.git
```

프로젝트 폴더는 저장소 안의 다음 위치입니다.

```text
ai-shorts-auto-generator/
```

## 작업 저장 규칙

작업 하나가 끝나면 반드시 저장소에 남깁니다.

1. 변경 파일 저장
2. 테스트 또는 스모크 체크
3. `git commit`
4. `git push origin main`
5. 다음 사람이 볼 수 있도록 `HANDOFF.md` 또는 문서 갱신

## 처음 실행

Windows PowerShell에서 실행합니다.

```powershell
cd my-app\ai-shorts-auto-generator
python -m pip install -r requirements.txt
$env:PYTHONPATH='src'
python -m ai_shorts.web_app
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8731
```

Windows에서 더 쉽게 실행하려면 다음 파일을 더블클릭하거나 PowerShell에서 실행합니다.

```text
START_WEB_APP.bat
```

## 다른 PC에서 이어서 작업

```powershell
git clone https://github.com/se5139/my-app.git
cd my-app\ai-shorts-auto-generator
python -m pip install -r requirements.txt
$env:PYTHONPATH='src'
python -m ai_shorts.web_app
```

운영 스냅샷 ZIP이 있다면 압축을 풀고 `data` 폴더를 아래 위치에 복사합니다.

```text
my-app\ai-shorts-auto-generator\data
```

자세한 절차는 `docs/NEW_PC_START_HERE.md`를 봅니다.

## 현재 구현된 핵심 기능

- 자동 저장용 앱/프로젝트 상태 관리: `src/ai_shorts/state.py`
- 정책, 저작권, 원본성, 수익화 위험 검토: `src/ai_shorts/compliance.py`
- 주간 2~3개 초안 계획: `src/ai_shorts/weekly_planner.py`
- 로컬 대본 초안 생성: `src/ai_shorts/script_lab.py`
- 수동 업로드 패키지 생성: `src/ai_shorts/package_exporter.py`
- SVG/PNG/GIF 미리보기 생성: `src/ai_shorts/render_placeholder.py`, `src/ai_shorts/render_preview.py`
- ffmpeg가 있을 때 MP4 미리보기 생성: `src/ai_shorts/ffmpeg_renderer.py`
- 최종 업로드 전 체크리스트: `src/ai_shorts/upload_checklist.py`
- 성장 데이터 수동 기록/CSV 가져오기: `src/ai_shorts/growth_learning.py`
- 제작 준비도와 게이트 대시보드: `src/ai_shorts/production_readiness.py`
- API 키 준비 화면: `src/ai_shorts/api_keys.py`
- API 비용 차단기: `src/ai_shorts/cost_guard.py`
- API 스모크 체크 계획과 로컬 키 형식 검증: `src/ai_shorts/api_smoke_check.py`
- 새 PC 복구 안내와 운영 스냅샷: `src/ai_shorts/restore_guide.py`, `src/ai_shorts/operations_snapshot.py`

## 아직 의도적으로 막아둔 기능

아래 기능은 안전 장치가 충분해질 때까지 실제 실행하지 않습니다.

- YouTube 실제 업로드
- 유료 API 호출
- 외부 API 네트워크 호출
- OAuth 기반 자동 업로드
- 사람 승인 없는 공개 게시

## API 키 설정

웹 화면의 API 키 준비 섹션에서 아래 키를 저장할 수 있습니다.

- Gemini 생성용 키
- YouTube 수집용 키
- Naver Client ID / Secret
- Kakao REST API 키

키는 `data/secrets` 아래 로컬 파일에 저장되고, 화면에는 원문이 아니라 마스킹된 상태만 표시됩니다.

주의:

- API 키를 GitHub에 올리지 않습니다.
- `.env`, `.env.*`, `data/`는 `.gitignore`에 포함되어 있습니다.
- 현재 스모크 체크는 실제 네트워크 호출을 하지 않습니다.
- 모든 API 테스트는 `evaluate_api_call(...)` 비용 차단기를 먼저 통과해야 합니다.

## 의존성

현재 필수 Python 의존성은 다음과 같습니다.

- `Pillow`: PNG/GIF 미리보기 이미지 생성용

설치:

```powershell
python -m pip install -r requirements.txt
```

ffmpeg는 선택 사항입니다. MP4 미리보기를 만들려면 PC에 ffmpeg가 설치되어 있어야 합니다. 설치되지 않은 경우 앱이 설치 안내 파일을 생성합니다.

## 테스트와 점검

기본 문법 검사는 다음처럼 실행합니다.

```powershell
python -m py_compile src\ai_shorts\*.py tests\test_state.py
```

`pytest`가 설치되어 있다면 다음 명령으로 전체 테스트를 실행할 수 있습니다.

```powershell
python -m pytest
```

## 안전 원칙

- 외부 영상, 이미지, 음악, 효과음은 출처와 사용 권리를 확인해야 합니다.
- 유명 캐릭터, 브랜드, 연예인, 실존 인물과 유사한 콘텐츠는 사람이 반드시 검토해야 합니다.
- 반복/저품질/대량 자동 생성처럼 보이는 초안은 업로드하지 않습니다.
- 최종 업로드는 MP4, 정책 검토, 자산 출처, 제목/설명/태그, 사람 승인이 모두 통과된 뒤에만 진행합니다.
