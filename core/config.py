"""config — 키·설정 파일 쓰기 + 자가진단 (07_desktop 설정 화면·첫 실행 위저드).

키 정본은 **`~/.claude/develop-video.env`** — 엔진(util.js envFiles)과 core.agents 가
이미 같은 파일을 읽는 공용 규약이라, 화면은 그 파일의 편집기 노릇만 한다 (엔진 무수정).
저장소 `.env` 가 있으면 그쪽이 우선이므로 화면에 어느 파일이 이겼는지 보여 준다.

자가진단은 "무엇이 없는지 담당자가 읽고 조치할 수 있게" — 실패해도 앱은 동작한다.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import env

HOME_ENV = Path.home() / ".claude" / "develop-video.env"
REPO_ENV = env.INSTALL_DIR / ".env"

# 화면이 다루는 키 (설명은 툴팁·라벨로)
KEYS = [
    ("AZURE_SPEECH_KEY", "Azure Speech 키 — 납품본 TTS (없으면 edge 무료 폴백)"),
    ("AZURE_SPEECH_REGION", "Azure 지역 (예: koreacentral)"),
    ("ELEVENLABS_API_KEY", "ElevenLabs 키 — 유료·글자수 과금"),
    ("ANTHROPIC_API_KEY", "Claude 키 — AI 초안·평가 (종량제)"),
    ("OPENAI_API_KEY", "OpenAI 키 — AI 초안·평가 (선택 제공자)"),
]
SECRET_KEYS = {"AZURE_SPEECH_KEY", "ELEVENLABS_API_KEY", "ANTHROPIC_API_KEY",
               "OPENAI_API_KEY"}
# 키가 아닌 설정 — 같은 파일에 함께 둔다 (D15)
SETTINGS = ["AGENT_PROVIDER", "AGENT_TEST_MODE", "OPENAI_MODEL"]


def _parse(file: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not file.exists():
        return out
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def read_all() -> dict[str, Any]:
    """현재 값 + 어느 파일에서 왔는지 (셸 > 저장소 .env > 홈 공용 — 엔진과 같은 순서)."""
    home, repo = _parse(HOME_ENV), _parse(REPO_ENV)
    values, sources = {}, {}
    for name in [k for k, _ in KEYS] + SETTINGS:
        if os.environ.get(name):
            values[name], sources[name] = os.environ[name], "셸 환경변수"
        elif repo.get(name):
            values[name], sources[name] = repo[name], f"{REPO_ENV.name} (저장소)"
        elif home.get(name):
            values[name], sources[name] = home[name], "~/.claude/develop-video.env"
        else:
            values[name], sources[name] = "", ""
    return {"values": values, "sources": sources,
            "homeFile": str(HOME_ENV), "repoFile": str(REPO_ENV),
            "repoOverrides": sorted(set(repo) & set(values))}


def write_home_env(updates: dict[str, str]) -> Path:
    """홈 공용 파일에 값을 병합해 쓴다 — 기존 주석·순서는 보존하고 값만 바꾼다.

    빈 문자열은 "설정 안 함"이라 줄을 지우지 않고 빈 값으로 남긴다 (엔진 규약과 동일).
    """
    HOME_ENV.parent.mkdir(parents=True, exist_ok=True)
    lines = HOME_ENV.read_text(encoding="utf-8").splitlines() if HOME_ENV.exists() else []
    remaining = dict(updates)
    for i, line in enumerate(lines):
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=", line)
        if m and m.group(1) in remaining:
            lines[i] = f"{m.group(1)}={remaining.pop(m.group(1))}"
    if remaining:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# ── 앱 설정 화면이 기록 ──")
        lines += [f"{k}={v}" for k, v in remaining.items()]
    HOME_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return HOME_ENV


# ── 자가진단 ────────────────────────────────────────────────────────────────
def _run(args: list[str], timeout: int = 20) -> tuple[bool, str]:
    try:
        # cwd=엔진 루트 — check-tts.js 등 엔진 CLI 의 호출 규약 (04 subprocess 규약)
        p = subprocess.run(args, capture_output=True, timeout=timeout, cwd=env.ENGINE_DIR,
                           env=env.child_env(), encoding="utf-8", errors="replace",
                           creationflags=env.CREATE_NO_WINDOW)
        return p.returncode == 0, (p.stdout or p.stderr or "").strip().splitlines()[0][:120] \
            if (p.stdout or p.stderr) else ""
    except Exception as err:  # noqa: BLE001 — 진단은 실패 사유가 결과다
        return False, str(err)[:120]


def diagnose() -> list[dict[str, Any]]:
    """설치·실행 전제 점검 — 화면이 표로 보여 준다 (07 첫 실행 위저드 2단계와 공용)."""
    checks: list[dict[str, Any]] = []

    ok, msg = _run([env.node_exe(), "--version"])
    checks.append({"name": "Node", "ok": ok, "detail": msg or "없음",
                   "hint": "Node 20+ 설치 (렌더 엔진이 Node CLI — D4)"})

    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool, path=env.child_env().get("PATH"))
        checks.append({"name": tool, "ok": bool(path), "detail": path or "PATH 에 없음",
                       "hint": "ffmpeg 설치 후 PATH 등록 (설치본은 runtime\\ffmpeg 동봉)"})

    pw = env.ENGINE_DIR / "node_modules" / "playwright"
    checks.append({"name": "Playwright", "ok": pw.exists(),
                   "detail": "engine/node_modules/playwright" if pw.exists() else "미설치",
                   "hint": "engine 에서 npm install && npx playwright install chromium"})

    browsers = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(
        Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ms-playwright")
    has_browser = Path(browsers).exists()
    checks.append({"name": "Chromium", "ok": has_browser, "detail": browsers,
                   "hint": "npx playwright install chromium"})

    checks.append({"name": "데이터 폴더", "ok": True,
                   "detail": f"projects={env.projects_root()} · out={env.out_root()}",
                   "hint": ""})

    values = read_all()["values"]
    for label, name in (("Claude 키", "ANTHROPIC_API_KEY"), ("OpenAI 키", "OPENAI_API_KEY"),
                        ("Azure 키", "AZURE_SPEECH_KEY")):
        checks.append({"name": label, "ok": bool(values.get(name)),
                       "detail": "설정됨" if values.get(name) else "없음 (선택)",
                       "hint": "설정 화면에서 입력 — 없어도 앱은 완결 동작한다"})
    return checks


def check_tts() -> dict[str, Any]:
    """edge TTS 실합성 점검 — 네트워크까지 확인한다 (check-tts.js 재사용)."""
    ok, msg = _run([env.node_exe(), "check-tts.js"], timeout=90)
    return {"ok": ok, "detail": msg}
