# 05 — 에이전트 설계

> 결론 먼저: **Claude Agent SDK (Python) 기본 · LangChain/LangGraph 미채택 · 하이브리드**
> (에이전트는 저작·평가만, 나머지는 결정적 코드). 근거는 [01_architecture.md](01_architecture.md)의
> 비교표 — 여기서는 실행 설계만 다룬다.
> **2026-08-21 (D15): 제공자 이중화** — Claude 경로에 더해 OpenAI 경로를 선택 지원하고,
> `AGENT_TEST_MODE` 로 테스트 시 최저가 모델을 강제한다 (아래 "제공자 이중화" 절).

## 왜 이 구조인가 — 한 단락 요약

이 시스템의 제작 지식은 프롬프트가 아니라 **스킬 문서**(develop-video 799줄 + develop-lecture
425줄)로 존재하고, 이미 검증된 PoC(video-agent/agent.mjs)가 Claude Agent SDK 의
`settingSources` 로 그 스킬을 네이티브 로드해 동작했다. 결정적 오케스트레이션(큐·빌드·검증)은
일반 코드로 이미 완성이라 LangGraph 가 맡을 그래프가 남아 있지 않고, 남은 것은 "도구를 쥔
에이전트가 파일을 읽고 쓰는 열린 저작"뿐이다 — 그건 SDK 의 기본 형태다.

## 에이전트 작업 3종

모두 **단발 세션** (작업 하나 = query 하나 = 잡 하나). 상주 에이전트·대화 지속 없음 —
상태는 전부 파일로 남으므로 세션을 이어갈 이유가 없고, 비용·예측가능성에서 단발이 우월하다.

### A. 대본 초안 (draft)

| | |
|---|---|
| 입력 | episodeId · brief(회차 주제) · 근거 문서 경로들 (강좌 audience·episodeLength 는 course.json 에서) |
| 산출 | `plan.md`(구성표) · `facts.md`(출처 표) · `scenes.json`(골격+내레이션+params) · 필요시 `motion/*.html` |
| 규약 | develop-lecture SKILL 그대로: 회차 독립·골격(broll→title→hook→stinger→promise→ch/s→recap→outro)·예산 1,850자·용어 3~4개·재미 장치 3~4개·facts 근거 없는 수치 금지 |
| 도구 | Read·Write·Edit·Glob·Grep·Bash(제한)·WebSearch(자료조사) |
| 종료 조건 | 산출 파일 저장 + `--only tts` 실측으로 분량 확인까지 (스킬 5단계 규약) |

### B. 도식 생성 (diagram)

| | |
|---|---|
| 입력 | episodeId · clipId · 설명하려는 것 (+ 해당 구간 내레이션·발화시각) |
| 산출 | `projects/<id>/motion/<이름>.html` — `_base.css`/`_params.js` 참조, CSS 키프레임만 (rAF 금지 — 스크럽 렌더 제약), 발화시각 동기 delay |
| 규약 | 연출 팔레트(데이터 흐름·줌·그래프·계층·상태변화 — 한 도식에 기법 하나)·termnote(용어 주석) |
| 검증 | 생성 직후 preview.js 로 중간 시각 프레임 렌더 → 에이전트가 Read(이미지)로 자가 확인 후 종료 |

### C. 평가 (review)

| | |
|---|---|
| 입력 | episodeId (완성본 존재 필수) |
| 산출 | 점수 6항목(1~5)·고칠 것 목록 → `out/review-agent.json` + 제작 기록 md 의 `## 평가` |
| 규약 | `agents/reviewer.md` (스킬 동봉)를 읽고 그대로 수행. **제작 컨텍스트 없는 새 세션** — "만든 쪽이 채점하지 않는다" |
| 도구 | Read·Bash(ffprobe·ffmpeg 프레임 추출) — 쓰기는 평가 기록 파일만 |

컨셉 검증(스킬 4단계의 5안 병렬 심사)은 Claude Code 의 Workflow 도구 전용이라 SDK 로는
`asyncio.gather` 로 query N 개 병렬이면 재현되지만, **1차 범위에서 제외** — 강좌 회차는
골격이 고정이라 컨셉 검증의 대상(도입부 설계)이 이미 규약으로 닫혀 있다. 단발 홍보영상
기능을 나중에 넣으면 그때 추가.

## 실행 설계 (core/agents/)

```python
# 개념 스케치 — agent.mjs 의 Python 이식 + 잡 큐 통합
from claude_agent_sdk import query, ClaudeAgentOptions

options = ClaudeAgentOptions(
    cwd=REPO_ROOT,                          # .claude/skills/ 가 보이는 위치
    setting_sources=["project"],            # 스킬·규약 로드 (agent.mjs 검증 방식)
    system_prompt={"type": "preset", "preset": "claude_code", "append": TASK_RULES[task]},
    allowed_tools=["Read","Write","Edit","Glob","Grep","Bash","WebSearch"],
    disallowed_tools=["Bash(git commit*)","Bash(git push*)","Bash(rm -rf*)"],
    permission_mode="acceptEdits",
    max_turns=120,
)
async for message in query(prompt=task_prompt, options=options):
    ...  # 진행 텍스트를 잡 SSE 로 릴레이, 도구 호출은 로그로
```

