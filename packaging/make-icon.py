"""`packaging/VideoStudio.ico` 생성 — 설치본 exe·바로가기 아이콘 (5-8).

    <파이썬> packaging\\make-icon.py

앱 아이콘은 `app/icons.py` 가 코드로 그린다. exe 에 박으려면 파일이 있어야 하므로
여기서 같은 그림을 크기별 PNG 로 뽑아 **.ico 컨테이너로 손수 묶는다**.

왜 손수 묶는가: Qt 의 ICO 플러그인은 빌드에 따라 **읽기 전용**이라 `QPixmap.save(".ico")`
가 조용히 실패할 수 있다. ICO 형식은 헤더 6바이트 + 항목 16바이트/개 + 이미지 데이터라
직접 쓰는 편이 확실하고 의존성도 없다. 항목에 **PNG 를 그대로 넣는 것이 규격**이다
(Vista 이후). 실패하면 조용히 넘어가지 않고 예외로 알린다.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QBuffer, QByteArray, QSize      # noqa: E402
from PySide6.QtWidgets import QApplication                 # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)
OUT = REPO / "packaging" / "VideoStudio.ico"


def _png_bytes(icon, size: int) -> bytes:
    # 화면 배율을 1 로 못 박는다 — 안 그러면 175% 화면에서 16px 요청에 28px 가 온다(실측)
    px = icon.pixmap(QSize(size, size), 1.0)
    if px.width() != size:                      # 옛 시그니처 폴백
        px = icon.pixmap(QSize(size, size))
        px.setDevicePixelRatio(1.0)
        if px.width() != size:
            px = px.scaled(size, size)
    if px.isNull() or px.width() != size:
        raise RuntimeError(f"{size}px 픽스맵을 못 얻었다 (얻은 것: {px.size()})")
    buf = QBuffer(QByteArray())
    buf.open(QBuffer.WriteOnly)
    if not px.save(buf, "PNG"):
        raise RuntimeError(f"{size}px PNG 인코딩 실패")
    return bytes(buf.data())


def main() -> int:
    app = QApplication([])          # QPixmap 은 QGuiApplication 이 있어야 한다
    from app import icons

    blobs = [(s, _png_bytes(icons.app_icon(), s)) for s in SIZES]

    header = struct.pack("<HHH", 0, 1, len(blobs))          # reserved, type=1(icon), count
    offset = len(header) + 16 * len(blobs)
    entries, data = b"", b""
    for size, blob in blobs:
        # ICO 는 256 을 0 으로 적는다 (1바이트 필드라 256 이 안 들어간다)
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32,
                               len(blob), offset)
        data += blob
        offset += len(blob)
    OUT.write_bytes(header + entries + data)
    print(f"{OUT}  {OUT.stat().st_size / 1024:.1f} KB  ({len(blobs)}종: "
          f"{', '.join(str(s) for s in SIZES)})")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
