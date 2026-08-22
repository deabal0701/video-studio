"""목소리 카탈로그 + 샘플 캐시 (core/voices.py).

이 모듈의 존재 이유가 "같은 목소리를 두 번 합성하지 않는다"이므로, **캐시가 실제로
합성을 막는지**가 핵심 검사다. 네트워크·키에 의존하지 않게 엔진 호출은 가짜로 센다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core import voices


@pytest.fixture(autouse=True)
def _tmp_samples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """샘플 캐시를 임시 폴더로 — 실제 .cache 를 건드리지 않는다."""
    monkeypatch.setattr(voices, "_samples_root", lambda: tmp_path / "voice-samples")
    return tmp_path


def _fake_engine(monkeypatch: pytest.MonkeyPatch, calls: list, tmp_path: Path):
    """engine_io.tts_sample 을 가로채 호출을 세고 가짜 mp3 를 만든다."""
    from core import engine_io

    def fake(text, *, lang="ko", gender="female", voice=None, provider="edge"):
        calls.append((provider, voice))
        out = tmp_path / f"engine-{provider}-{voice}.mp3"
        out.write_bytes(b"ID3fake")
        return out

    monkeypatch.setattr(engine_io, "tts_sample", fake)


# ── 카탈로그 ─────────────────────────────────────────────────────────────────
def test_edge_catalog_is_the_measured_three():
    """edge 한국어는 3종뿐 (2026-08-22 edge_tts.list_voices 실측 — 322종 중 ko 3개)."""
    info = voices.catalog("edge")
    assert info["available"] is True
    assert [v["id"] for v in info["voices"]] == [
        "ko-KR-SunHiNeural", "ko-KR-InJoonNeural", "ko-KR-HyunsuMultilingualNeural"]
    assert info["paid"] is False


def test_unknown_provider_is_unavailable_not_crash():
    info = voices.catalog("없는제공자")
    assert info["available"] is False and info["voices"] == []
    assert "없는제공자" in info["reason"]


def test_catalog_reports_cache_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    assert all(not v["cached"] for v in voices.catalog("edge")["voices"])
    calls: list = []
    _fake_engine(monkeypatch, calls, tmp_path)
    voices.ensure_sample("edge", "ko-KR-SunHiNeural")
    cached = {v["id"]: v["cached"] for v in voices.catalog("edge")["voices"]}
    assert cached["ko-KR-SunHiNeural"] is True
    assert cached["ko-KR-InJoonNeural"] is False


# ── 캐시 ─────────────────────────────────────────────────────────────────────
def test_second_preview_does_not_synthesize_again(monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path):
    """이 모듈의 존재 이유 — 두 번째 미리듣기는 엔진을 부르지 않는다 (돈·시간)."""
    calls: list = []
    _fake_engine(monkeypatch, calls, tmp_path)
    first = voices.ensure_sample("eleven", "abc123")
    second = voices.ensure_sample("eleven", "abc123")
    assert first == second and first.is_file()
    assert calls == [("eleven", "abc123")], "캐시가 있는데 다시 합성했다"


def test_provider_reaches_the_engine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """2026-08-22 까지 engine_io.tts_sample 이 edge 로 하드코딩돼 있었다 —
    키를 넣어도 미리듣기가 언제나 edge 소리로 났다. 그 회귀를 막는다."""
    calls: list = []
    _fake_engine(monkeypatch, calls, tmp_path)
    voices.ensure_sample("azure", "ko-KR-YuJinNeural")
    assert calls == [("azure", "ko-KR-YuJinNeural")]


def test_sample_filename_survives_eleven_names():
    """eleven 이름은 'Sarah - Mature, Reassuring' 처럼 공백·쉼표가 섞인다."""
    p = voices.sample_path("eleven", "Sarah - Mature, Reassuring, Confident")
    assert p.suffix == ".mp3"
    assert not (set(p.stem) & set(' ,/\\:*?"<>|')), p.stem


def test_build_all_skips_cached_and_counts(monkeypatch: pytest.MonkeyPatch,
                                           tmp_path: Path):
    calls: list = []
    _fake_engine(monkeypatch, calls, tmp_path)
    voices.ensure_sample("edge", "ko-KR-SunHiNeural")
    calls.clear()

    r = voices.build_all("edge")
    assert r["made"] == 2 and r["cached"] == 1 and r["failed"] == []
    assert len(calls) == 2, "이미 있는 것을 다시 만들었다"
    assert r["chars"] == 2 * len(voices.SAMPLE_TEXT)

    again = voices.build_all("edge")
    assert again["made"] == 0 and again["cached"] == 3


def test_build_all_survives_one_bad_voice(monkeypatch: pytest.MonkeyPatch,
                                          tmp_path: Path):
    """한 목소리가 죽어도 나머지는 남아야 한다 — 전부 아니면 전무는 안 된다."""
    from core import engine_io

    def flaky(text, *, lang="ko", gender="female", voice=None, provider="edge"):
        if voice == "ko-KR-InJoonNeural":
            raise RuntimeError("합성 실패")
        out = tmp_path / f"{voice}.mp3"
        out.write_bytes(b"ID3fake")
        return out

    monkeypatch.setattr(engine_io, "tts_sample", flaky)
    r = voices.build_all("edge")
    assert r["made"] == 2
    assert [f["voice"] for f in r["failed"]] == ["ko-KR-InJoonNeural"]
