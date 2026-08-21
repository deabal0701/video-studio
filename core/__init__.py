"""core — 로직 전부 (UI 무관, 단독 테스트 가능).

구조·책임은 docs/design/01_architecture.md, 데이터 모델은 02_data-model.md 가 정본.
"""

from pathlib import Path

# 저장소 루트 — core/ 의 부모. 엔진·픽스처·projects/ 위치의 기준점.
REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = REPO_ROOT / "engine"
PROJECTS_DIR = REPO_ROOT / "projects"
FIXTURES_DIR = REPO_ROOT / "fixtures" / "projects"
