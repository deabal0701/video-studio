"""status — 파생 상태 계산 (02_data-model "파생 상태 — 계산으로만 얻는다, 저장 금지").

⬜ = scenes.json 없음 · 🔄 = 있으나 final 없음/평가 전 · ✅ = final mp4 존재(+평가 기록)
빌드 신선도: final mtime < scenes.json mtime → "대본이 더 새것 — 재빌드 필요"
평가 점수 연동(제작 기록 md frontmatter)은 3단계에서 붙인다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import env

OUT_ROOT = env.out_root()  # 개발 = engine/out (현행), 설치 = 데이터 폴더 (07_desktop)


def episode_status(episode_dir: Path, out_root: Path = OUT_ROOT) -> dict[str, Any]:
    scenes = episode_dir / "scenes.json"
    if not scenes.exists():
        return {"state": "empty", "final": [], "stale": False}
    final_dir = out_root / episode_dir.name / "final"
    finals = sorted(f.name for f in final_dir.glob("*.mp4")) if final_dir.exists() else []
    stale = False
    if finals:
        newest_final = max((final_dir / f).stat().st_mtime for f in finals)
        stale = newest_final < scenes.stat().st_mtime
    return {"state": "done" if finals else "wip", "final": finals, "stale": stale}
