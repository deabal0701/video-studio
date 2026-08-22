# 02 — 데이터 모델 · 경로 규칙 · 파생 상태

> 전부 실물(h5-saas `tools/video/projects/hr-basics*`)에서 실측한 구조다. 앱은 이 파일들을
> **그대로** 읽고 쓴다 — 새 포맷을 만들지 않는다. 엔진(build.js)이 이 스키마의 소비자이므로
> 앱이 임의 필드를 추가할 때는 `_` 접두(주석 관례)나 별도 파일로 한다.

## 파일 지도 — 무엇이 어디에

```
projects/
├── <강좌id>/                      # 강좌 공통 (예: hr-basics)
│   ├── course.json                # ★ 강좌 정체성 — 빌드에 직접 쓰이지 않는 참조 정본
│   ├── course-intro.html          # 회차 타이틀 카드 (params 로 회차 정보 주입)
│   └── course-stinger.html        # 시그니처 스팅어 3초 (회차 무관 고정)
└── <강좌id>-NN/                   # 회차 = 영상 한 편 (예: hr-basics-01)
    ├── scenes.json                # ★ 대본 — 빌드의 유일한 입력
    ├── plan.md                    # 구성표 (구간·내레이션·화면·글자수·소재길이)
    ├── facts.md                   # 자료조사 (주장—출처URL—확인날짜)
    ├── youtube.md                 # 배포 산출물 (제목·설명·챕터) — 앱이 자동 생성으로 대체
    ├── motion/*.html              # 회차 전용 도식
    ├── bg/*.jpg                   # B롤에서 뽑은 타이틀 배경 프레임
    └── out/                       # 파생물 — 삭제해도 재생성 가능
        ├── final/<변형>.mp4 · .srt
        ├── raw/take.webm · timeline.json    # 재합성용 — 지우지 않음
        ├── audio/manifest.json + 씬별 mp3   # TTS 캐시 (실측 길이의 출처)
        ├── motion/ · work/ · frames/
        └── .lock                            # 동시 실행 방지
```

강좌-회차 연결은 **폴더명 관례** — `<강좌id>-NN`. 회차 scenes.json 이 `../<강좌id>/…` 로
강좌 공통 파일을 상대 참조한다. 인덱서는 이 관례로 강좌를 묶는다
(비강좌 단발 영상 = course.json 없는 프로젝트 폴더).

## course.json — 강좌 정체성 (실측 스키마)

| 필드 | 타입 | 의미 | 앱 UI |
|---|---|---|---|
| `course` | str | 강좌 id = 폴더명 | 개설 시 확정, 이후 읽기 전용 |
| `title` | str | 강좌명 — 워터마크·타이틀 카드·스팅어에 들어감 | ① 강좌 설정 |
| `audience` | str | 대상 정의 (에이전트 초안 생성의 과녁) | ① |
| `tagline` | str | 스팅어 한 줄 — 개설 때 정하고 불변 | ① |
| `episodeLength` | str | 분량 규약 (예: "5분 — 약 1,850자") | ① (예산 계산 원천) |
| `episodes[]` | `{n, id, title, subtitle, 근거}` | 커리큘럼. `id` = 회차 폴더명 | ② 커리큘럼 보드 |
| `kind` | `lecture`(강의) · `promo`(홍보) · `ad`(광고) · `manual`(매뉴얼) · `general`(일반) | **엔진은 course.json 을 읽지 않는다** — 앱 전용 필드라 렌더에 영향 없음. 없으면 강의로 본다(옛 프로젝트) | 만들 때 고른다 (`core/kinds.py`) |
| ↳ 종류가 정하는 것 | 회차 골격(엔진 템플릿) · 기본 길이 · **기본 팔레트** | 강의만 `series: True` — 나머지는 단발 | — |
| `voice` | `{provider, lang, gender, rate, voice?}` | 시리즈 내내 고정 | ① (제공자·목소리·미리듣기) |
| ↳ `provider` | `edge`(무료·기본) · `azure` · `eleven` · `sapi` | 키 없으면 화면에서 비활성 | — |
| ↳ `voice` | 목소리 id — **있으면 `gender` 표보다 이것이 이긴다** (engine/lib/tts.js `resolveVoiceFor`). 카탈로그 실측(2026-08-22): edge 3종 · azure 10종 · eleven 계정별 | 미지정이면 `lang×gender` 기본값 | — |
| `palette` | `{brand, brandSoft, bg}` | 모션 클립 params 에 **수동 복붙되던 것** — 앱이 자동 주입 | ③ 브랜드 킷 |
| `render` | scenes.json render 와 동일 부분집합 | 회차가 그대로 복사해야 하는 블록 | ① (일관성 대조 기준) |

**규약**: 회차 scenes.json 의 `voice`·`render` 는 course.json 을 그대로 복사한다(스킬 규정).
지금은 python 원라이너로 수동 대조 — 앱은 **회차 저장 시 자동 대조**하고 어긋나면 경고 배지
+ "강좌 값으로 맞추기" 버튼을 단다.

## scenes.json — 대본 (실측 스키마)

### 최상위

