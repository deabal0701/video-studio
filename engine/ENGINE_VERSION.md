# engine 동기화 기록

원본 = h5-saas 저장소의 `.claude/skills/develop-video/scripts/` (+ templates/motion ·
develop-lecture/scripts/chapters.js). 엔진을 고칠 일이 생기면 **원본(스킬) 쪽을 고치고
다시 떠 온다** — 이 저장소에서 직접 고쳤으면 아래 표에 남기고 다음 동기화 때 상류로 올린다.
규칙 상세: [docs/design/01_architecture.md](../docs/design/01_architecture.md).

| 날짜 | 원본 커밋 | 내용 |
|---|---|---|
| 2026-08-14 | h5-saas `2d88dd6b` | 최초 vendoring — build.js·check-tts.js·lib/(preflight 포함)·motion/·templates/·assets/(fetch·CATALOG)·chapters.js·fonts/(Pretendard, h5-saas 프론트에서) |

## 로컬 수정 (원칙 0건)

| 날짜 | 파일 | 왜 | 상류 반영 |
|---|---|---|---|
| — | — | — | — |

## 신설 (앱 전용 — 상류 무관)

- `inspect.js` — **2026-08-14 작성.** preflight·templateKeys·ffprobe·TTS 캐시를 JSON 출력
  ([04_api.md](../docs/design/04_api.md) 계약). 기존 lib 재사용·기존 파일 무수정.
  templateKeys 규칙은 lib/preflight.js 의 비공개 함수를 그대로 옮긴 사본 — 상류에서
  preflight.js 가 바뀌면 inspect.js 도 함께 맞춘다.
- `preview.js` — **2026-08-15 작성.** 모션 html 1장의 상대 css/js 참조를 인라인한 자체완결
  문서를 stdout 으로. params 는 서빙 URL 질의 문자열이 담당(_params.js 의 location.search
  방식 그대로 — 프리뷰가 곧 실물). inspect.js 에는 `--list-templates` 갤러리 모드 추가.
