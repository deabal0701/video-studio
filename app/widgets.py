"""공용 소형 위젯 — 색 버튼·오디오 미리듣기 (①③·위저드 공용)."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QColorDialog, QPushButton


class ColorButton(QPushButton):
    """팔레트 색 하나 — 견본을 배경으로 보여주고 클릭 시 피커 (03 ① 브랜드 행)."""

    changed = Signal(str)

    def __init__(self, value: str = "#5B8DEF"):
        super().__init__()
        self.setFixedSize(44, 28)
        self.set_value(value)
        self.clicked.connect(self._pick)

    def set_value(self, value: str) -> None:
        self.value = value or "#000000"
        # **선택자를 반드시 붙인다.** Qt 스타일시트는 자식 위젯으로 전파되므로
        # 선택자 없는 `background: <색>` 은 이 버튼을 부모로 삼는 모든 위젯을 물들인다.
        # (2026-08-22 실측: 색 선택 대화상자 전체가 고르는 색으로 칠해져 글자가 안 보였다)
        self.setStyleSheet(f"ColorButton {{ background: {self.value};"
                           " border: 1px solid #d2d2d7; border-radius: 8px; }")
        self.setToolTip(self.value)

    def _pick(self) -> None:
        # 부모는 **창**이다 — 버튼을 부모로 주면 위 스타일시트를 대화상자가 물려받는다.
        color = QColorDialog.getColor(QColor(self.value), self.window(), "색 선택")
        if color.isValid():
            self.set_value(color.name())
            self.changed.emit(self.value)


class AudioPreview:
    """mp3 미리듣기 — TTS 샘플·BGM 시청취 공용 (파일 경로 재생).

    **재생 버튼은 토글이어야 한다** (2026-08-22 사용자 지적: "중지를 어떻게 하나?").
    `bind()` 로 버튼을 등록하면 재생 중엔 "중지"로 바뀌고, 끝나면 저절로 돌아온다.
    한 화면에 버튼이 여럿이면(목소리·BGM) 같은 인스턴스에 전부 등록한다 —
    플레이어가 하나라 소리도 겹치지 않는다.
    """

    def __init__(self) -> None:
        self.player = QMediaPlayer()
        self.out = QAudioOutput()
        self.player.setAudioOutput(self.out)
        self._buttons: dict = {}   # 버튼 → 평상시 라벨
        self._active = None        # 지금 재생을 시작한 버튼
        self.player.playbackStateChanged.connect(self._sync_buttons)

    def bind(self, btn, idle_text: str) -> None:
        """버튼을 토글로 등록 — 라벨 관리는 여기서 한다."""
        self._buttons[btn] = idle_text
        btn.setText(idle_text)

    def stop_if_playing(self, btn) -> bool:
        """그 버튼이 시작한 재생이 돌고 있으면 멈추고 True (호출자는 그대로 return)."""
        if self._active is btn and                 self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.stop()
            return True
        return False

    def start(self, btn, path) -> None:
        """버튼 주도 재생 — 라벨이 '중지'로 바뀐다."""
        self._active = btn
        self.play(path)

    def _sync_buttons(self, *_a) -> None:
        playing = self.player.playbackState() == QMediaPlayer.PlayingState
        for b, idle in self._buttons.items():
            b.setText("중지" if (playing and b is self._active) else idle)

    def play(self, path) -> None:
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()

    def stop(self) -> None:
        self.player.stop()
