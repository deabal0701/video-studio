"""agents — 순수 HTTP 에이전트 러너 (05_agent · D18 — 저작·평가만, D6·D7).

선택 제공자(claude/openai)의 키가 없으면 이 패키지 전체가 비활성이고, 앱의 다른 전부는
키 없이 동작한다 (4단계 수용 기준). 규약의 정본은 .claude/skills/ — skill_prompts 가
절 단위로 발췌해 시스템 프롬프트로 조립한다 (코드로 재인코딩하지 않는다, 원칙 3).
CLI·에이전트 하네스 의존 없음 — 파일 기입은 runner 가 결정적으로 수행한다.
"""

from .providers import KINDS, PROVIDERS
from .runner import agent_enabled, make_agent_work, provider, test_mode, usage_summary

__all__ = ["KINDS", "PROVIDERS", "agent_enabled", "make_agent_work", "provider",
           "test_mode", "usage_summary"]
