# 08 — Qt 화면 스타일 가이드 (PySide6)

> **모든 Qt 화면 작업(5-3~5-6) 착수 전에 읽는다.** D11 디자인 토큰의 정본 값은
> [app/theme.py](../../app/theme.py) 이고, 이 문서는 "그 토큰을 Qt 에서 어떻게 깨지지 않게
> 구현하는가"의 규칙이다. 웹 CSS 감각을 그대로 가져오면 깨지는 지점(§3)이 핵심이다.
> 근거 출처는 문서 말미(§9).

## 1. 3층 스타일 규칙 — 순서가 곧 규칙이다

앱 시작 시 반드시 이 순서로 고정한다 ([app/main.py](../../app/main.py)):

```python
app = QApplication(sys.argv)
app.setStyle("Fusion")                 # ① 스타일 고정
app.setPalette(theme.make_palette())   # ② 팔레트 명시
app.setStyleSheet(theme.STYLESHEET)    # ③ QSS 는 마지막
```

| 층 | 역할 | 왜 필수인가 |
|---|---|---|
| ① `setStyle("Fusion")` | 플랫폼 중립 위젯 렌더러 | 기본 `windows11` 스타일은 QSS 와 조합이 어긋난다(밑줄만 있는 평평한 입력 필드 등). Fusion + QSS 가 공식 권장 조합 |
| ② `setPalette()` | **모든** 색 역할(Base·Text·Window·Highlight…)을 명시 | **QSS 가 안 덮은 위젯은 OS 팔레트를 물려받는다** — Windows 11 다크모드에서 앱이 얼룩덜룩해진 5-3 실증 결함(설정 폼의 "대상" 박스가 검게 뜸)의 근본 원인. 팔레트를 명시하면 OS 테마와 무관해진다 |
| ③ QSS | 토큰 기반 시각(색·라운드·간격) | theme.py 한 곳만. 화면 코드에 색·픽셀 하드코딩 금지 (기존 규칙) |

**규칙: 새 위젯 타입을 화면에 처음 쓰면 QSS 에 그 타입 항목이 있는지 확인한다.**
없으면 팔레트 폴백으로는 뜨지만, QSS 로 명시해야 토큰과 일치한다. (이번 결함이 정확히
QLineEdit·QPlainTextEdit·QComboBox 누락이었다.)

## 2. 다크모드 — "따라가지 않는다"가 결정이다

- Qt 6.5+ 는 Windows 다크모드를 자동 감지해 팔레트를 바꾼다. 우리 앱은 **라이트 고정**
  (D11 토큰이 라이트 기준, 렌더 결과물 검수 색 판정도 라이트 기준).
- §1 의 ①+② 만으로 위젯 영역은 완전히 고정된다. 남는 것은 **창 제목줄**(OS 가 그림) —
  Qt 6.7+ 는 팔레트를 따라간다. 어긋나 보이면 `QT_QPA_PLATFORM=windows:darkmode=0` 이
  마지막 수단이지만, 위젯이 고정돼 있으면 제목줄 정도는 허용.
- 나중에 다크 테마를 제공하려면 theme.py 토큰을 딕셔너리 2벌로 만들고 palette+QSS 를
  재생성해 `setStyleSheet` 를 다시 부른다 (Qt-Material 방식 — §8).

## 3. QSS ≠ CSS — 웹 감각이 깨지는 지점

QSS 는 CSS 2.1 부분집합 + Qt 확장이다. **지원**: box model(margin·padding·border),
`border-radius`(모서리별), 그라디언트(`qlineargradient` 등), `:hover :pressed :focus
:checked :disabled :selected` 등 의사상태, `::` 서브컨트롤. **미지원 — 시도 금지**:

