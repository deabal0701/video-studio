"""저장 유스케이스 — etag 낙관적 잠금·무손실 저장·검증 동봉 (구 If-Match 계약)."""

import pytest

from core.facade import EtagMismatch, EtagRequired, Invalid

pytestmark = pytest.mark.usefixtures("copy_root")


def test_put_requires_etag(studio):
    body = studio.get_episode("hr-basics-01")
    with pytest.raises(EtagRequired):
        studio.put_episode("hr-basics-01", body["scenes"], None)


def test_put_etag_mismatch_with_current(studio):
    body = studio.get_episode("hr-basics-01")
    with pytest.raises(EtagMismatch) as e:
        studio.put_episode("hr-basics-01", body["scenes"], "stale-etag-0000")
    assert e.value.code == "etag_mismatch"
    assert e.value.extra["current"]["id"] == "hr-basics-01"  # 클라 diff 용 현재 내용 동봉


def test_put_unchanged_body_is_lossless(copy_root, studio):
    """무수정 저장 → 파일 **바이트** 동일 (개행 포함 — CRLF 번역 회귀 방지, 07 결함 5)."""
    before = (copy_root / "hr-basics-01" / "scenes.json").read_bytes()
    body = studio.get_episode("hr-basics-01")
    out = studio.put_episode("hr-basics-01", body["scenes"], body["etag"])
    assert out["etag"]
    assert (copy_root / "hr-basics-01" / "scenes.json").read_bytes() == before


def test_put_edit_saves_and_reports_consistency(studio):
    body = studio.get_episode("hr-basics-01")
    scenes = body["scenes"]
    scenes["render"]["crf"] = 21
    out = studio.put_episode("hr-basics-01", scenes, body["etag"])
    assert out["etag"] != body["etag"]
    assert any("bgm" in p for p in out["consistency"])  # 기존 어긋남 그대로 보고
    saved = studio.get_episode("hr-basics-01")["scenes"]
    assert saved["render"]["crf"] == 21
    assert saved["_경로메모"]  # `_` 주석 보존


def test_put_id_mismatch(studio):
    body = studio.get_episode("hr-basics-01")
    with pytest.raises(Invalid) as e:
        studio.put_episode("hr-basics-01", dict(body["scenes"], id="다른-id"), body["etag"])
    assert e.value.code == "id_mismatch"


def test_put_course_reconsistency(studio):
    body = studio.get_course("hr-basics")
    course = body["course"]
    course["render"]["crf"] = 19  # 회차와 같은 값 — 새 어긋남은 없다
    out = studio.put_course("hr-basics", course, body["etag"])
    # 회차가 실존하는 hr-basics-01 만 검사 대상 — 기존 bgm 어긋남이 배지 재료로 나온다
    assert "hr-basics-01" in out["consistency"]
    assert any("bgm" in p for p in out["consistency"]["hr-basics-01"])


def test_put_course_rejects_empty_title(studio):
    """빈 이름 저장 금지 (52회차 P20).

    개설은 이름을 요구하는데 수정만 빈 이름을 받아들였다 — 저장되면 대시보드 카드·
    프로젝트 헤더·삭제 확인이 이름 없이 뜨고 `render.watermark.text` 까지 비어
    **완성본 워터마크가 사라진다**. 읽기는 계속 관대하다(옛 파일도 열려야 한다).
    """
    body = studio.get_course("hr-basics")
    doc, etag = body["course"], body["etag"]
    for bad in ("", "   "):
        with pytest.raises(Invalid) as e:
            studio.put_course("hr-basics", {**doc, "title": bad}, etag)
        assert e.value.code == "bad_request"
    # 이름이 있으면 그대로 저장된다 — 가드가 정상 저장을 막지 않는다
    out = studio.put_course("hr-basics", {**doc, "title": "이름 있음"}, etag)
    assert out["etag"] != etag
    assert studio.get_course("hr-basics")["course"]["title"] == "이름 있음"
