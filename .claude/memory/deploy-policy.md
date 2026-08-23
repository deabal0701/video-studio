# 배포 정책 — 외부 게시는 지시가 있을 때만

**규칙:** 허깅페이스(및 그 밖의 외부 호스팅)에 올리는 작업은 **사용자가 명시적으로
"올려라"라고 할 때만** 실행한다. 빌드·검증까지는 알아서 해도 되지만, 게시는 안 된다.

**왜:** 게시는 되돌리기 어렵고 바깥으로 나가는 행위다. 캐시·색인이 남을 수 있다.
자동 배포를 파이프라인에 심으면 의도치 않은 공개가 생긴다 (2026-08-23 지시).

**적용:**
- 배포 자동화(훅·워치·CI 자동 push)를 **붙이지 않는다**.
- "영상 만들어줘" 요청은 mp4 산출까지가 완료다. 게시는 별도 지시.
- 배포 스크립트는 사람이 손으로 실행하는 형태로만 둔다.

**현재 배포 경로 (2026-08-23 실측):**
- 대상: Static Space `Daesik/video-studio-demo`
- 공개 주소는 `https://<user>-<space>.static.hf.space` — `*.hf.space` 는 404
- 토큰: `HF_TOKEN` (`~/.claude/develop-video.env`), `huggingface_hub` 사용
- 실측: Static Space 는 `Accept-Ranges: bytes` 를 주므로 영상 탐색 정상, LFS 파일도 그대로 서빙된다
- 한계: 무료 계정 공개 저장용량은 "best-effort"(보장 없음), 비공개 게시 불가(Private=404,
  Protected 는 PRO 전용). 용량이 커지면 Cloudflare R2(egress $0)로 옮긴다.
