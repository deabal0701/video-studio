"""설정 파일 병합 쓰기·자가진단 (5-6 설정 화면의 core 쪽).

키 정본은 홈 공용 `.env` — 기존 주석·순서를 보존하고 값만 바꾼다 (사람이 손으로도 연다).
"""

import core.config as config
from core.facade import Studio


def test_write_home_env_preserves_comments_and_order(tmp_path, monkeypatch):
    f = tmp_path / "develop-video.env"
    f.write_text("# 공용 키\nAZURE_SPEECH_KEY=old\n\n# 아래는 선택\nELEVENLABS_API_KEY=\n",
                 encoding="utf-8", newline="\n")
    monkeypatch.setattr(config, "HOME_ENV", f)

    config.write_home_env({"AZURE_SPEECH_KEY": "new", "OPENAI_API_KEY": "sk-o",
                           "AGENT_PROVIDER": "openai"})
    lines = f.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# 공용 키"                    # 주석 보존
    assert lines[1] == "AZURE_SPEECH_KEY=new"         # 값만 교체 (자리 유지)
    assert "# 아래는 선택" in lines                    # 중간 주석 보존
    assert "ELEVENLABS_API_KEY=" in lines             # 빈 값은 "설정 안 함"으로 남긴다
    assert "OPENAI_API_KEY=sk-o" in lines             # 새 키는 끝에 추가
    assert "AGENT_PROVIDER=openai" in lines


def test_read_all_reports_which_file_wins(tmp_path, monkeypatch):
    home = tmp_path / "home.env"
    repo = tmp_path / "repo.env"
    home.write_text("ANTHROPIC_API_KEY=home-key\nOPENAI_API_KEY=home-o\n", encoding="utf-8")
    repo.write_text("ANTHROPIC_API_KEY=repo-key\n", encoding="utf-8")
    monkeypatch.setattr(config, "HOME_ENV", home)
    monkeypatch.setattr(config, "REPO_ENV", repo)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    out = config.read_all()
    # 저장소 .env 가 홈 공용보다 우선 (엔진 envFiles 와 같은 순서)
    assert out["values"]["ANTHROPIC_API_KEY"] == "repo-key"
    assert "저장소" in out["sources"]["ANTHROPIC_API_KEY"]
    assert out["values"]["OPENAI_API_KEY"] == "home-o"

    # 셸 환경변수는 그보다 더 우선 — 화면이 "저장해도 그쪽이 이긴다"를 보여줄 근거
    monkeypatch.setenv("ANTHROPIC_API_KEY", "shell-key")
    out2 = config.read_all()
    assert out2["values"]["ANTHROPIC_API_KEY"] == "shell-key"
    assert out2["sources"]["ANTHROPIC_API_KEY"] == "셸 환경변수"


def test_diagnose_shape_and_never_raises():
    checks = config.diagnose()
    names = {c["name"] for c in checks}
    assert {"Node", "ffmpeg", "ffprobe", "Playwright", "데이터 폴더"} <= names
    for c in checks:
        assert set(c) == {"name", "ok", "detail", "hint"}
        assert isinstance(c["ok"], bool)


def test_facade_settings_roundtrip(tmp_path, monkeypatch):
    f = tmp_path / "h.env"
    monkeypatch.setattr(config, "HOME_ENV", f)
    monkeypatch.setattr(config, "REPO_ENV", tmp_path / "none.env")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    st = Studio()
    assert "AZURE_SPEECH_KEY" in st.settings()["values"]
    out = st.save_settings({"OPENAI_API_KEY": "sk-new"})
    assert out["values"]["OPENAI_API_KEY"] == "sk-new"
    assert f.read_text(encoding="utf-8").count("OPENAI_API_KEY=sk-new") == 1


# ── ffmpeg 자막(libass) ──────────────────────────────────────────────────────
# ffmpeg 가 PATH 에 있다는 것만으로는 부족하다. 2026-08-22 실측: conda-forge ffmpeg
# 9.0.1 에 `ass` 필터가 없어 존재 검사는 OK 인데 빌드가 [3] 합성에서 죽었다.
# 자가진단이 "OK" 라고 말하면서 빌드가 깨지는 것이 이 검사가 막으려는 상태다.
_FILTERS_WITH_ASS = (
    " ... amix             AA->A      Audio mixing.\n"
    " T.. ass              V->V       Render ASS subtitles onto input video.\n"
    " ... scale            V->V       Scale the input video size.\n"
)
_FILTERS_WITHOUT_ASS = (
    " ... amix             AA->A      Audio mixing.\n"
    " ... scale            V->V       Scale the input video size.\n"
    " ... aselect          A->N       Select audio frames to pass in output.\n"
)


def _fake_filters(monkeypatch, stdout: str):
    import subprocess

    from core import config as cfg

    class _P:
        def __init__(self):
            self.stdout, self.returncode = stdout, 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _P())
    return cfg


def test_ass_filter_detected(monkeypatch):
    cfg = _fake_filters(monkeypatch, _FILTERS_WITH_ASS)
    ok, detail = cfg._has_ass_filter()
    assert ok and "있음" in detail


def test_ass_filter_missing_is_reported(monkeypatch):
    cfg = _fake_filters(monkeypatch, _FILTERS_WITHOUT_ASS)
    ok, detail = cfg._has_ass_filter()
    assert not ok
    assert "합성" in detail, "왜 문제인지(빌드가 어디서 죽는지)를 말해야 한다"


def test_ass_filter_does_not_match_substrings(monkeypatch):
    """'aselect'·'assrender' 같은 이름에 걸리면 안 된다 — 필터 이름 열만 본다."""
    cfg = _fake_filters(monkeypatch, _FILTERS_WITHOUT_ASS)
    assert cfg._has_ass_filter()[0] is False


def test_ass_filter_probe_failure_is_not_a_pass(monkeypatch):
    """ffmpeg 를 못 부르면 '있다'고 하면 안 된다 — 모르면 NG 다."""
    import subprocess

    from core import config as cfg

    def boom(*a, **k):
        raise OSError("ffmpeg 없음")

    monkeypatch.setattr(subprocess, "run", boom)
    assert cfg._has_ass_filter()[0] is False


# ── 데이터 폴더 포인터 (.data-dir — 첫 실행 위저드 [변경…] 배선) ──────────────
def test_pointer_target_absent(tmp_path):
    from core import env
    assert env._pointer_target(tmp_path) is None


def test_pointer_target_reads_path(tmp_path):
    from core import env
    target = tmp_path / "custom-data"
    (tmp_path / ".data-dir").write_text(str(target), encoding="utf-8")
    assert env._pointer_target(tmp_path) == target.resolve()


def test_pointer_target_blank_falls_back(tmp_path):
    from core import env
    (tmp_path / ".data-dir").write_text("  \n", encoding="utf-8")
    assert env._pointer_target(tmp_path) is None
