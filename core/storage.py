"""storage — 파일 접근 추상화 (D9: 처음부터 추상화 계층).

로컬은 LocalFS, 상용은 S3 구현으로 교체한다. 이 인터페이스를 1단계부터 지키는 것이
상용 전환 비용을 정하는 전부다 (01_architecture "로컬 모드 / 상용 모드").
쓰기 충돌은 etag(mtime+size 해시) 낙관적 잠금으로 막는다 (04_api If-Match).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    """프로젝트 루트 아래의 상대 경로만 다룬다. 경로 문자열 계산은 core.paths 의 몫."""

    def read_bytes(self, rel: str) -> bytes: ...
    def write_bytes(self, rel: str, data: bytes) -> None: ...
    def exists(self, rel: str) -> bool: ...
    def listdir(self, rel: str = ".") -> list[str]: ...
    def etag(self, rel: str) -> str: ...
    def abspath(self, rel: str) -> Path: ...


class LocalFS:
    """로컬 파일시스템 구현 — 파일이 SSOT (원칙 1)."""

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()

    def abspath(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError(f"루트 밖 경로: {rel}")
        return p

    def read_bytes(self, rel: str) -> bytes:
        return self.abspath(rel).read_bytes()

    def write_bytes(self, rel: str, data: bytes) -> None:
        p = self.abspath(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def exists(self, rel: str) -> bool:
        return self.abspath(rel).exists()

    def listdir(self, rel: str = ".") -> list[str]:
        return sorted(e.name for e in self.abspath(rel).iterdir())

    def etag(self, rel: str) -> str:
        st = os.stat(self.abspath(rel))
        return hashlib.sha1(f"{st.st_mtime_ns}:{st.st_size}".encode()).hexdigest()[:16]
