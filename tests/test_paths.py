"""★ 경로 계산기 최우선 단위 테스트 — 02_data-model 표의 실측 5행이 그대로 케이스다.

이 값들은 hr-basics-01 재현 빌드(0단계)로 검증된 실측이다. 계산기가 이와 다른 값을
기입하면 오류 없이 검은 화면·무음·폰트 폴백으로 조용히 망가진다.
"""

from pathlib import Path

import pytest

from core import ENGINE_DIR, FIXTURES_DIR
from core.paths import RefKind, BUNDLED_FONT, bundled_font_ref, compute, invert

EP = FIXTURES_DIR / "hr-basics-01"          # 대본 폴더
COURSE = FIXTURES_DIR / "hr-basics"          # 강좌 폴더
COURSE_HTML = COURSE / "course-intro.html"   # 강좌 공통 html
EP_HTML = EP / "motion" / "hook-bill.html"   # 회차 전용 html
COMMON_HTML = ENGINE_DIR / "motion" / "chapter.html"  # 공용 html


# ── 실측 5행 ──────────────────────────────────────────────────────────────────

def test_row1_bgm_engine_root():
    got = compute(RefKind.BGM, ENGINE_DIR / "assets/bgm/mixkit-623-loop.mp3")
    assert got == "assets/bgm/mixkit-623-loop.mp3"


def test_row2_broll_engine_root():
    got = compute(RefKind.BROLL, ENGINE_DIR / "assets/broll/office-talk.mp4")
    assert got == "assets/broll/office-talk.mp4"


def test_row3_motion_scenes_dir_and_course_and_common():
    assert compute(RefKind.MOTION, EP_HTML, scenes_dir=EP) == "motion/hook-bill.html"
    assert compute(RefKind.MOTION, COURSE_HTML, scenes_dir=EP) == "../hr-basics/course-intro.html"
    # 공용 폴더 소속이면 엔진 폴백 규칙에 맞춰 맨이름
    assert compute(RefKind.MOTION, COMMON_HTML, scenes_dir=EP) == "chapter.html"


def test_row4_params_src_html_location():
    got = compute(RefKind.HTML_ASSET, EP / "bg" / "office-talk.jpg", html_file=COURSE_HTML)
    assert got == "../hr-basics-01/bg/office-talk.jpg"


def test_row5_fonturl_differs_per_html_location():
    assert bundled_font_ref(COURSE_HTML) == "../../../engine/fonts/PretendardVariable.woff2"
    assert bundled_font_ref(EP_HTML) == "../../../../engine/fonts/PretendardVariable.woff2"
    assert bundled_font_ref(COMMON_HTML) == "../fonts/PretendardVariable.woff2"


# ── 역산 라운드트립 (compute ∘ invert = 항등) ─────────────────────────────────

@pytest.mark.parametrize("kind,target,ctx", [
    (RefKind.BGM, ENGINE_DIR / "assets/bgm/mixkit-623-loop.mp3", {}),
    (RefKind.BROLL, ENGINE_DIR / "assets/broll/office-talk.mp4", {}),
    (RefKind.MOTION, EP_HTML, {"scenes_dir": EP}),
    (RefKind.MOTION, COURSE_HTML, {"scenes_dir": EP}),
    (RefKind.MOTION, COMMON_HTML, {"scenes_dir": EP}),
    (RefKind.HTML_ASSET, EP / "bg/office-talk.jpg", {"html_file": COURSE_HTML}),
    (RefKind.HTML_ASSET, BUNDLED_FONT, {"html_file": EP_HTML}),
])
def test_invert_roundtrip(kind, target, ctx):
    ref = compute(kind, target, **ctx)
    assert invert(kind, ref, **ctx) == Path(target).resolve()


def test_fixture_scenes_all_refs_resolve():
    """픽스처 대본의 경로 필드 전부가 실존 파일로 역산된다 — 표가 곧 현실임을 고정."""
    import json

    scenes = json.loads((EP / "scenes.json").read_text(encoding="utf-8"))
    render = scenes["render"]
    assert invert(RefKind.BGM, render["bgm"]).exists()
    for clip in render["motion"]["clips"]:
        if clip.get("video"):
            assert invert(RefKind.BROLL, clip["video"]).exists(), clip["id"]
        if clip.get("file"):
            html = invert(RefKind.MOTION, clip["file"], scenes_dir=EP)
            assert html.exists(), clip["id"]
            for key in ("src", "fontUrl"):
                if clip.get("params", {}).get(key):
                    assert invert(RefKind.HTML_ASSET, clip["params"][key],
                                  html_file=html).exists(), f"{clip['id']}.{key}"
