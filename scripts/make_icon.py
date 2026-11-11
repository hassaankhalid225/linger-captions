"""Generate assets/icon.ico (and docs/logo.png) from the same painter the app uses (ui.theme.paint_logo)."""

from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402

ICO = ROOT / "assets" / "icon.ico"
PNG = ROOT / "docs" / "logo.png"
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def render(size: int) -> Image.Image:
    from linger.ui.theme import paint_logo

    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    paint_logo(p, QRectF(0, 0, size, size))
    p.end()
    buf = QBuffer()
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")


def main() -> None:
    _app = QGuiApplication(sys.argv[:1])
    ICO.parent.mkdir(parents=True, exist_ok=True)
    frames = {s: render(s) for s in SIZES}
    # Pillow writes one frame per size; give it the crispest native rendering for each.
    frames[256].save(ICO, sizes=[(s, s) for s in SIZES], append_images=[frames[s] for s in SIZES[:-1]])
    render(512).save(PNG)
    print(f"wrote {ICO} and {PNG}")


if __name__ == "__main__":
    main()
