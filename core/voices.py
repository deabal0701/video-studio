"""목소리 카탈로그 + 로컬 샘플 캐시.

**미리듣기를 한 번만 합성하고 파일로 남긴다.** 이유가 두 가지다:

1. **돈** — ElevenLabs 는 글자수 과금이고 Azure 도 종량이다. 목소리를 고르느라 같은 문장을
   열 번 듣는 것이 정상인데, 그때마다 과금하면 담당자가 미리듣기를 안 쓰게 된다.
2. **속도** — 실측(2026-08-22): azure 0.6s · edge 3.3s. 캐시가 있으면 즉시 난다.

캐시 위치 = `<data>/.cache/voice-samples/<provider>/<voice>.mp3`. 설치본에 **동봉하지 않는다** —
합성 결과물을 재배포하는 셈이 되고, 어차피 담당자 PC 에서 몇 초면 만든다.

## 목소리가 몇 개인가 (2026-08-22 실측)

| 제공자 | 한국어 | 비용 |
|---|---|---|
| edge | **3** (SunHi 여 · InJoon 남 · HyunsuMultilingual 남) | 무료·무제한 |
| azure | **10** (edge 3종을 포함하는 상위집합) | 종량 (프리티어 월 50만자) |
| eleven | 계정 보유분 | 유료 종량 |

edge 와 azure 는 **같은 뉴럴 음성**이라(engine/lib/tts.js 머리말) 이름이 같으면 소리도 같다.
그래서 azure 키가 없어도 겹치는 3종은 edge 로 들어볼 수 있다.
"""

from __future__ import annotations

import json
import re
import shutil
import urllib.request
from pathlib import Path

from . import env

SAMPLE_TEXT = "안녕하세요, 이 목소리로 강좌를 만듭니다."

# edge 실측 목록 (edge_tts.list_voices() 2026-08-22 — 전체 322개 중 ko 는 이 3개뿐).
# 목록 조회에 네트워크가 필요하고 거의 변하지 않아 값으로 둔다. 틀리면 합성이 실패해서 드러난다.
EDGE_KO = [
    {"id": "ko-KR-SunHiNeural", "name": "선희", "gender": "female"},
    {"id": "ko-KR-InJoonNeural", "name": "인준", "gender": "male"},
    {"id": "ko-KR-HyunsuMultilingualNeural", "name": "현수 (다국어)", "gender": "male"},
]

# azure 실측 목록 (koreacentral voices/list 2026-08-22 — 전체 556개 중 ko 10개).
# 키가 있으면 실제 조회를 먼저 하고, 실패하면 이 값으로 내려간다.
AZURE_KO = [
    {"id": "ko-KR-SunHiNeural", "name": "선희", "gender": "female"},
    {"id": "ko-KR-JiMinNeural", "name": "지민", "gender": "female"},
    {"id": "ko-KR-SeoHyeonNeural", "name": "서현", "gender": "female"},
    {"id": "ko-KR-SoonBokNeural", "name": "순복", "gender": "female"},
    {"id": "ko-KR-YuJinNeural", "name": "유진", "gender": "female"},
    {"id": "ko-KR-InJoonNeural", "name": "인준", "gender": "male"},
    {"id": "ko-KR-BongJinNeural", "name": "봉진", "gender": "male"},
    {"id": "ko-KR-GookMinNeural", "name": "국민", "gender": "male"},
    {"id": "ko-KR-HyunsuNeural", "name": "현수", "gender": "male"},
    {"id": "ko-KR-HyunsuMultilingualNeural", "name": "현수 (다국어)", "gender": "male"},
]

PROVIDER_LABELS = {
    "edge": "기본 (무료)",
    "azure": "Azure (키 필요 · 목소리 많음)",
    "eleven": "ElevenLabs (키 필요 · 유료)",
}


def _samples_root() -> Path:
    """`cache_dir()` 아래 — 동결본에서 쓰기 가능한 데이터 폴더로 이미 갈라져 있고,
    지워도 몇 초면 다시 만들어지는 파생물이라 캐시가 맞는 자리다."""
    return env.cache_dir() / "voice-samples"


def _safe(name: str) -> str:
    """파일 이름으로 쓸 수 있게 — eleven 목소리 이름에는 공백·하이픈·설명이 붙는다."""
    return re.sub(r"[^\w가-힣.-]+", "_", name)[:80] or "voice"


def sample_path(provider: str, voice: str) -> Path:
    return _samples_root() / provider / f"{_safe(voice)}.mp3"


def has_sample(provider: str, voice: str) -> bool:
    p = sample_path(provider, voice)
    return p.is_file() and p.stat().st_size > 0