| 쓰고 싶은 것 | QSS 에 없음 | 대신 이렇게 |
|---|---|---|
| `box-shadow` | ✗ ("Unknown property") | `QGraphicsDropShadowEffect` + `setGraphicsEffect()` (위젯당 1개, 비용 있음 — 카드 수십 장에 남발 금지). 보통은 **1px 테두리 + 배경 대비**로 충분 (현행 카드가 이 방식) |
| `transition`·애니메이션 | ✗ | `QPropertyAnimation` (hover 등은 그냥 즉시 전환으로 — 과용 금지) |
| flexbox·grid | ✗ | 레이아웃은 QSS 가 아니라 **QLayout 클래스**의 일이다 (§4) |
| `text-shadow`, `transform` | ✗ | 쓰지 않는다 |

함정 2개:

- **border 세트 규칙**: `background-color` 만 지정하면 네이티브 그리기가 남아 배경이 안
  먹을 수 있다 — 배경을 바꾸는 위젯은 `border` 도 함께 명시한다 (`border: none` 이라도).
- **동적 속성 재적용**: `QLabel[chip="ok"]` 류는 속성 변경 후
  `style().unpolish(w); style().polish(w)` 를 불러야 갱신된다 (main_window 잡 칩이 선례).
- **radius 상한**: `border-radius` 가 박스 높이의 절반을 넘으면 CSS 처럼 클램프되지 않고
  **통째로 무시된다** — pill 버튼이 갑자기 각지면 높이(폰트·패딩)가 줄어든 것부터 의심.

## 4. 레이아웃 — 이쁜 화면의 8할은 QSS 가 아니라 레이아웃이다

5-3 설정 폼이 못생겼던 실제 이유 3개 중 2개가 레이아웃이었고, 그 뒤 전 화면 점검(09)에서
나온 빈 화면 3종도 전부 레이아웃이었다. **화면이 못생겼으면 QSS 보다 여기부터 본다.** 규칙:

1. **폼은 위로 붙인다.** `QFormLayout` 을 페이지에 직접 얹으면 남는 세로 공간을 행
   사이에 분배해 **행간이 200px 씩 벌어진다** (5-3 실측). 반드시:
   ```python
   outer = QVBoxLayout(self)
   outer.addLayout(form)
   outer.addStretch(1)          # 남는 공간은 폼 아래로
   ```
2. **읽는 폭을 제한한다.** 입력 필드가 창 폭 전체(1100px+)로 늘어나면 안 된다.
   한 줄 입력·콤보는 `setMaximumWidth(RD_FIELD)` (토큰 720px), 여러 줄은 폭 720 + 높이
   내용 기준. 폼 전체를 좁히는 게 아니라 **필드만** 좁힌다 (라벨 정렬 유지).
3. **간격은 토큰 배수만.** `GAP_STACK`(16)·`GAP_CARD`(20)·`GAP_SECTION`(40)·`PAGE_PAD`(22).
   `setSpacing`/`setContentsMargins` 에 임의 숫자를 넣지 않는다. QFormLayout 은
   `setHorizontalSpacing(16)`·`setVerticalSpacing(GAP_STACK)` 명시 (기본값이 스타일마다 다름).
4. **정렬 기본값**: 폼 라벨 오른쪽 정렬(현행), 버튼 행은 왼쪽 시작 + `addStretch(1)`,
   페이지 제목 아래 설명(`pageDesc`)은 제목과 같은 x.
5. 위계는 **여백 > 선 > 배경색** 순으로 만든다. 구분선을 긋기 전에 GAP_SECTION 을 먼저
   시도한다 (apple.com 문법 — D11).
6. **남는 공간을 누가 먹는지 항상 명시한다.** 안 정하면 Qt 가 마음대로 나눠 갖는다 —
   이 문서의 화면 결함 중 최다 원인이다. 두 얼굴로 나타난다: 명시 안 한 쪽이 **부풀거나**
   (1번의 폼 행간 붕괴), 명시 안 한 쪽이 **눌린다**(2026-08-22 빈 화면 3종 — ⑥ 검수 영상
   칸·⑤ 프리뷰가 300px 로 압축·⑦ 설명 칸 고정 높이). 주역 위젯에 `addWidget(w, stretch)`
   나 `setStretchFactor` 로 몫을 주고, 자투리는 `addStretch(1)` 로 흡수한다.
