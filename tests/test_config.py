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
