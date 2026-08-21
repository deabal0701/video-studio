# 소재 목록 (BGM · 인물 클립)

**파일 자체는 저장소에 넣지 않는다.** 무료 스톡은 "프로젝트에 사용"은 허용해도 소재 파일의
재배포는 대부분 금지한다. 커밋되는 것은 이 목록과 `fetch.js`뿐이고, 파일은 각자 받는다.

```bash
node assets/fetch.js bgm  <url> [파일명]
node assets/fetch.js clip <url> [파일명]
node assets/fetch.js list
```

허용 호스트가 아니면 받지 않는다. 유튜브 등에서 내려받은 소재는 이용약관 위반이자
저작권·초상권 문제가 되므로 쓰지 않는다.

## 어디서 받나

| 출처 | 상업적 사용 | 출처 표시 | 비고 |
|---|---|---|---|
| [Mixkit](https://mixkit.co/) | 허용 | 불필요 | 영상·음악·효과음. **CD·DVD·게임·TV/라디오 방송에는 사용 불가** |
| [Pexels](https://www.pexels.com/ko-kr/videos/) | 허용 | 불필요 | 영상·사진. 인물 소재가 많다 |
| [Pixabay](https://pixabay.com/ko/videos/) | 허용 | 불필요 | 영상·음악·사진 |
| [YouTube 오디오 보관함](https://studio.youtube.com/) | 유튜브 내 사용 | 곡마다 다름 | 유튜브에 올릴 때 가장 안전 |

각 소재의 라이선스는 **받는 시점에 해당 페이지에서 직접 확인한다.** 위 표는 요약이고 약관은 바뀐다.

## 받아 둔 BGM

받을 때마다 아래 표에 한 줄 추가한다. 출처 URL을 반드시 남긴다.

| 파일 | 길이 | 출처 | 라이선스 | 용도 메모 |
|---|---|---|---|---|
| `bgm/mixkit-623.mp3` | 4:49 | https://assets.mixkit.co/music/623/623.mp3 ([corporate 태그](https://mixkit.co/free-stock-music/tag/corporate/)) | Mixkit Free License | ai-lecture 채택 — 8분 강의에 루프 이음새 1번, 중간 에너지(-11.6dB) |
| `bgm/mixkit-132.mp3` | 2:07 | https://assets.mixkit.co/music/132/132.mp3 (동일) | Mixkit Free License | 후보 |
| `bgm/mixkit-471.mp3` | 1:39 | https://assets.mixkit.co/music/471/471.mp3 (동일) | Mixkit Free License | 후보 |
| `bgm/mixkit-623-loop.mp3` | 4:24 | 위 `mixkit-623.mp3` 에서 파생(재인코딩) | Mixkit Free License | **루프용 파생본.** 원곡은 270초부터 페이드아웃해 288.7초에 완전 무음이 된다 — 5분 영상에 깔면 뒷부분에서 음악이 죽고 루프가 돌며 갑자기 되살아난다(hr-basics-01 실측). 페이드 직전 264초까지 잘라내고 양끝에 0.35초 페이드를 넣어 루프 이음새를 부드럽게 했다.<br>`ffmpeg -t 264 -i mixkit-623.mp3 -af "afade=t=in:st=0:d=0.35,afade=t=out:st=263.65:d=0.35" -c:a libmp3lame -q:a 2 mixkit-623-loop.mp3` |
| `bgm/mixkit-234.mp3` | 1:58 | https://assets.mixkit.co/music/234/234.mp3 ([cinematic 태그](https://mixkit.co/free-stock-music/tag/cinematic/)) | Mixkit Free License | insait-promo-60s 채택 — **빌드형**: 0~10초 -39dB로 조용하다가 10초부터 -23dB로 올라오고 40~45초에서 최대(-17dB). 홍보 훅을 조용히 열고 로고 등장에서 터뜨리는 구성에 맞다 |
| `bgm/mixkit-234-60s.mp3` | 1:02 | 위 `mixkit-234.mp3` 파생(앞 62초 컷 + 끝 2초 페이드아웃) | Mixkit Free License | **60초 홍보용 파생본.** `ffmpeg -t 62 -i mixkit-234.mp3 -af "afade=t=out:st=60:d=2" -c:a libmp3lame -q:a 2 mixkit-234-60s.mp3` |

> **곡을 고를 때 끝부분을 반드시 재라.** 무료 스톡 음악은 대부분 끝에서 페이드아웃하는데,
> 영상이 곡보다 길면 그 구간이 그대로 무음이 된다(프레임 검증으로는 절대 안 보인다).
> `ffmpeg -ss <끝-10> -t 3 -i <곡> -af volumedetect -f null -` 로 확인하고, 페이드가 길면
> 위처럼 잘라 파생본을 만든다.

곡은 **직접 들어 보고 고른다.** 30초 광고에는 1~2분짜리로 충분하고(루프가 걸린다), 매뉴얼에는
아예 넣지 않거나 아주 낮게 까는 편이 낫다.

## 받아 둔 인물 클립

| 파일 | 길이 | 출처 | 라이선스 | 프레이밍 메모 |
|---|---|---|---|---|
| (없음) | | | | |

## 받아 둔 사진 (photo.html 배경)

**얼굴이 식별되는 인물 사진을 특정 서사의 당사자("스무 살의 나")로 쓰지 않는다.**
뒷모습·손·풍경·사물·실루엣이면 이 문제가 없고 생애사 톤에도 더 맞는다.

| 파일 | 출처 | 라이선스 | 내용 메모 |
|---|---|---|---|
| `photo/alley-child.jpg` | https://www.pexels.com/photo/1006121/ | Pexels License | 나무 사이 길 — 여정·유년 은유. 얼굴 없음 |
| `photo/lone-fisherman.jpg` | https://www.pexels.com/photo/6710950/ | Pexels License | 망망대해 홀로 뜬 작은 배. 얼굴 없음(원경) |
| `photo/sunset-sail.jpg` | https://www.pexels.com/photo/1481262/ | Pexels License | 석양 바다 위 배·사공 실루엣 |
| `photo/sunset-fishermen.jpg` | https://www.pexels.com/photo/12362554/ | Pexels License | 석양에 낚싯대 든 어부 실루엣 |
| `photo/sunset-boat.jpg` | https://www.pexels.com/photo/1118874/ | Pexels License | 폭풍·번개 하늘 아래 돛단배 |
| `photo/shark-1.jpg` | https://www.pexels.com/photo/4666748/ | Pexels License | 파도 아래 상어 |
| `photo/shark-2.jpg` | https://www.pexels.com/photo/5967796/ | Pexels License | 깊은 물속 고래상어 |
| `photo/big-fish.jpg` | https://www.pexels.com/photo/4810629/ | Pexels License | 푸른 물속 톱상어 실루엣 — "거대한 물고기" 연출용 |
| `photo/lion-rest.jpg` | https://www.pexels.com/photo/4179460/ | Pexels License | 볕 아래 쉬는 사자 |
| `photo/old-rope.jpg` | https://www.pexels.com/photo/27644254/ | Pexels License | 낡은 로프 클로즈업 |
| `photo/boat-person.jpg` | https://www.pexels.com/photo/2080960/ | Pexels License | 새벽 분홍 바다의 작은 배 실루엣 |
| `photo/hangang-dusk.jpg` | https://www.pexels.com/photo/15375820/ | Pexels License | 해질녘 한강·서울 스카이라인 (O-seop Sim). 한강 쇼츠 인트로용 |
| `photo/hangang-aerial.jpg` | https://www.pexels.com/photo/34554596/ | Pexels License | 한강·다리 항공샷 (Chhabiraj Adhikari). 강폭·둔치 위치 설명용 |
| `photo/hangang-cloudy.jpg` | https://www.pexels.com/photo/19222549/ | Pexels License | 흐린 하늘 아래 한강과 다리 (Muneeb Babar). 장마·먹구름 톤 |
| `photo/hangang-mapo.jpg` | https://www.pexels.com/photo/25244824/ | Pexels License | 석양의 마포대교와 열차 (Mocchi NO). 마무리 컷 |

## 받아 둔 B롤 영상 (클립 `video`)

| 파일 | 길이 | 출처 | 라이선스 | 내용 메모 |
|---|---|---|---|---|
| `broll/road-drone.mp4` | 33초 · 1280×720 | https://www.pexels.com/video/3571264/ | Pexels License | 해변 파도 드론 샷 — 반복·회복 은유. 얼굴 없음 |
| `broll/shark-swim.mp4` | 4.9초 · 1920×1080 | https://www.pexels.com/video/7997336/ | Pexels License | 물속 상어 유영 |
| `broll/cables-blue.mp4` | 23.5초 · 2560×1440 · 25fps | https://www.pexels.com/video/blue-colored-cables-1085656/ (직접링크 https://videos.pexels.com/video-files/1085656/1085656-uhd_2560_1440_25fps.mp4) | Pexels License | 파란 조명 아래 네트워크 케이블 + 초록 LED (Dima Krivoy). api-gateway 인트로 채택 — 어두운 남색 덱과 톤이 맞고 "요청이 지나는 길"이라는 주제와 직결. 얼굴 없음 |
| `broll/ai-datacenter.mp4` | 14.3초 · 1280×720 | https://mixkit.co/free-stock-video/bluish-data-center-hallway-23282/ | Mixkit Free License | 파란 서버룸 복도 — AI 학습 인프라 은유. 얼굴 없음 |
| `broll/ai-typing.mp4` | 14.2초 · 1920×1080 | https://mixkit.co/free-stock-video/close-up-shot-of-a-person-typing-on-a-laptop-1808/ | Mixkit Free License | 노트북 타이핑 손 클로즈업. 얼굴 없음 |
| `broll/ai-code.mp4` | 29초 · 1280×720 | https://mixkit.co/free-stock-video/computational-digital-codes-14596/ | Mixkit Free License | 초록 헥스 코드 화면 — 학습·코딩 은유 |
| `broll/ai-city.mp4` | 24.2초 · 1920×1080 | https://mixkit.co/free-stock-video/aerial-landscape-of-a-city-at-night-41542/ | Mixkit Free License | 야경 도시 드론 (다리·고층빌딩) |
| `broll/ai-city2.mp4` | 12초 · 1920×1080 | https://mixkit.co/free-stock-video/great-strip-of-a-big-city-at-night-41159/ | Mixkit Free License | 야간 도심 대로 |
| `broll/ai-create.mp4` | 15초 · 1280×720 | https://mixkit.co/free-stock-video/golden-particles-rising-in-a-digital-world-14154/ | Mixkit Free License | 골드 파티클 추상 — 생성 AI 은유 |
| `broll/ai-film.mp4` | 43.3초 · 1280×720 | https://mixkit.co/free-stock-video/color-correction-close-up-of-the-process-47208/ | Mixkit Free License | 색보정 작업 화면 클로즈업 — 영상 제작 은유. 얼굴 없음 |
| `broll/office-talk.mp4` | 18.9초 · 1920×1080 · 25fps | https://www.pexels.com/video/8033300/ (직접링크 https://videos.pexels.com/video-files/8033300/8033300-hd_1920_1080_25fps.mp4) | Pexels License | 사무실 회의 테이블 **부감(탑다운)** — 네 사람이 둘러앉아 노트북 작업. hr-basics 1강 인트로 채택(`videoStart 5`): 얼굴이 정면으로 크게 잡히지 않고 **가운데가 테이블이라 제목이 설 자리가 있다** |
| `broll/office-meeting.mp4` | 15.0초 · 1920×1080 · 25fps | https://www.pexels.com/video/3246669/ (직접링크 https://videos.pexels.com/video-files/3246669/3246669-hd_1920_1080_25fps.mp4) | Pexels License | 회의 중 인물 상반신 클로즈업 + 포스트잇 보드. **탈락 후보** — 화면 정중앙이 얼굴이라 타이틀 카드가 얼굴 위에 얹힌다 |
| `broll/dough-knead.mp4` | 0:12 · 3840×2160 | https://www.pexels.com/video/person-kneading-a-dough-4122559/ | Pexels License | 반죽 치대는 손 클로즈업 (Anastasia Shuraeva). bread-basics 1강 인트로 채택. 얼굴 없음 |

인물 클립은 `zoom`·`focusX`·`focusY` 값을 함께 적어 두면 다음에 그대로 쓸 수 있다.
얼굴은 보통 화면 위쪽에 있어서 기본값(가운데)으로 자르면 원 안이 책상·가슴으로 찬다.

## 쓰는 법

`scenes.json`에서 경로로 가리킨다. `render.bgm`은 **영상 작업 폴더 기준 상대 경로**다.

```json
"render": {
  "bgm": "../../.claude/skills/develop-video/assets/bgm/mixkit-132.mp3",
  "bgmGain": 0.18,
  "bgmDucking": true
}
```

`bgmDucking`은 내레이션이 나올 때 배경음을 자동으로 눌러 준다(사이드체인). 일정 볼륨으로 깔면
말과 배경음이 같은 대역에서 싸워 대사가 묻힌다. 기본값은 켬이다.

프로젝트 안에 두고 쓰려면 `tools/video/assets/`로 복사하고 그쪽 경로를 적는다.
그 경우에도 **`.gitignore`에 넣는 것을 잊지 말 것.**