7. **고정 비율 콘텐츠는 stretch 가 아니라 비율로 잡는다** — 영상·엔진 문서(1920×1080)처럼
   가로세로 비가 정해진 것에 stretch 만 주면 **고친 자리에서 새 결함이 난다**: 눌린 건
   풀리지만 세로로 늘어난 만큼 콘텐츠 아래에 흰 띠가 남는다 (2026-08-22 ⑤ 프리뷰 실측).
   stretch 로 자리를 받은 뒤 `resizeEvent` 에서 16:9 로 되잡는다
   (`app/pages/clip_editor.py` 의 `_PreviewColumn` 이 선례).

## 5. 위젯별 규약 (이 프로젝트의 결)

| 위젯 | 규약 |
|---|---|
| 입력(QLineEdit·QPlainTextEdit·QComboBox·QSpinBox) | 흰 배경 + 1px SEPARATOR 테두리 + radius 8 + padding 6~10px. `:focus` 에 ACCENT 테두리. **밑줄만 있는 필드·테두리 없는 필드 금지** |
| 버튼 | pill (radius = 높이/2). primary(파랑 채움)는 화면당 1개 원칙, 나머지는 흰 배경 테두리. 아이콘+텍스트 조합 가능 |
| 카드 | `QFrame#card` — 흰 배경·1px 테두리·radius 18. 클릭 카드는 `:hover` 에 테두리 진하게 |
| 칩 | `QLabel[chip=...]` **5종** — `info` 중립(회색) · `run` 진행 중(파랑) · `warn` 주의(주황) · `ok` 성공(초록) · `err` 실패(빨강). **색이 곧 뜻이다** — 새 상태색을 만들지 말고 이 5종에 맵핑한다. 속성을 바꾼 뒤에는 `unpolish`/`polish` (§3) |
| 표 | 헤더는 배경 없는 caption 스타일(현행). 행 높이 32px+, `setAlternatingRowColors(True)` 권장 |
| 로그 | `QPlainTextEdit#log` 다크 패널 (유일하게 어두운 표면 — 다른 곳에 BG_DARK 쓰지 않는다) |
| 상태 표시 | **색 점 + 한국어 라벨** — `theme.STATE_COLORS` + `theme.dot(color)`. 상태를 기호로 말하지 않는다 (아래 항목) |
| 문구 | **Qt 가 그리는 문구는 번역기로, 우리가 쓰는 문구는 한국어 문자열로.** `QDialogButtonBox.Cancel`·`QMessageBox.question` 의 Yes/No 는 우리 문자열이 아니라 Qt 가 그리므로 한국어로 안 바뀐다(2026-08-22 실측: 새 강좌 위저드에 영문 "Cancel" 노출). [app/i18n.py](../../app/i18n.py) 가 `qtbase_ko.qm` 을 `installTranslator` 로 얹어 표준 문구를 한 번에 해결한다 — **최선 노력**(파일이 없으면 그 문구만 영문, 앱은 그대로 뜬다). 우리가 직접 만드는 버튼은 번역 파일과 무관하게 한국어를 명시한다. QApplication 을 만드는 모든 경로(앱·캡처 스크립트·동결본 spec)가 이 설치를 거쳐야 한다 |
| 아이콘 | **이모지에 의미를 싣지 않는다.** 장식으로도 쓰지 않는다 — OS 이모지 폰트가 제멋대로 대체 렌더한다. 2026-08-22 전 화면 캡처 실측: `⬜`→체크박스 아이콘 · `🔄`→"END" 화살표 · `✅`→초록 체크 · `🏠🎞⚙🔧`→크기·색 제각각. **상태 기호가 뜬금없는 그림이 된다.** 아이콘이 꼭 필요하면 `qtawesome` 의 Material Design(`mdi6.*`): `qta.icon("mdi6.home", color=theme.INK_2)`. **집행자**: [tests/test_repo_hygiene.py](../../tests/test_repo_hygiene.py) 가 `app/` 의 문자열 리터럴을 AST 로 훑는다(독스트링 제외 — 설명문에는 실측 예시를 적어도 된다). `✓`·`▶` 는 텍스트 글리프로 안정 렌더돼 허용 |
| 카드 폭 | `theme.CARD_W`(320) 상한 — 카드가 1장일 때 화면 폭 전체로 늘어나는 것을 막는다 (§4-2 의 카드 판) |
| 내비 | **하이라이트는 "지금 어디인가"의 답이다 — 틀리면 안 된다.** 페이지를 코드로 바꿀 때(`show_course`·`show_episode` 처럼 스택만 전환하는 경로) 내비 선택도 함께 옮긴다. 내비 밖에서 파고든 화면은 출발지 항목에 표시한다. 2026-08-22 실측: 설정 화면에서 회차로 들어가면 화면은 회차인데 내비는 "설정"에 남아 있었다 |
| 스크롤 | 콘텐츠가 넘칠 수 있는 페이지는 전체를 QScrollArea 로 감싼다 (`setWidgetResizable(True)`) |

