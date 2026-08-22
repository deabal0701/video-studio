"""scaffold — 회차 스캐폴딩 (03 ② [회차 생성] — 지금 수동으로 하는 것 전부).

폴더 생성 → episode.scenes.json 템플릿 → course 의 voice/render/palette 주입 →
골격 클립(broll·title·hook·stinger·promise·ch1·s1·recap·outro) 생성 → plan.md 카피.
경로는 core.paths 가 이 저장소 기준으로 기입한다 (템플릿의 구 h5-saas 경로를 쓰지 않는다).

생성 직후 규약: scenes.voice ≡ course.voice ∧ scenes.render ⊇ course.render 가
성립해야 한다 (일관성 대조가 0건) — 테스트가 고정한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import ENGINE_DIR, paths
from .schema import dump_json, load_json

LECTURE_TEMPLATES = ENGINE_DIR / "templates" / "lecture"
EPISODE_TEMPLATE = LECTURE_TEMPLATES / "episode.scenes.json"
COURSE_TEMPLATE = LECTURE_TEMPLATES / "course.json"
PLAN_TEMPLATE = ENGINE_DIR / "templates" / "plan.md"

DEFAULT_PALETTE = {"brand": "#3E63DD", "brandSoft": "#93A4F5", "bg": "#070b14"}


def scaffold_course(root: Path, course_id: str, *, title: str, tagline: str = "",
                    audience: str = "", episode_length: str | None = None,
                    voice: dict[str, Any] | None = None,
                    palette: dict[str, Any] | None = None,
                    bgm: str | None = None,
                    episodes: list[dict[str, Any]] | None = None) -> Path:
    """강좌 개설 (04: 폴더 + course.json + intro/stinger 템플릿 카피).

    intro/stinger html 의 공용 `_base.css`·`_params.js` 참조는 목적지 기준으로 재계산한다 —
    템플릿은 엔진 안(templates/lecture/)에 있어 `../../motion/` 이지만, projects/ 위치는
    저장소 배치에 따라 다르다 (0단계 픽스처 이전에서 실측한 함정).
    """
    course_dir = root / course_id
    if (course_dir / "course.json").exists():
        raise FileExistsError(f"이미 있다: {course_id}")

    course = load_json(COURSE_TEMPLATE)
    palette = {**DEFAULT_PALETTE, **(palette or {})}
    course.update({"course": course_id, "title": title})
    if tagline:
        course["tagline"] = tagline
    if audience:
        course["audience"] = audience
    if episode_length:
        course["episodeLength"] = episode_length
    course["episodes"] = episodes or []
    if voice:
        course["voice"] = voice
    course["palette"] = palette  # 회차 클립 params 자동 주입의 원천 (③ 브랜드 킷)
    render = course["render"]
    render.update({"background": palette["bg"], "brand": palette["brand"],
                   "brandText": palette["brandSoft"], "watermark": {"text": title},
                   # bgm 은 엔진 루트 기준 (02 경로 표). 개설 화면에서 귀로 골라 넘긴다.
                   "bgm": bgm or "assets/bgm/mixkit-623-loop.mp3"})

    course_dir.mkdir(parents=True)
    (course_dir / "course.json").write_text(dump_json(course), encoding="utf-8", newline="\n")
    copy_brand_kit(course_dir)
    return course_dir


def copy_brand_kit(course_dir: Path) -> list[str]:
    """프리셋(기본 1종)의 intro/stinger html 을 강좌 폴더로 카피 — ③ 브랜드 킷 갤러리.

    공용 `_base.css`·`_params.js` 참조를 목적지 기준으로 재계산한다 (경로 함정 방지).
    이미 있으면 덮어쓴다 — 호출 화면이 확인을 받는다.
    """
    rel_motion = paths.relpath(ENGINE_DIR / "motion", course_dir)
    copied = []
    for name in ("course-intro.html", "course-stinger.html"):
        text = (LECTURE_TEMPLATES / name).read_text(encoding="utf-8")
        text = text.replace('"../../motion/_', f'"{rel_motion}/_')
        (course_dir / name).write_text(text, encoding="utf-8", newline="\n")
        copied.append(name)
    return copied

# 골격 관례 (02 clip 표): 실제 파일이 정해진 클립만 fontUrl 을 계산해 넣는다.
_PLACEHOLDER = "["  # 템플릿의 대괄호 자리표시 — 저자가 채울 몫


def _inject_params(clip: dict[str, Any], palette: dict[str, Any],
                   ep_dir: Path) -> None:
    """palette(brand·brandSoft·bg)와 동봉 폰트 fontUrl 을 클립 params 에 주입.

    course._색메모 실측 규약: 모션은 render.brand 를 물려받지 않으므로 **모든 클립 params 에
    직접 넣는다.** fontUrl 은 html 위치마다 값이 다르므로(02 규칙) 계산해 기입한다.
    """
    params = clip.setdefault("params", {})
    for key in ("brand", "brandSoft", "bg"):
        if palette.get(key):
            params[key] = palette[key]
    file = clip.get("file", "")
    if file and _PLACEHOLDER not in file:
        html = paths.invert(paths.RefKind.MOTION, file, scenes_dir=ep_dir)
        params["fontUrl"] = paths.bundled_font_ref(html)
    # wipe:off 를 항상 마지막에 (모션 전용 영상의 흰 점멸 방지 — preflight 6번 규칙)
    params["wipe"] = params.get("wipe", "off")


def scaffold_episode(root: Path, course_id: str, n: int,
                     title: str | None = None, subtitle: str | None = None) -> Path:
    """회차 폴더를 만들고 scenes.json·plan.md 골격을 깐다. 반환: 회차 폴더 경로."""
    course_dir = root / course_id
    course = load_json(course_dir / "course.json")
    entry = next((e for e in course.get("episodes", []) if e.get("n") == n), None)
    eid = (entry or {}).get("id") or f"{course_id}-{n:02d}"
    ep_dir = root / eid
    if (ep_dir / "scenes.json").exists():
        raise FileExistsError(f"이미 있다: {eid}")

    scenes = load_json(EPISODE_TEMPLATE)
    ep_title = title or (entry or {}).get("title", "")
    ep_subtitle = subtitle or (entry or {}).get("subtitle", "")

    scenes["_읽어보기"] = (
        f"{course.get('title', course_id)} {n}강 — {ep_title}. 구성표는 plan.md, "
        f"강좌 정체성은 ../{course_id}/course.json. "
        f"실행(engine/ 에서): node build.js --scenes <이 파일 경로>"
    )
    scenes["id"] = eid
    scenes["voice"] = dict(course.get("voice", {}))  # 규약: 통째로 복사

    render = scenes["render"]
    render.pop("_", None)
    # course.render(색·자막·워터마크·BGM)를 그대로 얹는다 → scenes.render ⊇ course.render
    motion = render.pop("motion")
    render.update(course.get("render", {}))
    render["motion"] = motion  # motion 은 항상 마지막 키 (픽스처 실측 순서)

    palette = course.get("palette", {})
    for clip in motion["clips"]:
        cid = clip["id"]
        if cid == "broll":
            clip["video"] = "assets/broll/[회차 주제에 맞는 파일].mp4"  # 엔진 루트 기준
        elif cid == "title":
            clip["file"] = f"../{course_id}/course-intro.html"
            clip["params"].update({
                "src": f"../{eid}/bg/[B롤과 같은 파일명].jpg",
                "kicker": course.get("title", ""),
                "num": f"{n}강",
                "title": ep_title,
                "subtitle": ep_subtitle,
            })
        elif cid == "stinger":
            clip["file"] = f"../{course_id}/course-stinger.html"
            clip["params"].update({
                "brandline": course.get("title", ""),
                "tagline": course.get("tagline", ""),
            })
        elif cid == "outro":
            clip["params"].update({
                "subtitle": f"{course.get('title', '')} · {n}강",
            })
        _inject_params(clip, palette, ep_dir)

    scenes["variants"] = [{"id": f"{eid}-16x9", "width": 1920, "height": 1080}]

    (ep_dir / "motion").mkdir(parents=True)
    (ep_dir / "bg").mkdir()
    (ep_dir / "scenes.json").write_text(dump_json(scenes), encoding="utf-8", newline="\n")
    if PLAN_TEMPLATE.exists():
        (ep_dir / "plan.md").write_text(
            PLAN_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")

    # 커리큘럼에 없던 회차면 course.episodes 에 등록 (② 보드가 곧 정본이 되게)
    if entry is None:
        course.setdefault("episodes", []).append(
            {"n": n, "id": eid, "title": ep_title, "subtitle": ep_subtitle})
        (course_dir / "course.json").write_text(dump_json(course), encoding="utf-8", newline="\n")
    return ep_dir