# ── 카탈로그 ─────────────────────────────────────────────────────────────────
def _azure_live(key: str, region: str) -> list[dict]:
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list"
    req = urllib.request.Request(url, headers={"Ocp-Apim-Subscription-Key": key})
    with urllib.request.urlopen(req, timeout=20) as res:   # noqa: S310 — 고정 호스트
        data = json.load(res)
    known = {v["id"]: v["name"] for v in AZURE_KO}
    out = []
    for v in data:
        if not str(v.get("Locale", "")).startswith("ko-"):
            continue
        vid = v["ShortName"]
        out.append({"id": vid, "name": known.get(vid, v.get("LocalName") or vid),
                    "gender": str(v.get("Gender", "")).lower()})
    return out


def _eleven_live(key: str) -> list[dict]:
    req = urllib.request.Request("https://api.elevenlabs.io/v1/voices",
                                 headers={"xi-api-key": key})
    with urllib.request.urlopen(req, timeout=20) as res:   # noqa: S310 — 고정 호스트
        data = json.load(res)
    out = []
    for v in data.get("voices") or []:
        out.append({"id": v["voice_id"], "name": v.get("name") or v["voice_id"],
                    "gender": str((v.get("labels") or {}).get("gender", "")).lower()})
    return out


def catalog(provider: str) -> dict:
    """{provider, voices:[{id,name,gender,cached}], available, reason} — 실패해도 목록은 준다."""
    from . import config

    values = config.read_all()["values"]
    reason = ""
    if provider == "edge":
        voices, available = list(EDGE_KO), True
    elif provider == "azure":
        key, region = values.get("AZURE_SPEECH_KEY"), values.get("AZURE_SPEECH_REGION")
        available = bool(key and region)
        reason = "" if available else "Azure Speech 키·지역이 설정 화면에 없습니다"
        voices = list(AZURE_KO)
        if available:
            try:    # 실제 계정이 가진 목록이 정본 — 실패하면 실측 값으로 내려간다
                voices = _azure_live(key, region) or voices
            except Exception as err:   # noqa: BLE001
                reason = f"목록 조회 실패 — 실측 기준값을 보여줍니다 ({type(err).__name__})"
    elif provider == "eleven":
        key = values.get("ELEVENLABS_API_KEY")
        available = bool(key)
        reason = "" if available else "ElevenLabs 키가 설정 화면에 없습니다"
        voices = []
        if available:
            try:
                voices = _eleven_live(key)
                if not voices:
                    reason = ("계정에 쓸 수 있는 목소리가 없습니다 — "
                              "보이스 라이브러리에서 '내 음성'에 추가하세요")
            except Exception as err:   # noqa: BLE001
                available, reason = False, f"목록 조회 실패 ({type(err).__name__})"
    else:
        return {"provider": provider, "voices": [], "available": False,
                "reason": f"모르는 제공자: {provider}"}

    for v in voices:
        v["cached"] = has_sample(provider, v["id"])
    return {"provider": provider, "voices": voices, "available": available,
            "reason": reason, "paid": provider == "eleven"}


# ── 샘플 ─────────────────────────────────────────────────────────────────────
def ensure_sample(provider: str, voice: str, *, text: str = SAMPLE_TEXT,
                  gender: str = "female") -> Path:
    """캐시에 있으면 그대로, 없으면 한 번만 합성해 넣는다."""
    dest = sample_path(provider, voice)
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    from . import engine_io

    src = engine_io.tts_sample(text, gender=gender, voice=voice, provider=provider)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)     # 엔진 임시 파일은 그쪽이 치운다 — 복사만 한다
    return dest


def build_all(provider: str, *, text: str = SAMPLE_TEXT) -> dict:
    """그 제공자의 목소리를 전부 한 번씩 만들어 둔다 (이후 미리듣기는 공짜·즉시).

    실패한 목소리는 건너뛰고 사유를 모아 돌려준다 — 하나가 죽어도 나머지는 남아야 한다.
    """
    info = catalog(provider)
    made, skipped, failed = 0, 0, []
    for v in info["voices"]:
        if has_sample(provider, v["id"]):
            skipped += 1
            continue
        try:
            ensure_sample(provider, v["id"], text=text, gender=v.get("gender") or "female")
            made += 1
        except Exception as err:   # noqa: BLE001 — 한 목소리의 실패가 전체를 막지 않는다
            failed.append({"voice": v["id"], "error": str(err)[-200:]})
    return {"provider": provider, "made": made, "cached": skipped, "failed": failed,
            "chars": made * len(text), "dir": str(_samples_root() / provider)}
