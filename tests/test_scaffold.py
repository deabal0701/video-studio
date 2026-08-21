"""회차 스캐폴딩 — course 주입·경로 기입·일관성 0건 (2단계)."""

import shutil

import pytest
from fastapi.testclient import TestClient

from core import FIXTURES_DIR, schema, validate
from core.scaffold import scaffold_episode
from api.main import app

client = TestClient(app)


@pytest.fixture
def root(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    shutil.copytree(FIXTURES_DIR, root)
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(root))
    return root


def test_scaffold_injects_course_identity(root):
    ep_dir = scaffold_episode(root, "hr-basics", 2)
    assert ep_dir.name == "hr-basics-02"  # 커리큘럼의 id 를 그대로 쓴다
    scenes = schema.load_json(ep_dir / "scenes.json")
    course = schema.load_json(root / "hr-basics" / "course.json")

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


def test_scaffold_duplicate_raises(root):
    scaffold_episode(root, "hr-basics", 2)
    with pytest.raises(FileExistsError):
        scaffold_episode(root, "hr-basics", 2)


def test_scaffold_new_n_registers_in_course(root):
    scaffold_episode(root, "hr-basics", 9, title="보너스", subtitle="부록")
    course = schema.load_json(root / "hr-basics" / "course.json")
    added = [e for e in course["episodes"] if e["n"] == 9]
    assert added and added[0]["id"] == "hr-basics-09" and added[0]["title"] == "보너스"


def test_create_episode_api(root):
    r = client.post("/api/courses/hr-basics/episodes", json={"n": 2})
    assert r.status_code == 201 and r.json()["id"] == "hr-basics-02"
    # 목록 캐시 즉시 갱신 — 보드에 바로 나타난다
    board = client.get("/api/courses/hr-basics/episodes").json()
    wip = [b for b in board if b["id"] == "hr-basics-02"]
    # 파생 상태는 전역 engine/out 을 본다 — 같은 id 의 산출물이 남아 있으면 done 으로 보인다
    assert wip and wip[0]["state"] in ("wip", "done")
    # 중복 생성 409
    assert client.post("/api/courses/hr-basics/episodes", json={"n": 2}).status_code == 409
    assert client.post("/api/courses/hr-basics/episodes", json={}).status_code == 422


def test_tts_sample_endpoint_mocked(root, monkeypatch):
    import core.engine_io as engine_io

    fake = root / "sample.mp3"
    fake.write_bytes(b"ID3fake")
    monkeypatch.setattr(engine_io, "tts_sample", lambda text, **kw: fake)
    r = client.post("/api/tts/sample", json={"text": "안녕하세요"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/mpeg")
    assert r.content == b"ID3fake"