| 필드 | 타입 | 비고 |
|---|---|---|
| `id` | str | 영상 id = 폴더명 = out 폴더명. **셋 일치 필수** |
| `baseUrl` | str | 화면 녹화용 앱 주소 (모션 전용이면 무의미하나 존재) |
| `capture` | `{width, height, storageState?}` | 녹화 뷰포트 |
| `voice` | course 와 동일 구조 | CLI `--provider`·`--gender` 로 덮어쓰기 가능 |
| `render` | 아래 | 합성 설정 전부 |
| `variants[]` | `{id, width, height, label?, captions?}` | 출력 변형. 세로(h>w)=쇼츠 판정 |
| `scenes[]` | `{id, narration, hold?, actions[]}` | **화면 녹화 씬** — 강좌는 대개 빈 배열 (모션 전용) |

### render

| 필드 | 기본/실측값 | 비고 |
|---|---|---|
| `fps`·`crf`·`preset` | 30 · 19 · medium | 인코딩 |
| `background`·`brand`·`brandText` | 강좌 palette 와 연동 | |
| `subtitleFont`·`subtitleScale`·`subtitleMargin` | (비움=OS 기본) · 0.046 · 0.065 | ★ 자막은 **시스템 설치 폰트만** 쓸 수 있다(엔진에 fontsdir 없음). 비우면 util.js 가 OS별 기본(darwin: Apple SD Gothic Neo / win: Malgun / linux: Noto CJK)을 쓴다 — 픽스처는 2026-08-14 "Malgun Gothic" 지정을 제거. Pretendard 교체(R2)는 엔진 상류에 fontsdir 지원이 필요해 상용 트랙 과제로 남김 ([06](06_roadmap.md)) |
| `watermark.text`·`watermarkAlign` | 강좌명 · 9(우상) | 비면 합성 경고 |
| `bgm`·`bgmGain`·`bgmDucking` | 경로 · 0.08 · true | 강의 기본 0.08 (무음 노출 방지 — 스킬 실측 71건/93초 사례) |
| `subtitles`·`captions` | true | 자막 끄기 요청 시만 false (.srt 는 항상 나감) |
| `endCard` | `{narration, duration, …}` | 촬영 없이 합성 단계에서 생성 |
| `motion.dir` | "motion" | 회차 전용 폴더 |
| `motion.clips[]` | 아래 | **강좌 영상의 본체** |

### clip (motion.clips 원소) — 대본 에디터의 편집 단위

| 필드 | 타입 | 편집 UI | 검증 |
|---|---|---|---|
| `id` | str | 자동 제안 (골격 관례: broll·title·hook·stinger·promise·chN·sN·recap·outro) | 중복 금지 |
| `file` | str — 모션 html 경로 | **템플릿 피커** (갤러리) | 존재 검사 · `video` 와 배타 |
| `video` | str — B롤 경로 | **라이브러리 피커** | 존재 검사 · 길이 검사 (아래) |
| `videoStart` | num | B롤 시작 오프셋 | `(소스길이 − videoStart) ≥ duration` — 위반 시 정지 프레임 |
| `shade` | num | 슬라이더 (B롤 0.35 · 타이틀 0.55 관례) | |
| `duration` | num | 무내레이션 클립만 직접 입력 | 내레이션 있으면 `max(duration, 음성+0.5)` 로 자동 — UI 는 실측치 표시 |
| `before` | "end" 등 | 고급 (기본 숨김) | |
| `narration` | str | **텍스트영역 + 글자수 뱃지** | 회차 예산 게이지에 합산 |
| `params` | obj | **자동 생성 폼** — 템플릿이 받는 키만 노출 (inspect.js templateKeys) | 받지 않는 키 입력 불가 → "조용히 사라지는 글자" 원천 차단 |
| `audioFile` | str | 없음 — 빌드가 채움 | 앱은 쓰지 않고 보존만 |
| `_*` | str | 주석 관례 — **보존 필수** (라운드트립에서 유실 금지) | |

**직렬화 규약**: 앱이 scenes.json 을 저장할 때 ① `_` 접두 주석 필드 보존 ② 키 순서 보존
③ 들여쓰기 2칸 유지 — Claude Code·사람과 같은 파일을 편집하므로 diff 가 깨끗해야 한다.
pydantic 모델은 `extra="allow"` 로 미지 필드를 통과시킨다 (엔진이 진화해도 앱이 데이터를 깎지 않게).

## ★ 경로 규칙 — 이 앱의 존재 이유

한 대본 안에 **상대경로 기준이 5종** 공존한다 (실측 — hr-basics-01 의 `_경로메모`:
"기준이 달라 실측으로 확정했다"). 전부 틀려도 **오류가 안 나고 조용히 망가진다.**

> 2026-08-14 실측 갱신: 구(h5-saas) 기준이던 표를 **이 저장소 + 현행 엔진** 실측으로 교체.
> compose.js 가 bgm 을 `AD_DIR`(엔진 루트)로 resolve 하고("bgm 경로는 영상 작업 폴더 기준"
> 주석), clip.file 은 **대본 폴더**(`projects/<id>/`) 기준(`resolveMotionFile`)이다 —
> 아래 실측 예가 그대로 `core/paths.py` 단위 테스트 케이스다.

