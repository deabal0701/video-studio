"""동결본 스모크 — dist\\VideoStudio 가 **혼자서** 뜨는지 실측한다 (5-7).

개발 트리·conda 와 섞이지 않았음을 보이는 것이 목적이라, 동결본을 임시 폴더로 복사한 뒤
PATH 를 System32 만 남기고 실행한다. 화면은 offscreen 으로 띄우고 아래를 판정한다:

  1. 앱이 뜬다 (플랫폼 플러그인 로드 — conda 동결이 깨지던 지점)
  2. 대시보드가 강좌를 읽는다 (core·엔진 경로가 설치 배치에서 맞다)
  3. **프리뷰가 로드된다** (QtWebEngineProcess·pak·icudtl + bootstrap 플래그 — 08 §9)
  3b. **AI 규약(.claude/skills)이 동봉돼 절이 뽑힌다** (D18)
  4. 프리뷰 픽셀이 잡힌다 (offscreen grab — 08 §6)

사용:  conda run -n penv3.13-video python packaging\smoke-frozen.py   (판정 로직만 호스트에서)
실제 판정은 동결본 안의 파이썬이 아니라 **동결 exe 를 실행**해 결과 파일로 받는다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist" / "VideoStudio"

# 설치 폴더에 쓰기가 허용되는 유일한 예외 (07 "설치 폴더 쓰기 예외" — 의도된 결정).
# 스톡 소재는 재배포 금지라 사용자가 직접 받고, 엔진 경로 규약상 engine/assets 아래여야 한다.
# 그 밖의 새 파일·변경 파일은 **전부 실패**로 본다 (5-1 env.py 수정의 종단 수용 기준).
WRITE_ALLOWED = ("engine/assets/",)


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """(상대경로 → (size, mtime_ns)) — 실행 전후 대조용."""
    out: dict[str, tuple[int, int]] = {}
    for p in root.rglob("*"):
        if p.is_file():
            st = p.stat()
            out[p.relative_to(root).as_posix()] = (st.st_size, st.st_mtime_ns)
    return out


def _diff_writes(before: dict, after: dict) -> list[str]:
    changed = [k for k in after if k not in before or after[k] != before[k]]
    changed += [k for k in before if k not in after]        # 삭제도 쓰기다
    return sorted(k for k in changed
                  if not any(k.startswith(a) for a in WRITE_ALLOWED))

# 동결본 안에서 실행될 검사 — VS_SMOKE 로 켜고 결과를 JSON 파일에 쓴다 (app/main.py 가 분기)
PROBE_ENV = "VS_SMOKE_OUT"


def main() -> int:
    if not (DIST / "VideoStudio.exe").exists():
        print("동결본이 없다 — pyinstaller 를 먼저 돌리세요", file=sys.stderr)
        return 2

    work = Path(tempfile.mkdtemp(prefix="vs-frozen-"))
    app_dir = work / "app"
    print(f"동결본 복사 → {app_dir}")
    shutil.copytree(DIST, app_dir)

    data = work / "data"
    (data / "projects").mkdir(parents=True)
    shutil.copytree(REPO / "fixtures" / "projects", data / "projects", dirs_exist_ok=True)
    out_file = work / "smoke.json"

    env = {
        "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
        "TEMP": str(work), "TMP": str(work),
        "USERPROFILE": os.environ.get("USERPROFILE", str(Path.home())),
        "LOCALAPPDATA": str(work / "localappdata"),
        # 개발 트리·conda 와 섞이지 않게 PATH 를 최소로 — 런타임은 앱이 스스로 주입한다
        "PATH": os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"),
        "QT_QPA_PLATFORM": "offscreen",
        "VIDEO_STUDIO_INSTALL": str(app_dir),
        "VIDEO_STUDIO_DATA": str(data),
        "VIDEO_STUDIO_PROJECTS": str(data / "projects"),
        PROBE_ENV: str(out_file),
    }
    print("설치 폴더 스냅샷…")
    before = _snapshot(app_dir)
    print("실행 (PATH=System32 만)…")
    proc = subprocess.run([str(app_dir / "VideoStudio.exe")], env=env, cwd=str(work),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=600)
    # 설치 폴더는 읽기 전용이어야 한다 — 캐시·산출물·프리뷰 임시문서가 새면 여기서 잡힌다
    writes = _diff_writes(before, _snapshot(app_dir))
    result = {"exitCode": proc.returncode,
              "installWrites": writes[:20],
              "installWriteCount": len(writes),
              "stderrTail": (proc.stderr or "").strip().splitlines()[-8:]}
    if out_file.exists():
        result.update(json.loads(out_file.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=1))
    # preview_colors 1 = 단색 = 로드 실패 (08 §6 지표). JS 응답만으로는 조기 통과한다
    ok = (result.get("app_started") and result.get("courses", 0) > 0
          and result.get("templates", 0) > 0
          and result.get("preview_loaded") and result.get("preview_anims", 0) > 0
          and result.get("preview_colors", 0) > 1 and not writes
          and result.get("voices_edge", 0) > 0
          and result.get("voice_cache_writable")
          and result.get("skills_ok"))
    if writes:
        print(f"실패: 설치 폴더에 쓰기 {len(writes)}건 — 데이터 폴더로 가야 한다")
    if result.get("preview_colors", 0) <= 1:
        print("실패: 프리뷰가 단색 — WebEngine 자산 또는 bootstrap 플래그 확인")
    if not result.get("skills_ok"):
        print(f"실패: AI 규약 발췌 불가 — {result.get('skills_detail', '.claude/skills 미동봉')}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
