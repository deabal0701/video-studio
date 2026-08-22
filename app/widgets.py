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
    """mp3 미리듣기 — TTS 샘플·BGM 시청취 공용 (파일 경로 재생)."""

    def __init__(self) -> None:
        self.player = QMediaPlayer()
        self.out = QAudioOutput()
        self.player.setAudioOutput(self.out)

    def play(self, path) -> None:
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()

    def stop(self) -> None:
        self.player.stop()
