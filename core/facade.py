"""facade — 화면이 부르는 유스케이스 전부 (07_desktop 5-2 — 구 api 라우터 로직 이관).

04_api 의 REST 표가 이 모듈의 계약으로 1:1 승계된다: 경로 → 메서드, HTTP 상태 → 예외.
UI(Qt)와 테스트는 Studio 를 직접 호출한다 — HTTP 없음.

etag 낙관적 잠금(구 If-Match)은 그대로 유지된다: 파일 SSOT 라 앱 밖(에디터·Claude Code)의
동시 편집이 실재하기 때문이다. 쓰기 메서드는 etag 를 요구하고, 불일치면 EtagMismatch 에
현재 내용을 실어 던진다 (화면이 diff 를 보여 주고 사람이 병합).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Iterator

from pydantic import ValidationError

from . import agents, engine_io, env, library, media_ops, paths, schema, status, validate
from .indexer import Index
from .jobs import JobQueue
from .schema import Document
from .status import OUT_ROOT


# ── 예외 — 구 HTTP 상태의 승계 (04_api 헤더 주석) ────────────────────────────
class StudioError(Exception):
    """{code, message, hint?} — 구 에러 응답 구조. status 는 구 HTTP 코드(참고용)."""

    status = 400

    def __init__(self, code: str, message: str, hint: str | None = None, **extra: Any):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.extra = extra

    def detail(self) -> dict[str, Any]:
        d = {"code": self.code, "message": self.message, **self.extra}
        if self.hint:
            d["hint"] = self.hint
        return d


class NotFound(StudioError):
    status = 404


class Invalid(StudioError):
    status = 422


class Conflict(StudioError):
    status = 409


class EtagRequired(StudioError):
    status = 428


class EtagMismatch(Conflict):
    """현재 etag·내용 동봉 — 화면이 diff 를 보여 준다."""


class NotBuilt(Conflict):
    """완성본 없음 — 먼저 빌드해야 하는 조회."""


class Forbidden(StudioError):
    status = 403


class AgentDisabled(Forbidden):
    pass


class UpstreamError(StudioError):
    status = 502


def _etag(file: Path) -> str:
    st = file.stat()
    return hashlib.sha1(f"{st.st_mtime_ns}:{st.st_size}".encode()).hexdigest()[:16]


def path_issues(body: dict[str, Any], scenes_dir: Path) -> list[str]:
    """저장 시 경로 실존 검사 — 02 규칙 5 ("사전점검의 사각을 앱이 메운다").

    params.src 가 깨져도 엔진은 조용히 검은 배경을 만들므로 저장 결과에서 바로 알린다.
    """
    issues: list[str] = []
    for clip in body.get("render", {}).get("motion", {}).get("clips", []):
        cid = clip.get("id", "?")
        if clip.get("video") and not paths.invert(paths.RefKind.BROLL, clip["video"]).exists():
            issues.append(f"{cid}: B롤 없음 — {clip['video']}")
        if clip.get("file"):
            html = paths.invert(paths.RefKind.MOTION, clip["file"], scenes_dir=scenes_dir)
            if not html.exists():
                issues.append(f"{cid}: 템플릿 없음 — {clip['file']}")
                continue
            for key in ("src", "fontUrl"):
                v = (clip.get("params") or {}).get(key)
                if v and not paths.invert(paths.RefKind.HTML_ASSET, v, html_file=html).exists():
                    issues.append(f"{cid}: params.{key} 가 가리키는 파일 없음 — {v} (조용히 검은 배경/폰트 폴백)")
    return issues


class Studio:
    """유스케이스 진입점 — root/queue/index 를 주입할 수 있어 단독 테스트가 된다.

    root=None 이면 호출 시점의 env.projects_root() 를 쓴다 (테스트의 환경변수 전환 지원).
    """

    def __init__(self, root: Path | None = None, *, queue: JobQueue | None = None,
                 index: Index | None = None):
        self._root = Path(root).resolve() if root else None
        self._queue = queue
        self._indexes: dict[Path, Index] = {}
        if index is not None:
            self._indexes[self.root] = index

    # ── 문맥 ────────────────────────────────────────────────────────────────
    @property
    def root(self) -> Path:
        return self._root or env.projects_root()

    @property
    def queue(self) -> JobQueue:
        if self._queue is None:
            self._queue = JobQueue()
        return self._queue

    def index(self) -> Index:
        root = self.root
        if root not in self._indexes:
            self._indexes[root] = Index(root)
        return self._indexes[root]

    def episode_dir(self, eid: str) -> Path:
        d = self.root / eid
        if not (d / "scenes.json").exists():
            raise NotFound("episode_not_found", eid)
        return d

    # ── 조회 (04 강좌·회차) ─────────────────────────────────────────────────
    def _episode_summary(self, eid: str) -> dict:
        return {"id": eid, **status.episode_status(self.root / eid)}

    def list_courses(self) -> list[dict]:
        """구조는 SQLite 캐시에서, 상태 배지는 계산으로 (파생 상태 저장 금지 — 02)."""
        from . import kinds as kinds_mod

        out = []
        for c in self.index().courses():
            if c.get("single"):
                out.append(c)
                continue
            episodes = [self._episode_summary(e) for e in c["episodes"]]
            # 브랜드 색·종류 — 화면이 프로젝트 아이콘을 그 색으로 칠한다 (app/icons.py)
            brand, kind = "", None
            try:
                doc = schema.load_json(self.root / c["id"] / "course.json")
                brand = (doc.get("palette") or {}).get("brand", "")
                kind = doc.get("kind")
            except Exception:  # noqa: BLE001 — 색을 못 읽어도 목록은 떠야 한다
                pass
            # 단발 종류(홍보 등)가 1편뿐이면 그 id — 대시보드가 보드를 건너뛰고 직행한다
            sole = None
            if kind and not kinds_mod.get(kind)["series"] and len(episodes) == 1:
                sole = episodes[0]["id"]
            out.append({"id": c["id"], "title": c["title"], "episodeCount": c["episodeCount"],
                        "scaffolded": len(episodes), "brand": brand, "kind": kind,
                        "soleEpisode": sole,
                        "done": sum(1 for e in episodes if e["state"] == "done")})
        return out

    def get_course(self, cid: str) -> dict:
        file = self.root / cid / "course.json"
        if not file.exists():
            raise NotFound("course_not_found", cid)
        doc = schema.load_json(file)
        badges = {e["id"]: self._episode_summary(e["id"]) if (self.root / e["id"]).exists()
                  else {"id": e["id"], "state": "empty", "final": [], "stale": False}
                  for e in doc.get("episodes", [])}
        return {"course": doc, "etag": _etag(file), "episodes": badges}

    def course_board(self, cid: str) -> list[dict]:
        return list(self.get_course(cid)["episodes"].values())

    def get_episode(self, eid: str) -> dict:
        d = self.episode_dir(eid)
        file = d / "scenes.json"
        return {"scenes": schema.load_json(file), "etag": _etag(file),
                **status.episode_status(d)}

    # ── 저장 (etag 낙관적 잠금) ──────────────────────────────────────────────
    def _save_with_etag(self, file: Path, body: dict[str, Any], etag: str | None) -> str:
        if not etag:
            raise EtagRequired("if_match_required", "etag 가 필요합니다",
                               hint="조회 결과의 etag 를 넣으세요")
        current = _etag(file)
        if etag != current:
            raise EtagMismatch("etag_mismatch", "파일이 밖에서 바뀌었습니다 — diff 를 보고 병합하세요",
                               etag=current, current=schema.load_json(file))
        doc = Document.load(file)
        doc.data = body
        doc.save()
        return _etag(file)

    def put_course(self, cid: str, body: dict[str, Any], etag: str | None) -> dict:
        file = self.root / cid / "course.json"
        if not file.exists():
            raise NotFound("course_not_found", cid)
        try:
            model = schema.Course.model_validate(body)
        except ValidationError as err:
            raise Invalid("invalid_course", str(err.errors()[:3])) from err
        if model.course != cid:
            raise Invalid("id_mismatch", f"course '{model.course}' ≠ 폴더명 '{cid}'")
        new_etag = self._save_with_etag(file, body, etag)
        problems = {}
        for ep in body.get("episodes", []):
            scenes_file = self.root / ep["id"] / "scenes.json"
            if scenes_file.exists():
                found = validate.consistency(schema.load_json(scenes_file), body)
                if found:
                    problems[ep["id"]] = found
        return {"etag": new_etag, "consistency": problems}

    def put_episode(self, eid: str, body: dict[str, Any], etag: str | None) -> dict:
        d = self.episode_dir(eid)
        file = d / "scenes.json"
        try:
            model = schema.Scenes.model_validate(body)
        except ValidationError as err:
            raise Invalid("invalid_scenes", str(err.errors()[:3])) from err
        if model.id != eid:
            raise Invalid("id_mismatch", f"id '{model.id}' ≠ 폴더명 '{eid}' — out 폴더가 갈라진다")
        new_etag = self._save_with_etag(file, body, etag)
        course_file = d.parent / eid.rsplit("-", 1)[0] / "course.json"
        problems = (validate.consistency(body, schema.load_json(course_file))
                    if course_file.exists() else [])
        return {"etag": new_etag, "consistency": problems,
                "pathIssues": path_issues(body, d)}

    def sync_course(self, eid: str, etag: str | None) -> dict:
        """voice·render 를 course 값으로 (02: 어긋나면 경고 배지 + 이 버튼)."""
        d = self.episode_dir(eid)
        course_file = d.parent / eid.rsplit("-", 1)[0] / "course.json"
        if not course_file.exists():
            raise NotFound("course_not_found", eid)
        file = d / "scenes.json"
        if not etag:
            raise EtagRequired("if_match_required", "etag 가 필요합니다")
        if etag != _etag(file):
            raise EtagMismatch("etag_mismatch", "파일이 밖에서 바뀌었습니다")
        course = schema.load_json(course_file)
        doc = Document.load(file)
        if course.get("voice"):
            doc.data["voice"] = dict(course["voice"])
        doc.data.setdefault("render", {}).update(course.get("render", {}))
        doc.save()
        return {"etag": _etag(file),
                "consistency": validate.consistency(doc.data, course)}

    # ── 개설·스캐폴딩 ────────────────────────────────────────────────────────
    def create_course(self, body: dict[str, Any]) -> dict:
        import re

        from .scaffold import scaffold_course

        cid = str(body.get("course", "")).strip()
        title = str(body.get("title", "")).strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", cid):
            raise Invalid("bad_id", "강좌 id 는 kebab-case (영소문자·숫자·하이픈)")
        if not title:
            raise Invalid("bad_request", "title 필요")
        try:
            d = scaffold_course(self.root, cid, title=title,
                                tagline=body.get("tagline", ""),
                                audience=body.get("audience", ""),
                                episode_length=body.get("episodeLength"),
                                voice=body.get("voice"), palette=body.get("palette"),
                                bgm=body.get("bgm"), kind=body.get("kind"),
                                episodes=body.get("episodes"))
        except FileExistsError as err:
            raise Conflict("already_exists", str(err)) from err
        self.index().rescan()
        return {"id": d.name, "etag": _etag(d / "course.json")}

    def create_episode(self, cid: str, n: int, *, title: str | None = None,
                       subtitle: str | None = None) -> dict:
        from .scaffold import scaffold_episode

        if not (self.root / cid / "course.json").exists():
            raise NotFound("course_not_found", cid)
        if not isinstance(n, int) or n < 1:
            raise Invalid("bad_request", "n(회차 번호) 필요")
        try:
            ep_dir = scaffold_episode(self.root, cid, n, title=title, subtitle=subtitle)
        except FileExistsError as err:
            raise Conflict("already_exists", str(err)) from err
        self.index().rescan()
        return {"id": ep_dir.name, "etag": _etag(ep_dir / "scenes.json")}

    def apply_brand_kit(self, cid: str) -> dict:
        from .scaffold import copy_brand_kit

        d = self.root / cid
        if not (d / "course.json").exists():
            raise NotFound("course_not_found", cid)
        return {"copied": copy_brand_kit(d)}

    # ── 구성표 (plan.md) ─────────────────────────────────────────────────────
    def get_plan(self, eid: str) -> dict:
        file = self.episode_dir(eid) / "plan.md"
        if not file.exists():
            raise NotFound("plan_not_found", eid)
        return {"markdown": file.read_text(encoding="utf-8"), "etag": _etag(file)}

    def put_plan(self, eid: str, markdown: str, etag: str | None) -> dict:
        file = self.episode_dir(eid) / "plan.md"
        if file.exists():
            if not etag:
                raise EtagRequired("if_match_required", "etag 가 필요합니다")
            if etag != _etag(file):
                raise EtagMismatch("etag_mismatch", "plan.md 가 밖에서 바뀌었습니다",
                                   current=file.read_text(encoding="utf-8"))
        file.write_text(str(markdown), encoding="utf-8", newline="\n")
        return {"etag": _etag(file)}

    def plan_apply(self, eid: str) -> dict:
        from . import plan_apply as pa

        d = self.episode_dir(eid)
        try:
            out = pa.apply(d)
        except FileNotFoundError as err:
            raise NotFound("plan_not_found", str(err)) from err
        return {**out, "etag": _etag(d / "scenes.json")}

    # ── 빌드·잡 ─────────────────────────────────────────────────────────────
    def preflight(self, eid: str) -> dict:
        return {"findings": engine_io.inspect(self.episode_dir(eid))["preflight"]}

    def inspect(self, eid: str) -> dict:
        """inspect.js 원본 JSON — ⑤ 에디터 재료 (받는 키·audioCache 실측·media)."""
        return engine_io.inspect(self.episode_dir(eid))

    def submit_build(self, eid: str, *, only: str | None = None,
                     variant: str | None = None) -> dict:
        d = self.episode_dir(eid)
        job = self.queue.submit(eid, d / "scenes.json", only=only, variant=variant)
        return {"jobId": job.id}

    @staticmethod
    def _job_view(job) -> dict[str, Any]:
        return {"jobId": job.id, "episodeId": job.episode_id, "state": job.state.value,
                "error": job.error}

    def jobs(self) -> list[dict]:
        return [self._job_view(j) for j in self.queue.list()]

    def job(self, jid: str) -> dict:
        job = self.queue.get(jid)
        if not job:
            raise NotFound("job_not_found", jid)
        return self._job_view(job)

    def cancel_job(self, jid: str) -> dict:
        if not self.queue.get(jid):
            raise NotFound("job_not_found", jid)
        return {"canceled": self.queue.cancel(jid)}

    def job_events(self, jid: str) -> Iterator[dict[str, Any]]:
        """지나간 이벤트부터 재생하고 종료까지 블로킹 — qtbridge 가 워커 스레드에서 소비."""
        if not self.queue.get(jid):
            raise NotFound("job_not_found", jid)
        return self.queue.subscribe(jid)

    # ── 검수 ────────────────────────────────────────────────────────────────
    def frames(self, eid: str, *, preset: str | None = None, t: float | None = None) -> dict:
        d = self.episode_dir(eid)
        try:
            if t is not None:
                picked = [{"t": t, "file": media_ops.extract_frame(eid, t).name}]
            elif preset == "review":
                picked = media_ops.review_frames(eid, d)
            else:
                raise Invalid("bad_request", "preset=review 또는 t=<초> 필요")
        except FileNotFoundError as err:
            raise NotBuilt("not_built", str(err), hint="먼저 빌드하세요") from err
        return {"frames": [{**f, "path": str(OUT_ROOT / eid / "frames" / f["file"])}
                           for f in picked]}

    def silence(self, eid: str) -> dict:
        self.episode_dir(eid)
        try:
            silences = media_ops.detect_silence(eid)
        except FileNotFoundError as err:
            raise NotBuilt("not_built", str(err), hint="먼저 빌드하세요") from err
        return {"silences": silences,
                "total": round(sum(s["duration"] for s in silences), 2),
                "suspect": [s for s in silences if s["cause"] == "clip-end"]}

    def subtitle_check(self, eid: str) -> dict:
        from . import deliverables as deliv

        return deliv.subtitle_check(self.episode_dir(eid))

    def _title_frame(self, episode_dir: Path) -> str | None:
        """타이틀 카드 시각의 프레임 경로 — 완성본이 있어야 한다."""
        eid = episode_dir.name
        if media_ops.final_mp4(eid) is None:
            return None
        starts = media_ops.clip_start_times(episode_dir)
        scenes = schema.load_json(episode_dir / "scenes.json")
        for clip in scenes.get("render", {}).get("motion", {}).get("clips", []):
            if str(clip.get("file", "")).endswith("course-intro.html"):
                t = starts[clip["id"]] + 1.2
                return str(media_ops.extract_frame(eid, round(t, 1)))
        return None

    def consistency(self, eid: str) -> dict:
        """voice/render ≡ course 대조 + 직전 회차 타이틀 프레임 쌍."""
        d = self.episode_dir(eid)
        course_id = eid.rsplit("-", 1)[0]
        course_file = d.parent / course_id / "course.json"
        if not course_file.exists():
            return {"course": None, "problems": [], "single": True, "titlePair": None}
        course = schema.load_json(course_file)
        problems = validate.consistency(schema.load_json(d / "scenes.json"), course)
        pair = None
        entry = next((e for e in course.get("episodes", []) if e.get("id") == eid), None)
        if entry:
            prev = next((e for e in course.get("episodes", [])
                         if e.get("n") == entry.get("n", 0) - 1), None)
            if prev and (d.parent / prev["id"] / "scenes.json").exists():
                try:
                    pair = {"prevId": prev["id"],
                            "prev": self._title_frame(d.parent / prev["id"]),
                            "current": self._title_frame(d)}
                except Exception:  # noqa: BLE001 — 프레임 실패는 쌍 없음으로
                    pair = None
        return {"course": course_id, "problems": problems, "single": False, "titlePair": pair}

    def get_review(self, eid: str) -> dict:
        self.episode_dir(eid)
        f = OUT_ROOT / eid / "review.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"items": {}}

    def put_review(self, eid: str, body: dict[str, Any]) -> dict:
        self.episode_dir(eid)
        f = OUT_ROOT / eid / "review.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        record = {"items": body.get("items", {}), "note": body.get("note", ""),
                  "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S")}
        f.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8", newline="\n")
        return record

    def bg_frame(self, eid: str, *, video: str, video_start: float, clip_file: str) -> dict:
        """B롤 프레임 → bg/ 저장 → 그 html 기준 src 상대경로 (⑤ title 특수 버튼)."""
        d = self.episode_dir(eid)
        source = paths.invert(paths.RefKind.BROLL, video)
        if not source.exists():
            raise NotFound("broll_not_found", video)
        html = paths.invert(paths.RefKind.MOTION, clip_file, scenes_dir=d)
        if not html.exists():
            raise NotFound("template_not_found", clip_file)
        out = media_ops.extract_bg_frame(d, source, video_start)
        return {"src": paths.compute(paths.RefKind.HTML_ASSET, out, html_file=html),
                "file": out.name}

    # ── 배포 ────────────────────────────────────────────────────────────────
    def deliverables(self, eid: str) -> dict:
        from . import deliverables as deliv

        return deliv.build(self.episode_dir(eid), self.root)

    def save_deliverables(self, eid: str, *, title: str, description: str) -> dict:
        from . import deliverables as deliv

        out = deliv.write_youtube_md(self.episode_dir(eid), title, description)
        return {"file": out.name}

    # ── 자산·템플릿·TTS ─────────────────────────────────────────────────────
    def assets(self, kind: str = "broll") -> list[dict]:
        try:
            return library.list_assets(kind)
        except ValueError as err:
            raise Invalid("bad_kind", str(err)) from err

    def add_asset(self, *, kind: str, url: str, license: str, source: str | None = None,
                  name: str | None = None, note: str = "") -> dict:
        try:
            return library.add_asset(kind, url, license=license, source=source,
                                     name=name, note=note)
        except ValueError as err:
            raise Invalid("invalid", str(err)) from err
        except RuntimeError as err:
            raise UpstreamError("fetch_failed", str(err),
                                hint="허용 호스트와 URL 을 확인하세요") from err

    def asset_path(self, kind: str, name: str) -> Path:
        root = library.KIND_DIRS.get(kind)
        if root is None:
            raise Invalid("bad_kind", kind)
        target = (root / name).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            raise NotFound("asset_not_found", name)
        return target

    def _template_scope_dir(self, scope: str) -> Path | None:
        if scope == "common":
            return None
        d = (self.root / scope).resolve()
        if not d.is_relative_to(self.root.resolve()) or not d.exists():
            raise NotFound("episode_not_found", scope)
        return d

    def templates(self, scope: str = "common") -> list[dict]:
        templates = engine_io.list_templates(self._template_scope_dir(scope))
        return [{"file": name, "scope": t["scope"], "params": t["params"]}
                for name, t in templates.items()]

    def template_preview(self, file: str, scope: str = "common") -> str:
        """preview.js 자체완결 html — **갤러리 목록의 파일명만 허용** (화이트리스트).

        preview.js 는 절대경로도 그대로 읽으므로(5-0 이전 HTTP 시절 실측 결함) 여기서 막는다.
        """
        project_dir = self._template_scope_dir(scope)
        allowed = set(engine_io.list_templates(project_dir))
        if file not in allowed:
            raise NotFound("template_not_found", file,
                           hint="갤러리 목록의 파일명만 허용됩니다")
        try:
            return engine_io.preview(file, project_dir)
        except RuntimeError as err:
            raise NotFound("template_not_found", str(err)[-300:]) from err

    def tts_sample(self, *, text: str = "연결 테스트입니다.", lang: str = "ko",
                   gender: str = "female", voice: str | None = None) -> Path:
        try:
            return engine_io.tts_sample(text, lang=lang, gender=gender, voice=voice)
        except Exception as err:  # noqa: BLE001 — 네트워크·엔진 사정을 그대로 알린다
            raise UpstreamError("tts_failed", str(err)[-500:],
                                hint="네트워크와 edge-tts 를 확인하세요") from err

    # ── 영상 종류 (강의·홍보·광고·매뉴얼·일반) ──────────────────────────────
    def video_kinds(self) -> list[dict[str, Any]]:
        from . import kinds

        return [{"id": k, **v} for k, v in kinds.KINDS.items()]

    # ── 목소리 (카탈로그 + 로컬 샘플 캐시) ───────────────────────────────────
    def voice_catalog(self, provider: str = "edge") -> dict:
        """제공자별 목소리 목록 — 키가 없으면 사유와 함께 available=False 로 돌려준다."""
        from . import voices

        return voices.catalog(provider)

    def voice_sample(self, provider: str, voice: str, *, gender: str = "female") -> Path:
        """미리듣기 mp3 — 캐시에 있으면 즉시, 없으면 한 번만 합성해 넣는다."""
        from . import voices

        try:
            return voices.ensure_sample(provider, voice, gender=gender)
        except Exception as err:  # noqa: BLE001 — 네트워크·키 사정을 그대로 알린다
            raise UpstreamError("tts_failed", str(err)[-500:],
                                hint="설정 화면에서 키와 연결을 확인하세요") from err

    def voice_samples_build(self, provider: str) -> dict:
        """그 제공자의 목소리를 전부 한 번씩 만들어 둔다 — 이후 미리듣기는 공짜·즉시."""
        from . import voices

        return voices.build_all(provider)

    # ── 파일 접근 (구 정적 서빙 — 데스크톱은 경로 반환) ──────────────────────
    def media_path(self, eid: str, rel: str) -> Path:
        base = (OUT_ROOT / eid).resolve()
        target = (base / rel).resolve()
        if not target.is_relative_to(base):
            raise Forbidden("forbidden", rel)
        if not target.is_file():
            raise NotFound("media_not_found", rel)
        return target

    # ── 에이전트 (D15 — 키 게이트는 agents 모듈) ─────────────────────────────
    def agent_status(self) -> dict:
        return agents.agent_enabled()

    def agent_usage(self) -> dict:
        return agents.usage_summary()

    # ── 설정·진단 (07 설정 화면 — 키 정본은 홈 공용 .env) ────────────────────
    def settings(self) -> dict[str, Any]:
        from . import config

        return {**config.read_all(), "keys": config.KEYS,
                "secretKeys": sorted(config.SECRET_KEYS), "settings": config.SETTINGS}

    def save_settings(self, updates: dict[str, str]) -> dict[str, Any]:
        from . import config

        # 셸 환경변수가 이기는 규약이라, 저장 직후 화면이 실제 적용값을 다시 읽게 한다
        path = config.write_home_env(updates)
        return {"file": str(path), **config.read_all()}

    def diagnose(self) -> list[dict[str, Any]]:
        from . import config

        return config.diagnose()

    def check_tts(self) -> dict[str, Any]:
        from . import config

        return config.check_tts()

    def agent_submit(self, kind: str, episode_id: str, payload: dict[str, Any]) -> dict:
        gate = agents.agent_enabled()
        if not gate["enabled"]:
            raise AgentDisabled("agent_disabled", gate["reason"])
        self.episode_dir(episode_id)
        work = agents.make_agent_work(kind, episode_id, payload, self.root)
        job = self.queue.submit_agent(episode_id, work)
        return {"jobId": job.id}
