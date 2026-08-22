#Requires -Version 5.1
# collect-runtime.ps1 — 설치본에 동봉할 런타임을 dist\VideoStudio\runtime\ 에 모은다 (D14).
#
#   .\packaging\collect-runtime.ps1            # 없는 것만 받아서 채운다
#   .\packaging\collect-runtime.ps1 -Force     # 전부 다시
#
# 모으는 것 (07 "런타임 번들" 표):
#   runtime\node\node.exe      Node 공식 zip
#   runtime\ffmpeg\ffmpeg.exe·ffprobe.exe   ★ LGPL shared 빌드 (GPL 회피 — R8)
#   runtime\chromium\          Playwright 브라우저 (PLAYWRIGHT_BROWSERS_PATH 로 지정)
#   runtime\tts\edge-tts.exe   동결 앱에는 python 이 없다 — 엔진 tts.js 탐색 1순위를 채운다
#   engine\                    node_modules 포함 통째 복사 (엔진 무수정 — 파일 배치 그대로)
#
# 판정은 $LASTEXITCODE 로 한다 ($? 는 PS 5.1 에서 네이티브 stderr 를 오류로 던진다 — 08 §9).
param([switch]$Force)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$dist = Join-Path $repo "dist\VideoStudio"
$rt = Join-Path $dist "runtime"
if (-not (Test-Path $dist)) { throw "먼저 동결하세요: .\.qt-venv\Scripts\pyinstaller.exe packaging\VideoStudio.spec --noconfirm" }
New-Item -ItemType Directory -Force $rt | Out-Null

function Fetch($url, $out) {
  if ((Test-Path $out) -and -not $Force) { return }
  Write-Host "  받는 중: $url" -ForegroundColor DarkGray
  Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
}

# ── 1. Node ──────────────────────────────────────────────────────────────────
$nodeDir = Join-Path $rt "node"
if ($Force -or -not (Test-Path (Join-Path $nodeDir "node.exe"))) {
  Write-Host "[1/5] Node" -ForegroundColor Cyan
  $ver = (& node --version).Trim()          # 개발 PC 와 같은 메이저를 쓴다
  $zip = Join-Path $env:TEMP "node-$ver.zip"
  Fetch "https://nodejs.org/dist/$ver/node-$ver-win-x64.zip" $zip
  $tmp = Join-Path $env:TEMP "node-x-$ver"
  Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
  Expand-Archive $zip $tmp -Force
  New-Item -ItemType Directory -Force $nodeDir | Out-Null
  Copy-Item (Join-Path $tmp "node-$ver-win-x64\node.exe") $nodeDir -Force
}

# ── 2. ffmpeg (LGPL shared — 라이선스 분쟁 여지 제거, R8) ────────────────────
$ffDir = Join-Path $rt "ffmpeg"
if ($Force -or -not (Test-Path (Join-Path $ffDir "ffmpeg.exe"))) {
  Write-Host "[2/5] ffmpeg (LGPL shared)" -ForegroundColor Cyan
  $zip = Join-Path $env:TEMP "ffmpeg-lgpl.zip"
  Fetch "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-full_build-shared.zip" $zip
  $tmp = Join-Path $env:TEMP "ffmpeg-x"
  Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
  Expand-Archive $zip $tmp -Force
  New-Item -ItemType Directory -Force $ffDir | Out-Null
  Get-ChildItem $tmp -Recurse -Filter "*.exe" | Where-Object { $_.Name -in "ffmpeg.exe", "ffprobe.exe" } |
    ForEach-Object { Copy-Item $_.FullName $ffDir -Force }
  Get-ChildItem $tmp -Recurse -Filter "*.dll" | ForEach-Object { Copy-Item $_.FullName $ffDir -Force }
  Get-ChildItem $tmp -Recurse -Include "LICENSE*", "COPYING*" |
    ForEach-Object { Copy-Item $_.FullName (Join-Path $ffDir "LICENSE-ffmpeg.txt") -Force }
}

# ── 3. Playwright Chromium ───────────────────────────────────────────────────
$chDir = Join-Path $rt "chromium"
if ($Force -or -not (Test-Path $chDir)) {
  Write-Host "[3/5] Chromium (Playwright)" -ForegroundColor Cyan
  $env:PLAYWRIGHT_BROWSERS_PATH = $chDir
  Push-Location (Join-Path $repo "engine")
  npx playwright install chromium
  Pop-Location
}
# headless shell 은 엔진이 쓰지 않는다 (chromium.launch() 는 풀 브라우저) — 271MB 제거
Get-ChildItem $chDir -Directory -Filter "chromium_headless_shell*" -ErrorAction SilentlyContinue |
  ForEach-Object { Remove-Item -Recurse -Force $_.FullName }

# ── 4. edge-tts 셔틀 ─────────────────────────────────────────────────────────
$ttsDir = Join-Path $rt "tts"
if ($Force -or -not (Test-Path (Join-Path $ttsDir "edge-tts.exe"))) {
  Write-Host "[4/5] edge-tts 셔틀" -ForegroundColor Cyan
  $py = Join-Path $repo ".qt-venv\Scripts\python.exe"
  # pip 는 정상 종료해도 stderr 를 쓴다 — PS 5.1 은 그걸 NativeCommandError 로 바꾸고
  # $ErrorActionPreference=Stop 이 종료시킨다. 이 파일 머리말의 규칙대로 종료코드로 판정한다.
  $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  & $py -m pip install --quiet edge-tts pyinstaller
  $pipCode = $LASTEXITCODE
  $ErrorActionPreference = $prev
  if ($pipCode -ne 0) { throw "edge-tts 의존 설치 실패 (pip exit $pipCode)" }
  $shim = Join-Path $env:TEMP "edge-tts-shim.py"
  Set-Content $shim "import sys`nfrom edge_tts.util import main`nsys.exit(main())" -Encoding utf8
  # pyinstaller 도 INFO 를 stderr 로 쓴다 — pip 와 같은 함정 (위 참조)
  $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  & (Join-Path $repo ".qt-venv\Scripts\pyinstaller.exe") --onefile --name edge-tts `
    --distpath $ttsDir --workpath (Join-Path $env:TEMP "tts-build") `
    --specpath (Join-Path $env:TEMP "tts-build") --noconfirm $shim
  $pyiCode = $LASTEXITCODE
  $ErrorActionPreference = $prev
  if ($pyiCode -ne 0) { throw "edge-tts 셔틀 빌드 실패 (exit $pyiCode)" }
}

# ── 5. engine (무수정 통째 복사) ─────────────────────────────────────────────
# ★ 스톡 소재(bgm·broll·photo·presenter)는 **재배포 금지**라 설치본에 넣지 않는다 (R3).
#   CATALOG.md·fetch.js 만 넣고, 실물은 첫 실행 위저드가 원 출처에서 받는다.
#   out/·.cache 는 데이터 폴더로 가므로 역시 제외.
Write-Host "[5/5] engine (소재 제외 — 재배포 금지)" -ForegroundColor Cyan
robocopy (Join-Path $repo "engine") (Join-Path $dist "engine") /E `
  /XD out .cache bgm broll photo presenter /NFL /NDL /NJH /NJS | Out-Null
# 설치 루트에 빈 package.json — 엔진 findRoot/envFiles 상향 탐색의 경계표 (07)
Set-Content (Join-Path $dist "package.json") '{"private":true}' -Encoding utf8

$size = (Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum / 1GB
Write-Host ("완료 — dist\VideoStudio {0:N2} GB" -f $size) -ForegroundColor Green
