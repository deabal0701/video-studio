"""에이전트 러너 — 3종(draft·diagram·review) 순수 HTTP 오케스트레이션 (D18 · 05_agent).

작업 하나 = 잡 하나 = HTTP 호출 1~N회(상한 고정 — 루프는 코드가 돈다, 모델이 아니라).
상태는 전부 파일로 남는다. 모델은 **내용(텍스트·JSON·html)만** 반환하고 파일 기입은
여기서 결정적으로 한다 — 경로·palette·voice 를 모델에 맡기지 않는다 (02 경로 함정 5종).

  draft  : ① 구성표·근거표(산문) → ② 클립 내레이션(구조화, 같은 system 재사용=캐시 적중)
           → 결정적 병합 → 검증 되먹임 1회 → 자리표시자 file 클립은 도식 생성 연쇄
  diagram: 생성·기입 → engine/snapshot.js 정지 프레임 → vision 되먹임 확인 1회
  review : 검수 프레임 4+1장 vision 채점 → out/<id>/review-agent.json
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Callable

from .. import REPO_ROOT, engine_io, env, kinds, media_ops, paths, schema, validate
from ..status import OUT_ROOT
from . import llm, providers, skill_prompts

# 사용량 미터는 파생물 — 설치 모드에선 데이터 폴더에 쌓인다 (설치 폴더 무쓰기)
USAGE_FILE = env.cache_dir() / "agent-usage.jsonl"


# ── 환경 설정 조회 — 셸 → 저장소 .env → 홈 공용 파일 순 (engine util 과 같은 규약) ──
def _env_value(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    for env_file in (REPO_ROOT / ".env",
                     Path.home() / ".claude" / "develop-video.env"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith(f"{name}="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
    return None


# ── 제공자·모델 (D15 — 선택·해석은 providers 가 정본) ─────────────────────────
def provider() -> str:
    return providers.provider(_env_value)


def test_mode() -> bool:
    return providers.test_mode(_env_value)


# ── 키 게이트 — 선택한 제공자의 키만 검사 (앱의 다른 전부는 키 없이 동작) ──────
def _find_key(prov: str | None = None) -> str | None:
    return _env_value(providers.KEY_ENV[prov or provider()])


def task_model(kind: str) -> str:
    return providers.task_model(_env_value, kind)


def agent_enabled() -> dict[str, Any]:
    return providers.status(_env_value)


KINDS = providers.KINDS


# ── 구조화 생성 계약 (양 제공자 공통 — strict 스키마) ─────────────────────────
PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["plan_md", "facts_md"],
    "properties": {
        "plan_md": {"type": "string",
                    "description": "구성표 markdown — 구간|말하는 것|화면|글자수 표 포함"},
        "facts_md": {"type": "string",
                     "description": "주장—출처—확인날짜 표. 근거 자료 밖의 수치 금지"},
    },
}

CLIPS_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["clips"],
    "properties": {"clips": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["id", "narration", "screen", "params", "broll"],
        "properties": {
            "id": {"type": "string", "description": "골격에 이미 있는 클립 id 만"},
            "narration": {"type": "string"},
            "screen": {"type": "string",
                       "description": "화면에 무엇이 보이는지 — 도식 생성의 지시문"},
            "params": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["key", "value"],
                "properties": {"key": {"type": "string"},
                               "value": {"type": "string"}}},
                "description": "카드의 [자리표시자] 글자 값 채우기 — 이미 있는 키만"},
            "broll": {"type": "string",
                      "description": "실사(video) 구간이면 소재 목록에서 고른 파일명, 아니면 빈 문자열"},
        }}}},
}

SCENES_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["scenes"],
    "properties": {"scenes": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["id", "narration", "actions"],
        "properties": {
            "id": {"type": "string", "description": "s1·s2… 순서대로"},
            "narration": {"type": "string", "description": "이 화면을 보며 하는 말"},
            "actions": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["do", "target", "value"],
                "properties": {
                    "do": {"type": "string",
                           "enum": ["goto", "click", "type", "scroll", "wait",
                                    "waitFor", "highlight"]},
                    "target": {"type": "string",
                               "description": "click·type·waitFor·highlight 는 **요소 목록의 "
                                              "selector 를 그대로**, goto 는 경로(/ 로 시작)"},
                    "value": {"type": "string",
                              "description": "type 은 넣을 글자, scroll·wait 는 숫자, 그 외 빈 문자열"},
                }}},
        }}}},
}

DIAGRAM_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["html"],
    "properties": {"html": {"type": "string", "description": "모션 도식 html 전문"}},
}

VERIFY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["ok", "problem", "html"],
    "properties": {
        "ok": {"type": "boolean", "description": "렌더가 의도를 전달하면 true"},
        "problem": {"type": "string", "description": "무엇이 잘못 보이는지 (ok 면 빈 문자열)"},
        "html": {"type": "string", "description": "수정한 html 전문 (ok 면 빈 문자열)"},
    },
}

REVIEW_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["scores", "fixes", "overall"],
    "properties": {
        "scores": {
            "type": "object", "additionalProperties": False,
            "required": ["구성", "설명력", "화면", "분량", "일관성", "완성도"],
            "properties": {k: {"type": "number"} for k in
                           ("구성", "설명력", "화면", "분량", "일관성", "완성도")},
        },
        "fixes": {"type": "array", "items": {"type": "string"}},
        "overall": {"type": "number"},
    },
}


class _Meter:
    """호출·토큰 적산 — 잡 하나의 사용량 미터."""

    def __init__(self) -> None:
        self.calls = 0
        self.inp = 0
        self.out = 0

    def add(self, usage: dict[str, Any]) -> None:
        self.calls += 1
        self.inp += int(usage.get("inputTokens") or 0)
        self.out += int(usage.get("outputTokens") or 0)

    def summary(self) -> dict[str, Any]:
        return {"calls": self.calls, "inputTokens": self.inp, "outputTokens": self.out}


def make_agent_work(kind: str, episode_id: str, payload: dict[str, Any],
                    projects_root: Path,
                    llm_call: Callable | None = None) -> Callable[[], Iterator[dict]]:
    """잡 큐에 실을 work 제너레이터 팩토리. llm_call 주입으로 키·네트워크 없이 테스트한다.

    llm_call(system=, user=, json_schema=None, images=None, task=kind) → (내용, usage)
    """
    if kind not in KINDS:
        raise ValueError(f"모르는 에이전트 작업: {kind}")

    if llm_call is None:
        prov = provider()
        key = _find_key(prov) or ""

        def llm_call(*, system: str, user: str, json_schema: dict | None = None,
                     images: list | None = None, task: str = kind):
            return llm.complete(prov, key=key, model=task_model(task), system=system,
                                user=user, json_schema=json_schema, images=images)

    works = {"draft": _draft_work, "diagram": _diagram_work, "review": _review_work}
    return works[kind](episode_id, payload, projects_root, llm_call)


# ── draft — 2단계 + 검증 되먹임 + 도식 연쇄 ──────────────────────────────────
def _draft_work(episode_id: str, payload: dict[str, Any], projects_root: Path,
                llm_call: Callable) -> Callable[[], Iterator[dict]]:
    def work() -> Iterator[dict[str, Any]]:
        prov, model = provider(), task_model("draft")
        yield _log(f"에이전트 draft 시작 ({prov} · {model}) — {episode_id}")
        ep_dir = projects_root / episode_id
        course_id = episode_id.rsplit("-", 1)[0]
        course_file = ep_dir.parent / course_id / "course.json"
        course = schema.load_json(course_file) if course_file.exists() else {}
        series = bool(kinds.get(course.get("kind")).get("series", True))
        system = skill_prompts.draft_rules(series=series)
        meter = _Meter()

        # ① 구성표·근거표 — "문장부터 쓰면 반드시 되돌아온다" (스킬 순서 그대로)
        sources = _source_texts(payload)
        yield _log("구성표·근거표 생성 중…")
        plan, u = llm_call(system=system, user=_plan_user(course, payload, sources),
                           json_schema=PLAN_SCHEMA)
        meter.add(u)
        written = []
        for name, key in (("plan.md", "plan_md"), ("facts.md", "facts_md")):
            if plan.get(key):
                (ep_dir / name).write_text(plan[key], encoding="utf-8", newline="\n")
                written.append(name)
        yield _log(f"기입: {', '.join(written) or '(없음)'}")

        # ② 클립 내레이션 — 골격은 scenes.json 이 정본, 모델은 내용만
        doc = schema.Document.load(ep_dir / "scenes.json")
        clips = doc.data["render"]["motion"]["clips"]
        brolls = _broll_choices()
        add_ok = _may_speak(clips)   # 병합 전에 확정 (아래 재생성까지 같은 값)
        user2 = _clips_user(course, payload, plan.get("plan_md", ""), clips, brolls,
                            add_ok)
        yield _log(f"클립 내레이션 생성 중… (골격 {len(clips)}개)")
        data, u = llm_call(system=system, user=user2, json_schema=CLIPS_SCHEMA)
        meter.add(u)
        _merge_clips(clips, data, brolls, add_ok)

        # 검증 되먹임 — 모델이 고칠 수 있는 것(자리표시자·분량 초과)만 1회 재생성
        budget = _char_budget(course)
        problems = _text_defects(clips) + _budget_defect(clips, budget)
        if problems:
            yield _log(f"검증 지적 {len(problems)}건 — 되먹여 재생성 1회")
            feedback = (user2 + "\n\n앞선 초안의 결함 — 아래를 고쳐 전체를 다시 반환하라:\n- "
                        + "\n- ".join(problems))
            data, u = llm_call(system=system, user=feedback, json_schema=CLIPS_SCHEMA)
            meter.add(u)
            _merge_clips(clips, data, brolls, add_ok)

        # 녹화 씬 — 앱 주소가 있으면 실제 화면을 찍는 대본을 만든다 (I-2)
        capture = course.get("capture") or {}
        if capture.get("baseUrl") and doc.data.get("scenes"):
            for line in _write_scenes(llm_call, system, doc.data, capture, payload,
                                      meter):
                yield _log(line)

        # 되먹임 뒤에도 남은 내레이션 자리표시자는 비운다 — 그대로 두면 TTS 가 대괄호를
        # 읽거나(결함 차단이 없었다면) 빌드가 막혀 "한 번에" 가 막다른 길이 된다.
        # 지어내지 않고 비우는 쪽을 고른다 — 무엇이 비었는지 말해 주면 사람이 채운다.
        for c in clips:
            n = c.get("narration")
            if isinstance(n, str) and "[" in n:
                c["narration"] = ""
                yield _log(f"{kinds.role_label(c.get('id'))}({c.get('id')}) 내레이션을 "
                           f"채우지 못해 비웠습니다 — 대본 화면에서 채워 주세요")

        # 재생성 뒤에도 B롤이 비었으면 임시로 채운다 — "한 번에" 가 막다른 길이 되면
        # 담당자는 무엇을 해야 하는지 모른다. 무엇을 넣었는지 로그로 분명히 말한다.
        for c in clips:
            if isinstance(c.get("video"), str) and "[" in c["video"] and brolls:
                c["video"] = f"assets/broll/{brolls[0]}"
                yield _log(f"B롤을 고르지 못해 '{brolls[0]}' 를 임시로 넣었습니다 — "
                           f"대본 화면에서 바꿀 수 있습니다")

        # 자리표시자 file 클립 → 도식 생성 연쇄 (구 에이전틱 경로가 하던 몫)
        diag_system = None
        todo = [c for c in clips
                if isinstance(c.get("file"), str) and "[" in c["file"]]
        for clip in todo[:8]:
            cid = str(clip.get("id") or "diagram")
            if diag_system is None:
                diag_system = skill_prompts.diagram_rules(
                    course.get("palette") or {})
            yield _log(f"도식 생성: {cid}")
            html, usages, notes = _generate_diagram(
                llm_call, diag_system, ep_dir,
                describe=str(clip.get("_화면메모") or clip["file"]),
                narration=str(clip.get("narration") or ""), clip_id=cid)
            for usage in usages:
                meter.add(usage)
            for note in notes:
                yield _log(note)
            target = ep_dir / "motion" / f"{cid}.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(html.strip() + "\n", encoding="utf-8", newline="\n")
            clip["file"] = f"motion/{cid}.html"
            yield _log(f"기입: motion/{cid}.html")

        # 타이틀 배경 — B롤과 같은 시각의 프레임을 bg/ 로 (스킬 인트로 규약의 기계화)
        for line in _title_bg(ep_dir, clips):
            yield _log(line)

        doc.save()
        yield _log("기입: scenes.json")

        remaining = validate.draft_defects(doc.data)
        if remaining:
            yield _log(f"사람이 확인할 것 {len(remaining)}건 — 대본 화면의 결함 안내를 보세요")
        _record_usage("draft", episode_id,
                      {"provider": prov, "model": model, **meter.summary()})
        yield _log(f"에이전트 draft 완료 (호출 {meter.calls}회 · "
                   f"토큰 {meter.inp:,}+{meter.out:,})")

    return work


def _plan_user(course: dict, payload: dict, sources: str) -> str:
    parts = [f"강좌/프로젝트: {course.get('title', '')} — {course.get('tagline', '')}",
             f"대상: {course.get('audience', '')}",
             f"이번 영상 주제(brief): {payload.get('brief', '')}",
             f"내레이션 글자 예산: 약 {_char_budget(course):,}자"]
    if sources:
        parts.append("근거 자료 — 아래 내용만 근거로 쓰고, 밖의 수치를 지어내지 마라:\n"
                     + sources)
    parts.append("구성표(plan_md)와 근거표(facts_md)를 만들어라. 아직 문장(내레이션)을 "
                 "쓰지 마라 — 구간 배분과 화면 계획이 먼저다.")
    return "\n\n".join(parts)


def _may_speak(clips: list[dict]) -> bool:
    """카드 클립에 내레이션을 **새로 달아도 되는가**.

    골격이 speaking 클립을 명시하면(강의: title·hook·… 에 narration 키, broll·stinger 는
    무음 설계) 그 지정을 그대로 따른다. 그런데 단발 종류(홍보·광고·매뉴얼)의 엔진 템플릿은
    내레이션을 **최상위 scenes(앱 녹화 씬)** 에 두고 카드에는 아예 두지 않는데,
    스캐폴딩이 그 녹화 씬을 걷어낸다(scaffold._trim_clips — 녹화할 웹앱이 없다).
    그러면 말할 곳이 한 군데도 없어 **무음 영상**이 나온다 (2026-08-23 화면 실측:
    홍보 1편이 3.2초 무음으로 완주). 사람은 ⑤ 에디터에서 쳐 넣을 수 있는 자리라,
    AI 도 넣을 수 있어야 한다.
    """
    return not any("narration" in c for c in clips)


def _clips_user(course: dict, payload: dict, plan_md: str,
                clips: list[dict], brolls: list[str], add_ok: bool) -> str:
    skeleton = []
    for c in clips:
        cid = str(c.get("id") or "?")
        entry = {"id": cid, "역할": kinds.role_label(cid),
                 "말하기": add_ok or "narration" in c}
        if isinstance(c.get("video"), str):
            entry["실사"] = c["video"]
            if "[" in c["video"]:
                entry["실사고르기"] = "필수 — 아래 소재 목록에서 파일명 하나를 broll 에 넣어라"
        if isinstance(c.get("file"), str):
            entry["화면"] = c["file"]
        fill = [k for k, v in (c.get("params") or {}).items()
                if not k.startswith("_") and isinstance(v, str) and "[" in v]
        if fill:
            entry["채울 params"] = fill
        note = c.get("_") or c.get("_화면메모")
        if note:
            entry["메모"] = str(note)[:200]
        skeleton.append(entry)
    return "\n\n".join(p for p in [
        f"확정된 구성표:\n{plan_md}",
        f"이번 영상 주제(brief): {payload.get('brief', '')}",
        "골격(scenes.json 클립) — 이 id 들만, 순서 불변:\n"
        + json.dumps(skeleton, ensure_ascii=False, indent=1),
        f"내레이션 글자 예산 총 약 {_char_budget(course):,}자 — 구성표의 배분을 지켜라. "
        "말하기=false 구간은 narration 을 빈 문자열로 둔다.",
        (f"실사(B롤) 소재 목록 — 이 파일명 중에서만 고른다:\n- " + "\n- ".join(brolls))
        if brolls else "실사(B롤) 소재 없음 — broll 은 전부 빈 문자열로.",
        "클립마다 narration(대본)·screen(화면에 보일 것)·params(카드의 [자리표시자] 값)를 "
        "채워 반환하라. [대괄호] 를 어떤 값에도 남기지 마라.",
    ] if p)


# 경로형 params — **모델이 채우면 안 된다.** 기준 html 위치에 따라 답이 달라지고(02 경로
# 함정 5종), 틀려도 오류가 아니라 **조용히 빈 배경**이 된다. 2026-08-23 실측: 강의 초안에서
# 모델이 title.src 에 `bg/money-basics-01-frame.jpg` 를 지어냈다 — 그럴듯하지만
# course-intro.html 기준으로는 없는 경로다(정답은 `../<회차>/bg/<파일>.jpg`).
# 자리표시자로 남겨 두면 _title_bg 가 실물 프레임을 뽑아 정확한 상대경로를 기입한다.
PATH_PARAMS = ("src", "fontUrl")


def _set_narration(clip: dict, text: str) -> None:
    """내레이션 기입 — 키가 없으면 params 앞에 끼운다 (픽스처 키 순서 규약)."""
    if "narration" in clip:
        clip["narration"] = text
        return
    items = list(clip.items())
    at = next((i for i, (k, _) in enumerate(items) if k == "params"), len(items))
    clip.clear()
    clip.update(dict(items[:at] + [("narration", text)] + items[at:]))


def _merge_clips(clips: list[dict], data: dict, brolls: list[str],
                 add_ok: bool) -> None:
    """모델 응답을 골격에 결정적으로 병합 — 골격 밖 id·모르는 params 키는 버린다.

    add_ok 는 **1차 병합 전에** 정해 넘긴다 — 병합이 narration 키를 만들고 나면
    _may_speak 가 False 로 뒤집혀 재생성 회차가 갑자기 다르게 동작한다.
    """
    by_id = {str(c.get("id")): c for c in clips}
    for item in data.get("clips", []):
        clip = by_id.get(str(item.get("id")))
        if clip is None:
            continue
        if item.get("narration") and (add_ok or "narration" in clip):
            _set_narration(clip, str(item["narration"]))
        if item.get("screen"):
            clip["_화면메모"] = str(item["screen"])  # `_` 주석 필드 — 엔진 무관
        current = clip.get("params") or {}
        for kv in item.get("params") or []:
            key = str(kv.get("key") or "")
            if key in PATH_PARAMS:
                continue          # 경로는 우리가 계산한다 (PATH_PARAMS 주석)
            if key in current and not key.startswith("_") \
                    and isinstance(current[key], str) and "[" in current[key]:
                current[key] = str(kv.get("value") or "")
        pick = str(item.get("broll") or "")
        if pick and pick in brolls and isinstance(clip.get("video"), str) \
                and "[" in clip["video"]:
            clip["video"] = f"assets/broll/{pick}"  # 엔진 루트 기준 (scaffold 규약)


# record.js 액션 문법으로의 변환표 — 모델은 (do·target·value) 평평한 형태로만 답하고
# 실제 키 이름은 여기서 붙인다. 모르는 do 는 버린다(엔진이 "알 수 없는 액션"으로 죽지 않게).
def _to_action(item: dict, login: dict, css_map: dict[str, str] | None = None) -> dict | None:
    do = str(item.get("do") or "")
    target, value = str(item.get("target") or ""), str(item.get("value") or "")
    if do == "goto":
        return {"goto": target or "/"}
    if do == "wait":
        return {"wait": _num(value, 1.0)}
    if do == "scroll":
        # 모델은 "3"(세 번쯤 굴리기)처럼 **양이 아니라 정도**로 답하는 일이 잦다 —
        # 그대로 3px 을 굴리면 화면이 안 움직여 정지 사진처럼 보인다 (2026-08-23 실측).
        # 작은 값은 화면 단위로 읽는다. 음수는 위로 올리는 뜻이라 부호를 지킨다.
        raw = _num(value, 400)
        px = raw if abs(raw) >= 50 else raw * 320
        return {"scroll": int(px), "duration": 1.4}
    if not target:
        return None
    if do in ("click", "waitFor"):
        # optional — probe 이후 화면이 조금 달라져도 촬영을 끊지 않는다. 건너뛴 액션은
        # 엔진이 "(건너뜀)" 으로 로그에 남기므로 사람이 알 수 있다 (record.js 223행).
        return {do: target, "optional": True}
    if do == "highlight":
        # `highlight` 만 브라우저 네이티브 querySelector 로 돈다(record.js __adHighlight) —
        # Playwright 전용 `:has-text()` 를 주면 "not a valid selector" 로 **빌드가 죽는다**
        # (2026-08-23 실측). probe 가 함께 뽑아 둔 순수 CSS 경로로 바꾼다.
        native = (css_map or {}).get(target, target)
        if ":has-text" in native or ":has(" in native:
            return None            # 번역 못 하면 버린다 — 강조는 부가 연출이다
        # optional: 화면이 조금 달라져 못 찾아도 촬영을 끊지 않는다 (record.js 219행)
        return {"highlight": native, "duration": 2.2, "optional": True}
    if do == "type":
        # 비밀번호는 **이름만** 남긴다 — 값은 빌드 순간에 .env 에서 풀린다 (I-5)
        if login.get("passwordEnv") and "password" in target:
            return {"type": target, "textEnv": login["passwordEnv"], "optional": True}
        return {"type": target, "text": value, "optional": True}
    return None


def _num(text: str, fallback: float) -> float:
    try:
        return float(str(text).strip() or fallback)
    except ValueError:
        return fallback


def _write_scenes(llm_call: Callable, system: str, scenes_doc: dict,
                  capture: dict, payload: dict, meter: _Meter) -> list[str]:
    """앱 화면 녹화 대본을 만든다 — **셀렉터는 실제 페이지에서 훑어 온 목록에서만** 고른다.

    모델에게 브라우저가 없어 셀렉터를 지어내면 record.js 가 조용히 건너뛰고(223행) 아무 일도
    안 일어난 화면이 찍힌다. probe.js 로 먼저 훑어 "여기 이런 버튼이 있다"를 주는 이유다.
    """
    notes: list[str] = []
    login = capture.get("login") or {}
    base = str(capture["baseUrl"]).rstrip("/")
    # 로그인 세션을 파일로 남겨 **녹화가 그대로 이어받게** 한다 — 안 그러면 녹화는 새 세션이라
    # 로그인 화면이 찍힌다 (2026-08-23 실측: 내레이션은 대시보드를 말하는데 화면은 로그인).
    state = env.cache_dir() / "capture" / f"{scenes_doc.get('id', 'session')}.json"
    try:
        found = engine_io.probe(
            base, routes=[r.strip() for r in str(capture.get("routes") or "/").split(",")],
            login_user=login.get("user"),
            login_pass=_env_value(login["passwordEnv"]) if login.get("passwordEnv") else None,
            save_state=state if login.get("user") else None)
    except Exception as err:  # noqa: BLE001 — 앱이 안 떠 있을 수 있다: 녹화만 포기
        return [f"앱 화면 훑기 실패 — 녹화 씬 없이 진행합니다 ({str(err)[:90]})"]
    if found.get("stateSaved"):
        # 엔진이 읽는 자리. login 도 같이 둔다 — 빌드 직전에 세션을 새로 따기 위해서다
        # (값이 아니라 .env **이름**만 — I-5).
        scenes_doc.setdefault("capture", {}).update(
            {"storageState": str(state), "login": dict(login)})

    routes = found.get("routes") or []
    notes.append(f"앱 화면 훑기: {len(routes)}개 경로 · 로그인={found.get('loggedIn', '불필요')}")
    menu = []
    for r in routes:
        menu.append({"경로": r.get("route"), "제목": r.get("heading") or r.get("title"),
                     "스크롤가능": r.get("scrollable"),
                     "누를수있는것": [{"글자": b["text"], "selector": b["selector"]}
                                for b in (r.get("buttons") or [])[:14]],
                     "입력칸": [{"안내글": i.get("placeholder"), "selector": i["selector"]}
                             for i in (r.get("inputs") or [])[:6]]})
    n = max(2, min(4, len(scenes_doc.get("scenes") or [])))
    user = "\n\n".join([
        f"녹화할 앱: {base}",
        f"이 영상의 주제: {payload.get('brief', '')}",
        "실제 화면에서 훑어 온 요소 목록 — **selector 는 여기 있는 것만 그대로 쓴다**:\n"
        + json.dumps(menu, ensure_ascii=False, indent=1),
        (f"로그인은 이미 되어 있다(계정 {login.get('user')}) — 로그인 화면을 다시 찍지 마라."
         if found.get("loggedIn") else ""),
        f"화면을 보여 주는 녹화 씬 {n}개를 만들어라. 각 씬은 그 화면을 보며 할 말(narration)과 "
        "조작(actions)을 갖는다. 조작은 goto(경로 이동)·click·scroll·wait·highlight 를 쓰고, "
        "**화면이 실제로 바뀌는 조작**을 넣어라(가만히 있는 화면은 정지 사진처럼 보인다). "
        "제품에 없는 기능을 말하지 마라 — 위 목록에 보이는 것만 말한다.",
    ])
    data, u = llm_call(system=system, user=user, json_schema=SCENES_SCHEMA)
    meter.add(u)

    css_map = {e["selector"]: e.get("cssSelector") or e["selector"]
               for r in routes for e in (r.get("buttons") or []) + (r.get("inputs") or [])
               if e.get("selector")}
    built = []
    for i, sc in enumerate(data.get("scenes", [])[:6], start=1):
        actions = [a for a in (_to_action(x, login, css_map)
                               for x in sc.get("actions") or []) if a]
        if not actions:
            continue
        built.append({"id": f"s{i}", "narration": str(sc.get("narration") or ""),
                      "hold": 0.6, "actions": actions})
    if not built:
        return notes + ["녹화 씬을 만들지 못했습니다 — 모션그래픽만으로 진행합니다"]
    scenes_doc["scenes"] = built
    # 카드가 사라진 씬을 가리키지 않게 다시 묶는다 (F-3 함정 — before 고아 클립)
    ids = {s["id"] for s in built}
    for clip in scenes_doc["render"]["motion"]["clips"]:
        if clip.get("before") not in ids and clip.get("before") != "end":
            clip["before"] = "end"
    notes.append(f"녹화 씬 {len(built)}개 기입 "
                 f"({' · '.join(s['id'] + ':' + str(len(s['actions'])) + '동작' for s in built)})")
    return notes


def _text_defects(clips: list[dict]) -> list[str]:
    """모델이 재생성으로 고칠 수 있는 결함 — [자리표시자] 잔존.

    B롤(video)도 포함한다: 목록에서 파일명 하나를 고르는 일이라 모델이 할 수 있고,
    안 고르면 **빌드가 결함 차단에 막힌다** (2026-08-23 실측: 강의 초안이 B롤 하나
    때문에 완주 못 함 — 나머지 415자·도식 4장은 다 채워 놓고).
    """
    problems = []
    for c in clips:
        if isinstance(c.get("video"), str) and "[" in c["video"]:
            problems.append(f"{c.get('id', '?')} 구간의 실사(B롤)를 고르지 않았다 — "
                            f"소재 목록의 파일명 하나를 broll 에 넣어라")
        fields = [f for f in ("narration", "caption")
                  if isinstance(c.get(f), str) and "[" in c[f]]
        fields += [f"params.{k}" for k, v in (c.get("params") or {}).items()
                   if not k.startswith("_") and isinstance(v, str) and "[" in v]
        if fields:
            problems.append(f"{c.get('id', '?')} 구간의 {', '.join(fields)} 에 "
                            f"[자리표시자] 가 남아 있다")
    return problems


BUDGET_SLACK = 1.25   # 이만큼까지는 봐준다 — 예산은 어림수라 매번 되먹이면 낭비다


def _budget_defect(clips: list[dict], budget: int) -> list[str]:
    """분량 초과 — 길이가 곧 산출물 사양이라 넘치면 요청과 다른 영상이 나온다.

    2026-08-23 실측: "10초"(예산 65자) 홍보에 haiku 가 110자를 써 **15.4초**가 나왔다.
    화면의 예산 게이지는 초과를 보여 주지만(사람은 거기서 줄인다) AI 경로에는 그 되먹임이
    없었다. 상위 모델은 대체로 지키므로 초과분만 되돌려 준다.
    """
    total = sum(len(c.get("narration") or "") for c in clips)
    if not budget or total <= budget * BUDGET_SLACK:
        return []
    return [f"내레이션 합계가 {total}자로 예산 {budget}자를 넘었다 — "
            f"구간마다 줄여 합계를 {budget}자 이하로 맞춰라 (길이가 곧 영상 사양이다)"]


def _char_budget(course: dict) -> int:
    stored = str(course.get("episodeLength") or "")
    m = re.search(r"([\d,]+)\s*자", stored)
    if m:
        return int(m.group(1).replace(",", ""))
    return kinds.length_to_chars(stored) or 1850


def _broll_choices() -> list[str]:
    broll_dir = env.ENGINE_DIR / "assets" / "broll"
    if not broll_dir.exists():
        return []
    return sorted(p.name for p in broll_dir.glob("*.mp4"))


def _source_texts(payload: dict[str, Any], *, cap: int = 24_000,
                  total_cap: int = 96_000) -> str:
    """근거 문서는 경로가 아니라 **내용**을 전달한다 (모델에게 파일 도구가 없다)."""
    chunks: list[str] = []
    total = 0
    files: list[Path] = []
    for raw in payload.get("sourceDocs") or []:
        p = Path(str(raw))
        if p.is_dir():
            files += sorted(q for q in p.iterdir()
                            if q.suffix.lower() in (".md", ".txt", ".json", ".csv"))
        elif p.is_file():
            files.append(p)
    for p in files[:12]:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")[:cap]
        except OSError:
            continue
        total += len(text)
        chunks.append(f"### {p.name}\n{text}")
        if total > total_cap:
            break
    if payload.get("source"):
        chunks.append(f"### 원고 전문 — 이 글의 내용만으로 내레이션을 채워라\n"
                      f"{str(payload['source'])[:total_cap]}")
    return "\n\n".join(chunks)


def _title_bg(ep_dir: Path, clips: list[dict]) -> list[str]:
    """B롤이 정해졌으면 videoStart 프레임을 bg/ 로 뽑아 타이틀 src 를 채운다 (실패해도 계속)."""
    by_id = {str(c.get("id")): c for c in clips}
    broll, title = by_id.get("broll"), by_id.get("title")
    if not (broll and title):
        return []
    video = broll.get("video")
    src = (title.get("params") or {}).get("src")
    if not (isinstance(video, str) and "[" not in video
            and isinstance(src, str) and "[" in src
            and isinstance(title.get("file"), str)):
        return []
    try:
        source = paths.invert(paths.RefKind.BROLL, video)
        html = paths.invert(paths.RefKind.MOTION, title["file"], scenes_dir=ep_dir)
        out = media_ops.extract_bg_frame(ep_dir, source, float(broll.get("videoStart") or 1.0))
        title["params"]["src"] = paths.compute(paths.RefKind.HTML_ASSET, out,
                                               html_file=html)
        return [f"기입: bg/{out.name} (타이틀 배경 — B롤 {broll.get('videoStart', 1.0)}s 프레임)"]
    except Exception as err:  # noqa: BLE001 — 부가 단계: 실패는 보고만
        return [f"타이틀 배경 추출 건너뜀 — {err}"]


# ── diagram — 생성 + 렌더 확인 되먹임 ────────────────────────────────────────
_CSS_RE = re.compile(r'(<link[^>]*href=")[^"]*_base\.css(")')
_JS_RE = re.compile(r'(<script[^>]*src=")[^"]*_params\.js(")')


def _fix_shared_links(html: str, target: Path) -> str:
    """공용 `_base.css`·`_params.js` 링크를 **우리가 계산한 상대경로**로 바꾼다.

    몇 단계를 거슬러 올라가야 하는지는 배치가 정한다(스킬 예시는 `../../motion/`, 이 저장소는
    `../../../../engine/motion/`) — 모델이 셀 수 없는 값이다. 2026-08-23 실측: 모델이
    `../_base.css` 를 써서 스타일이 통째로 안 걸렸고, 그 결과 **자기 색을 박은 도식**이
    파랑 강좌에 보라·분홍으로 섞여 나왔다. 스킬도 같은 함정을 경고한다("경로가 틀리면
    스타일 없는 맨 HTML 이 조용히 찍힌다"). 경로는 우리가 쓴다 — PATH_PARAMS 와 같은 원칙.
    """
    base = paths.compute(paths.RefKind.HTML_ASSET,
                         env.ENGINE_DIR / "motion" / "_base.css", html_file=target)
    params = paths.compute(paths.RefKind.HTML_ASSET,
                           env.ENGINE_DIR / "motion" / "_params.js", html_file=target)
    html = _CSS_RE.sub(lambda m: m.group(1) + base + m.group(2), html)
    html = _JS_RE.sub(lambda m: m.group(1) + params + m.group(2), html)
    css_tag = f'<link rel="stylesheet" href="{base}">'
    js_tag = f'<script src="{params}"></script>'
    if "_base.css" not in html:      # 아예 안 넣었으면 머리에 끼운다
        head = css_tag + "\n" + js_tag
        html = (html.replace("</head>", head + "\n</head>", 1) if "</head>" in html
                else head + "\n" + html)
    elif "_params.js" not in html:   # css 만 있으면 params 를 그 뒤에 붙인다
        html = html.replace(css_tag, css_tag + "\n" + js_tag, 1)
    return html


def _generate_diagram(llm_call: Callable, system: str, ep_dir: Path, *,
                      describe: str, narration: str,
                      clip_id: str) -> tuple[str, list[dict], list[str]]:
    """도식 html 생성 → 정지 프레임 캡처 → vision 확인 → (필요시) 수정 1회.

    반환: (최종 html, usage 목록, 진행 로그)
    """
    usages: list[dict] = []
    notes: list[str] = []
    user = (f"설명하려는 것: {describe}\n해당 내레이션: {narration}\n"
            f"클립 id: {clip_id}\nhtml 전문을 반환하라.")
    data, u = llm_call(system=system, user=user, json_schema=DIAGRAM_SCHEMA,
                       task="diagram")
    usages.append(u)
    html = _fix_shared_links(data["html"], ep_dir / "motion" / f"{clip_id}.html")

    png = _snapshot(ep_dir, clip_id, html, narration)
    if png is None:
        notes.append("렌더 확인 생략 — 프레임 캡처를 쓸 수 없는 환경")
        return html, usages, notes
    verify_user = (f"첨부 이미지는 이 도식의 렌더 프레임이다.\n설명하려는 것: {describe}\n"
                   f"의도가 전달되는가? 글자 겹침·빈 화면·잘림이 있으면 ok=false 로 하고 "
                   f"수정한 html 전문을 반환하라.")
    verdict, u = llm_call(system=system, user=verify_user, json_schema=VERIFY_SCHEMA,
                          images=[("image/png", png)], task="diagram")
    usages.append(u)
    if verdict.get("ok") or not verdict.get("html"):
        notes.append(f"렌더 확인 통과: {clip_id}")
        return html, usages, notes
    notes.append(f"렌더 확인 지적 — 수정 재기입: {verdict.get('problem', '')[:120]}")
    return (_fix_shared_links(verdict["html"], ep_dir / "motion" / f"{clip_id}.html"),
            usages, notes)


def _snapshot(ep_dir: Path, clip_id: str, html: str, narration: str) -> bytes | None:
    """html 을 임시 기입해 중간 시각 프레임 png 를 뽑는다 — 실패하면 None (확인 생략)."""
    tmp = ep_dir / "motion" / f"_check-{clip_id}.html"
    png = env.cache_dir() / "agent-snapshots" / f"{ep_dir.name}-{clip_id}.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(html, encoding="utf-8", newline="\n")
        # 등장 delay 가 발화시각에 걸리므로 예상 길이의 75% 지점 — 요소가 모여 있을 때를 본다
        at = max(3.0, min(12.0, len(narration) / 6.4 * 0.75))
        engine_io.snapshot(tmp.name, ep_dir, png, at=at)
        return png.read_bytes()
    except Exception:  # noqa: BLE001 — 크로미움 부재 등: 확인만 생략
        return None
    finally:
        tmp.unlink(missing_ok=True)


def _diagram_work(episode_id: str, payload: dict[str, Any], projects_root: Path,
                  llm_call: Callable) -> Callable[[], Iterator[dict]]:
    def work() -> Iterator[dict[str, Any]]:
        prov, model = provider(), task_model("diagram")
        yield _log(f"에이전트 diagram 시작 ({prov} · {model}) — {episode_id}")
        ep_dir = projects_root / episode_id
        course_file = (ep_dir.parent / episode_id.rsplit("-", 1)[0] / "course.json")
        palette = (schema.load_json(course_file).get("palette") or {}
                   if course_file.exists() else {})
        system = skill_prompts.diagram_rules(palette)
        meter = _Meter()
        clip_id = str(payload.get("clipId") or "diagram")
        yield _log("도식 html 생성 중…")
        html, usages, notes = _generate_diagram(
            llm_call, system, ep_dir,
            describe=str(payload.get("describe") or ""),
            narration=str(payload.get("narration") or ""), clip_id=clip_id)
        for usage in usages:
            meter.add(usage)
        for note in notes:
            yield _log(note)
        target = ep_dir / "motion" / f"{clip_id}.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html.strip() + "\n", encoding="utf-8", newline="\n")
        yield _log(f"기입 완료: motion/{clip_id}.html")
        _record_usage("diagram", episode_id,
                      {"provider": prov, "model": model, **meter.summary()})
        yield _log(f"에이전트 diagram 완료 (호출 {meter.calls}회 · "
                   f"토큰 {meter.inp:,}+{meter.out:,})")

    return work


# ── review — 완성본 프레임만 보고 채점 ("만든 쪽이 채점하지 않는다") ──────────
def _review_images(episode_id: str) -> list[tuple[str, bytes]]:
    frames_dir = OUT_ROOT / episode_id / "frames"
    return [("image/jpeg", f.read_bytes())
            for f in sorted(frames_dir.glob("review-*.jpg"))[:5]]


def _review_work(episode_id: str, payload: dict[str, Any], projects_root: Path,
                 llm_call: Callable) -> Callable[[], Iterator[dict]]:
    def work() -> Iterator[dict[str, Any]]:
        prov, model = provider(), task_model("review")
        yield _log(f"에이전트 review 시작 ({prov} · {model}) — {episode_id}")
        images = _review_images(episode_id)
        if not images:
            yield _log("검수 프레임이 없습니다 — 먼저 빌드하세요")
            return
        meter = _Meter()
        system = skill_prompts.review_rules()
        user = (f"영상 {episode_id} 의 검수 프레임 {len(images)}장이 첨부돼 있다. "
                "6항목(구성·설명력·화면·분량·일관성·완성도)을 1~5로 채점하고 "
                "고칠 것을 적어라.")
        yield _log(f"프레임 {len(images)}장 평가 중…")
        data, u = llm_call(system=system, user=user, json_schema=REVIEW_SCHEMA,
                           images=images)
        meter.add(u)
        out = OUT_ROOT / episode_id / "review-agent.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
        yield _log(f"평가 완료 — overall {data.get('overall')} · 고칠 것 "
                   f"{len(data.get('fixes', []))}건 → out/{episode_id}/review-agent.json")
        _record_usage("review", episode_id,
                      {"provider": prov, "model": model, **meter.summary()})
        yield _log(f"에이전트 review 완료 (호출 {meter.calls}회 · "
                   f"토큰 {meter.inp:,}+{meter.out:,})")

    return work


# ── 공용 ─────────────────────────────────────────────────────────────────────
def _log(line: str) -> dict[str, Any]:
    return {"kind": "log", "line": line}


def _record_usage(kind: str, episode_id: str, usage: dict[str, Any]) -> None:
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "kind": kind, "episodeId": episode_id, **usage},
                           ensure_ascii=False) + "\n")


def usage_summary() -> dict[str, Any]:
    """토큰 미터 (설정 화면의 사용량 표)."""
    runs: list[dict[str, Any]] = []
    if USAGE_FILE.exists():
        for line in USAGE_FILE.read_text(encoding="utf-8").splitlines():
            try:
                runs.append(json.loads(line))
            except ValueError:
                continue
    return {"runs": runs[-50:],
            # costUsd 는 구(에이전틱) 기록의 잔재 필드 — 있으면 합산해 계속 보여준다
            "totalCostUsd": round(sum(r.get("costUsd", 0) or 0 for r in runs), 4),
            "totalTokens": sum((r.get("inputTokens", 0) or 0)
                               + (r.get("outputTokens", 0) or 0) for r in runs),
            "count": len(runs)}
