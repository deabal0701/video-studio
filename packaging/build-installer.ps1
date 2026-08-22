#Requires -Version 5.1
# build-installer.ps1 — 설치본 전 과정 (5-7·5-8).
#
#   .\packaging\build-installer.ps1            # 동결 → 런타임 → 라이선스 → 스모크 → 설치기
#   .\packaging\build-installer.ps1 -SkipFreeze  # 동결 건너뛰고 나머지만
#
# ★ 동결도 개발과 같은 conda env(penv3.13-video, pip 휠 PySide6)에서 한다 — 2026-08-22
#   통일. 옛 .qt-venv 는 은퇴: pip 휠 실패는 conda 가 아니라 옛 env 의 DLL 오염이었다.
# 판정은 $LASTEXITCODE 로 — PS 5.1 은 네이티브 stderr 를 오류로 던진다 (08 §9).
param([switch]$SkipFreeze, [switch]$SkipSmoke)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$CondaEnv = "penv3.13-video"

$prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
conda run -n $CondaEnv python -c "import PySide6, PyInstaller" 2>$null
$envReady = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prev
if (-not $envReady) {
  throw "conda env $CondaEnv 가 준비되지 않았다 — .un.ps1 -Setup 을 먼저 실행"
}

if (-not $SkipFreeze) {
  Write-Host "[1/5] 동결 (PyInstaller onedir — $CondaEnv)" -ForegroundColor Cyan
  $ErrorActionPreference = "Continue"
  conda run -n $CondaEnv pyinstaller (Join-Path $PSScriptRoot "VideoStudio.spec") --noconfirm `
      --distpath (Join-Path $repo "dist") --workpath (Join-Path $repo "build") | Out-Null
  $code = $LASTEXITCODE
  $ErrorActionPreference = $prev
  if ($code -ne 0) { throw "동결 실패 (exit $code)" }
}

Write-Host "[2/5] 런타임 수집 (node·ffmpeg·chromium·edge-tts·engine)" -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "collect-runtime.ps1")

Write-Host "[3/5] 라이선스 수집" -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "collect-licenses.ps1")

if (-not $SkipSmoke) {
  Write-Host "[4/5] 동결본 스모크 (PATH=System32 만 · 설치 폴더 무쓰기 검사 포함)" -ForegroundColor Cyan
  $ErrorActionPreference = "Continue"
  conda run -n $CondaEnv python (Join-Path $PSScriptRoot "smoke-frozen.py")
  $code = $LASTEXITCODE
  $ErrorActionPreference = $prev
  if ($code -ne 0) { throw "동결본 스모크 실패 — 설치기를 만들지 않는다" }
}

Write-Host "[5/5] 설치기 (Inno Setup)" -ForegroundColor Cyan
$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
  Write-Host "  ISCC.exe 없음 — Inno Setup 6 을 설치하면 이 단계가 자동으로 됩니다." -ForegroundColor Yellow
  Write-Host "  https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
  Write-Host "  (여기까지는 성공 — dist\VideoStudio 를 그대로 복사해도 실행됩니다)" -ForegroundColor Green
  exit 0
}
& $iscc (Join-Path $PSScriptRoot "VideoStudio.iss")
if ($LASTEXITCODE -ne 0) { throw "설치기 생성 실패" }
$out = Join-Path $PSScriptRoot "out\VideoStudioSetup.exe"
Write-Host ("완료 — {0} ({1:N0} MB)" -f $out, ((Get-Item $out).Length / 1MB)) -ForegroundColor Green
Write-Host "※ 코드 서명 없이 배포하면 SmartScreen 이 차단합니다 — VideoStudio.iss 의 SignTool 절 참조" -ForegroundColor Yellow
