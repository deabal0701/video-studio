"""회차 스캐폴딩 — course 주입·경로 기입·일관성 0건 (2단계)."""

import json

import pytest

from core import schema, validate
from core.facade import Conflict, Invalid
from core import scaffold
from core.scaffold import scaffold_episode


def test_scaffold_injects_course_identity(copy_root):
    ep_dir = scaffold_episode(copy_root, "hr-basics", 2)
    assert ep_dir.name == "hr-basics-02"  # 커리큘럼의 id 를 그대로 쓴다
    scenes = schema.load_json(ep_dir / "scenes.json")
    course = schema.load_json(copy_root / "hr-basics" / "course.json")

    # 규약: voice ≡ course.voice ∧ render ⊇ course.render → 일관성 대조 0건
    assert validate.consistency(scenes, course) == []

    clips = {c["id"]: c for c in scenes["render"]["motion"]["clips"]}
    # 골격 클립 관례 (02: broll·title·hook·stinger·promise·…·outro)
    assert list(clips)[:5] == ["broll", "title", "hook", "stinger", "promise"]
    # 강좌 파일 경로가 이 저장소 기준으로 기입됐다
    assert clips["title"]["file"] == "../hr-basics/course-intro.html"
    assert clips["stinger"]["file"] == "../hr-basics/course-stinger.html"
    # 커리큘럼의 제목·부제 주입
    assert clips["title"]["params"]["title"] == "인사정보"
    assert clips["title"]["params"]["num"] == "2강"
    assert clips["stinger"]["params"]["tagline"] == course["tagline"]
    # palette 가 모든 클립 params 에 직접 (course._색메모 규약)
    for cid, clip in clips.items():
        if cid == "broll":
            continue
        assert clip["params"]["brand"] == "#F97316", cid
    # fontUrl 은 html 위치별 계산값 — 강좌 html 3단 · 공용 html 1단 상위
    assert clips["title"]["params"]["fontUrl"].endswith("engine/fonts/PretendardVariable.woff2")
    assert clips["ch1"]["params"]["fontUrl"] == "../fonts/PretendardVariable.woff2"
    assert scenes["variants"][0]["id"] == "hr-basics-02-16x9"
    assert (ep_dir / "motion").is_dir() and (ep_dir / "bg").is_dir()
    assert (ep_dir / "plan.md").exists()


def test_scaffold_duplicate_raises(copy_root):
    scaffold_episode(copy_root, "hr-basics", 2)
    with pytest.raises(FileExistsError):
        scaffold_episode(copy_root, "hr-basics", 2)


def test_scaffold_new_n_registers_in_course(copy_root):
    scaffold_episode(copy_root, "hr-basics", 9, title="보너스", subtitle="부록")
    course = schema.load_json(copy_root / "hr-basics" / "course.json")
    added = [e for e in course["episodes"] if e["n"] == 9]
    assert added and added[0]["id"] == "hr-basics-09" and added[0]["title"] == "보너스"


def test_create_episode_facade(copy_root, studio):
    out = studio.create_episode("hr-basics", 2)
    assert out["id"] == "hr-basics-02"
    # 목록 캐시 즉시 갱신 — 보드에 바로 나타난다
    board = studio.course_board("hr-basics")
    wip = [b for b in board if b["id"] == "hr-basics-02"]
    # 파생 상태는 전역 out 루트를 본다 — 같은 id 의 산출물이 남아 있으면 done 으로 보인다
    assert wip and wip[0]["state"] in ("wip", "done")
    with pytest.raises(Conflict):
        studio.create_episode("hr-basics", 2)  # 중복 생성
    with pytest.raises(Invalid):
        studio.create_episode("hr-basics", None)


def test_tts_sample_mocked(copy_root, studio, monkeypatch):
    import core.engine_io as engine_io

    fake = copy_root / "sample.mp3"
    fake.write_bytes(b"ID3fake")
    monkeypatch.setattr(engine_io, "tts_sample", lambda text, **kw: fake)
    out = studio.tts_sample(text="안녕하세요")
    assert out == fake and out.read_bytes() == b"ID3fake"


