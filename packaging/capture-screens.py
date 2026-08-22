"""화면 전수 캡처 — UI/UX 점검의 재료 (09_ui-review 의 스크린샷 생성기).

    conda run -n penv3.13-video python packaging\\capture-screens.py [출력폴더]

실창(onscreen)으로 띄운다 — offscreen 은 Qt 위젯 한글이 두부라 눈검수에 못 쓴다
(08_qt-style §6). 창이 잠깐 떴다 사라지는 것이 정상이다.

화면을 바꾼 뒤 이 스크립트를 다시 돌려 **같은 파일 이름**으로 덮으면, 09 문서의
"현재 → 수정 후" 대조가 그대로 유지된다.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "docs" / "ui-shots"
OUT.mkdir(parents=True, exist_ok=True)

# 픽스처 사본을 데이터로 — 원본을 더럽히지 않는다
ROOT = Path(tempfile.mkdtemp(prefix="vs-shots-")) / "projects"
shutil.copytree(REPO / "fixtures" / "projects", ROOT)
os.environ["VIDEO_STUDIO_PROJECTS"] = str(ROOT)

from app import bootstrap  # noqa: E402,F401
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
from app import i18n, icons, theme  # noqa: E402
from app.main_window import MainWindow  # noqa: E402

i18n.install_korean(app)   # 앱과 같은 조건으로 찍는다
app.setWindowIcon(icons.app_icon())
app.setStyle("Fusion")
app.setPalette(theme.make_palette())
app.setStyleSheet(theme.STYLESHEET)
win = MainWindow()
win.resize(1600, 1000)
win.show()


def pump(sec: float, until=None) -> bool:
    deadline = time.time() + sec
    while time.time() < deadline:
        app.processEvents()
        if until and until():
            return True
        time.sleep(0.02)
    return bool(until()) if until else True


def shot(name: str, widget=None) -> None:
    # 조건 충족 직후엔 위젯이 아직 배치·페인트 전이다 — 한 박자 돌리고 찍는다
    # (2026-08-22: 이걸 빼먹어 대시보드가 "빈 화면"으로 찍혔다. 화면 결함이 아니라 캡처 결함)
    pump(0.8)
    (widget or win).grab().save(str(OUT / f"{name}.png"))
    print(f"  ✓ {name}")


print(f"캡처 → {OUT}")

# ── 1. 대시보드 ──────────────────────────────────────────────────────────────
pump(15, lambda: win.dashboard.grid.count() > 0)
shot("01-dashboard")

# ── 2. 새 강좌 위저드 (모달) ─────────────────────────────────────────────────
from app.dialogs import NewCourseDialog  # noqa: E402

dlg = NewCourseDialog(win.make_studio, win)
dlg.show()
pump(2)
dlg.adv_btn.setChecked(True)   # 접기까지 펼쳐 찍는다 — 숨은 결함도 봐야 한다
pump(1)
shot("02-new-course-wizard", dlg)
dlg.close()

# ── 3~5. 프로젝트 화면 탭 ────────────────────────────────────────────────────
win.show_course("hr-basics")
pump(15, lambda: win.course_page.title.text() != "")


def tab(widget, label: str) -> None:
    """탭을 **이름으로** 고른다 — 번호로 고르면 탭 순서가 바뀔 때 조용히 딴 화면을 찍는다.

    2026-08-22 실측: 프로젝트 탭이 `① 설정·② 영상 목록·③ 브랜드 킷` 에서
    `영상 목록·설정·브랜드 킷` 으로 재배치됐는데 여기는 인덱스 그대로였다. 그래서
    `03-course-board.png` 에 설정이, `04-course-settings.png` 에 영상 목록이 찍혔다 —
    **파일 이름과 내용이 서로 바뀐 채로** 커밋까지 갔다(빌드도 캡처도 오류를 내지 않는다).
    """
    for i in range(widget.count()):
        if label in widget.tabText(i):
            widget.setCurrentIndex(i)
            return
    raise SystemExit(f"탭을 못 찾았다: {label} — 있는 것: "
                     f"{[widget.tabText(i) for i in range(widget.count())]}")


tab(win.course_page.tabs, "영상 목록")
pump(2)
shot("03-course-board")
tab(win.course_page.tabs, "설정")
pump(12, lambda: win.course_page.settings.title.text() != "")
shot("04-course-settings")
tab(win.course_page.tabs, "브랜드 킷")
pump(6)
shot("05-course-brandkit")

# ── 6~9. 영상 화면 탭 ①②③④ ────────────────────────────────────────────────
win.show_episode("hr-basics-01")
ep, clip = win.episode_page, win.episode_page.clip_tab
pump(20, lambda: clip.clip_list.count() > 0)
pump(90, lambda: bool(clip._gallery))
ids = [c.get("id") for c in clip.clips]
if "hook" in ids:
    clip.clip_list.setCurrentRow(ids.index("hook"))
pump(25)
clip.scrub.setValue(35)
pump(3)
shot("06-episode-script")           # ② 대본 (본체)
if "broll" in ids:                  # B롤 클립 — 다른 편집 상태
    clip.clip_list.setCurrentRow(ids.index("broll"))
    pump(5)
    shot("07-episode-script-broll")
tab(ep.tabs, "구성표")
pump(12)
shot("08-episode-plan")             # ① 구성표
tab(ep.tabs, "검수")
pump(120, lambda: ep.frames_row.count() > 1)
shot("09-episode-review")           # ③ 검수
tab(ep.tabs, "배포")
pump(60, lambda: bool(ep.deploy_tab.title.text()))
shot("10-episode-deploy")           # ⑦ 배포

# ── 11~13. 내비 페이지 ───────────────────────────────────────────────────────
win.nav.setCurrentRow(1)
pump(3)
shot("11-library")
win.nav.setCurrentRow(2)
pump(3)
shot("12-jobs")
win.nav.setCurrentRow(3)
pump(60, lambda: win.settings_page._loaded and win.settings_page.diag_table.rowCount() > 0)
shot("13-settings")

# ── 14. 첫 실행 위저드 ───────────────────────────────────────────────────────
from app.pages.first_run import FirstRunWizard  # noqa: E402

wiz = FirstRunWizard(win.make_studio, win)
wiz.show()
pump(20)
shot("14-first-run", wiz)   # 위젯 인자 필수 — 빼면 뒤의 메인 창이 찍힌다
# 마지막 쪽(준비물 — 소재·목소리)까지 넘겨서 찍는다. 1쪽만 찍으면 뒤쪽은 아무도 안 본다
for _ in range(3):
    wiz.next()
    pump(8)
shot("16-first-run-ready", wiz)
wiz.close()

# ── 15. 빌드 중 상태바 칩 ────────────────────────────────────────────────────
# 진짜 빌드를 돌리면 out/ 산출물을 덮어쓴다. 칩이 어떻게 읽히는지만 보면 되므로
# **잡 이벤트를 그대로 흘려 넣는다** — 화면이 받는 값은 실제 잡과 같은 모양이다.
# (엔진을 돌린 캡처가 아니다. 이 장은 상태바 렌더 확인용이다.)
win.show_episode("hr-basics-01")
pump(20, lambda: win.episode_page.title.text() != "")
win._on_job_event("job-demo", "hr-basics-01", {"kind": "state", "state": "running"})
win._on_job_event("job-demo", "hr-basics-01",
                  {"kind": "step", "line": "render 3/17 · motion/hook-bill.html"})
pump(3)
shot("15-build-running")
win._on_job_event("job-demo", "hr-basics-01", {"kind": "state", "state": "done"})

print(f"완료 — {len(list(OUT.glob('*.png')))}장")
