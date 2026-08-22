"""env — 설치/데이터 폴더·자식 프로세스 실행환경 (07_desktop "경로·실행환경 계층").

설치형의 핵심 분리: 설치 폴더(읽기 전용 — 코드·엔진·런타임)와 데이터 폴더(쓰기 —
projects·out·캐시)를 가른다. 개발 모드(저장소 안 실행)에서는 기존 배치를 그대로 유지해
테스트·픽스처가 변하지 않게 한다.

판별: PyInstaller 동결(sys.frozen) 또는 `VIDEO_STUDIO_INSTALL` 환경변수 → 설치 모드.
이 모듈은 core 의 다른 모듈을 임포트하지 않는다 (모두가 이 모듈을 임포트하는 최하층).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# ── 모드 판별 ────────────────────────────────────────────────────────────────
FROZEN = bool(getattr(sys, "frozen", False)) or bool(os.environ.get("VIDEO_STUDIO_INSTALL"))

# 저장소 루트(개발) / 설치 폴더(동결 — exe 옆) — 5-0 실측: 설치 루트의 package.json 이
# 엔진 findRoot/envFiles 상향 탐색의 경계표가 된다 (패키징이 빈 package.json 을 놓는다).
if getattr(sys, "frozen", False):
    INSTALL_DIR = Path(sys.executable).resolve().parent
elif os.environ.get("VIDEO_STUDIO_INSTALL"):
    INSTALL_DIR = Path(os.environ["VIDEO_STUDIO_INSTALL"]).resolve()
else:
    INSTALL_DIR = Path(__file__).resolve().parent.parent  # = REPO_ROOT

REPO_ROOT = INSTALL_DIR  # 기존 core 코드와의 호환 이름 (개발 모드 의미 그대로)
ENGINE_DIR = INSTALL_DIR / "engine"
RUNTIME_DIR = INSTALL_DIR / "runtime"          # 동봉 node·ffmpeg·tts·chromium (없으면 시스템)

# ── 데이터 폴더 (쓰기) ────────────────────────────────────────────────────────
def _default_data_dir() -> Path:
    if not FROZEN:
        return INSTALL_DIR  # 개발: 저장소가 곧 데이터 (projects/·engine/out — 현행 유지)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "VideoStudio"


def _pointer_target(base: Path) -> Path | None:
    """`<기본 폴더>/.data-dir` 포인터 — 첫 실행 위저드의 [변경…]이 적는 리다이렉트.

    환경변수(VIDEO_STUDIO_DATA)가 항상 우선이고, 포인터가 깨져 있으면 기본값으로 후퇴한다.
    """
    try:
        ptr = base / ".data-dir"
        if ptr.exists():
            text = ptr.read_text(encoding="utf-8").strip()
            if text:
                return Path(text).resolve()
    except OSError:
        pass
    return None


def _resolve_data_dir() -> Path:
    override = os.environ.get("VIDEO_STUDIO_DATA")
    if override:
        return Path(override).resolve()
    base = _default_data_dir()
    return _pointer_target(base) or base.resolve()


DATA_DIR = _resolve_data_dir()


def projects_root() -> Path:
    """프로젝트 루트 — `VIDEO_STUDIO_PROJECTS` 오버라이드(기존 규약) 유지."""
    override = os.environ.get("VIDEO_STUDIO_PROJECTS")
    if override:
        return Path(override).resolve()
    return (DATA_DIR / "projects") if FROZEN else (INSTALL_DIR / "projects")


def out_root() -> Path:
    """빌드 산출물 루트 — 개발은 현행(engine/out), 설치는 데이터 폴더 (engine `--out`)."""
    return (DATA_DIR / "out") if FROZEN else (ENGINE_DIR / "out")


def cache_dir() -> Path:
    d = (DATA_DIR / ".cache") if FROZEN else (INSTALL_DIR / ".cache")
    d.mkdir(parents=True, exist_ok=True)
    return d


# 파일 로깅은 아직 없다 — 넣게 되면 여기 log_dir() 를 되살려 cache_dir 옆에 둔다
# (구 log_dir 은 부르는 곳이 한 곳도 없어 2026-08-22 제거).


# ── 자식 프로세스 실행환경 ────────────────────────────────────────────────────
# 5-0 실측: 엔진은 'ffmpeg'·'edge-tts' 를 맨이름으로 찾으므로 PATH 선두 주입만으로 동작하고,
# Playwright 브라우저는 PLAYWRIGHT_BROWSERS_PATH 로 지정된다.
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def node_exe() -> str:
    bundled = RUNTIME_DIR / "node" / ("node.exe" if os.name == "nt" else "node")
    return str(bundled) if bundled.exists() else "node"


def child_env() -> dict[str, str]:
    """엔진 subprocess 용 환경 — 번들 런타임이 있으면 PATH 선두에 얹는다."""
    env = dict(os.environ)
    prepend: list[str] = []
    for name in ("node", "ffmpeg", "tts"):
        d = RUNTIME_DIR / name
        if d.is_dir():
            prepend.append(str(d))
    if prepend:
        env["PATH"] = os.pathsep.join([*prepend, env.get("PATH", "")])
    chromium = RUNTIME_DIR / "chromium"
    if chromium.is_dir():
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(chromium)
    return env


def child_kwargs() -> dict:
    """자식 프로세스 호출 규약 한 벌 — `subprocess.run/Popen(**env.child_kwargs())`.

    셋 다 빠지면 설치본에서만 깨지고 개발 PC 에서는 멀쩡해 보인다 (07 결함 2·3):

    - `encoding="utf-8"` — 없으면 파이썬이 로케일(한국어 Windows = cp949)로 디코드해
      한글 출력에서 UnicodeDecodeError. **conda penv3.13-video 는 UTF-8 모드(PEP 540)가
      켜져 있어 이 결함을 가려 준다** — 동결본의 python.org 런타임은 꺼져 있어 그대로 터진다
      (2026-08-22 실측: 같은 테스트가 conda 통과·venv 실패).
    - `creationflags=CREATE_NO_WINDOW` — GUI 앱에서 호출마다 콘솔 창이 깜빡인다.
    - `env=child_env()` — 설치본의 node·ffmpeg 는 `runtime\\` 에만 있다. 이걸 빠뜨리면
      맨이름 호출이 PATH 에서 안 잡혀 담당자 PC 에서만 실패한다.
    """
    return {"encoding": "utf-8", "errors": "replace",
            "creationflags": CREATE_NO_WINDOW, "env": child_env()}
