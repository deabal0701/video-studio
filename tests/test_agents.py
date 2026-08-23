"""D18 — 순수 HTTP 에이전트: 키 게이트·오케스트레이션·잡 큐 통합·사용량 미터.

LLM 은 llm_call 주입으로 대체한다(키·네트워크 불요) — 스키마를 보고 단계를 구분하는
가짜가 오케스트레이션(2단계 초안·검증 되먹임·도식 연쇄·평가)을 통째로 검증한다.
"""

import json
import time

import pytest

from core import FIXTURES_DIR, scaffold
from core.agents import runner
from core.facade import AgentDisabled, Studio
from core.jobs import JobQueue, JobState
from core.schema import load_json

pytestmark = pytest.mark.usefixtures("fixtures_root")


@pytest.fixture(autouse=True)
def no_key(monkeypatch, tmp_path):
    import os

    monkeypatch.setattr(runner, "USAGE_FILE", tmp_path / "usage.jsonl")
    # 개발 머신의 .env(실키·모델 오버라이드)와 격리 — 테스트는 프로세스 환경변수만 본다
    monkeypatch.setattr(runner, "_env_value", lambda name: os.environ.get(name) or None)
    for k in ("ANTHROPIC_API_KEY", "AGENT_MODEL_DRAFT",
              "AGENT_MODEL_DIAGRAM", "AGENT_MODEL_REVIEW"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def no_chromium(monkeypatch):
    """렌더 확인은 캡처 가능 환경에서만 — 테스트는 '생략' 분기를 탄다 (크로미움 불요)."""
    from core import engine_io

    def _no(*a, **k):
        raise RuntimeError("no chromium in tests")

    monkeypatch.setattr(engine_io, "snapshot", _no)


def _fake_llm(calls: list, *, defect_first: bool = False):
    """스키마로 단계를 구분하는 가짜 — 골격 id 는 요청의 골격 JSON 에서 읽는다."""

    def call(*, system, user, json_schema=None, images=None, task=None):
        calls.append({"task": task, "user": user, "images": images,
                      "schema": json_schema})
        usage = {"inputTokens": 100, "outputTokens": 50}
        props = (json_schema or {}).get("properties", {})
        if "plan_md" in props:
            return {"plan_md": "# 구성표\n\n| 구간 | 화면 |", "facts_md": "| 주장 | 출처 |"}, usage
        if "clips" in props:
            ids = [e["id"] for e in _skeleton_from(user)]
            n_clip_calls = sum(1 for c in calls if c["schema"] and
                               "clips" in c["schema"]["properties"])
            broken = defect_first and n_clip_calls == 1
            return {"clips": [
                {"id": cid,
                 "narration": ("[미정] 내용" if broken and cid == "hook"
                               else f"{cid} 구간의 설명입니다."),
                 "screen": f"{cid} 화면 설명",
                 "params": [{"key": "title", "value": "테스트 제목"},
                            {"key": "num", "value": "1강"}],
                 "broll": ""} for cid in ids]}, usage
        if "ok" in props:
            return {"ok": True, "problem": "", "html": ""}, usage
        if "html" in props:
            return {"html": "<!doctype html><div class=\"diagram\">도식</div>"}, usage
        if "scores" in props:
            return {"scores": {k: 4 for k in
                               ("구성", "설명력", "화면", "분량", "일관성", "완성도")},
                    "fixes": ["고칠 것 하나"], "overall": 4.0}, usage
        return "텍스트", usage

    return call


def _skeleton_from(user: str) -> list[dict]:
    start = user.find("[\n")
    end = user.find("\n]", start)
    return json.loads(user[start:end + 2]) if start != -1 else []


def _lecture_episode(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    scaffold.scaffold_course(root, "demo", title="데모 강좌", tagline="테스트",
                             kind="lecture",
                             episodes=[{"n": 1, "id": "demo-01", "title": "1강"}])
    scaffold.scaffold_episode(root, "demo", 1, title="첫 강")
    return root


# ── 게이트 (수용 기준 절반: 키 없으면 에이전트만 비활성) ─────────────────────
def test_no_key_disables_agent_menu(studio):
    body = studio.agent_status()
    assert body["enabled"] is False and "ANTHROPIC_API_KEY" in body["reason"]
    assert body["models"] == {"draft": "claude-opus-5", "diagram": "claude-sonnet-5",
                              "review": "claude-opus-5"}
    with pytest.raises(AgentDisabled):
        studio.agent_submit("review", "hr-basics-01", {})
    # 키 없이도 조회·검증은 그대로 동작
    assert studio.list_courses()
    assert studio.agent_usage()["count"] == 0


# ── draft — 2단계·기입·도식 연쇄가 실파일로 남는다 ──────────────────────────
def test_draft_writes_plan_scenes_and_diagrams(tmp_path):
    root = _lecture_episode(tmp_path)
    calls: list = []
    work = runner.make_agent_work("draft", "demo-01", {"brief": "테스트 주제"}, root,
                                  llm_call=_fake_llm(calls))
    events = list(work())
    ep = root / "demo-01"
    assert (ep / "plan.md").read_text(encoding="utf-8").startswith("# 구성표")
    assert (ep / "facts.md").exists()
    scenes = load_json(ep / "scenes.json")
    clips = {c["id"]: c for c in scenes["render"]["motion"]["clips"]}
    assert clips["hook"]["narration"].endswith("설명입니다.")
    assert clips["hook"]["_화면메모"] == "hook 화면 설명"
    # 자리표시자 file 클립은 도식이 생성돼 연결된다 (구 에이전틱 경로의 몫)
    assert clips["hook"]["file"] == "motion/hook.html"
    assert (ep / "motion" / "hook.html").exists()
    # params 는 이미 있던 [자리표시자] 키만 채운다
    assert clips["ch1"]["params"]["title"] == "테스트 제목"
    # 렌더 확인은 생략 분기 (no_chromium) — 생략 로그가 남는다
    lines = [e["line"] for e in events]
    assert any("렌더 확인 생략" in l for l in lines)
    assert any("draft 완료" in l for l in lines)
    # 사용량 미터
    usage = runner.usage_summary()
    assert usage["count"] == 1 and usage["runs"][0]["calls"] == len(calls)


def test_draft_feeds_back_text_defects_once(tmp_path):
    """1차 응답에 [자리표시자] 가 남으면 결함을 되먹여 정확히 1회 재생성한다."""
    root = _lecture_episode(tmp_path)
    calls: list = []
    work = runner.make_agent_work("draft", "demo-01", {"brief": "주제"}, root,
                                  llm_call=_fake_llm(calls, defect_first=True))
    events = list(work())
    clip_calls = [c for c in calls
                  if c["schema"] and "clips" in c["schema"]["properties"]]
    assert len(clip_calls) == 2
    assert "결함" in clip_calls[1]["user"]
    scenes = load_json(root / "demo-01" / "scenes.json")
    hook = next(c for c in scenes["render"]["motion"]["clips"] if c["id"] == "hook")
    assert "[" not in hook["narration"]
    assert any("재생성 1회" in e["line"] for e in events)


def test_single_video_clips_get_narration(tmp_path):
    """단발(홍보·광고)은 골격에 narration 키가 없다 — 그래도 AI 가 말을 넣어야 한다.

    엔진 promo 템플릿은 내레이션을 최상위 scenes(앱 녹화)에 두는데 스캐폴딩이 그걸
    걷어낸다. 키를 그대로 따르면 **무음 영상**이 나온다 (2026-08-23 화면 실측:
    홍보 1편이 3.2초 무음으로 완주했다).
    """
    root = tmp_path / "projects"
    root.mkdir()
    scaffold.scaffold_course(root, "promo", title="홍보 테스트", kind="promo")
    scaffold.scaffold_episode(root, "promo", 1)
    before = load_json(root / "promo-01" / "scenes.json")["render"]["motion"]["clips"]
    assert not any("narration" in c for c in before), "전제: 골격에 말할 자리가 없다"

    calls: list = []
    list(runner.make_agent_work("draft", "promo-01", {"brief": "제품 소개"}, root,
                                llm_call=_fake_llm(calls))())
    after = load_json(root / "promo-01" / "scenes.json")["render"]["motion"]["clips"]
    assert all(c.get("narration") for c in after), "단발 카드가 무음으로 남았다"
    # 키 순서 규약 — narration 은 params 앞
    keys = list(after[0].keys())
    assert keys.index("narration") < keys.index("params")
    # 모델에게도 말해도 된다고 알렸는가
    clip_call = next(c for c in calls
                     if c["schema"] and "clips" in c["schema"]["properties"])
    assert '"말하기": true' in clip_call["user"]


def test_series_keeps_silent_clips_silent(tmp_path):
    """강의 골격은 broll·stinger 를 무음으로 설계했다 — 그 지정은 그대로 따른다."""
    root = _lecture_episode(tmp_path)
    list(runner.make_agent_work("draft", "demo-01", {"brief": "주제"}, root,
                                llm_call=_fake_llm([]))())
    clips = {c["id"]: c
             for c in load_json(root / "demo-01" / "scenes.json")["render"]["motion"]["clips"]}
    assert not clips["broll"].get("narration")     # 실사 2초 무내레이션
    assert not clips["stinger"].get("narration")   # 전환 카드
    assert clips["hook"]["narration"]              # 말하는 구간은 채워졌다


def test_budget_overrun_is_fed_back(tmp_path, monkeypatch):
    """예산을 크게 넘기면 되먹여 줄이게 한다 — 길이가 곧 영상 사양이다.

    2026-08-23 실측: "10초"(65자) 홍보에 haiku 가 110자를 써 15.4초가 나왔다.
    """
    root = tmp_path / "projects"
    root.mkdir()
    scaffold.scaffold_course(root, "tiny", title="짧은 홍보", kind="promo",
                             episode_length="10초 (약 65자)")
    scaffold.scaffold_episode(root, "tiny", 1)

    long_line = "가" * 80                     # 3클립 × 80자 = 240자 ≫ 65자
    calls: list = []

    def llm(*, system, user, json_schema=None, images=None, task=None):
        calls.append(user)
        props = (json_schema or {}).get("properties", {})
        if "plan_md" in props:
            return {"plan_md": "표", "facts_md": "표"}, {}
        if "clips" in props:
            over = len([u for u in calls if "골격" in u]) == 1   # 1차만 초과
            ids = [e["id"] for e in _skeleton_from(user)]
            return {"clips": [{"id": i, "narration": long_line if over else "짧게.",
                               "screen": "화면", "params": [], "broll": ""}
                              for i in ids]}, {}
        return {}, {}

    list(runner.make_agent_work("draft", "tiny-01", {"brief": "x"}, root,
                                llm_call=llm)())
    retry = [u for u in calls if "예산" in u and "넘었다" in u]
    assert retry, "분량 초과가 되먹여지지 않았다"
    clips = load_json(root / "tiny-01" / "scenes.json")["render"]["motion"]["clips"]
    assert sum(len(c.get("narration", "")) for c in clips) < 65 * 1.25


def test_budget_within_slack_is_not_fed_back(tmp_path):
    """예산에 조금 못 미치거나 살짝 넘는 것은 그냥 둔다 (되먹임 낭비 방지)."""
    assert runner._budget_defect([{"narration": "가" * 70}], 65) == []
    assert runner._budget_defect([{"narration": "가" * 90}], 65) != []


def test_unpicked_broll_is_fed_back_then_filled(tmp_path, monkeypatch):
    """B롤을 안 고르면 빌드가 결함 차단에 막힌다 — 되먹이고, 그래도 비면 임시로 채운다.

    2026-08-23 실측: 강의 초안이 나머지(415자·도식 4장)를 다 채우고 B롤 하나 때문에
    완주하지 못했다.
    """
    monkeypatch.setattr(runner, "_broll_choices", lambda: ["a.mp4", "b.mp4"])
    root = _lecture_episode(tmp_path)
    calls: list = []

    def llm(*, system, user, json_schema=None, images=None, task=None):
        calls.append(user)
        props = (json_schema or {}).get("properties", {})
        if "plan_md" in props:
            return {"plan_md": "표", "facts_md": "표"}, {}
        if "clips" in props:                    # 끝까지 broll 을 안 고른다
            return {"clips": [{"id": e["id"], "narration": "짧게.", "screen": "화면",
                               "params": [], "broll": ""}
                              for e in _skeleton_from(user)]}, {}
        if "html" in props:
            return {"html": "<div>도식</div>"}, {}
        return {}, {}

    events = list(runner.make_agent_work("draft", "demo-01", {"brief": "x"}, root,
                                         llm_call=llm)())
    assert any("실사(B롤)를 고르지 않았다" in u for u in calls), "되먹임이 없었다"
    clips = load_json(root / "demo-01" / "scenes.json")["render"]["motion"]["clips"]
    broll = next(c for c in clips if c["id"] == "broll")
    assert broll["video"] == "assets/broll/a.mp4"          # 임시 선택
    assert any("임시로 넣었습니다" in e["line"] for e in events), "무엇을 넣었는지 안 알렸다"
    # 빌드를 막던 **B롤 결함**이 사라졌다 (이게 목적이다 — params 는 이 가짜가 안 채운다)
    from core import validate

    left = validate.draft_defects(load_json(root / "demo-01" / "scenes.json"))
    assert not [p for p in left if "video" in p]


def test_broll_pick_from_model_is_honored(tmp_path, monkeypatch):
    """모델이 목록 안의 파일명을 고르면 그대로 쓴다 (목록 밖 이름은 버린다)."""
    monkeypatch.setattr(runner, "_broll_choices", lambda: ["a.mp4", "b.mp4"])
    root = _lecture_episode(tmp_path)

    def llm(*, system, user, json_schema=None, images=None, task=None):
        props = (json_schema or {}).get("properties", {})
        if "plan_md" in props:
            return {"plan_md": "표", "facts_md": "표"}, {}
        if "clips" in props:
            return {"clips": [{"id": e["id"], "narration": "짧게.", "screen": "화면",
                               "params": [],
                               "broll": "b.mp4" if e["id"] == "broll" else "없는것.mp4"}
                              for e in _skeleton_from(user)]}, {}
        if "html" in props:
            return {"html": "<div>도식</div>"}, {}
        return {}, {}

    list(runner.make_agent_work("draft", "demo-01", {"brief": "x"}, root,
                                llm_call=llm)())
    clips = load_json(root / "demo-01" / "scenes.json")["render"]["motion"]["clips"]
    assert next(c for c in clips if c["id"] == "broll")["video"] == "assets/broll/b.mp4"


def test_model_cannot_write_path_params(tmp_path, monkeypatch):
    """경로형 params(src·fontUrl)는 모델이 못 채운다 — 우리가 계산한다.

    2026-08-23 실측: 모델이 title.src 에 `bg/<회차>-frame.jpg` 를 지어냈다. 그럴듯하지만
    기준 html(course-intro.html)에서는 없는 경로라 **오류 없이 배경만 빠진다**.
    """
    root = _lecture_episode(tmp_path)

    def llm(*, system, user, json_schema=None, images=None, task=None):
        props = (json_schema or {}).get("properties", {})
        if "plan_md" in props:
            return {"plan_md": "표", "facts_md": "표"}, {}
        if "clips" in props:
            return {"clips": [{"id": e["id"], "narration": "말.", "screen": "화면",
                               "params": [{"key": "src", "value": "bg/지어낸.jpg"},
                                          {"key": "title", "value": "진짜 제목"}],
                               "broll": ""} for e in _skeleton_from(user)]}, {}
        if "html" in props:
            return {"html": "<div>도식</div>"}, {}
        return {}, {}

    list(runner.make_agent_work("draft", "demo-01", {"brief": "x"}, root,
                                llm_call=llm)())
    clips = {c["id"]: c
             for c in load_json(root / "demo-01" / "scenes.json")["render"]["motion"]["clips"]}
    assert "지어낸" not in json.dumps(clips, ensure_ascii=False)
    assert clips["ch1"]["params"]["title"] == "진짜 제목"     # 글자 params 는 그대로 채운다


def test_leftover_narration_placeholder_is_emptied(tmp_path):
    """되먹임 뒤에도 남은 [자리표시자] 내레이션은 비우고 알린다.

    두면 TTS 가 대괄호를 읽거나 결함 차단에 빌드가 막혀 "한 번에" 가 막다른 길이 된다.
    지어내지 않고 비우는 쪽을 고른다.
    """
    root = _lecture_episode(tmp_path)

    def llm(*, system, user, json_schema=None, images=None, task=None):
        props = (json_schema or {}).get("properties", {})
        if "plan_md" in props:
            return {"plan_md": "표", "facts_md": "표"}, {}
        if "clips" in props:      # title 만 끝까지 안 채운다 (haiku 실측 재현)
            return {"clips": [{"id": e["id"],
                               "narration": "" if e["id"] == "title" else "말.",
                               "screen": "화면", "params": [], "broll": ""}
                              for e in _skeleton_from(user)]}, {}
        if "html" in props:
            return {"html": "<div>도식</div>"}, {}
        return {}, {}

    events = list(runner.make_agent_work("draft", "demo-01", {"brief": "x"}, root,
                                         llm_call=llm)())
    clips = {c["id"]: c
             for c in load_json(root / "demo-01" / "scenes.json")["render"]["motion"]["clips"]}
    assert clips["title"]["narration"] == ""
    assert any("비웠습니다" in e["line"] for e in events)


def test_diagram_shared_links_are_rewritten_by_us(tmp_path):
    """공용 _base.css·_params.js 경로는 앱이 계산해 기입한다 — 모델이 못 센다.

    2026-08-23 실측: 모델이 `../_base.css` 를 써서 스타일이 통째로 안 걸렸고, 그래서
    자기 색을 박은 보라·분홍 도식이 파랑 강좌에 섞여 나왔다.
    """
    root = _lecture_episode(tmp_path)

    def llm(*, system, user, json_schema=None, images=None, task=None):
        props = (json_schema or {}).get("properties", {})
        if "plan_md" in props:
            return {"plan_md": "표", "facts_md": "표"}, {}
        if "clips" in props:
            return {"clips": [{"id": e["id"], "narration": "말.", "screen": "화면",
                               "params": [], "broll": ""}
                              for e in _skeleton_from(user)]}, {}
        if "html" in props:      # 모델이 엉뚱한 경로를 쓴다
            return {"html": '<head><link rel="stylesheet" href="../_base.css">'
                            '<script src="../_params.js"></script></head><div>도식</div>'}, {}
        return {}, {}

    list(runner.make_agent_work("draft", "demo-01", {"brief": "x"}, root,
                                llm_call=llm)())
    html = (root / "demo-01" / "motion" / "hook.html").read_text(encoding="utf-8")
    assert '"../_base.css"' not in html
    # 기입된 경로가 실제 파일을 가리켜야 한다 (이게 유일한 판정)
    from core import paths as paths_mod

    for name in ("_base.css", "_params.js"):
        ref = html.split(f'"')[1] if False else None
    import re as _re

    for m in _re.finditer(r'(?:href|src)="([^"]*_(?:base\.css|params\.js))"', html):
        target = paths_mod.invert(paths_mod.RefKind.HTML_ASSET, m.group(1),
                                  html_file=root / "demo-01" / "motion" / "hook.html")
        assert target.exists(), f"{m.group(1)} 가 실물을 못 가리킨다 → 스타일 없는 맨 HTML"


def test_diagram_prompt_carries_palette():
    """팔레트를 프롬프트에 넣고, 색을 직접 정하지 말라고 못 박는다."""
    from core.agents import skill_prompts

    text = skill_prompts.diagram_rules({"brand": "#5B8DEF", "bg": "#0B1220"})
    assert "#5B8DEF" in text and "var(--brand)" in text
    assert "직접 정하지 마라" in text
    # 경로 규칙이 담긴 절이 실제로 들어왔는가 (2026-08-23 누락 회귀)
    assert "_base.css" in text and "스타일 없는 맨 HTML" in text


def test_highlight_uses_native_css_not_playwright_syntax():
    """`highlight` 는 브라우저 네이티브 querySelector 로 돈다 — `:has-text()` 면 빌드가 죽는다.

    2026-08-23 실측: `button:has-text("공지사항")` 을 highlight 에 주자
    "not a valid selector" 로 녹화가 중단됐다 (record.js __adHighlight).
    """
    css_map = {'button:has-text("공지사항")': "div:nth-of-type(2) > button"}
    got = runner._to_action(
        {"do": "highlight", "target": 'button:has-text("공지사항")', "value": ""},
        {}, css_map)
    assert got["highlight"] == "div:nth-of-type(2) > button"
    assert got["optional"] is True          # 못 찾아도 촬영을 끊지 않는다
    # 번역할 수 없으면 아예 버린다 (강조는 부가 연출 — 빌드를 죽일 이유가 없다)
    assert runner._to_action(
        {"do": "highlight", "target": 'button:has-text("없음")', "value": ""}, {}, {}) is None


def test_small_scroll_values_become_visible_scrolls():
    """모델이 "3"(세 번쯤)처럼 정도로 답해도 화면이 실제로 움직여야 한다.

    2026-08-23 실측: `scroll: 3` 이 3px 이 되어 두 씬이 정지 사진처럼 찍혔다.
    """
    assert runner._to_action({"do": "scroll", "target": "", "value": "3"}, {})["scroll"] == 960
    assert runner._to_action({"do": "scroll", "target": "", "value": "-3"}, {})["scroll"] == -960
    # 원래 픽셀로 답했으면 그대로 둔다
    assert runner._to_action({"do": "scroll", "target": "", "value": "520"}, {})["scroll"] == 520


def test_password_stays_as_env_name_in_actions():
    """녹화 액션에 비밀번호를 박지 않는다 — 이름만 (I-5). 값은 빌드 순간에 풀린다."""
    got = runner._to_action(
        {"do": "type", "target": "input[type=password]", "value": "그대로쓰면안됨"},
        {"passwordEnv": "MYAPP_PW"})
    assert got["textEnv"] == "MYAPP_PW" and "text" not in got


def test_build_resolves_textenv_into_temp_scenes(tmp_path, monkeypatch):
    """빌드 직전에만 임시 대본으로 풀고, 원본 대본에는 비밀번호가 없다."""
    from core import engine_io

    monkeypatch.setenv("TEST_PW", "s3cret")
    scenes = tmp_path / "scenes.json"
    scenes.write_text(json.dumps(
        {"id": "x", "scenes": [{"id": "s1", "actions": [
            {"type": "input[type=password]", "textEnv": "TEST_PW"}]}]},
        ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(engine_io.env, "cache_dir", lambda: tmp_path / "cache")
    resolved = engine_io._resolve_secrets(scenes)
    assert resolved is not None
    body = resolved.read_text(encoding="utf-8")
    assert "s3cret" in body and "textEnv" not in body
    assert "s3cret" not in scenes.read_text(encoding="utf-8")   # 원본은 그대로


# ── 잡 큐 통합 — 이벤트·상태·미터 계약 (D8) ─────────────────────────────────
def test_agent_job_runs_in_queue(tmp_path):
    root = _lecture_episode(tmp_path)
    work = runner.make_agent_work("draft", "demo-01", {"brief": "큐 테스트"}, root,
                                  llm_call=_fake_llm([]))
    q = JobQueue(runner=None, preflight=lambda d: {"preflight": []}, verifier=None)
    job = q.submit_agent("demo-01", work)
    deadline = time.time() + 15
    while job.state not in (JobState.DONE, JobState.FAILED) and time.time() < deadline:
        time.sleep(0.05)
    assert job.state is JobState.DONE, job.error
    lines = [e.get("line", "") for e in job.events if e["kind"] == "log"]
    assert any("구성표" in l for l in lines)
    assert any("draft 완료" in l for l in lines)


def test_agent_submit_when_enabled(monkeypatch, tmp_path):
    root = _lecture_episode(tmp_path)
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(root))

    from core import agents as agents_pkg

    monkeypatch.setattr(agents_pkg, "agent_enabled", lambda: {"enabled": True})
    monkeypatch.setattr(
        agents_pkg, "make_agent_work",
        lambda kind, eid, payload, r: runner.make_agent_work(
            kind, eid, payload, r, llm_call=_fake_llm([])))

    st = Studio(queue=JobQueue(runner=None, preflight=lambda d: {"preflight": []},
                               verifier=None))
    job_id = st.agent_submit("draft", "demo-01", {"brief": "테스트"})["jobId"]
    deadline = time.time() + 15
    while time.time() < deadline:
        state = st.job(job_id)["state"]
        if state in ("done", "failed"):
            break
        time.sleep(0.05)
    assert state == "done"


# ── diagram — 단독 작업 (⑤ [AI 도식]) ───────────────────────────────────────
def test_diagram_writes_motion_html(tmp_path):
    root = _lecture_episode(tmp_path)
    calls: list = []
    work = runner.make_agent_work(
        "diagram", "demo-01",
        {"clipId": "s1", "describe": "데이터 흐름", "narration": "설명 문장"},
        root, llm_call=_fake_llm(calls))
    events = list(work())
    assert (root / "demo-01" / "motion" / "s1.html").exists()
    assert any("diagram 완료" in e["line"] for e in events)


# ── review — 프레임 vision 채점 ──────────────────────────────────────────────
def test_review_scores_frames(monkeypatch, tmp_path):
    out_root = tmp_path / "out"
    (out_root / "demo-01" / "frames").mkdir(parents=True)
    for i in range(3):
        (out_root / "demo-01" / "frames" / f"review-{i}.jpg").write_bytes(b"jpegdata")
    monkeypatch.setattr(runner, "OUT_ROOT", out_root)
    calls: list = []
    work = runner.make_agent_work("review", "demo-01", {}, tmp_path,
                                  llm_call=_fake_llm(calls))
    events = list(work())
    saved = json.loads((out_root / "demo-01" / "review-agent.json")
                       .read_text(encoding="utf-8"))
    assert saved["overall"] == 4.0 and len(saved["fixes"]) == 1
    assert len(calls[0]["images"]) == 3          # 프레임이 vision 입력으로 갔다
    assert any("평가 완료" in e["line"] for e in events)


def test_review_without_frames_says_build_first(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "OUT_ROOT", tmp_path / "empty-out")
    work = runner.make_agent_work("review", "demo-01", {}, tmp_path,
                                  llm_call=_fake_llm([]))
    events = list(work())
    assert any("먼저 빌드" in e["line"] for e in events)


# ── 공용 계약 ────────────────────────────────────────────────────────────────
def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        runner.make_agent_work("hack", "x", {}, FIXTURES_DIR)


def test_task_model_env_override(monkeypatch):
    assert runner.task_model("diagram") == "claude-sonnet-5"
    monkeypatch.setenv("AGENT_MODEL_DIAGRAM", "claude-haiku-4-5-20251001")
    assert runner.task_model("diagram") == "claude-haiku-4-5-20251001"
    assert runner.task_model("draft") == "claude-opus-5"  # 다른 작업은 그대로
