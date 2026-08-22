"""media_ops — 완성본 검수용 미디어 조작 (04_api: frames·silence).

ffmpeg/ffprobe 직접 호출 (engine 호출 계약 표의 "프레임 추출 = ffmpeg 직접" 행).
검수 프레임 preset=review 는 4분위 4장 + 끝 직전 1장(엔드카드) = 4+1종.
추출물은 out/<id>/frames/ 에 캐시 — 완성본이 더 새로우면 다시 뽑는다.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from . import env
from .status import OUT_ROOT
from .validate import CHARS_PER_SEC_LECTURE

import json as _json
import re as _re

from .schema import load_json


def final_mp4(episode_id: str) -> Path | None:
    final_dir = OUT_ROOT / episode_id / "final"
    if not final_dir.exists():
        return None
    files = sorted(final_dir.glob("*.mp4"))
    return files[0] if files else None


def media_duration(file: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(file)],
        capture_output=True, timeout=60, check=True, **env.child_kwargs(),
    ).stdout.strip()
    return float(out)


def extract_frame(episode_id: str, t: float) -> Path:
    """임의 시각 프레임 — out/<id>/frames/ 캐시. 완성본보다 오래된 캐시는 다시 뽑는다."""
    video = final_mp4(episode_id)
    if video is None:
        raise FileNotFoundError(f"final mp4 없음: {episode_id}")
    frames_dir = OUT_ROOT / episode_id / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    out = frames_dir / f"review-{t:07.1f}.jpg"
    if not (out.exists() and out.stat().st_mtime >= video.stat().st_mtime):
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", str(out)],
            timeout=60, check=True, **env.child_kwargs(),
        )
    return out


def clip_start_times(episode_dir: Path) -> dict[str, float]:
    """클립별 시작 시각 — chapters.js 와 같은 누적 규칙 (max(duration, 음성+0.5))."""
    scenes = load_json(episode_dir / "scenes.json")
    manifest_file = OUT_ROOT / episode_dir.name / "audio" / "manifest.json"
    manifest = _json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else {}
    starts: dict[str, float] = {}
    cursor = 0.0
    for clip in scenes.get("render", {}).get("motion", {}).get("clips", []):
        starts[clip["id"]] = cursor
        spoken = (manifest.get(f"motion-{clip['id']}") or {}).get("duration")
        if clip.get("narration"):
            base = (spoken + 0.5 if spoken
                    else len(clip["narration"]) / CHARS_PER_SEC_LECTURE + 0.5)
            cursor += max(clip.get("duration") or 0, base)
        else:
            cursor += clip.get("duration") or 0
    return starts


_YAVG_RE = _re.compile(r"pts_time:(?P<t>[\d.]+)|lavfi\.signalstats\.YAVG=(?P<y>[\d.]+)")


def _brightness_samples(video: Path, samples: int = 14) -> list[tuple[float, float]]:
    """한 패스로 (시각, 평균 밝기 YAVG) 표본 — 밝은/어두운 프레임을 실측으로 고른다."""
    total = media_duration(video)
    fps = max(samples / total, 0.05)
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video),
         "-vf", f"fps={fps},signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
         "-f", "null", "-"],
        capture_output=True, timeout=300, **env.child_kwargs(),
    )
    out: list[tuple[float, float]] = []
    t: float | None = None
    for m in _YAVG_RE.finditer(proc.stdout):
        if m.group("t") is not None:
            t = float(m.group("t"))
        elif t is not None:
            out.append((t, float(m.group("y"))))
            t = None
    return out


def review_frames(episode_id: str, episode_dir: Path | None = None) -> list[dict]:
    """검수 프레임 4+1종 (03 ⑥: 밝은/어두운/모션/마지막 + 타이틀) — 명암은 실측 선별.

    밝은 프레임 = 워터마크가 묻히는지, 어두운 프레임 = 자막이 뜨는지를 보는 용도라
    고정 4분위가 아니라 실제 최대/최소 밝기 지점을 고른다.
    """
    video = final_mp4(episode_id)
    if video is None:
        raise FileNotFoundError(f"final mp4 없음: {episode_id}")
    total = media_duration(video)

    title_t = total * 0.02
    if episode_dir is not None and (episode_dir / "scenes.json").exists():
        starts = clip_start_times(episode_dir)
        scenes = load_json(episode_dir / "scenes.json")
        for clip in scenes.get("render", {}).get("motion", {}).get("clips", []):
            if str(clip.get("file", "")).endswith("course-intro.html"):
                title_t = min(starts[clip["id"]] + 1.2, total - 0.5)  # 카드 등장 뒤
                break

    span = [(t, y) for t, y in _brightness_samples(video)
            if total * 0.03 <= t <= total * 0.95] or [(total * 0.5, 0.0)]
    bright_t = max(span, key=lambda s: s[1])[0]
    dark_t = min(span, key=lambda s: s[1])[0]

    picks = [("title", title_t), ("bright", bright_t), ("dark", dark_t),
             ("motion", total * 0.5), ("last", total * 0.98)]
    return [{"kind": kind, "t": round(t, 1),
             "file": extract_frame(episode_id, round(t, 1)).name} for kind, t in picks]


def extract_bg_frame(episode_dir: Path, source: Path, t: float) -> Path:
    """B롤의 t 시각 프레임을 회차 bg/ 에 저장 — 타이틀 카드 배경 규약의 한 버튼화 (03 ⑤).

    "videoStart 와 같은 시각의 프레임"이어야 B롤 정지 → 제목 등장이 이어진다 —
    두 값이 어긋나면 둘 다 조용히 망가진다(스킬 경고). 호출자가 같은 값을 넘긴다.
    """
    out_dir = episode_dir / "bg"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{source.stem}.jpg"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-ss", f"{t:.2f}", "-i", str(source), "-frames:v", "1",
         "-vf", "scale=1920:-1", str(out)],
        timeout=60, check=True, **env.child_kwargs(),
    )
    return out


_SILENCE_RE = re.compile(
    r"silence_(start|end): ([\d.]+)(?: \| silence_duration: ([\d.]+))?")

# 원인 분류 (04_api): 짧고 고른 무음 = 숨 고르기(uniform-breath — 스킬 실측 71건/93초 사례),
# 길면 클립 끝 공백(clip-end — BGM 죽음·전환 공백 의심)으로 사람 확인 대상.
BREATH_MAX = 1.2


def detect_silence(episode_id: str, *, noise: str = "-35dB", min_dur: float = 0.35) -> list[dict]:
    video = final_mp4(episode_id)
    if video is None:
        raise FileNotFoundError(f"final mp4 없음: {episode_id}")
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video),
         "-af", f"silencedetect=noise={noise}:d={min_dur}", "-f", "null", "-"],
        capture_output=True, timeout=300, **env.child_kwargs(),
    )
    silences: list[dict] = []
    start: float | None = None
    for kind, at, dur in _SILENCE_RE.findall(proc.stderr):
        if kind == "start":
            start = float(at)
        elif start is not None:
            duration = float(dur) if dur else float(at) - start
            silences.append({
                "start": round(start, 2),
                "end": round(float(at), 2),
                "duration": round(duration, 2),
                "cause": "uniform-breath" if duration <= BREATH_MAX else "clip-end",
            })
            start = None
    return silences
