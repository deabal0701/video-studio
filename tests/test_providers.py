"""D15 제공자 이중화 — 선택·모델 해석·키 게이트·테스트 모드 (5-6).

env_value 를 주입해 실 .env·셸과 격리한다 (providers 는 조회 함수를 인자로 받는다).
"""

import pytest

from core.agents import providers


def env(**kw):
    return kw.get


def test_default_provider_is_claude_with_task_models():
    st = providers.status(env(ANTHROPIC_API_KEY="sk-x"))
    assert st["provider"] == "claude" and st["enabled"] is True
    assert st["models"] == {"draft": "claude-opus-5", "diagram": "claude-sonnet-5",
                            "review": "claude-opus-5"}
    assert st["testMode"] is False


def test_unknown_provider_falls_back_to_claude():
    assert providers.provider(env(AGENT_PROVIDER="gemini")) == "claude"
    assert providers.provider(env(AGENT_PROVIDER="OpenAI")) == "openai"  # 대소문자 무관


def test_key_gate_is_per_provider():
    """선택한 제공자의 키만 본다 — 다른 제공자 키가 있어도 비활성 (사유는 그 제공자 것)."""
    st = providers.status(env(AGENT_PROVIDER="openai", ANTHROPIC_API_KEY="sk-x"))
    assert st["enabled"] is False
    assert "OPENAI_API_KEY" in st["reason"]
    assert st["keys"] == {"claude": True, "openai": False}  # 화면이 "전환하면 됨"을 안내


def test_test_mode_forces_cheapest_over_override():
    """테스트 모드는 작업별 오버라이드보다 이긴다 — 지시의 취지("테스트는 최저가")."""
    e = env(AGENT_TEST_MODE="1", AGENT_MODEL_DRAFT="claude-opus-5")
    assert providers.task_model(e, "draft") == "claude-haiku-4-5"
    assert providers.status(e)["testMode"] is True
    # openai 쪽도 같은 규칙 + 계정별 조정 가능
    e2 = env(AGENT_PROVIDER="openai", AGENT_TEST_MODE="1", OPENAI_TEST_MODEL="my-nano")
    assert providers.task_model(e2, "review") == "my-nano"


def test_openai_model_resolution_order():
    """오버라이드 > OPENAI_MODEL > 기본."""
    assert providers.task_model(env(AGENT_PROVIDER="openai"), "draft") == "gpt-4o-mini"
    assert providers.task_model(
        env(AGENT_PROVIDER="openai", OPENAI_MODEL="gpt-x"), "draft") == "gpt-x"
    assert providers.task_model(
        env(AGENT_PROVIDER="openai", OPENAI_MODEL="gpt-x",
            AGENT_MODEL_DIAGRAM="gpt-diagram"), "diagram") == "gpt-diagram"


@pytest.mark.parametrize("value,expected",
                         [("1", True), ("true", True), ("ON", True),
                          ("0", False), ("", False), (None, False)])
def test_test_mode_parsing(value, expected):
    assert providers.test_mode(env(AGENT_TEST_MODE=value)) is expected
