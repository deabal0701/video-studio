# run.ps1 — Video Studio 실행 런처 (준비가 안 돼 있으면 알아서 준비하고 띄운다).
#
#   .\run.ps1              앱 실행 (데이터 = projects\)
#   .\run.ps1 -Fixtures    앱 실행 (데이터 = fixtures\projects — 개발용 hr-basics)
#   .\run.ps1 -Setup       준비만 (실행 안 함)
#   .\run.ps1 -Test        pytest
#
# 파이썬은 conda penv3.13-insait **하나다** (2026-08-21 통일 — 사용자 지시).
# PySide6 는 pip 휠이 아니라 **conda-forge 빌드**를 쓴다: pip 휠은 conda 파이썬에서
# Qt6Core DLL 충돌(WinError 127)로 안 뜬다 — .claude\memory\pyside6-environment.md.
param(
  [switch]$Fixtures,
  [switch]$Setup,
  [switch]$Test
)
$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$CondaEnv = "penv3.13-insait"

function Need($name, $hint) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { throw "$name 이(가) 없다. $hint" }
}
Need conda "miniconda/anaconda 설치 후 $CondaEnv 환경이 필요하다."

if ($Test) {
  conda run -n $CondaEnv python -m pytest -q
  exit $LASTEXITCODE
}

# ── 준비 1: PySide6 (conda-forge 빌드 — pip 휠 금지) ─────────────────────────
# 판정은 $? 가 아니라 **종료코드**로 한다: PS 5.1 은 네이티브 exe 의 stderr 를 리다이렉트하면
# 각 줄을 ErrorRecord 로 감싸고, $ErrorActionPreference="Stop" 아래서는 그것이 **종료 오류로
# 던져진다**(NativeCommandError) — 임포트가 실패하는 첫 실행에서 설치로 못 넘어가고 죽는다.
# (2026-08-21 실측: 실패 임포트 → THREW NativeCommandError / 아래 패턴 → bad=1 good=0 무예외)
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
conda run -n $CondaEnv python -c "import PySide6.QtCore, PySide6.QtWebEngineWidgets, PySide6.QtMultimedia, pydantic" 2>$null
$qtReady = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prev
if (-not $qtReady) {
  Write-Host "[1/2] PySide6 (conda-forge) 설치 중 (최초 1회, 수 분)..." -ForegroundColor Cyan
  $ErrorActionPreference = "Continue"
  conda run -n $CondaEnv pip uninstall -y PySide6 PySide6_Addons PySide6_Essentials shiboken6 2>$null | Out-Null
  $ErrorActionPreference = $prev
  conda install -y -n $CondaEnv -c conda-forge pyside6 qt6-webengine qt6-multimedia
  conda run -n $CondaEnv pip install --quiet pydantic
}

# ── 준비 2: 엔진 의존성 (Playwright) ─────────────────────────────────────────
if (-not (Test-Path (Join-Path $repo "engine\node_modules\playwright"))) {
  Need npm "Node 20+ 설치 필요 (렌더 엔진 = Node CLI — docs\design\00_overview.md D4)."
  Write-Host "[2/2] engine 의존성 설치 중 (최초 1회)..." -ForegroundColor Cyan
  Push-Location (Join-Path $repo "engine")
  npm install
  npx playwright install chromium
  Pop-Location
}

if ($Setup) { Write-Host "준비 완료. .\run.ps1 로 실행한다." -ForegroundColor Green; exit 0 }

# ── 실행 ─────────────────────────────────────────────────────────────────────
if ($Fixtures) { $env:VIDEO_STUDIO_PROJECTS = Join-Path $repo "fixtures\projects" }
Set-Location $repo
conda run --no-capture-output -n $CondaEnv python -m app
exit $LASTEXITCODE
