# Python 실행 환경 — conda penv3.13-insait

**모든 Python 실행(스크립트·pytest·uvicorn·pip)은 conda `penv3.13-insait` 환경을 쓴다.**

```
conda run -n penv3.13-insait python ...
conda run -n penv3.13-insait python -m pytest -q
```

## 주의 (실측 — 2026-08-21)

- 맨 `python` 을 치면 **base(miniconda) 파이썬이 잡힌다** — 프로젝트 의존성이 없어
  pydantic/fastapi ImportError 가 난다. 반드시 `conda run -n penv3.13-insait` 경유.
- 이 환경은 Python 3.13.13. **프로젝트 의존성이 아직 설치돼 있지 않다**(fastapi·pydantic·
  sse-starlette·watchfiles 없음 — pytest 수집이 15건 에러로 실패했음). 처음 쓰기 전에:

  ```
  conda run -n penv3.13-insait pip install -e ".[dev]"
  ```

- `--timeout=N` 인자는 pytest-timeout 플러그인 설정과 충돌했음 — `-q` 만으로 실행
  (타임아웃은 pyproject.toml 의 `timeout = 60` 이 이미 건다).
- CLAUDE.md·docs/BUILD_LOOP.md 에도 같은 환경이 명시돼 있다 (이 파일이 실행 세부의 정본).
