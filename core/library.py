"""library — 미디어 라이브러리 (03: "라이선스 필드 필수 — CATALOG.md 규약의 DB화").

정본은 여전히 파일이다: 소재 실물 = engine/assets/<kind>/, 라이선스·출처 = CATALOG.md 표.
이 모듈은 그 둘을 조인해 목록을 만들고(스캔 + ffprobe 실측 + CATALOG 파싱),
새 소재는 fetch.js(허용 호스트 검증)로 받고 CATALOG.md 에 한 줄을 **추가**한다 —
"받을 때마다 표에 한 줄 추가한다" 규약의 기계화. 라이선스 없이 받기는 거부한다.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from . import ENGINE_DIR

ASSETS_DIR = ENGINE_DIR / "assets"
CATALOG = ASSETS_DIR / "CATALOG.md"

KIND_DIRS = {
    "bgm": ASSETS_DIR / "bgm",
    "broll": ASSETS_DIR / "broll",
    "photo": ASSETS_DIR / "photo",
    "font": ENGINE_DIR / "fonts",
}
MEDIA_KINDS = {"bgm", "broll"}  # ffprobe 실측 대상 (photo 는 크기만, font 는 메타 없음)

# CATALOG 의 종류별 표 섹션 제목 — 행 추가 위치를 찾는 앵커
SECTION_HEAD = {
    "bgm": "## 받아 둔 BGM",
    "photo": "## 받아 둔 사진",
    "broll": "## 받아 둔 B롤 영상",
}

_probe_cache: dict[tuple[str, int], dict[str, Any]] = {}


def _probe(file: Path) -> dict[str, Any]:
    key = (str(file), file.stat().st_mtime_ns)
    if key not in _probe_cache:
        try:
            import json as _json
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height:format=duration",
                 "-of", "json", str(file)],
                capture_output=True, text=True, timeout=60, check=True).stdout
            info = _json.loads(out)
            _probe_cache[key] = {
                "duration": round(float(info.get("format", {}).get("duration", 0) or 0), 2),
                "width": (info.get("streams") or [{}])[0].get("width", 0),
                "height": (info.get("streams") or [{}])[0].get("height", 0),
            }
        except Exception:  # noqa: BLE001 — 못 재면 메타 없이 목록에는 남긴다
            _probe_cache[key] = {"duration": 0, "width": 0, "height": 0}
    return _probe_cache[key]


def parse_catalog(catalog: Path = CATALOG) -> dict[str, dict[str, str]]:
    """CATALOG.md 의 모든 표에서 {`dir/파일명`: {source, license, note}} 를 뽑는다."""
    if not catalog.exists():
        return {}
    meta: dict[str, dict[str, str]] = {}
    header: list[str] = []
    for line in catalog.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            header = []
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if any(set(c) <= {"-", " ", ":"} and c for c in cells):
            continue  # 구분선
        if "파일" in cells[0]:
            header = cells
            continue
        m = re.match(r"`([^`]+)`", cells[0])
        if not m or not header:
            continue
        row = dict(zip(header, cells))
        meta[m.group(1)] = {
            "source": row.get("출처", ""),
            "license": row.get("라이선스", ""),
            "note": next((row[k] for k in row if "메모" in k), ""),
        }
    return meta


def list_assets(kind: str, *, catalog: Path = CATALOG) -> list[dict[str, Any]]:
    if kind not in KIND_DIRS:
        raise ValueError(f"모르는 종류: {kind}")
    root = KIND_DIRS[kind]
    cat = parse_catalog(catalog)
    out = []
    if root.exists():
        for f in sorted(root.iterdir()):
            if not f.is_file() or f.name.startswith(".") or f.suffix in (".txt", ".md"):
                continue
            entry: dict[str, Any] = {
                "kind": kind,
                "name": f.name,
                "bytes": f.stat().st_size,
                # scenes.json 기입값 미리 계산 — bgm·broll 은 엔진 루트 기준 (02 경로 표)
                "ref": f"{f.relative_to(ENGINE_DIR).as_posix()}",
                **(cat.get(f"{root.name}/{f.name}", {"source": "", "license": "", "note": ""})),
            }
            if kind in MEDIA_KINDS:
                entry.update(_probe(f))
            entry["licensed"] = bool(entry["license"])
            out.append(entry)
    return out


def add_asset(kind: str, url: str, *, license: str, source: str | None = None,
              name: str | None = None, note: str = "",
              catalog: Path = CATALOG, runner=None) -> dict[str, Any]:
    """fetch.js 로 받고 CATALOG.md 표에 한 줄 추가. 라이선스 없으면 받지 않는다."""
    if kind not in SECTION_HEAD:
        raise ValueError(f"받기를 지원하지 않는 종류: {kind}")
    if not license.strip():
        raise ValueError("라이선스가 필요하다 — 소재 페이지에서 확인해 적는다 (CATALOG 규약)")

    run = runner or (lambda args: subprocess.run(
        ["node", "assets/fetch.js", *args], cwd=ENGINE_DIR,
        capture_output=True, text=True, timeout=300))
    proc = run([kind, url] + ([name] if name else []))
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip()[-500:])

    file_name = name or Path(url.split("?")[0]).name
    file = KIND_DIRS[kind] / file_name
    meta = _probe(file) if kind in MEDIA_KINDS and file.exists() else {}
    length = ""
    if meta.get("duration"):
        m, s = divmod(int(meta["duration"]), 60)
        length = f"{m}:{s:02d}"
        if meta.get("width"):
            length += f" · {meta['width']}×{meta['height']}"

    # CATALOG 섹션 표의 마지막 행 뒤에 추가 (열 구성은 섹션마다 다르다 — 실측 표 그대로)
    rel = f"{KIND_DIRS[kind].name}/{file_name}"
    src = source or url
    row = {
        "bgm": f"| `{rel}` | {length} | {src} | {license} | {note} |",
        "broll": f"| `{rel}` | {length} | {src} | {license} | {note} |",
        "photo": f"| `{rel}` | {src} | {license} | {note} |",
    }[kind]
    lines = catalog.read_text(encoding="utf-8").splitlines()
    # 제목에 부가 설명이 붙을 수 있다 (실측: "## 받아 둔 B롤 영상 (클립 `video`)") — 접두 일치
    anchor = next(i for i, l in enumerate(lines) if l.startswith(SECTION_HEAD[kind]))
    end = anchor + 1
    for i in range(anchor + 1, len(lines)):
        if lines[i].startswith("## "):
            break
        if lines[i].startswith("|"):
            end = i
    lines.insert(end + 1, row)
    catalog.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    # ref 는 목록 API 와 같은 규약 — scenes 기입값(엔진 루트 기준)
    return {"kind": kind, "name": file_name,
            "ref": (KIND_DIRS[kind] / file_name).relative_to(ENGINE_DIR).as_posix(),
            "license": license, "source": src, **meta}
