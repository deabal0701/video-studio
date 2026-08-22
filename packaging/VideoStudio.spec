# PyInstaller spec — Video Studio 설치본 (07_desktop "단일 실행파일 — 패키징").
#
#   conda run -n penv3.13-video pyinstaller packaging\VideoStudio.spec --noconfirm
#
# ★ 동결도 개발과 같은 env(penv3.13-video)에서 한다 — 단 그 env 의 PySide6 가 **pip 휠**
#   이어야 한다. PyInstaller 훅은 pip 휠 배치만 안다 (conda-forge 는 Qt 자산을 site-packages
#   밖 $PREFIX\Library\ 에 두어 훅이 빈손 — 실측 conda-forge 0개 vs pip 휠 144개 DLL).
#   깨끗한 conda env 에선 pip 휠 PySide6 가 정상이라(2026-08-22 실측 — 옛 env 실패는 DLL
#   오염) 개발·동결이 한 env 로 합쳐졌다. 상세 배치 대조표는 docs/design/08_qt-style.md §9.
#
# onedir 인 이유: onefile 은 600MB 를 매 실행 임시 해제라 기동 30초+·백신 오탐 (07 표).
# engine/·runtime/ 는 exe 옆에 **그대로 복사**한다 — Node 가 읽는 파일 배치가 그대로여야
# 하고(엔진 무수정), env.py 가 sys.executable 옆을 INSTALL_DIR 로 본다.

import os
from pathlib import Path

REPO = Path(os.environ.get("VS_REPO", Path(SPECPATH).parent)).resolve()

# 동결본이 읽는 데이터 — engine/runtime 은 Analysis 밖에서 복사한다(수십만 파일 회피).
datas = [
    (str(REPO / "engine" / "templates"), "engine/templates"),
    (str(REPO / "engine" / "motion"), "engine/motion"),
    (str(REPO / "engine" / "fonts"), "engine/fonts"),
]

# Qt 표준 버튼("Cancel"·"Yes") 한국어 번역 — 훅이 챙긴다는 보장이 없어 명시한다 (09 G6).
# 없으면 앱은 그대로 뜨되 그 문구만 영문이 된다 (app/i18n.py 는 최선 노력).
import PySide6 as _ps  # noqa: E402

_qm = Path(_ps.__file__).parent / "translations" / "qtbase_ko.qm"
if _qm.exists():
    datas.append((str(_qm), "PySide6/translations"))

a = Analysis(
    [str(REPO / "app" / "main.py")],
    pathex=[str(REPO)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "core.facade", "core.config", "core.voices", "core.agents.providers",
        "core.agents.openai_runner", "app.pages.settings", "app.pages.first_run",
        "app.smoke_probe",
    ],
    hookspath=[],
    excludes=[
        # 쓰지 않는 Qt 모듈 — 용량 절감 (프리뷰=WebEngine·재생=Multimedia 는 유지)
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtQuick3D", "PySide6.QtBluetooth",
        "PySide6.QtNfc", "PySide6.QtSensors", "PySide6.QtSerialPort",
        "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtTest",
        "tkinter", "matplotlib", "numpy", "pytest",
    ],
    noarchive=False,
)
# ── 안 쓰는 Qt 자산 걷어내기 (5-7 용량) ──────────────────────────────────────
# 위 `excludes=` 는 **파이썬 바인딩(.pyd)만** 막는다 — DLL·qml·리소스는 훅이 그대로
# 수집한다. 1,291MB 설치본 실측(2026-08-22)에서 그 잔여분이 이만큼이었다:
#   qtwebengine_devtools_resources.debug.pak  72.3MB  ← 디버그 산출물. 배포본에 있을 이유 없음
#   qtwebengine_locales (전 언어)             43.7MB  ← 한국어만 쓴다
#   안 쓰는 Qt 모듈 DLL (3D·Quick3D·Charts·
#     Controls2 스타일·Pdf·VirtualKeyboard…)  ~45MB
#   qtbase_*.qm 185개                          ~9MB   ← ko 7개면 259KB
# 이 앱이 실제로 쓰는 것은 QWidgets + QtWebEngineWidgets(프리뷰 D10) + QtMultimedia(재생)뿐.
#
# ★ 판정은 추정이 아니라 **동결 스모크**다 — packaging/smoke-frozen.py 가 프리뷰 로드와
#   픽셀 색 수까지 본다. 여기서 뭘 잘못 빼면 그 스모크가 잡는다.
_DROP_DLL = (
    "Qt63D", "Qt6Quick3D",                    # 3D — 안 쓴다
    "Qt6Charts", "Qt6DataVisualization", "Qt6Graphs",
    "Qt6Pdf", "Qt6Location",
    "Qt6QuickControls2", "Qt6QuickDialogs2",  # UI 는 QWidgets 다 (Controls2 는 QML 용)
    "Qt6QuickTemplates2",                     #   ↑ Controls2 전용 의존
    "Qt6Labs", "Qt6QuickTimeline",
    "Qt6Sensors", "Qt6SerialPort", "Qt6Bluetooth", "Qt6Nfc",
    "Qt6RemoteObjects", "Qt6Scxml", "Qt6StateMachine",
    "Qt6TextToSpeech",                        # TTS 는 엔진(edge/azure)이 한다 — Qt 것이 아니다
    "Qt6VirtualKeyboard", "Qt6WebView",
    "Qt6Test", "Qt6QuickTest",
)
_DROP_QML = ("qml/QtQuick3D", "qml/Qt3D", "qml/QtGraphs", "qml/QtCharts",
             "qml/QtDataVisualization")
# Chromium 로케일 — ko 만 쓰지만 en-US 는 폴백으로 남긴다 (없는 로케일을 요청하면 죽는다)
_KEEP_LOCALE = ("ko.pak", "en-US.pak")


def _keep(dest: str) -> bool:
    d = dest.replace("\\", "/")
    name = d.rsplit("/", 1)[-1]
    if name.startswith(_DROP_DLL):
        return False
    if any(seg in d for seg in _DROP_QML):
        return False
    if "qtwebengine_locales/" in d and name not in _KEEP_LOCALE:
        return False
    if name.startswith("qtwebengine_devtools_resources"):   # 디버그·개발자도구 리소스
        return False
    if d.endswith(".qm") and not name.endswith("_ko.qm"):   # 한국어 외 번역
        return False
    return True


def _prune(entries, label):
    kept = [e for e in entries if _keep(e[0])]
    print(f"[spec] {label}: {len(entries)} -> {len(kept)} ({len(entries) - len(kept)}건 제외)")
    return kept


a.binaries = _prune(a.binaries, "binaries")
a.datas = _prune(a.datas, "datas")

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="VideoStudio",
    console=False,          # GUI — 자식 프로세스 콘솔은 CREATE_NO_WINDOW 가 따로 막는다
    disable_windowed_traceback=False,
    icon=None,              # 5-8 에서 아이콘·서명
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,  # UPX 금지 — Qt/Chromium DLL 압축은 오작동·백신 오탐 유발
    name="VideoStudio",
)