| 필드 | 기준 디렉토리 | 실측 예 (fixtures/projects/hr-basics-01) | 틀리면 |
|---|---|---|---|
| `render.bgm` | **엔진 루트** (`engine/`) | `assets/bgm/mixkit-623-loop.mp3` | 합성 실패 or 무음 |
| `clip.video` (B롤) | **엔진 루트** (`engine/`) | `assets/broll/office-talk.mp4` | 검은 화면 |
| `clip.file` (모션) | **대본 폴더** (`projects/<id>/`) → 공용 `engine/motion/` 폴백 | `motion/hook-bill.html` 또는 `../hr-basics/course-intro.html` | 검은 화면 |
| `params.src` (카드 배경 이미지) | **그 html 파일** 위치 | course-intro.html 은 강좌 폴더에 있으므로 `../hr-basics-01/bg/…` | **조용히 검은 배경** (사전점검도 못 잡음 — 값이 가리키는 파일까지는 안 봄) |
| `params.fontUrl` | **그 html 파일** 위치 | 강좌 html 3단 상위 · 회차 motion/ html 4단 상위 · 공용 engine/motion/ html 1단 상위 (`../fonts/…`) — **같은 값이 클립마다 다름** | 폰트 폴백 (조용) |

전용 html 이 참조하는 공용 `_base.css`·`_params.js` 도 같은 함정이다 — 기준은 그 html 파일
위치이고, 이 저장소에서는 `engine/motion/` 까지 회차 motion/ html 4단 · 강좌 html 3단 상위다.

**앱의 처리 — 사람은 경로 문자열을 절대 만지지 않는다:**

1. UI 는 **자산 참조** (`{kind: "bgm"|"broll"|"motion"|"image"|"font", id}`) 로만 다룬다.
2. `core/paths.py` 가 저장 시점에 기준별 상대경로를 **계산해 기입**한다.
   - 입력: 자산의 절대 위치 + 참조 필드 종류 + (params 의 경우) 소속 html 의 위치
   - 계산기는 위 표 5행을 각각 단위 테스트로 고정한다 (실측 예가 그대로 테스트 케이스)
3. 읽을 때는 역산해 자산 참조로 복원. 역산 불가(수동 편집 등)면 원문 보존 + 화면에 경고 표시.
4. `fontUrl` 은 엔진 동봉 폰트(`engine/fonts/Pretendard…`)를 기본으로 자동 주입.
5. `params.src` 는 저장 시 **파일 존재까지 검사** (사전점검의 사각을 앱이 메움).

## 길이·분량 계산 (build.js 규칙과 동일해야 함)

| 규칙 | 값 |
|---|---|
| 클립 길이 | `max(선언 duration, 음성길이 + 0.5)` |
| 화면 씬 길이 | 음성길이 + `hold`(기본 0.6) |
| 총 길이 | 클립 합 + 씬 합 + endCard |
| 페이스 | 표준 6.3자/초 (선희 +6% · 인준 +15%) / **강좌 6.4자/초** (선희 +8% · 인준 +19%) |
| 강좌 예산 | 1,850자 (290초 × 6.4 − 여유) · 완성본 허용 4:40~5:20 |

앱 표시 규칙: TTS 캐시(`out/audio/manifest.json`)가 있으면 **실측 길이**, 없으면
글자수÷페이스 **추정 길이** — 라벨을 갈라 보여 준다("실측/추정"). 추정→실측 전환은
`--only tts` 잡(몇 초·무료)으로 화면에서 바로 갱신할 수 있게 한다.

## 파생 상태 — 계산으로만 얻는다 (저장 금지)

| 상태 | 도출 규칙 |
|---|---|
| 회차 상태 ⬜/🔄/✅ | ⬜ = scenes.json 없음 · 🔄 = 있으나 final 없음/평가 전 · ✅ = final mp4 존재 + 평가 기록 |
| 예산 초과 | 내레이션 합 vs course.episodeLength 역산 예산 |
| 일관성 | scenes.voice ≡ course.voice ∧ scenes.render ⊇ course.render |
| 평가 점수 | 제작 기록 md 의 frontmatter `score:` |
| 빌드 신선도 | final mtime < scenes.json mtime → "대본이 더 새것 — 재빌드 필요" 배지 |

## 동시성·충돌

| 위험 | 장치 |
|---|---|
| 같은 회차 이중 빌드 | 엔진의 `out/<id>/.lock` 존중 + 앱 큐가 회차별 직렬화 |
| 앱 ↔ 외부(Claude Code·에디터) 동시 편집 | 저장 API 에 `If-Match: <mtime-etag>` — 불일치 시 409 + 화면에 diff 보여 주고 사람이 병합 |
| 파일 외부 변경 감지 | `watchfiles` → 인덱스 갱신 + 열려 있는 편집 화면에 "파일이 밖에서 바뀜" 알림 |
| 캐시 vs 파일 불일치 | SQLite 는 항상 버릴 수 있는 파생물 — mtime 불일치 시 해당 항목 재스캔 |