| 설계 항목 | 결정 |
|---|---|
| 잡 통합 | 에이전트 실행도 **같은 잡 큐**의 잡 (kind=agent). SSE 로 진행 릴레이, 취소 지원 |
| 파일 경계 | 해당 회차 폴더 + 스킬(읽기) 밖 쓰기 금지 — disallowedTools 와 프롬프트 규칙으로 이중 |
| 편집 충돌 | 에이전트 잡 실행 중 그 회차는 UI 편집 잠금 (같은 파일을 동시에 쓰면 안 됨). 종료 후 watchfiles 가 UI 갱신 |
| 키 | `.env` 의 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` — 셸 → 저장소 `.env` → `~/.claude/develop-video.env`(공용) 순 (엔진과 동일 규약). 설치본은 첫 실행 위저드가 공용 파일에 기록. **선택 제공자의 키가 없으면 에이전트 메뉴만 비활성 + 사유 — 앱의 다른 전부는 키 없이 동작** |
| 비용 가드 | maxTurns + `AGENT_TEST_MODE`(최저가 강제) + `usage` 미터 화면 |
| 모델 | 작업별 기본(`TASK_MODELS`) + `.env` `AGENT_MODEL_DRAFT/DIAGRAM/REVIEW` 오버라이드. **현행 운영: 전부 Haiku** (2026-08-15 사용자 지시 — 4단계 실키 완주 $0.46/편). Opus/Sonnet 은 명시 지시 시 |

## 제공자 이중화 (D15 — 2026-08-21 사용자 지시)

전환 스위치는 데스크톱 **설정 화면** (.env 가 정본, 화면은 그 편집기).

```
AGENT_PROVIDER=claude|openai      # 기본 claude
AGENT_TEST_MODE=1                 # 켜면 제공자 불문 최저가 모델 강제 — "테스트는 싸게"
OPENAI_API_KEY=…  OPENAI_MODEL=…  # openai 경로. 모델 미지정 시 최저가 티어 기본
```

| | claude (기본) | openai (선택) |
|---|---|---|
| 구현 | 기존 `claude-agent-sdk` 경로 그대로 — 에이전틱(스킬 문서를 직접 읽고 파일 순회·기입) | 신규 — chat completions 구조화 생성으로 **내용만** 받고, plan.md·facts.md·scenes.json 파일 기입은 우리 코드가 결정적으로 수행 |
| 규약 주입 | `.claude/skills/` 네이티브 로드 (settingSources) | 스킬 규약의 기계화 가능 요지를 프롬프트에 요약 주입 — 원칙 3 의 예외를 명시적으로 감수 (품질은 claude 경로 우위) |
| 평가(C) | 완성본·프레임을 SDK 도구로 직접 읽음 | 검수 프레임 4+1장을 vision 입력으로 전달 |
| 테스트 모델 | `claude-haiku-4-5` ($1/$5 MTok) | nano/mini 티어 (OPENAI_MODEL 로 교체) |
| 키 게이트 | 제공자별 독립 — 선택된 제공자의 키만 검사 |

openai 경로의 존재 이유: 비용 비교, 그리고 조직 정책상 OpenAI 키만 가진 담당자의 대안.
초안 품질의 기본 권장은 claude 경로다.

## 사람 ↔ 에이전트 동선 (제품 관점)

```
② 커리큘럼: [AI 초안] → 잡 실행 (A) → plan/facts/scenes 생김
④⑤: 사람이 화면에서 손질 (에이전트 산출물 = 같은 파일이라 그대로 편집됨)
⑤: 설명 구간에 그림이 없다 → [AI 도식] (B) → 갤러리에 나타남 → 클립에 연결
⑥: 빌드 → [AI 평가] (C) → 점수·지적 → 사람이 고침 → 재빌드 → 재채점은 1회 (스킬 규약)
```

**에이전트가 없어도 모든 단계를 사람이 할 수 있다** — 에이전트는 가속기이지 필수 경로가
아니다. 이것이 상용 요금제 설계의 축이 된다 (기본 기능 vs AI 크레딧).

## 상용 모드에서 달라지는 것

| | 로컬 | 상용 |
|---|---|---|
| 키 | 사용자 본인 키 | 서비스 키 — 테넌트별 사용량 미터링·크레딧 차감 |
| 실행 위치 | 앱 서버 프로세스 | 에이전트 워커 (렌더 워커와 동종 격리 — 파일 접근이 테넌트 스코프) |
| 안전 | 개인 저장소 | 산출물 검열(라이선스·내레이션 근거) 정책 추가 검토 |
