$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Src = Join-Path $Root "src"
$env:PYTHONPATH = $Src

$BundledPython = "C:\Users\se513\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Candidates = @()

if ($env:AI_SHORTS_PYTHON) {
    $Candidates += $env:AI_SHORTS_PYTHON
}

$Candidates += $BundledPython
$Candidates += "python"

$Python = $null
foreach ($Candidate in $Candidates) {
    if ($Candidate -eq "python") {
        $Python = $Candidate
        break
    }
    if (Test-Path -LiteralPath $Candidate) {
        $Python = $Candidate
        break
    }
}

Set-Location -LiteralPath $Root
Write-Host "쇼츠 자동 생성 프로그램을 시작합니다."
Write-Host "브라우저에서 http://127.0.0.1:8731 주소를 여세요."
& $Python -m ai_shorts.web_app
