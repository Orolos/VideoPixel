"""Generează assets/videopixel.ico (+ .png) din „V”-ul pixel definit în vlclibrary/theme.py."""
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication

from vlclibrary.theme import v_image

app = QGuiApplication([])
base = v_image()
SIZES = [16, 32, 48, 64, 128, 256]       # multipli întregi ai lui 16 -> rămâne pixel art curat


def png_bytes(img):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


images = [(s, png_bytes(base.scaled(s, s, Qt.IgnoreAspectRatio, Qt.FastTransformation))) for s in SIZES]
header = struct.pack("<HHH", 0, 1, len(images))
offset = 6 + 16 * len(images)
entries, blobs = b"", b""
for s, data in images:
    entries += struct.pack("<BBBBHHII", 0 if s >= 256 else s, 0 if s >= 256 else s, 0, 0, 1, 32,
                           len(data), offset + len(blobs))
    blobs += data
out = ROOT / "assets"
out.mkdir(exist_ok=True)
(out / "videopixel.ico").write_bytes(header + entries + blobs)
(out / "videopixel.png").write_bytes(images[-1][1])
print("ok", [s for s, _ in images])
