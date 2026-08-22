"""agents — Claude Agent SDK 러너 (05_agent.md — 저작·평가만, D6·D7).

키(`ANTHROPIC_API_KEY`)가 없으면 이 패키지 전체가 비활성이고, 앱의 다른 전부는
키 없이 동작한다 (4단계 수용 기준). 규약의 정본은 .claude/skills/ — 에이전트가
settingSources 로 네이티브 로드한다 (프롬프트로 재인코딩하지 않는다, 원칙 3).
"""

from .providers import KINDS, PROVIDERS
from .runner import agent_enabled, make_agent_work, provider, test_mode, usage_summary

__all__ = ["KINDS", "PROVIDERS", "agent_enabled", "make_agent_work", "provider",
           "test_mode", "usage_summary"]
