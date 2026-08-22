"""openai_runner — 에이전트 OpenAI 경로 (D15 · 05_agent "제공자 이중화").

claude 경로와 역할 경계가 다르다:

  claude : 에이전틱 — SDK 가 스킬을 네이티브 로드하고 파일을 직접 읽고 쓴다.
  openai : **구조화 생성만** — 모델은 내용(JSON/HTML)만 돌려주고,
           **파일 기입은 이 모듈이 결정적으로 수행**한다 (경로·palette·fontUrl 은
           scaffold/paths 규약 그대로. 모델에게 경로를 맡기지 않는다).

그래서 스킬 규약(1,200줄)을 네이티브로 못 읽는다 — 기계화 가능한 요지를 프롬프트에
요약 주입한다. 원칙 3 의 예외를 명시적으로 감수하는 경로이고, 초안 품질의 기본 권장은
claude 다 (05_agent 표).

openai 패키지는 선택 의존성 — 키가 있어도 미설치면 사유를 그대로 알린다.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Callable, Iterator

from .. import schema
from ..status import OUT_ROOT

# 스킬 규약의 기계화 가능한 요지 (정본은 .claude/skills — 여기는 요약 주입분)
LECTURE_RULES = """당신은 강좌 회차 대본 작가다. 아래 규약을 지킨다.
- 골격 순서: broll → title → hook → stinger → promise → (ch/s 반복) → recap → outro
- 내레이션 총량 예산 약 1,850자 (초당 6.4자 = 약 5분). 넘치면 압축이 아니라 회차 분할
- 회차는 독립이다 — 앞 회차를 참조하지 않는다
- 근거 없는 수치를 쓰지 않는다. 수치를 쓰면 facts 에 출처 URL 과 확인 날짜를 남긴다
- 설명 구간을 글자 카드로 때우지 않는다 — 무엇을 그림으로 보일지 screen 에 적는다
- 구어체 존댓말. 한 문장은 짧게."""

DRAFT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["plan_md", "facts_md", "clips"],
    "properties": {
        "plan_md": {"type": "string", "description": "구성표 markdown (## 구간 배분 표 포함)"},
        "facts_md": {"type": "string", "description": "주장—출처URL—확인날짜 표"},
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "narration", "screen"],
                "properties": {
                    "id": {"type": "string", "description": "골격 관례 id (hook·ch1·s1a…)"},
                    "narration": {"type": "string"},
                    "screen": {"type": "string", "description": "무엇을 그림으로 보일지"},
                },
            },
        },
    },
}

REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["scores", "fixes", "overall"],
    "properties": {
        "scores": {
            "type": "object",
            "additionalProperties": False,
            "required": ["구성", "설명력", "화면", "분량", "일관성", "완성도"],
            "properties": {k: {"type": "number"} for k in
                           ("구성", "설명력", "화면", "분량", "일관성", "완성도")},
        },
        "fixes": {"type": "array", "items": {"type": "string"}},
        "overall": {"type": "number"},
    },
}


def _client(key: str):
    try:
        from openai import OpenAI
    except ImportError as err:  # noqa: BLE001
        raise RuntimeError(
            "openai 패키지가 없습니다 — conda run -n penv3.13-insait pip install openai"
        ) from err
    return OpenAI(api_key=key)


def _structured(client, model: str, system: str, user: list | str,
                json_schema: dict | None) -> tuple[Any, dict]:
    """구조화 생성 1회 — (파싱된 내용, usage). json_schema 가 없으면 원문 텍스트."""
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    if json_schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "result", "strict": True, "schema": json_schema},
        }
    res = client.chat.completions.create(**kwargs)
    text = res.choices[0].message.content or ""
    usage = {}
    if getattr(res, "usage", None):
        usage = {"inputTokens": res.usage.prompt_tokens,
                 "outputTokens": res.usage.completion_tokens}
    return (json.loads(text) if json_schema is not None else text), usage


# ── 작업 3종 — 모델은 내용만, 파일 기입은 여기서 ────────────────────────────────
def _apply_draft(ep_dir: Path, data: dict) -> list[str]:
    """생성 내용을 회차 폴더에 결정적으로 기입한다 (경로·params 는 우리 규약 그대로)."""
    from ..scaffold import _inject_params

    written = []
    if data.get("plan_md"):
        (ep_dir / "plan.md").write_text(data["plan_md"], encoding="utf-8", newline="\n")
        written.append("plan.md")
    if data.get("facts_md"):
        (ep_dir / "facts.md").write_text(data["facts_md"], encoding="utf-8", newline="\n")
        written.append("facts.md")

    scenes_file = ep_dir / "scenes.json"
    doc = schema.Document.load(scenes_file)
    clips = doc.data["render"]["motion"]["clips"]
    by_id = {c.get("id"): c for c in clips}
    course_id = ep_dir.name.rsplit("-", 1)[0]
    course_file = ep_dir.parent / course_id / "course.json"
    palette = (schema.load_json(course_file).get("palette", {})
               if course_file.exists() else {})
    for item in data.get("clips", []):
        cid = item.get("id")
        if not cid:
            continue
        clip = by_id.get(cid)
        if clip is None:  # 골격에 없던 구간 — 끝에 붙이고 화면 메모를 주석 필드로
            clip = {"id": cid, "file": "", "before": "end", "narration": ""}
            _inject_params(clip, palette, ep_dir)
            clips.append(clip)
            by_id[cid] = clip
        clip["narration"] = item.get("narration", "")
        if item.get("screen"):
            clip["_화면메모"] = item["screen"]  # `_` 주석 필드 — 엔진 무관, 사람이 읽는다
    doc.save()
    written.append("scenes.json")
    return written


def _review_images(episode_id: str) -> list[dict]:
    frames_dir = OUT_ROOT / episode_id / "frames"
    out = []
    for f in sorted(frames_dir.glob("review-*.jpg"))[:5]:
        b64 = base64.b64encode(f.read_bytes()).decode()
        out.append({"type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    return out


def make_work(kind: str, episode_id: str, payload: dict[str, Any],
              projects_root: Path, *, key: str, model: str,
              client_factory: Callable | None = None) -> Callable[[], Iterator[dict]]:
    """잡 큐에 실을 work 제너레이터 — claude 경로와 같은 이벤트 계약."""

    def work() -> Iterator[dict[str, Any]]:
        yield {"kind": "log", "line": f"에이전트 {kind} 시작 (openai · {model}) — {episode_id}"}
        client = (client_factory or _client)(key)
        ep_dir = projects_root / episode_id

        if kind == "draft":
            course_id = episode_id.rsplit("-", 1)[0]
            course_file = ep_dir.parent / course_id / "course.json"
            course = schema.load_json(course_file) if course_file.exists() else {}
            user = (f"강좌: {course.get('title', course_id)} / {course.get('tagline', '')}\n"
                    f"대상: {course.get('audience', '')}\n"
                    f"이번 회차 주제(brief): {payload.get('brief', '')}\n"
                    f"근거 문서: {payload.get('sourceDocs', [])}\n"
                    "구성표·근거표·클립별 내레이션을 만들어라.")
            yield {"kind": "log", "line": "구성표·내레이션 생성 중…"}
            data, usage = _structured(client, model, LECTURE_RULES, user, DRAFT_SCHEMA)
            written = _apply_draft(ep_dir, data)
            yield {"kind": "log",
                   "line": f"기입 완료: {', '.join(written)} (클립 {len(data.get('clips', []))}개)"}

        elif kind == "diagram":
            rules = ("당신은 모션 그래픽 html 을 만든다. CSS 키프레임만 쓴다(rAF·<video> 금지 "
                     "— 스크럽 렌더 제약). 공용 _base.css·_params.js 를 상대 참조한다. "
                     "발화시각에 등장 delay 를 맞춘다. html 전문만 출력한다.")
            user = (f"설명하려는 것: {payload.get('describe', '')}\n"
                    f"해당 내레이션: {payload.get('narration', '')}\n"
                    f"클립 id: {payload.get('clipId', '')}")
            yield {"kind": "log", "line": "도식 html 생성 중…"}
            html, usage = _structured(client, model, rules, user, None)
            name = f"{payload.get('clipId') or 'diagram'}.html"
            target = ep_dir / "motion" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(html.strip(), encoding="utf-8", newline="\n")
            yield {"kind": "log", "line": f"기입 완료: motion/{name}"}

        else:  # review — 완성본 프레임만 보고 채점 ("만든 쪽이 채점하지 않는다")
            rules = ("당신은 제작 컨텍스트가 없는 평가자다. 첨부된 완성본 검수 프레임만 보고 "
                     "6항목(구성·설명력·화면·분량·일관성·완성도)을 1~5로 채점하고 고칠 것을 "
                     "적는다. 낮은 점수를 감추지 않는다.")
            images = _review_images(episode_id)
            if not images:
                yield {"kind": "log", "line": "검수 프레임이 없습니다 — 먼저 빌드하세요"}
                return
            user = [{"type": "text", "text": f"회차 {episode_id} 의 검수 프레임 {len(images)}장"},
                    *images]
            yield {"kind": "log", "line": f"프레임 {len(images)}장 평가 중…"}
            data, usage = _structured(client, model, rules, user, REVIEW_SCHEMA)
            out = OUT_ROOT / episode_id / "review-agent.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
            yield {"kind": "log",
                   "line": f"평가 완료 — overall {data.get('overall')} · 고칠 것 "
                           f"{len(data.get('fixes', []))}건 → out/{episode_id}/review-agent.json"}

        from .runner import _record_usage

        _record_usage(kind, episode_id, {"provider": "openai", "model": model, **usage})
        yield {"kind": "log", "line": f"에이전트 {kind} 완료 (토큰 "
                                      f"{usage.get('inputTokens', 0)}+{usage.get('outputTokens', 0)})"}

    return work