## 6. 화면 검증 — "실측"의 Qt 판

- **offscreen 캡처로 색·좌표를 검증한다** (5-3 확립): `QT_QPA_PLATFORM=offscreen` +
  `widget.grab().toImage().pixelColor(x, y)`. 단 offscreen 은 ①**Qt 위젯 텍스트**의 한글이
  두부로 뜨고 ②**OS 다크모드가 적용되지 않는다** — 다크모드 오염 결함은 offscreen 에서
  재현이 안 됐다. §1 의 팔레트 명시가 돼 있으면 offscreen 결과 = 실창 결과다
  (그래서 §1 이 검증 전제이기도 하다).
- **두부는 Qt 위젯 텍스트에 한정된다** — `QWebEngineView` 안의 **웹 콘텐츠는 offscreen
  에서도 한글이 정상 렌더**된다 (2026-08-22 실측: 90px 한글 문장 → 잉크 3,746px, 육안 정상).
  즉 프리뷰(모션 html) 검증은 offscreen 캡처로 충분하고, 두부를 이유로 실창을 잡을 필요 없다.
- **QWebEngineView 의 `grab()` 은 §9 의 Chromium 플래그가 있어야 픽셀이 잡힌다.**
  5-0 의 "웹뷰는 grab 에 안 잡힌다" 결론은 플래그 없는 상태의 관찰이었다 —
  같은 문서·같은 코드로 재실측(2026-08-22): 플래그 없음 → `loadFinished(ok=False)`,
  캡처 고유색 1개(빈 화면) / 플래그 있음 → `ok=True`, 고유색 8개(정상 렌더).
  **플래그 없이 빈 캡처가 나오면 "웹뷰는 원래 안 잡힌다"가 아니라 로드 실패를 의심한다.**
- **고유색 1개 = 로드 실패, 단 `t=0` 은 예외.** 모션 문서는 요소가 페이드인하므로 시작
  시각의 캡처는 배경뿐이라 정상이어도 색이 거의 없다 — **중간 시각으로 시킹한 뒤 캡처한다**
  (`getAnimations({subtree:true})` 로 `pause()` + `currentTime` 지정, ⑤ 스크럽과 같은 방식).
  두 세션이 각각 이 함정을 밟았다: 로드에 성공(`ok=true`)했는데도 텍스트가 안 보여
  실패로 오독 → 한 사이클 낭비 (2026-08-22).
- **로드 완료 판정을 `runJavaScript` 응답으로 하지 않는다** — 초기 빈 페이지에서도 JS 는
  응답하므로 조기 통과한다. `loadFinished(ok)` 시그널을 받거나 `view.url()` 이 채워질
  때까지 기다린 뒤 판정한다.
