"""대시보드 카드 문구 — "아무것도 안 했는데 다 했다"고 말하지 않는다 (65회차 P9·P2).

Qt 를 띄우지 않고 문구 규칙만 고정한다 — 카드가 쓰는 판단은 total/done 두 수뿐이다.
"""

from __future__ import annotations

from app import theme
from core import kinds


def card_progress(total: int, done: int, kind: str | None) -> str:
    """app/pages/dashboard.py 의 시리즈 카드가 쓰는 규칙과 같은 식."""
    if total == 0:
        return "카드를 열어 첫 영상을 추가하세요"
    if done < total:
        return f"완료 {done} / {total}"
    return f"전부 완료 ({total}{kinds.unit(kind)})"


def test_empty_project_does_not_claim_completion():
    """영상이 0개면 "전부 완료 (0강)" 이 아니라 다음 행동을 말한다."""
    assert card_progress(0, 0, "lecture") == "카드를 열어 첫 영상을 추가하세요"
    assert card_progress(0, 0, "promo") == "카드를 열어 첫 영상을 추가하세요"
    assert "완료" not in card_progress(0, 0, None)


def test_progress_and_completion_wording():
    assert card_progress(6, 1, "lecture") == "완료 1 / 6"
    assert card_progress(6, 6, "lecture") == "전부 완료 (6강)"
    assert card_progress(3, 3, "promo") == "전부 완료 (3편)"


def test_bar_color_means_state_not_kind():
    """바 색 = 상태 — 완성 초록·진행 파랑. 회색 채움 금지 (2026-08-23 "완성인데 왜 회색인가").

    단발 카드는 (done, 1)로, 시리즈 카드는 (done, total)로 같은 규칙을 쓴다 —
    단발 완성과 시리즈 전부 완료가 같은 초록이어야 범례 없이 읽힌다.
    """
    assert theme.bar_chunk(1, 1) == theme.SUCCESS      # 단발 완성
    assert theme.bar_chunk(6, 6) == theme.SUCCESS      # 시리즈 전부 완료
    assert theme.bar_chunk(1, 6) == theme.ACCENT       # 부분 진행 = 파랑
    assert theme.bar_chunk(0, 1) == theme.ACCENT       # 0% — 채움이 없어 색은 안 보인다
    assert theme.bar_chunk(0, 0) == theme.ACCENT       # 빈 프로젝트도 0%
    assert theme.INK_3 not in {theme.bar_chunk(d, t)   # 어떤 조합도 회색을 채우지 않는다
                               for d in range(3) for t in range(3)}
