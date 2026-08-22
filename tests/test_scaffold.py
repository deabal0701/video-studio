"""회차 스캐폴딩 — course 주입·경로 기입·일관성 0건 (2단계)."""

import pytest

from core import schema, validate
from core.facade import Conflict, Invalid
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
