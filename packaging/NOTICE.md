# 제3자 구성요소 고지 (Third-Party Notices)

Video Studio 설치본에는 아래 오픈소스 구성요소가 **그대로(수정 없이)** 동봉됩니다.
각 구성요소의 저작권은 원저작자에게 있으며, 전문(全文)은 설치 폴더의 `licenses\` 에 있습니다.

| 구성요소 | 용도 | 라이선스 | 전문 |
|---|---|---|---|
| **Qt 6 / PySide6** | 앱 화면 · 프리뷰(QtWebEngine) · 미디어 재생 | **LGPL v3** | `licenses\LGPL-3.0.txt` (+ `GPL-3.0.txt` — LGPL v3 이 참조) |
| **FFmpeg** | 영상·음성 합성, 프레임 추출, 무음 검출 | **LGPL v2.1** (shared 빌드) | `licenses\ffmpeg\` |
| **Node.js** | 렌더 엔진 실행 (`engine/`) | MIT (+ 동봉 제3자 고지) | `licenses\node-LICENSE.txt` |
| **Chromium** (Playwright 동봉) | 모션그래픽 렌더 · 화면 녹화 | BSD 3-Clause 외 | `licenses\chromium-LICENSE.txt` — 동봉 제3자 전체 목록은 브라우저의 `chrome://credits` 참조 |
| **Playwright** | 브라우저 제어 | Apache-2.0 | `licenses\playwright-LICENSE.txt` |
| **Pretendard** | 자막·화면 글꼴 | SIL Open Font License 1.1 | `licenses\Pretendard-LICENSE.txt` |
| **edge-tts** | 기본 음성 합성 | LGPL v3 | `licenses\edge-tts-LICENSE.txt` |
| **pydantic** | 데이터 검증 | MIT | `licenses\pydantic-LICENSE.txt` |

## LGPL 준수 안내 (Qt/PySide6 · FFmpeg · edge-tts)

- 이 프로그램은 위 LGPL 구성요소를 **동적 링크**로 사용하며, 해당 라이브러리를 **수정하지
  않았습니다**. 각 라이브러리는 설치 폴더에 **별도 파일**(DLL·EXE)로 들어 있습니다.
- **교체(relink) 권리**: 사용자는 해당 라이브러리를 같은 이름·같은 인터페이스의 다른
  버전으로 교체해 이 프로그램을 실행할 수 있습니다. Qt 는 `_internal\PySide6\` 및
  `_internal\` 의 `Qt6*.dll`, FFmpeg 는 `runtime\ffmpeg\` 의 실행 파일·DLL 을 바꾸면 됩니다.
- **소스 코드 제공**: 위 구성요소의 소스는 각 프로젝트 공식 배포처에서 받을 수 있습니다
  (Qt: <https://download.qt.io/>, FFmpeg: <https://ffmpeg.org/download.html>,
  edge-tts: <https://github.com/rany2/edge-tts>). 배포처 접근이 어려운 경우 배포 담당자에게
  요청하면 동일 버전의 소스를 제공합니다.

## 동봉하지 않는 것

- **스톡 소재(BGM·B롤·사진)** 는 설치본에 넣지 않습니다 — 원 제공처(Mixkit·Pexels 등)의
  약관이 **소재 파일 재배포를 금지**하기 때문입니다. 첫 실행 위저드 또는 라이브러리 화면에서
  사용자가 원 출처에서 직접 받고, 출처·라이선스는 `engine\assets\CATALOG.md` 에 기록됩니다.
- **음성 합성 서비스**: 기본 TTS(edge)는 Microsoft Edge 읽어주기 엔드포인트를 사용합니다 —
  무료·키 불요이나 **상용 서비스용 정식 계약이 아닙니다.** 대외 납품·상용 배포에는
  Azure Speech 등 정식 계약 제공자로 전환해야 합니다 (설정 화면에서 키만 넣으면 전환됩니다).