def test_single_kind_has_no_recording_scenes(tmp_path):
    """단발 종류(홍보·광고 등)의 골격에 녹화 씬이 남으면 빌드가 localhost 를 찾다 죽는다.

    2026-08-22 '한 번에 모드' E2E 실측: promo 템플릿의 scenes(웹앱 화면 녹화용)가
    그대로 내려와 `ERR_CONNECTION_REFUSED` — 단발은 모션그래픽 단독이 기본이다.
    """
    import json

    from core.scaffold import scaffold_course, scaffold_episode

    for kind in ("promo", "ad", "manual", "general"):
        cid = f"t-{kind}"
        scaffold_course(tmp_path, cid, title="t", kind=kind)
        scaffold_episode(tmp_path, cid, 1, title="t")
        sc = json.loads((tmp_path / f"{cid}-01" / "scenes.json").read_text(encoding="utf-8"))
        assert sc.get("scenes") == [], f"{kind}: 녹화 씬이 남아 있다"
        assert sc["render"]["motion"]["clips"], f"{kind}: 모션 클립이 없다"

    # 강의는 원래 골격 그대로 (scenes 없는 템플릿)
    scaffold_course(tmp_path, "t-lec", title="t", kind="lecture")
    scaffold_episode(tmp_path, "t-lec", 1, title="t")
    sc = json.loads((tmp_path / "t-lec-01" / "scenes.json").read_text(encoding="utf-8"))
    assert sc["render"]["motion"]["clips"]


def test_delete_course_removes_everything(tmp_path, monkeypatch):
    """프로젝트 삭제 = 원본(프로젝트·영상 폴더)과 파생물(out) 전부 (2026-08-22 신설)."""
    import json

    from core import facade, status

    out_root = tmp_path / "out"
    monkeypatch.setattr(status, "OUT_ROOT", out_root)
    monkeypatch.setattr(facade, "OUT_ROOT", out_root)
    s = facade.Studio(root=tmp_path)
    s.create_course({"course": "del-x", "title": "삭제 확인", "kind": "promo"})
    s.create_episode("del-x", 1, title="삭제 확인")
    (out_root / "del-x-01").mkdir(parents=True)
    (out_root / "del-x-01" / "x.mp4").write_bytes(b"x")

    r = s.delete_course("del-x")
    assert r["episodes"] == ["del-x-01"]
    assert not (tmp_path / "del-x").exists()
    assert not (tmp_path / "del-x-01").exists()
    assert not (out_root / "del-x-01").exists()
    assert all(c["id"] != "del-x" for c in s.list_courses())


def test_delete_course_rejects_bad_id(tmp_path):
    """경로 탈출 금지 — id 형식이 아니면 거부한다."""
    import pytest as _pytest

    from core import facade

    s = facade.Studio(root=tmp_path)
    for bad in ("..", "a/b", "A..B", ""):
        with _pytest.raises((facade.Invalid, facade.NotFound)):
            s.delete_course(bad)


def test_delete_episode_keeps_project_slot(tmp_path, monkeypatch):
    """영상 삭제는 폴더만 — 프로젝트 목록의 자리는 남아 다시 만들 수 있다."""
    from core import facade, status

    out_root = tmp_path / "out"
    monkeypatch.setattr(status, "OUT_ROOT", out_root)
    monkeypatch.setattr(facade, "OUT_ROOT", out_root)
    s = facade.Studio(root=tmp_path)
    s.create_course({"course": "del-y", "title": "y", "kind": "lecture",
                     "episodes": [{"n": 1, "id": "del-y-01", "title": "y1"}]})
    s.create_episode("del-y", 1)
    s.delete_episode("del-y-01")
    assert not (tmp_path / "del-y-01").exists()
    board = s.course_board("del-y")
    assert any(b["id"] == "del-y-01" and b["state"] == "empty" for b in board)
    s.create_episode("del-y", 1)   # 자리가 남았으니 다시 만들 수 있다


