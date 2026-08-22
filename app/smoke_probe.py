"""동결본 자가검사 — `VS_SMOKE_OUT` 이 있을 때만 도는 경로 (5-7).

동결본은 개발 트리 밖에서 혼자 떠야 하므로, 판정을 **앱 안에서** 하고 결과를 JSON 으로
남긴다 (packaging/smoke-frozen.py 가 그 파일을 읽는다). 검사 항목은 동결이 깨지는 순서:

  1. 앱 기동 — Qt 플랫폼 플러그인 로드 (conda 동결이 죽던 지점)
  2. core → 엔진 경로 — 강좌 목록·템플릿 갤러리가 설치 배치에서 읽히는가
  3. **프리뷰 로드** — QtWebEngineProcess·pak·icudtl + bootstrap 플래그가 동결본에 살아 있는가
  4. 프리뷰 픽셀 — offscreen grab 으로 고유색 수 (08 §6: 로드 실패면 1색)
"""

from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path

from core import env


def run_probe(app, win) -> int:
    out: dict = {"app_started": True, "frozen": env.FROZEN,
                 "install": str(env.INSTALL_DIR), "data": str(env.DATA_DIR),
                 "out_root": str(env.out_root())}
    target = Path(os.environ["VS_SMOKE_OUT"])

    def pump(sec: float, until=None) -> bool:
        deadline = time.time() + sec
        while time.time() < deadline:
            app.processEvents()
            if until and until():
                return True
            time.sleep(0.02)
        return bool(until()) if until else True

    try:
        win.show()
        studio = win.make_studio()

        # 목소리 카탈로그 — core.voices 가 동결본에 들어왔는가 + 샘플 캐시가 쓰기 가능한가.
        # (지연 임포트가 많은 모듈이라 "개발 트리에서 되니 되겠지"로 넘기면 안 된다)
        cat = studio.voice_catalog("edge")
        out["voices_edge"] = len(cat["voices"])
        from core import voices as _voices

        probe = _voices.sample_path("_smoke", "probe")
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_bytes(b"ok")
        out["voice_cache_writable"] = probe.is_file()
        out["voice_cache_dir"] = str(probe.parent)
        probe.unlink()

        courses = studio.list_courses()
        out["courses"] = len(courses)
        out["courseIds"] = [c["id"] for c in courses][:5]

        eid = next((e for c in courses if not c.get("single")
                    for e in studio.get_course(c["id"])["episodes"]
                    if studio.get_course(c["id"])["episodes"][e]["state"] != "empty"), None)
        out["episode"] = eid
        if eid:
            win.show_episode(eid)
            clip = win.episode_page.clip_tab
            out["clips"] = pump(60, lambda: clip.clip_list.count() > 0) and clip.clip_list.count()
            # 템플릿 갤러리 = 엔진 subprocess(node) 가 설치 배치에서 도는지
            out["templates"] = pump(120, lambda: bool(clip._gallery)) and len(clip._gallery)
            # 프리뷰 = WebEngine 자산 + bootstrap 플래그
            ids = [c.get("id") for c in clip.clips]
            if "hook" in ids:
                clip.clip_list.setCurrentRow(ids.index("hook"))
            out["previewClip"] = (clip.cur or {}).get("file")
            # 프리뷰 로드는 비동기(node 호출 2회) — **URL 이 채워질 때까지** 기다린다.
            # 초기 빈 페이지에도 JS 는 돌기 때문에, JS 응답만 보고 판정하면 조기 통과한다.
            out["preview_url_ready"] = pump(180, lambda: bool(clip.preview.url().toString()))
            state: dict = {}

            def probe_page():
                clip.preview.page().runJavaScript(
                    "JSON.stringify({a: document.getAnimations({subtree:true}).length,"
                    " t: document.body.innerText.slice(0,30)})",
                    0, lambda r: state.update(json.loads(r)) if r else None)

            # 애니메이션이 잡힐 때까지 — 로드 직후엔 아직 0 일 수 있다
            pump(60, lambda: (probe_page(), state.get("a"))[1] if not state.get("a") else True)
            out["preview_loaded"] = state.get("a") is not None
            out["preview_anims"] = state.get("a")
            out["preview_url"] = clip.preview.url().toString()[:200]
            out["preview_text"] = state.get("t", "")
            # 픽셀 검사는 **시킹 후**에 — t=0 은 요소가 페이드인 전이라 단색이 정상이다
            clip.scrub.setValue(35)   # 3.5s
            pump(3)
            shot = clip.preview.grab().toImage()
            colors = {shot.pixel(x, y)
                      for x in range(0, max(1, shot.width()), 12)
                      for y in range(0, max(1, shot.height()), 12)}
            out["preview_colors"] = len(colors)  # 1 이면 로드 실패 (08 §6)
    except Exception as err:  # noqa: BLE001 — 실패 사유가 결과다
        out["error"] = f"{type(err).__name__}: {err}"
        out["traceback"] = traceback.format_exc().splitlines()[-6:]

    target.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                      encoding="utf-8", newline="\n")
    return 0
