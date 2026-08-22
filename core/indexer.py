"""indexer — projects/ 스캔 → 강좌·회차 목록 (04_api "인덱서").

기동 시 전체 스캔 → SQLite 파생 캐시(언제나 삭제 가능. 스키마 버전 올리면 전체 재스캔),
이후 watchfiles 가 변경을 알리면 재스캔. 캐시에는 **구조만**(강좌·회차·제목) 넣는다 —
파생 상태(⬜/🔄/✅·stale)는 저장 금지 원칙(02)대로 요청 시점에 계산한다(core.status).
강좌 판정: course.json 있는 폴더. 회차 판정: `<강좌id>-NN` 패턴 + scenes.json.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from . import env

_EPISODE_RE = re.compile(r"^(?P<course>.+)-(?P<n>\d{2,})$")

SCHEMA_VERSION = 1


@dataclass
class CourseEntry:
    id: str
    dir: Path
    episodes: list[str] = field(default_factory=list)


def scan(projects_root: Path) -> tuple[list[CourseEntry], list[str]]:
    """(강좌 목록, 패턴 밖 단발 영상 id 목록)을 돌려준다."""
    courses: dict[str, CourseEntry] = {}
    singles: list[str] = []
    if not projects_root.exists():
        return [], []
    dirs = [d for d in sorted(projects_root.iterdir()) if d.is_dir()]
    for d in dirs:
        if (d / "course.json").exists():
            courses[d.name] = CourseEntry(id=d.name, dir=d)
    for d in dirs:
        if d.name in courses or not (d / "scenes.json").exists():
            continue
        m = _EPISODE_RE.match(d.name)
        if m and m.group("course") in courses:
            courses[m.group("course")].episodes.append(d.name)
        else:
            singles.append(d.name)
    return list(courses.values()), singles


class Index:
    """SQLite 파생 캐시. 삭제해도 다음 조회가 재생성한다."""

    def __init__(self, root: Path, cache_dir: Path | None = None):
        self.root = Path(root)
        # 정본은 env.cache_dir() — 설치 모드에선 데이터 폴더다 (설치 폴더는 읽기 전용)
        cache_dir = cache_dir or env.cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        stamp = hashlib.sha1(str(self.root).encode()).hexdigest()[:10]
        self.db_file = cache_dir / f"index-{stamp}.sqlite"

    def _connect(self) -> sqlite3.Connection:
        """주의: sqlite3 의 `with con:` 은 커밋만 하고 닫지 않는다 — 열린 연결이 남으면
        Windows 에서 캐시 삭제("언제나 삭제 가능" 규약)가 WinError 32 로 막힌다 (5-1 실측).
        호출부는 `with closing(self._connect()) as con, con:` 으로 닫힘+트랜잭션을 함께 건다."""
        con = sqlite3.connect(self.db_file)
        con.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS courses "
                    "(id TEXT PRIMARY KEY, title TEXT, episode_count INTEGER)")
        con.execute("CREATE TABLE IF NOT EXISTS episodes "
                    "(id TEXT PRIMARY KEY, course_id TEXT)")  # course_id NULL = 단발 영상
        return con

    def _signature(self) -> str:
        """루트 아래 1층 폴더의 (이름, mtime) 스냅샷 — 바뀌면 재스캔."""
        entries = sorted(
            (d.name, d.stat().st_mtime_ns) for d in self.root.iterdir() if d.is_dir()
        ) if self.root.exists() else []
        return hashlib.sha1(json.dumps(entries).encode()).hexdigest()

    def rescan(self) -> None:
        courses, singles = scan(self.root)
        with closing(self._connect()) as con, con:
            con.execute("DELETE FROM courses")
            con.execute("DELETE FROM episodes")
            for c in courses:
                doc = {}
                try:
                    doc = json.loads((c.dir / "course.json").read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    pass  # 깨진 course.json — 목록에는 폴더명으로라도 남긴다
                con.execute("INSERT INTO courses VALUES (?,?,?)",
                            (c.id, doc.get("title", c.id), len(doc.get("episodes", []))))
                con.executemany("INSERT INTO episodes VALUES (?,?)",
                                [(e, c.id) for e in c.episodes])
            con.executemany("INSERT INTO episodes VALUES (?,?)", [(s, None) for s in singles])
            con.execute("INSERT OR REPLACE INTO meta VALUES ('schema', ?)", (str(SCHEMA_VERSION),))
            con.execute("INSERT OR REPLACE INTO meta VALUES ('signature', ?)", (self._signature(),))

    def _fresh(self, con: sqlite3.Connection) -> bool:
        meta = dict(con.execute("SELECT key, value FROM meta"))
        return meta.get("schema") == str(SCHEMA_VERSION) and meta.get("signature") == self._signature()

    def ensure_fresh(self) -> None:
        with closing(self._connect()) as con, con:
            fresh = self._fresh(con)
        if not fresh:
            self.rescan()

    def courses(self) -> list[dict]:
        self.ensure_fresh()
        with closing(self._connect()) as con, con:
            rows = con.execute("SELECT id, title, episode_count FROM courses ORDER BY id").fetchall()
            out = [{"id": r[0], "title": r[1], "episodeCount": r[2],
                    "episodes": [e[0] for e in con.execute(
                        "SELECT id FROM episodes WHERE course_id=? ORDER BY id", (r[0],))]}
                   for r in rows]
            singles = [e[0] for e in con.execute(
                "SELECT id FROM episodes WHERE course_id IS NULL ORDER BY id")]
        return out + [{"id": s, "title": s, "single": True} for s in singles]