def test_single_video_clips_are_reanchored_to_end(tmp_path):
    """단발은 녹화 씬을 걷어내므로 거기 묶인 클립을 풀어 줘야 한다.

    compose.js 는 `before` 가 가리키는 씬이 없으면 클립을 **오류 없이 버린다**.
    풀어 주지 않으면 promo 는 intro·proof 가, manual 은 4개가 사라지고
    `before:"end"` 인 outro 한 장짜리 3.2초 영상이 나온다 (2026-08-23 화면 실측).
    """
    from core.schema import load_json

    root = tmp_path / "projects"
    root.mkdir()
    for kind, cid in (("promo", "p"), ("manual", "m")):
        scaffold.scaffold_course(root, cid, title=f"{kind} 테스트", kind=kind)
        scaffold.scaffold_episode(root, cid, 1)
        scenes = load_json(root / f"{cid}-01" / "scenes.json")
        assert scenes["scenes"] == []          # 녹화 씬은 걷어낸 채로
        clips = scenes["render"]["motion"]["clips"]
        assert len(clips) > 1, f"{kind}: 클립이 남아 있어야 한다"
        assert all(c["before"] == "end" for c in clips),             f"{kind}: 사라진 씬에 묶인 클립이 있다 — 빌드에서 조용히 버려진다"


def test_series_before_anchors_untouched(tmp_path):
    """강의 골격은 처음부터 전부 end 다 — 손대지 않는다."""
    from core.schema import load_json

    root = tmp_path / "projects"
    root.mkdir()
    scaffold.scaffold_course(root, "lec", title="강의", kind="lecture",
                             episodes=[{"n": 1, "id": "lec-01", "title": "1강"}])
    scaffold.scaffold_episode(root, "lec", 1)
    clips = load_json(root / "lec-01" / "scenes.json")["render"]["motion"]["clips"]
    assert all(c["before"] == "end" for c in clips)


def test_capture_keeps_recording_scenes(tmp_path):
    """앱 주소가 있으면 녹화 씬을 살린다 (I-2) — 없으면 지금까지처럼 걷어낸다."""
    from core.schema import load_json

    root = tmp_path / "projects"
    root.mkdir()
    scaffold.scaffold_course(root, "cap", title="녹화", kind="promo",
                             capture={"baseUrl": "http://app.example.com:8080",
                                      "login": {"user": "admin",
                                                "passwordEnv": "APP_PW"}})
    scaffold.scaffold_episode(root, "cap", 1)
    sc = load_json(root / "cap-01" / "scenes.json")
    assert sc["scenes"], "녹화 씬이 사라졌다 — 그러면 화면을 못 찍는다"
    assert sc["baseUrl"] == "http://app.example.com:8080"   # 엔진이 읽는 자리
    assert sc["capture"]["width"] == 1920
    # 비밀번호 자체는 어디에도 없다 (I-5) — 이름만
    course = load_json(root / "cap" / "course.json")
    assert course["capture"]["login"]["passwordEnv"] == "APP_PW"
    assert "password" not in json.dumps(course, ensure_ascii=False).lower().replace(
        "passwordenv", "")


def test_no_capture_still_strips_scenes(tmp_path):
    """주소가 없으면 종전대로 — 녹화할 앱이 없는데 남기면 빌드가 죽는다."""
    from core.schema import load_json

    root = tmp_path / "projects"
    root.mkdir()
    scaffold.scaffold_course(root, "plain", title="일반", kind="promo")
    scaffold.scaffold_episode(root, "plain", 1)
    sc = load_json(root / "plain-01" / "scenes.json")
    assert sc["scenes"] == [] and "baseUrl" not in sc