- **캡처 자체를 의심한다 — 조건 충족 직후의 `grab()` 은 빈 화면이다.** 데이터가 도착해도
  위젯은 아직 배치·페인트 전이라, 그 순간 찍으면 멀쩡한 화면이 "아무것도 안 보인다"로
  나온다. 조건 충족 후 **이벤트 루프를 한 번 더 돌린다**(`processEvents` 를 0.5~1초
  펌프). 2026-08-22 실측: 대시보드를 "카드가 안 보인다"고 오진할 뻔했고 `pump(0.8)`
  으로 정상 확인. **화면 결함을 보고하기 전에 캡처 방식부터 의심한다.**
- Playwright 교차 스크린샷은 여전히 유효한 대조 수단이다 (엔진이 실제로 굽는 화면과의 대조).

## 7. 하지 말 것 목록 (실증 사고 모음)

> **어떤 규칙은 테스트로, 어떤 규칙은 글로 지킨다.** 판정이 객관적이고(참/거짓이 명확)
> 재발이 잦으면 [tests/test_repo_hygiene.py](../../tests/test_repo_hygiene.py) 에 집행자를
> 세운다 (BOM·이모지가 그렇게 갔다). 판단이 필요하거나 사례가 손에 꼽으면 여기 글로 둔다 —
> "주석이 달렸는가" 같은 대리 지표를 기계로 강제하면 형식만 갖춘 주석이 늘 뿐이다.

- QSS 없이 위젯 추가 → OS 다크모드에서 검은 얼룩 (5-3 설정 폼)
- QFormLayout 을 스트레치 없이 페이지에 직접 → 행간 붕괴 (5-3 설정 폼)
- 화면 코드에 `setStyleSheet("색·픽셀 하드코딩")` → 토큰 우회. 예외는 ColorButton 처럼
  **값 자체가 데이터**인 경우뿐
- `box-shadow`·`transition` 등 미지원 CSS 를 QSS 에 넣기 → 조용히 무시되거나 경고
- 시그널을 클로저에 직접 연결 → 워커 스레드에서 위젯 접근 (bridge.py 영속 디스패처 경유 — 5-3)
- **선택 상태를 코드로 바꾸면서 시그널을 안 막기** — `setCurrentRow`·`setCurrentIndex` 는
  사용자 조작과 똑같이 `currentRowChanged` 를 쏘므로, 그 핸들러가 방금 한 일을 되돌린다
  (내비를 맞추려다 열어 둔 회차가 대시보드로 튕겨 나갔다 — 2026-08-22). `blockSignals`
  로 감싸고 **왜 감쌌는지 주석을 남긴다** (안 남기면 다음 사람이 "불필요해 보이는" 그 줄을 지운다)
- 이모지 아이콘 신규 추가 — 장식이든 **상태 기호든** (§5). 상태는 색 점 + 한국어 라벨
- 배치·페인트 전에 캡처해 놓고 "화면이 비었다"고 오진 (§6)
- 개발 진행 문구를 화면에 노출 ("5-4 에서 열립니다" 류 자리표시자) — 담당자가 읽는 화면이다
- QWebEngineView 를 쓰는 스크립트에서 `app.bootstrap` 임포트 생략 → 프리뷰 로드 실패(§9)
- 빈 캡처를 보고 "웹뷰는 grab 이 안 된다"로 결론 → 실제로는 로드 실패였다 (§6)
- 시킹 없이 `t=0` 을 캡처하고 로드 실패로 판정 → 페이드인 전이라 정상인 화면이다 (§6)
- 설치 폴더(코드·엔진이 있는 곳)에 쓰기 — 캐시·산출물·로그는 전부 `env.cache_dir()`·
  `env.out_root()` 로. 개발 모드에서는 둘이 같은 폴더라 **버그가 안 보인다**: 동결본
  스모크의 "설치 폴더 쓰기 0건" 검사가 유일한 안전망이다 (5-7 에서 indexer·agents
  캐시 2건이 이 검사로 잡혔다)

## 8. 기성 테마 라이브러리 — 검토했고, 안 쓴다

