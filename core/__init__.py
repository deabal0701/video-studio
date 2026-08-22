"""core — 로직 전부 (UI 무관, 단독 테스트 가능).

구조·책임은 docs/design/01_architecture.md, 데이터 모델은 02_data-model.md 가 정본.
"""

# 경로의 정본은 core.env (07_desktop — 설치/데이터 폴더 분리). 여기는 호환 재수출만.
from .env import ENGINE_DIR, REPO_ROOT  # noqa: F401

FIXTURES_DIR = REPO_ROOT / "fixtures" / "projects"
