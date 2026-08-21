"""schema — course/scenes 모델 + 직렬화 (02_data-model).

직렬화 규약: ① `_` 접두 주석 필드 보존 ② 키 순서 보존 ③ 들여쓰기 2칸 —
Claude Code·사람과 같은 파일을 편집하므로 diff 가 깨끗해야 한다.
pydantic 모델은 extra="allow" 로 미지 필드를 통과시킨다 (엔진이 진화해도 데이터를 깎지 않게).

무손실 규칙(2단계 수용 기준 "열고 저장했을 때 diff 0")은 Document 가 진다:
내용이 안 바뀌었으면 **원문 그대로** 다시 쓴다(손으로 쓴 한 줄 객체 등 서식까지 보존).
내용이 바뀌었을 때만 표준형(2칸 들여쓰기·키 순서 유지)으로 직렬화한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


def load_json(file: Path) -> dict[str, Any]:
    """키 순서를 보존해 읽는다 (Python dict 는 삽입 순서 보존)."""
    return json.loads(file.read_text(encoding="utf-8"))


def dump_json(value: dict[str, Any]) -> str:
    """2칸 들여쓰기 · 한글 원문 유지 · 끝 개행 — 엔진 writeJson 과 같은 모양."""
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def save_json(file: Path, value: dict[str, Any]) -> None:
    file.write_text(dump_json(value), encoding="utf-8")


class Document:
    """한 JSON 파일의 편집 세션 — 원문·데이터·etag 를 함께 들고 다닌다.

    사용: doc = Document.load(path) → doc.data 수정 → doc.save() (If-Match 는 호출자 몫).
    """

    def __init__(self, file: Path, text: str):
        self.file = Path(file)
        self.original_text = text
        self.data: dict[str, Any] = json.loads(text)
        self._original_data = json.loads(text)  # 변경 감지용 별도 사본

    @classmethod
    def load(cls, file: Path) -> "Document":
        return cls(file, Path(file).read_text(encoding="utf-8"))

    @property
    def dirty(self) -> bool:
        return self.data != self._original_data

    def dumps(self) -> str:
        # 무손실 핵심: 내용이 그대로면 원문 그대로 — 서식(한 줄 객체·개행)까지 보존돼 diff 0.
        return dump_json(self.data) if self.dirty else self.original_text

    def save(self) -> None:
        self.file.write_text(self.dumps(), encoding="utf-8")


class Voice(BaseModel):
    model_config = ConfigDict(extra="allow")
    provider: str = "edge"
    lang: str = "ko"
    gender: str = "female"
    rate: str | None = None


class Course(BaseModel):
    """course.json — 강좌 정체성 (참조 정본, 빌드에 직접 쓰이지 않는다)."""

    model_config = ConfigDict(extra="allow")
    course: str
    title: str
    voice: Voice | None = None
    episodes: list[dict[str, Any]] = []


class Scenes(BaseModel):
    """scenes.json — 대본, 빌드의 유일한 입력. id = 폴더명 = out 폴더명 (셋 일치 필수)."""

    model_config = ConfigDict(extra="allow")
    id: str
    voice: Voice | None = None
    render: dict[str, Any] = {}
    scenes: list[dict[str, Any]] = []
    variants: list[dict[str, Any]] = []
