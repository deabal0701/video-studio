#Requires -Version 5.1
# collect-licenses.ps1 — 설치본에 동봉할 라이선스 전문을 모은다 (5-8 · R8).
#
#   .\packaging\collect-licenses.ps1
#
# LGPL 은 "고지 + 전문 동봉 + 교체(relink) 가능"을 요구한다. Qt/PySide6 휠에는 상용
# 라이선스 참조만 들어 있고 **LGPL 전문이 없어서**, 정본(gnu.org)에서 받아 캐시한다.
# 원문을 손으로 쓰지 않는 이유: 라이선스는 글자 그대로가 효력이라 재작성하면 안 된다.
#
# 받은 전문은 packaging\licenses\ 에 캐시하고(1회), dist\VideoStudio\licenses\ 로 복사한다.
# 전문이 하나라도 없으면 **실패한다** — 고지 없이 배포하는 사고를 막는다.
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$cache = Join-Path $PSScriptRoot "licenses"
$dist = Join-Path $repo "dist\VideoStudio"
New-Item -ItemType Directory -Force $cache | Out-Null

# ── 1. 정본에서 받아 캐시 (없을 때만) ────────────────────────────────────────
$fetch = @{
  "LGPL-3.0.txt" = "https://www.gnu.org/licenses/lgpl-3.0.txt"
  "GPL-3.0.txt"  = "https://www.gnu.org/licenses/gpl-3.0.txt"   # LGPL v3 이 참조한다
  # Playwright 의 Chromium 빌드에는 CREDITS 파일이 없다(정본은 브라우저 안 chrome://credits) —
  # Chromium 자체 라이선스를 정본 저장소에서 받는다 (2026-08-22 실측: chrome-win64 에 라이선스 파일 0개)
  "chromium-LICENSE.txt" = "https://raw.githubusercontent.com/chromium/chromium/main/LICENSE"
}
foreach ($name in $fetch.Keys) {
  $path = Join-Path $cache $name
  if (Test-Path $path) { continue }
  Write-Host "  받는 중: $name" -ForegroundColor DarkGray
  Invoke-WebRequest -Uri $fetch[$name] -OutFile $path -UseBasicParsing
}

# ── 2. 이미 있는 것들을 캐시로 모은다 ────────────────────────────────────────
function Grab($src, $dest) {
  if (Test-Path $src) { Copy-Item $src (Join-Path $cache $dest) -Force; return $true }
  return $false
}
Grab (Join-Path $repo "engine\fonts\LICENSE.txt") "Pretendard-LICENSE.txt" | Out-Null
Grab (Join-Path $repo "engine\node_modules\playwright\LICENSE") "playwright-LICENSE.txt" | Out-Null
Grab (Join-Path $dist "runtime\ffmpeg\LICENSE-ffmpeg.txt") "ffmpeg-LICENSE.txt" | Out-Null
Grab (Join-Path $dist "runtime\chromium\ffmpeg-1011\COPYING.LGPLv2.1") "LGPL-2.1.txt" | Out-Null
# pydantic — 동결 env(penv3.13-video) 의 dist-info 에서
$prevEA = $ErrorActionPreference; $ErrorActionPreference = "Continue"
$sitePkg = (conda run -n penv3.13-video python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])" 2>$null | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1)
$ErrorActionPreference = $prevEA
if (-not $sitePkg) { throw "penv3.13-video site-packages 를 못 찾았다" }
Get-ChildItem $sitePkg -Directory -Filter "pydantic-*.dist-info" -EA SilentlyContinue |
  ForEach-Object { Grab (Join-Path $_.FullName "licenses\LICENSE") "pydantic-LICENSE.txt" | Out-Null }

# Node LICENSE — zip 안에 있다. 없으면 배포 zip 에서 한 번 더 받는다.
if (-not (Test-Path (Join-Path $cache "node-LICENSE.txt"))) {
  $ver = (& node --version).Trim()
  $zip = Join-Path $env:TEMP "node-$ver.zip"
  if (-not (Test-Path $zip)) {
    Invoke-WebRequest "https://nodejs.org/dist/$ver/node-$ver-win-x64.zip" -OutFile $zip -UseBasicParsing
  }
  $tmp = Join-Path $env:TEMP "node-lic-$ver"
  Remove-Item -Recurse -Force $tmp -EA SilentlyContinue
  Expand-Archive $zip $tmp -Force
  Grab (Join-Path $tmp "node-$ver-win-x64\LICENSE") "node-LICENSE.txt" | Out-Null
}

# edge-tts — 동결 env 의 dist-info
Get-ChildItem $sitePkg -Directory -Filter "edge_tts-*.dist-info" -EA SilentlyContinue |
  ForEach-Object {
    $f = Get-ChildItem $_.FullName -Recurse -Include "LICENSE*" -File -EA SilentlyContinue | Select-Object -First 1
    if ($f) { Copy-Item $f.FullName (Join-Path $cache "edge-tts-LICENSE.txt") -Force }
  }

# ── 3. 검증 — NOTICE.md 가 약속한 전문이 전부 있어야 한다 ────────────────────
$required = @("LGPL-3.0.txt", "GPL-3.0.txt", "LGPL-2.1.txt", "ffmpeg-LICENSE.txt",
              "node-LICENSE.txt", "playwright-LICENSE.txt", "Pretendard-LICENSE.txt",
              "pydantic-LICENSE.txt", "edge-tts-LICENSE.txt", "chromium-LICENSE.txt")
$missing = $required | Where-Object { -not (Test-Path (Join-Path $cache $_)) }
if ($missing) {
  throw "라이선스 전문 누락 — 고지 없이 배포할 수 없다: $($missing -join ', ')`n" +
        "  (수동으로 packaging\licenses\ 에 넣거나, 해당 구성요소를 NOTICE.md 에서 빼세요)"
}

# ── 4. dist 로 복사 + NOTICE 동봉 ────────────────────────────────────────────
if (Test-Path $dist) {
  $out = Join-Path $dist "licenses"
  New-Item -ItemType Directory -Force $out | Out-Null
  Copy-Item (Join-Path $cache "*") $out -Force
  Copy-Item (Join-Path $PSScriptRoot "NOTICE.md") (Join-Path $dist "NOTICE.md") -Force
  Write-Host "라이선스 $($required.Count)종 동봉 완료 — dist\VideoStudio\licenses\" -ForegroundColor Green
} else {
  Write-Host "캐시만 갱신 (dist 없음) — packaging\licenses\" -ForegroundColor Yellow
}
