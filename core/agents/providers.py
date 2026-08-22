"""providers — 에이전트 제공자 선택·모델 해석 (D15, 05_agent "제공자 이중화").

    AGENT_PROVIDER=claude|openai     기본 claude
    AGENT_TEST_MODE=1                제공자 불문 **최저가 모델 강제** ("테스트는 싸게")
    AGENT_MODEL_DRAFT/DIAGRAM/REVIEW 작업별 오버라이드 (테스트 모드가 아닐 때만)

키는 제공자별로 독립 — 선택한 제공자의 키만 검사한다. 키가 없으면 에이전트 메뉴만
비활성되고 앱의 나머지 전부는 그대로 동작한다 (원칙 2).
"""

from __future__ import annotations

from typing import Any

KINDS = ("draft", "diagram", "review")
PROVIDERS = ("claude", "openai")

KEY_ENV = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
KEY_HINT = {
    "claude": "ANTHROPIC_API_KEY 없음 — .env 에 넣으면 켜집니다 (종량제 키, 구독 불가)",
    "openai": "OPENAI_API_KEY 없음 — .env 에 넣으면 켜집니다",
}

# 작업별 기본 모델 (05_agent 모델 행). claude 는 열린 저작=Opus·도식=Sonnet 급.
DEFAULT_MODELS: dict[str, dict[str, str]] = {
    "claude": {
        "draft": "claude-opus-5",      # 열린 저작 — 규약 준수·구성력이 본체
        "diagram": "claude-sonnet-5",  # html 1장 생성 — 비용을 낮춘다
        "review": "claude-opus-5",     # 평가 일관성
    },
    # openai 는 계정마다 쓸 수 있는 모델이 달라 **설정 화면에서 지정**하는 것을 전제로 한다.
    # OPENAI_MODEL 로 일괄 지정, AGENT_MODEL_* 로 작업별 오버라이드.
    "openai": {k: "gpt-4o-mini" for k in KINDS},
}

# 테스트 모드 최저가 (사용자 지시 — "테스트시는 최저가인 모델").
# claude 는 4단계 실키 실측이 Haiku($0.46/편). openai 는 계정 티어에 맞춰 설정 화면에서 조정.
TEST_MODELS = {"claude": "claude-haiku-4-5", "openai": "gpt-4o-mini"}


def provider(env_value) -> str:
    """선택된 제공자 — 모르는 값이면 기본(claude)으로 떨어진다."""
    v = (env_value("AGENT_PROVIDER") or "claude").strip().lower()
    return v if v in PROVIDERS else "claude"


def test_mode(env_value) -> bool:
    return str(env_value("AGENT_TEST_MODE") or "").strip().lower() in ("1", "true", "yes", "on")


def test_model(env_value, prov: str | None = None) -> str:
    prov = prov or provider(env_value)
    return (env_value(f"{prov.upper()}_TEST_MODEL")
            or (env_value("OPENAI_TEST_MODEL") if prov == "openai" else None)
            or TEST_MODELS[prov])


def task_model(env_value, kind: str, prov: str | None = None) -> str:
    """작업별 모델. 테스트 모드면 오버라이드보다 **최저가가 이긴다** (지시의 취지)."""
    prov = prov or provider(env_value)
    if test_mode(env_value):
        return test_model(env_value, prov)
    override = env_value(f"AGENT_MODEL_{kind.upper()}")
    if override:
        return override
    if prov == "openai":
        return env_value("OPENAI_MODEL") or DEFAULT_MODELS["openai"][kind]
    return DEFAULT_MODELS[prov][kind]


def status(env_value) -> dict[str, Any]:
    """게이트 — 화면이 버튼 활성/비활성과 사유를 이걸로 정한다."""
    prov = provider(env_value)
    models = {k: task_model(env_value, k, prov) for k in KINDS}
    out: dict[str, Any] = {
        "provider": prov,
        "models": models,
        "testMode": test_mode(env_value),
        # 다른 제공자에 키가 있으면 화면이 "전환하면 쓸 수 있다"고 안내할 수 있다
        "keys": {p: bool(env_value(KEY_ENV[p])) for p in PROVIDERS},
    }
    if env_value(KEY_ENV[prov]):
        out["enabled"] = True
        return out
    out["enabled"] = False
    out["reason"] = KEY_HINT[prov]
    return out
