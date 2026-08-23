"""paths — 상대경로 계산기 (이 앱의 존재 이유 — 02_data-model ★ 경로 규칙).

한 대본 안에 상대경로 기준이 5종 공존하고, 전부 틀려도 오류 없이 조용히 망가진다.
사람은 경로 문자열을 만지지 않는다: UI 는 자산 참조로만 다루고, 저장 시점에 이 모듈이
기준별 상대경로를 계산해 기입하며, 읽을 때는 역산해 자산 참조로 복원한다.

기준 (현행 엔진 실측 — 02_data-model 표. 그 5행이 tests/test_paths.py 케이스다):

  render.bgm      → 엔진 루트(engine/)          # compose.js: path.resolve(AD_DIR, bgm)
  clip.video      → 엔진 루트(engine/)          # media.js:   path.resolve(AD_DIR, file)
  clip.file       → 대본 폴더(projects/<id>/) → 없으면 공용 engine/motion/ 폴백
  params.src      → 그 html 파일 위치
  params.fontUrl  → 그 html 파일 위치 (같은 값이 클립마다 다르다)
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from . import ENGINE_DIR

COMMON_MOTION_DIR = ENGINE_DIR / "motion"
BUNDLED_FONT = ENGINE_DIR / "fonts" / "PretendardVariable.woff2"
# 화면이 글꼴을 **이름으로** 말할 수 있게 (69회차 P2·P16 — 브랜드 킷이 "프로젝트 기본
# 글꼴"이라고만 해서 무슨 글꼴인지 끝내 알 수 없었다). 파일명에서 추측하지 않는다
BUNDLED_FONT_NAME = "Pretendard"


class RefKind(str, Enum):
    """상대경로 기준의 종류 — scenes.json 의 어느 필드에 들어가는 값인가."""

    BGM = "bgm"            # render.bgm
    BROLL = "broll"        # clip.video
    MOTION = "motion"      # clip.file
    HTML_ASSET = "html"    # params.src · params.fontUrl (기준 = html 파일 위치)


def relpath(target: Path, base_dir: Path) -> str:
    """base_dir 기준 POSIX 상대경로. 모든 계산의 공통 말단.

    드라이브가 다르면(Windows — 예: 설치 D:·데이터 C:) 상대화가 불가능하므로 절대경로를
    기입한다 — 엔진의 path.resolve 는 절대경로를 그대로 쓰고, invert 의 pathlib 결합도
    절대 성분이 이긴다 (5-1 실측: 구 저장소가 C: 라 잠복했던 결함).
    """
    target = Path(target).resolve()
    try:
        return Path(os.path.relpath(target, Path(base_dir).resolve())).as_posix()
    except ValueError:  # 다른 드라이브 — 상대경로가 존재하지 않는다
        return target.as_posix()


def compute(kind: RefKind, target: Path, *, scenes_dir: Path | None = None,
            html_file: Path | None = None) -> str:
    """자산의 절대 위치 → scenes.json 에 기입할 상대경로 문자열.

    kind 별 필요 문맥: MOTION 은 scenes_dir, HTML_ASSET 은 html_file.
    MOTION 이 공용 폴더(engine/motion/) 안이면 엔진의 폴백 규칙에 맞춰 맨이름으로 쓴다.
    """
    target = Path(target).resolve()
    if kind in (RefKind.BGM, RefKind.BROLL):
        return relpath(target, ENGINE_DIR)
    if kind is RefKind.MOTION:
        if scenes_dir is None:
            raise ValueError("MOTION 은 scenes_dir 가 필요하다")
        if target.is_relative_to(COMMON_MOTION_DIR):
            return relpath(target, COMMON_MOTION_DIR)  # 공용 폴백 — "chapter.html"
        return relpath(target, scenes_dir)
    if kind is RefKind.HTML_ASSET:
        if html_file is None:
            raise ValueError("HTML_ASSET 은 html_file 이 필요하다")
        return relpath(target, Path(html_file).parent)
    raise ValueError(f"모르는 기준: {kind}")


def invert(kind: RefKind, ref: str, *, scenes_dir: Path | None = None,
           html_file: Path | None = None) -> Path:
    """기입된 상대경로 문자열 → 자산의 절대 위치 (엔진이 실제로 여는 파일).

    compute 의 역산 — 라운드트립(compute∘invert = 항등)을 테스트가 고정한다.
    MOTION 은 엔진 resolveMotionFile 과 같은 순서: 대본 폴더 먼저, 공용 motion/ 폴백.
    """
    if kind in (RefKind.BGM, RefKind.BROLL):
        return (ENGINE_DIR / ref).resolve()
    if kind is RefKind.MOTION:
        if scenes_dir is None:
            raise ValueError("MOTION 은 scenes_dir 가 필요하다")
        local = (Path(scenes_dir) / ref).resolve()
        if local.exists():
            return local
        return (COMMON_MOTION_DIR / ref).resolve()
    if kind is RefKind.HTML_ASSET:
        if html_file is None:
            raise ValueError("HTML_ASSET 은 html_file 이 필요하다")
        return (Path(html_file).parent / ref).resolve()
    raise ValueError(f"모르는 기준: {kind}")


def bundled_font_ref(html_file: Path) -> str:
    """동봉 폰트(engine/fonts/Pretendard…)의 fontUrl 값 — html 위치마다 다르다 (02 규칙 4)."""
    return compute(RefKind.HTML_ASSET, BUNDLED_FONT, html_file=Path(html_file))
