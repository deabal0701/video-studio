# run.ps1 — Video Studio 실행 런처 (준비가 안 돼 있으면 알아서 준비하고 띄운다).
#
#   .\run.ps1              앱 실행 (데이터 = projects\)
#   .\run.ps1 -Fixtures    앱 실행 (데이터 = fixtures\projects — 개발용 hr-basics)
#   .\run.ps1 -Setup       준비만 (실행 안 함)
#   .\run.ps1 -Test        pytest
#
# 파이썬은 conda penv3.13-video **하나다** (2026-08-22 재통일 — insait 와 분리, pip 휠).
# 옛 env(penv3.13-insait)의 pip 휠 실패(Qt6Core DLL WinError 127)는 conda 자체가 아니라
# **그 env 의 DLL 오염**이었다 — 깨끗한 env 에선 pip 휠 정상(실측). 덕분에 동결까지 이
# env 하나로 합쳐졌다(.qt-venv 은퇴) — .claude\memory\pyside6-environment.md.
param(
  [switch]$Fixtures,
  [switch]$Setup,
  [switch]$Test
)
$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$CondaEnv = "penv3.13-video"

function Need($name, $hint) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { throw "$name 이(가) 없다. $hint" }
}
Need conda "miniconda/anaconda 설치 후 $CondaEnv 환경이 필요하다."

# env 파이썬을 **직접 호출**한다 — `conda run` 은 conda 가 활성화된 Git Bash 에서 뜬
# powershell 에서는 PATH 재계산이 꼬여 base(3.9) 파이썬을 잡는다(2026-08-22 실측 —
# 그 상태로 pip 이 돌면 claude-agent-sdk >=3.10 불충족으로 설치 실패). 직접 호출은 면역이고,
# 이 env 는 전부 pip 휠이라 활성화 없이도 임포트 정상(같은 날 실측: Qt 3종·sqlite3·ssl).
$envPrefix = (conda env list --json | ConvertFrom-Json).envs |
  Where-Object { (Split-Path $_ -Leaf) -eq $CondaEnv } | Select-Object -First 1
if (-not $envPrefix) { throw "conda env '$CondaEnv' 가 없다. conda create -n $CondaEnv python=3.13" }
$Py = Join-Path $envPrefix "python.exe"

if ($Test) {
  & $Py -m pytest -q
  exit $LASTEXITCODE
}

# ── 준비 1: 의존성 (전부 pip — PySide6 포함) ─────────────────────────────────
# 판정은 $? 가 아니라 **종료코드**로 한다: PS 5.1 은 네이티브 exe 의 stderr 를 리다이렉트하면
# 각 줄을 ErrorRecord 로 감싸고, $ErrorActionPreference="Stop" 아래서는 그것이 **종료 오류로
# 던져진다**(NativeCommandError) — 임포트가 실패하는 첫 실행에서 설치로 못 넘어가고 죽는다.
# (2026-08-21 실측: 실패 임포트 → THREW NativeCommandError / 아래 패턴 → bad=1 good=0 무예외)
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $Py -c "import PySide6.QtCore, PySide6.QtWebEngineWidgets, PySide6.QtMultimedia, pydantic, pytest, edge_tts" 2>$null
$qtReady = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prev
if (-not $qtReady) {
  Write-Host "[1/2] 의존성 설치 중 (pip — 최초 1회, 수 분)..." -ForegroundColor Cyan
  $ErrorActionPreference = "Continue"
  & $Py -m pip install --quiet PySide6 pydantic pytest pytest-timeout claude-agent-sdk openai edge-tts pyinstaller
  $pipCode = $LASTEXITCODE
  $ErrorActionPreference = $prev
  if ($pipCode -ne 0) { throw "pip 설치 실패 (exit $pipCode) — env 확인: conda create -n $CondaEnv python=3.13" }
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
& $Py -m app
exit $LASTEXITCODE
