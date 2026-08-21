"""engine_io — Node CLI 호출 계약 (04_api.md "engine 호출 계약").

엔진은 무수정 원칙 — Python 쪽이 엔진의 현재 출력 형식에 맞춘다.
subprocess 규약: cwd = 엔진 루트 · 타임아웃(빌드 60분·기타 60초) · 취소 = SIGTERM→SIGKILL ·
stdout 은 라인 단위 스트리밍으로 SSE 에 릴레이.

stdout 파서는 이 모듈에 격리한다 — 엔진 형식이 바뀌면 여기만 고친다.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from . import ENGINE_DIR

BUILD_TIMEOUT = 60 * 60  # 빌드 60분
QUICK_TIMEOUT = 60       # 기타 60초

# build.js stdout 계약: `[N] 제목` = phase 전환 · `  · <id> <len>s …` = step
_PHASE_RE = re.compile(r"^\[(\d+)\]\s+(.*)$")
_STEP_RE = re.compile(r"^\s+·\s+(?:모션\s+)?(\S+)\s+([\d.]+)s")


@dataclass
class BuildEvent:
    kind: str          # "phase" | "step" | "log"
    line: str
    phase: int | None = None
    title: str | None = None
    step_id: str | None = None
    seconds: float | None = None


def parse_build_line(line: str) -> BuildEvent:
    """빌드 stdout 한 줄 → 이벤트. 형식이 안 맞으면 그냥 log 로 흘린다."""
    if m := _PHASE_RE.match(line):
        return BuildEvent("phase", line, phase=int(m.group(1)), title=m.group(2).strip())
    if m := _STEP_RE.match(line):
        return BuildEvent("step", line, step_id=m.group(1), seconds=float(m.group(2)))
    return BuildEvent("log", line)


def _node(args: list[str], timeout: int = QUICK_TIMEOUT) -> str:
    proc = subprocess.run(
        ["node", *args], cwd=ENGINE_DIR, capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"node {' '.join(args)} → exit {proc.returncode}\n{proc.stderr[-3000:]}")
    return proc.stdout


def inspect(project_dir: Path) -> dict:
    """inspect.js — {preflight, templates, media, audioCache} JSON 한 방."""
    return json.loads(_node(["inspect.js", "--project", str(project_dir), "--json"]))


def build_stream(scenes_file: Path, *, only: str | None = None,
                 variant: str | None = None,
                 on_proc=None) -> Iterator[BuildEvent]:
    """build.js 를 라인 스트리밍으로 실행한다. 잡 큐(jobs.py)가 이 제너레이터를 소비한다.

    on_proc: Popen 을 넘겨받는 콜백 — 잡 큐가 취소(SIGTERM→SIGKILL)에 쓴다.
    (엔진 .lock 은 SIGTERM 을 받으면 스스로 정리한다 — util.js lockVideoDir.)
    """
    args = ["node", "build.js", "--scenes", str(scenes_file)]
    if only:
        args += ["--only", only]
    if variant:
        args += ["--variant", variant]
    with subprocess.Popen(
        args, cwd=ENGINE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    ) as proc:
        if on_proc is not None:
            on_proc(proc)
        assert proc.stdout is not None
        for line in proc.stdout:
            yield parse_build_line(line.rstrip("\n"))
        if proc.wait() != 0:
            raise RuntimeError(f"build.js exit {proc.returncode}")


def list_templates(project_dir: Path | None = None) -> dict:
    """inspect.js --list-templates — 갤러리용 전체 템플릿 + 받는 params (04_api)."""
    args = ["inspect.js", "--list-templates"]
    if project_dir is not None:
        args += ["--project", str(project_dir)]
    return json.loads(_node(args))["templates"]


def preview(file: str, project_dir: Path | None = None) -> str:
    """preview.js — css/js 인라인 자체완결 html. params 는 서빙 URL 질의가 담당한다."""
    args = ["preview.js", "--file", file]
    if project_dir is not None:
        args += ["--project", str(project_dir)]
    return _node(args)


def tts_sample(text: str, *, lang: str = "ko", gender: str = "female",
               voice: str | None = None) -> Path:
    """check-tts.js 로 한 문장을 실제 합성해 mp3 경로를 돌려준다 (미리듣기 — edge 무료).

    04_api 계약의 "TTS 샘플" 행. --keep 출력의 ffplay 안내 라인에서 파일 경로를 뽑는다.
    """
    args = ["check-tts.js", "--provider", "edge", "--text", text,
            "--lang", lang, "--gender", gender, "--keep"]
    if voice:
        args += ["--voice", voice]
    out = _node(args, timeout=QUICK_TIMEOUT)
    m = re.search(r'ffplay -autoexit -nodisp "([^"]+)"', out)
    if not m:
        raise RuntimeError(f"샘플 파일 경로를 찾지 못했다:\n{out[-500:]}")
    return Path(m.group(1))


def chapters(project_id: str, projects_root: Path) -> str:
    """chapters.js — stdout `MM:SS 제목` 라인들.

    CLI 는 <root>/projects/<id> 와 <root>/out/<id> 가 한 루트에 있다고 가정한다(구 배치).
    이 저장소는 projects 루트와 engine/out 이 갈라져 있으므로, 엔진을 고치는 대신
    심링크 임시 루트를 만들어 넘긴다 (엔진 무수정 원칙).
    """
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "projects").symlink_to(Path(projects_root).resolve())
        (root / "out").symlink_to(ENGINE_DIR / "out")
        return _node(["chapters.js", "--project", project_id, "--video-root", str(root)])
