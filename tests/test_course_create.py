"""강좌 개설 — 템플릿 카피·공용 참조 재계산·후속 스캐폴딩 일관성 (2단계)."""

import shutil

import pytest
from fastapi.testclient import TestClient

from core import ENGINE_DIR, FIXTURES_DIR, paths, schema, validate
from core.scaffold import scaffold_course, scaffold_episode
from api.main import app

client = TestClient(app)


@pytest.fixture
def root(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    shutil.copytree(FIXTURES_DIR, root)
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(root))
    return root


def test_scaffold_course_and_episode_chain(root):
    d = scaffold_course(root, "cloud-basics", title="클라우드 기본개념",
                        tagline="개념 하나를, 5분에",
                        voice={"provider": "edge", "lang": "ko", "gender": "female", "rate": "+8%"},
                        palette={"brand": "#0EA5E9", "brandSoft": "#7DD3FC", "bg": "#07121C"})
    course = schema.load_json(d / "course.json")
    assert course["course"] == "cloud-basics"
    assert course["render"]["watermark"]["text"] == "클라우드 기본개념"
    assert course["render"]["brand"] == "#0EA5E9"  # palette ↔ render 동기화
    assert course["render"]["bgm"] == "assets/bgm/mixkit-623-loop.mp3"  # 엔진 루트 기준

    # intro/stinger 카피 + 공용 _base.css 참조가 목적지 기준으로 재계산됐다
    rel = paths.relpath(ENGINE_DIR / "motion", d)
    intro = (d / "course-intro.html").read_text(encoding="utf-8")
    assert f'"{rel}/_base.css"' in intro and '"../../motion/_' not in intro

    # 개설 직후 회차 스캐폴딩 → 일관성 0건 (개설→회차 생성 체인이 규약을 지킨다)
    ep = scaffold_episode(root, "cloud-basics", 1, title="클라우드란", subtitle="빌려 쓴다는 것")
    scenes = schema.load_json(ep / "scenes.json")
    assert validate.consistency(scenes, schema.load_json(d / "course.json")) == []
    clips = {c["id"]: c for c in scenes["render"]["motion"]["clips"]}
    assert clips["title"]["params"]["brand"] == "#0EA5E9"


def test_create_course_api(root):
    r = client.post("/api/courses", json={"course": "new-course", "title": "새 강좌"})
    assert r.status_code == 201 and r.json()["id"] == "new-course"
    assert any(c["id"] == "new-course" for c in client.get("/api/courses").json())
    assert client.post("/api/courses", json={"course": "new-course", "title": "x"}).status_code == 409
    assert client.post("/api/courses", json={"course": "한글id", "title": "x"}).status_code == 422
    assert client.post("/api/courses", json={"course": "ok-id"}).status_code == 422
