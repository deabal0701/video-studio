"""미디어 라이브러리 — CATALOG.md 조인·라이선스 필수·fetch.js 거부 전파."""

import subprocess

import pytest

from core import library
from core.facade import Invalid, UpstreamError


def test_parse_catalog_real_file():
    cat = library.parse_catalog()
    assert cat["bgm/mixkit-623-loop.mp3"]["license"] == "Mixkit Free License"
    assert "office-talk" in str({k for k in cat})  # broll 표도 파싱된다
    assert cat["broll/office-talk.mp4"]["source"].startswith("https://www.pexels.com")


def test_list_assets_joins_catalog_and_probe(studio):
    bgm = studio.assets("bgm")
    loop = next(a for a in bgm if a["name"] == "mixkit-623-loop.mp3")
    assert loop["licensed"] is True and loop["license"] == "Mixkit Free License"
    assert loop["duration"] > 200          # ffprobe 실측 (264s)
    assert loop["ref"] == "assets/bgm/mixkit-623-loop.mp3"  # scenes 기입값 (엔진 루트 기준)

    broll = studio.assets("broll")
    talk = next(a for a in broll if a["name"] == "office-talk.mp4")
    assert (talk["width"], talk["height"]) == (1920, 1080)

    fonts = studio.assets("font")
    assert any(f["name"] == "PretendardVariable.woff2" for f in fonts)

    with pytest.raises(Invalid):
        studio.assets("없는종류")


def test_add_requires_license(studio):
    with pytest.raises(Invalid) as e:
        studio.add_asset(kind="bgm", url="https://assets.mixkit.co/x.mp3", license="")
    assert "라이선스" in e.value.message


def test_add_rejected_host_propagates(studio):
    with pytest.raises(UpstreamError) as e:
        studio.add_asset(kind="bgm", url="https://youtube.com/x.mp3", license="?")
    assert "허용되지 않은 호스트" in e.value.message


def test_add_appends_catalog_row(tmp_path):
    """다운로드는 가짜 runner 로 — CATALOG 행 추가 로직만 검증 (실 CATALOG 무변경)."""
    cat = tmp_path / "CATALOG.md"
    cat.write_text("# 목록\n\n## 받아 둔 BGM\n\n| 파일 | 길이 | 출처 | 라이선스 | 용도 메모 |\n"
                   "|---|---|---|---|---|\n"
                   "| `bgm/old.mp3` | 1:00 | u | L | m |\n\n## 받아 둔 사진\n",
                   encoding="utf-8")
    fake = subprocess.CompletedProcess([], 0, stdout="저장: assets/bgm/new.mp3", stderr="")
    out = library.add_asset("bgm", "https://assets.mixkit.co/music/1/new.mp3",
                            license="Mixkit Free License", note="테스트",
                            catalog=cat, runner=lambda args: fake)
    assert out["name"] == "new.mp3"
    text = cat.read_text(encoding="utf-8")
    lines = text.splitlines()
    old_i = lines.index("| `bgm/old.mp3` | 1:00 | u | L | m |")
    assert "`bgm/new.mp3`" in lines[old_i + 1]           # 표 마지막 행 뒤에 붙는다
    assert lines[old_i + 1].count("|") == 6              # bgm 표 열 수 유지
    assert library.parse_catalog(cat)["bgm/new.mp3"]["license"] == "Mixkit Free License"
