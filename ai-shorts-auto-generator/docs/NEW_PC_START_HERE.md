# 새 PC에서 이어서 시작하기

이 문서는 쇼츠 자동 생성 프로그램을 다른 PC에서 이어서 작업할 때 보는 초보자용 안내서입니다.

## 1. GitHub 저장소 받기

PowerShell을 열고 원하는 작업 폴더에서 실행합니다.

```powershell
git clone https://github.com/se5139/my-app.git
cd my-app\ai-shorts-auto-generator
```

## 2. Python 의존성 설치

```powershell
python -m pip install -r requirements.txt
```

현재 필수 의존성은 `Pillow`입니다. PNG/GIF 미리보기 생성에 사용합니다.

## 3. 이전 작업 데이터 복구

운영 스냅샷 ZIP이 있다면 압축을 풉니다.

압축을 푼 뒤 그 안의 `data` 폴더를 아래 위치에 복사합니다.

```text
my-app\ai-shorts-auto-generator\data
```

스냅샷은 웹 앱의 `운영 스냅샷 생성` 버튼으로 만들 수 있습니다.

주의:

- `data/secrets`에는 API 키가 들어갈 수 있으므로 GitHub에 올리지 않습니다.
- 운영 스냅샷 생성 로직은 secrets 폴더를 제외하도록 설계되어 있습니다.

## 4. 웹 앱 실행

PowerShell에서 실행합니다.

```powershell
$env:PYTHONPATH='src'
python -m ai_shorts.web_app
```

또는 Windows에서 다음 파일을 실행합니다.

```text
START_WEB_APP.bat
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8731
```

## 5. 실행 후 확인할 것

웹 화면에서 아래 항목이 보이는지 확인합니다.

- 최근 초안
- 주간 2~3개 계획
- 제작 준비도
- 콘텐츠 제작 흐름
- API 키 준비 상태
- API 비용 차단 상태
- 성장 데이터 기록
- 운영 스냅샷/핸드오프 보고서

## 6. API 키 설정

웹 화면에서 아래 키를 저장할 수 있습니다.

- Gemini 생성용 키
- YouTube 수집용 키
- Naver Client ID
- Naver Client Secret
- Kakao REST API 키

현재 단계에서는 키를 저장해도 실제 외부 API 호출은 실행하지 않습니다. 스모크 체크는 로컬 키 형식과 비용 차단 상태만 확인합니다.

## 7. 작업 후 저장

작업 하나가 끝나면 반드시 GitHub에 저장합니다.

```powershell
git status
git add .
git commit -m "Save AI shorts progress"
git push origin main
```

다른 PC에서 이어서 작업하려면 먼저 최신 내용을 받습니다.

```powershell
git pull origin main
```

## 8. 안전 규칙

- 실제 YouTube 업로드는 아직 자동 실행하지 않습니다.
- 유료 API 호출은 기본 차단합니다.
- 외부 영상, 이미지, 음악, 효과음은 출처와 사용 권리를 확인해야 합니다.
- 사람 승인 없이 공개 게시하지 않습니다.
- MP4, 정책 검토, 제목/설명/태그, 자산 출처 메모가 모두 준비된 뒤에만 업로드를 검토합니다.

## 9. 문제가 생겼을 때

먼저 아래 명령으로 문법 오류를 확인합니다.

```powershell
python -m py_compile src\ai_shorts\*.py tests\test_state.py
```

ffmpeg가 없어 MP4가 만들어지지 않는 경우에는 앱에서 생성되는 ffmpeg 설치 안내 파일을 확인합니다. GIF 미리보기는 `Pillow`만 설치되어 있으면 동작합니다.