[Qt-Material](https://qt-material.readthedocs.io/)(Material Design 테마)·
[Qt Advanced Stylesheets](https://github.com/githubuser0xFFFF/qtass-pyside6)(런타임 색 교체)
는 완성도가 있지만, D11 은 Material 이 아니라 apple.com 문법이고 토큰 정본이 이미
theme.py 에 있다. 통째 테마를 얹으면 웹판과의 시각 연속성이 깨지므로 **자체 토큰 유지**.
단 두 라이브러리의 **구조**(토큰 딕셔너리 → QSS 템플릿 생성, 다크/라이트 2벌)는 다크
테마가 필요해질 때 참고.

## 9. 실행 환경 메모 (화면 작업 전 확인)

- **QtWebEngine 은 `QApplication` 생성 전에 준비가 끝나야 한다** — [app/bootstrap.py](../../app/bootstrap.py)
  가 그것만 담당하고, [app/main.py](../../app/main.py) 가 **최상단에서** 임포트한다. 두 가지다:
  ① `from PySide6.QtWebEngineWidgets import QWebEngineView` 를 QApplication 보다 먼저
  (`AA_ShareOpenGLContexts` 가 그때 선다) ② `QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu
  --no-sandbox --disable-gpu-compositing`. ②가 없으면 **페이지가 아예 안 뜬다**
  (빈 화면이 아니라 `loadFinished(ok=False)`) — 2026-08-22 두 세션이 각각 재현.
  플래그를 주면 `Failed to create GLES3 context, fallback to GLES2` 경고만 남고 정상 렌더.
  GPU 가 멀쩡한 PC 도 소프트웨어 렌더로 내려가지만, 담당자 PC 의 GPU·드라이버가 제각각이라
  **예측 가능성을 택한 결정**이다 (설치본에도 그대로 간다 — 5-7).
  프리뷰를 쓰는 스크립트·스모크도 반드시 같은 경로(`import app.bootstrap` 먼저)를 탄다.
  **동결본(PyInstaller onedir)에서도 이 임포트 순서는 유지된다** — 별도 runtime hook 불필요
  (5-7 실측 2026-08-22: 동결본 프리뷰 정상 렌더 `anims=2`·고유색 28).
- 파이썬은 conda `penv3.13-video` **하나**다 (2026-08-22 재통일 — insait 와 분리).
  PySide6 포함 **전부 pip** 으로 설치하고, **동결(PyInstaller)도 같은 env** 에서 한다.
  실행은 `.\run.ps1`, 설치본은 `.\packaging\build-installer.ps1`.
  옛 env(penv3.13-insait)의 pip 휠 실패(Qt6Core DLL WinError 127)는 conda 자체가 아니라
  **그 env 의 DLL 오염**(libffi 승격 — ctypes 까지 깨져 있었다)이었다. 깨끗한 env 실측:
  pytest 141 · 프리뷰 고유색 34 · 동결 Qt DLL 42종+WebEngineProcess+icudtl 정상.
- **단, 이 env 의 PySide6 는 pip 휠이어야 한다** — conda-forge 로 다시 깔면 동결이 깨진다.
  conda-forge 는 Qt 자산을 파이썬 패키지 **밖**에 둔다:

  | 자산 | conda-forge | pip 휠 (PyInstaller 훅이 찾는 곳) |
  |---|---|---|
  | `Qt6*.dll` 81개 | `$PREFIX\Library\bin\` | `site-packages\PySide6\` |
  | 플랫폼 플러그인 | `$PREFIX\Library\lib\qt6\plugins\platforms\` | `site-packages\PySide6\plugins\platforms\` |
  | `QtWebEngineProcess.exe` | `$PREFIX\Library\lib\qt6\` | `site-packages\PySide6\` |
  | `*.pak`·`icudtl.dat`·locales | `$PREFIX\Library\share\qt6\resources\`·`translations\` | `site-packages\PySide6\resources\`·`translations\` |

  conda-forge 설치본의 `site-packages\PySide6` 안에는 **Qt6 DLL 0개·plugins 없음**(대조:
  pip 휠은 144개·plugins/platforms/QtWebEngineProcess/resources/icudtl 전부 — 두 세션이
  각각 재현)이라 훅의 `collect_dynamic_libs('PySide6')` 가 빈손이 된다 → 동결본이
  "could not find or load the Qt platform plugin" 로 죽거나, 떠도 WebEngine 프리뷰(D10)가
  못 뜬다. **한때 이 때문에 동결 전용 `.qt-venv` 를 따로 뒀는데**, pip 휠이 깨끗한 conda
  env 에서 정상임이 확인되며 은퇴했다(2026-08-22 — setup-qt-venv.ps1 삭제). 개발과 동결이
  같은 env 를 쓰는 지금, 이 표는 "**이 env 의 PySide6 를 pip 휠로 지켜야 하는 이유**"다.
- **`.ps1` 은 UTF-8 BOM 으로 저장한다 — 새 스크립트를 만들 때마다, 기존 것을 다시 쓸 때마다.**
  PowerShell 5.1 은 BOM 없는 파일을 ANSI 로 읽어 한글·em-dash 가 깨지고, 깨진 문자가
  구문에 걸리면 `Unexpected token '}'` 로 **파서까지 죽는다**(실행 전에는 안 드러난다).
  문서에 적힌 뒤에도 **세 번 재발했다**(setup-qt-venv.ps1 → run.ps1 재작성 → 5-8 신규 3종)
  — 그래서 규칙의 집행자를 [tests/test_repo_hygiene.py](../../tests/test_repo_hygiene.py)
  로 두었다. 새 `.ps1` 은 이 테스트가 자동으로 잡는다.
- **UI 의존성을 늘리면 라이선스 고지 의무가 따라온다** — PySide6(LGPL-3.0)·QtWebEngine
  (Chromium)·번들 폰트가 이미 그 대상이고, 고지 정본은 `NOTICE.md`(생성기 =
  `packaging/collect-licenses.ps1`)다. 주의: **PySide6 휠에도 Playwright Chromium 빌드에도
  라이선스 전문이 들어 있지 않다**(5-8 실측 — 휠에는 상용 라이선스 참조 파일 하나뿐,
  Chromium 정본은 브라우저 안 `chrome://credits`). 그래서 전문은 정본 출처에서 받아
  캐시하고, 하나라도 없으면 빌드를 실패시킨다 — **원문을 손으로 쓰지 않는다.**
  새 위젯 라이브러리(qtawesome 등)를 도입하면 그 라이선스도 이 목록에 추가한다.
- PS 5.1 에서 네이티브 exe 의 **stderr 를 리다이렉트하면 `$?` 가 거짓이 되고,
  `$ErrorActionPreference="Stop"` 아래서는 NativeCommandError 로 던져진다** — 준비 상태
  탐지는 `$?` 가 아니라 `$LASTEXITCODE` 로 판정한다 (run.ps1 준비 1 주석 참조).

## 10. 출처

- [Qt for Python — Styling the Widgets Application](https://doc.qt.io/qtforpython-6/tutorials/basictutorial/widgetstyling.html) (공식 튜토리얼)
- [Qt Style Sheets Reference](https://doc.qt.io/qt-6/stylesheet-reference.html) — 지원 속성·서브컨트롤·의사상태 전체 표
- [PythonGUIs — PySide6 tutorial](https://www.pythonguis.com/pyside6-tutorial/) · [Fusion+팔레트 권장 근거](https://www.pythonguis.com/faq/installation-via-pip-styling/)
- [Qt Forum — box-shadow 미지원과 대안](https://forum.qt.io/topic/26107/solved-unknown-property-box-shadow-styling-with-css) · [QGraphicsDropShadowEffect](https://doc.qt.io/qt-6/qgraphicsdropshadoweffect.html)
- [QFormLayout — fieldGrowthPolicy·간격](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QFormLayout.html)
- [qtawesome](https://github.com/spyder-ide/qtawesome) (Material Design Icons 동봉, `qta-browser` 로 탐색) · [qt-material-icons](https://github.com/beatreichenbach/qt-material-icons)
