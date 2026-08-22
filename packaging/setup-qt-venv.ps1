# PyInstaller 동결용 venv 부트스트랩 (5-7) — python.org 파이썬 + **pip 휠** PySide6.
#
# 개발·실행은 conda penv3.13-insait 하나로 통일됐다(2026-08-21). 이 스크립트는 그 우회가
# 아니라 **동결 전용**으로 남았다: PyInstaller 의 PySide6 훅이 pip 휠 배치만 안다.
#
#   conda-forge 배치 (개발 환경)            pip 휠 배치 (PyInstaller 훅이 찾는 곳)
#   $PREFIX\Library\bin\Qt6*.dll            site-packages\PySide6\Qt6*.dll
#   $PREFIX\Library\lib\qt6\plugins\        site-packages\PySide6\plugins\
#   $PREFIX\Library\lib\qt6\QtWebEngineProcess.exe   site-packages\PySide6\
#   $PREFIX\Library\share\qt6\resources\*.pak·icudtl.dat   site-packages\PySide6\resources\
#
# 2026-08-22 실측: conda 환경의 site-packages\PySide6 안에는 Qt6*.dll 0개·plugins 없음 —
# 훅의 collect_dynamic_libs('PySide6') 가 빈손이 된다. 그래서 동결은 이 venv 에서 한다.
# Qt 버전은 양쪽 동일(6.11.2)이라 동작 차이는 없다. 상세: docs/design/08_qt-style.md §9
#
#   .\packaging\setup-qt-venv.ps1          # 저장소 루트에 .qt-venv 생성 (동결용)
#   .qt-venv\Scripts\python -m app         # 동결 전 동작 확인용 실행 (일상 실행은 .\run.ps1)
param([string]$Python = "py -V:3.13")

$repo = Split-Path $PSScriptRoot -Parent
$venv = Join-Path $repo ".qt-venv"
if (-not (Test-Path $venv)) {
  Invoke-Expression "$Python -m venv `"$venv`""
}
& "$venv\Scripts\python.exe" -m pip install --quiet --upgrade PySide6 pydantic
& "$venv\Scripts\python.exe" -c "import PySide6.QtCore as q, pydantic; print('PySide6', q.qVersion(), '+ pydantic', pydantic.VERSION, 'OK')"
