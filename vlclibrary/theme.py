"""Tema „Crunchyroll în pixel art”: culori, fonturi, iconițe desenate pixel cu pixel, postere."""
from __future__ import annotations

import hashlib
import random
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QIcon, QImage, QImageReader, QPainter, QPalette, QPen, QPixmap,
)
from PySide6.QtWidgets import QLabel, QMessageBox, QSizePolicy

C = dict(
    bg="#0E0F12", panel="#16171B", panel2="#1F2127", panel3="#2A2D35",
    orange="#F47521", orange_lt="#FFA05A", orange_dk="#A8480C",
    text="#F2F2F4", muted="#8E909B", green="#7DE08D", gold="#FFC93C", red="#FF5A5F",
)
PIXEL_FONT = "Press Start 2P"
BODY_FONT = "VT323"


from .paths import resource_dir


def load_fonts() -> bool:
    ok = False
    for ttf in sorted((resource_dir() / "assets" / "fonts").glob("*.ttf")):
        ok = QFontDatabase.addApplicationFont(str(ttf)) >= 0 or ok
    return ok


# ---------------------------------------------------------------- iconițe pixel
ICONS: dict[str, list[str]] = {
    "play": ["##......", "####....", "######..", "########",
             "########", "######..", "####....", "##......"],
    "pause": ["###..###"] * 8,
    "check": ["........", ".......#", "......##", "#....##.",
              "##..##..", ".####...", "..##....", "........"],
    "plus": ["...##...", "...##...", "...##...", "########",
             "########", "...##...", "...##...", "...##..."],
    "folder": ["###.....", "########", "#......#", "#......#",
               "#......#", "#......#", "#......#", "########"],
    "film": ["########", "#......#", "#.#....#", "#.##...#",
             "#.###..#", "#.##...#", "#.#....#", "########"],
    "trash": ["..####..", "########", ".#.##.#.", ".#.##.#.",
              ".#.##.#.", ".#.##.#.", ".######.", "........"],
    "refresh": ["..####..", ".#....#.", "#.....##", "#....###",
                "#.......", "#.......", ".#....#.", "..####.."],
    "home": ["...##...", "..####..", ".######.", "########",
             ".#....#.", ".#.##.#.", ".#.##.#.", ".######."],
    "tv": [".#....#.", "..#..#..", "########", "#......#",
           "#.####.#", "#.####.#", "#......#", "########"],
    "star": ["...##...", "...##...", "########", ".######.",
             "..####..", "..####..", ".##..##.", ".#....#."],
    "prev": ["#......#", "#.....##", "#....###", "#...####",
             "#...####", "#....###", "#.....##", "#......#"],
    "next": ["#......#", "##.....#", "###....#", "####...#",
             "####...#", "###....#", "##.....#", "#......#"],
    "full": ["###..###", "#......#", "#......#", "........",
             "........", "#......#", "#......#", "###..###"],
    "search": [".####...", "#....#..", "#....#..", "#....#..",
               ".####...", "....##..", ".....##.", "......##"],
    "image": ["########", "#......#", "#.##...#", "#.##...#",
              "#...#..#", "#..###.#", "#.#####.", "########"],
}


def pixel_pixmap(name: str, color: str = C["text"], scale: int = 2) -> QPixmap:
    rows = ICONS[name]
    h, w = len(rows), len(rows[0])
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(0)
    col = QColor(color)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                img.setPixelColor(x, y, col)
    return QPixmap.fromImage(img.scaled(w * scale, h * scale, Qt.IgnoreAspectRatio,
                                        Qt.FastTransformation))


def pixel_icon(name: str, color: str = C["text"], scale: int = 2) -> QIcon:
    icon = QIcon()
    icon.addPixmap(pixel_pixmap(name, color, scale), QIcon.Normal)
    icon.addPixmap(pixel_pixmap(name, C["panel3"], scale), QIcon.Disabled)
    return icon


# „V” pixel (16x16): litera din VideoPixel, portocalie, cu lumină pe stânga și umbră pe dreapta
V_ROWS = [
    "................",
    "................",
    "..###......###..",
    "..###......###..",
    "...###....###...",
    "...###....###...",
    "....###..###....",
    "....###..###....",
    ".....######.....",
    ".....######.....",
    "......####......",
    "......####......",
    ".......##.......",
    ".......##.......",
    "................",
    "................",
]


def v_image() -> QImage:
    """Iconița aplicației la 16x16 (se scalează doar cu multipli întregi, ca să rămână pixel art)."""
    img = QImage(16, 16, QImage.Format_ARGB32)
    img.fill(0)
    black, ring, fill = QColor("#000000"), QColor("#4A2409"), QColor("#101114")
    for y in range(16):
        for x in range(16):
            corner = (x in (0, 15)) and (y in (0, 15, 1, 14)) or (y in (0, 15)) and (x in (1, 14))
            if corner:
                continue
            if x in (0, 15) or y in (0, 15):
                img.setPixelColor(x, y, black)
            elif x in (1, 14) or y in (1, 14):
                img.setPixelColor(x, y, ring)
            else:
                img.setPixelColor(x, y, fill)
    on = {(x, y) for y, row in enumerate(V_ROWS) for x, ch in enumerate(row) if ch == "#"}
    for (x, y) in on:
        if (x - 1, y) not in on:
            col = C["orange_lt"]
        elif (x + 1, y) not in on:
            col = C["orange_dk"]
        else:
            col = C["orange"]
        img.setPixelColor(x, y, QColor(col))
    return img


def app_icon() -> QIcon:
    base = v_image()
    icon = QIcon()
    for s in (16, 32, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(base.scaled(s, s, Qt.IgnoreAspectRatio, Qt.FastTransformation)))
    return icon


# ---------------------------------------------------------------- postere
_ACCENTS = [C["orange"], "#3EC9C0", "#FF6FA5", C["gold"], "#8E7CFF", "#7DE08D"]


def _frame(pm: QPixmap) -> QPixmap:
    p = QPainter(pm)
    p.setPen(QPen(QColor("#000000"), 4))
    p.drawRect(2, 2, pm.width() - 4, pm.height() - 4)
    p.setPen(QPen(QColor(C["panel3"]), 2))
    p.drawRect(5, 5, pm.width() - 10, pm.height() - 10)
    p.end()
    return pm


def placeholder_poster(name: str, w: int, h: int) -> QPixmap:
    seed = int(hashlib.md5(name.encode("utf-8")).hexdigest()[:8], 16)
    rnd = random.Random(seed)
    accent = QColor(_ACCENTS[seed % len(_ACCENTS)])
    pm = QPixmap(w, h)
    pm.fill(QColor(C["panel2"]))
    p = QPainter(pm)
    cell = max(4, w // 20)
    soft = QColor(accent)
    soft.setAlpha(60)
    for _ in range(26):
        x, y = rnd.randrange(0, w // cell) * cell, rnd.randrange(0, h // cell) * cell
        p.fillRect(x, y, cell, cell, soft)
    icon = pixel_pixmap("play", accent.name(), max(4, w // 14))
    p.drawPixmap((w - icon.width()) // 2, int(h * 0.22), icon)
    words = [t for t in name.replace("-", " ").split() if t]
    initials = "".join(t[0] for t in words[:2]).upper() or "?"
    f = QFont(PIXEL_FONT)
    f.setPixelSize(16 if w < 220 else 24)
    p.setFont(f)
    p.setPen(QColor(C["text"]))
    p.drawText(QRect(0, int(h * 0.62), w, int(h * 0.2)), Qt.AlignCenter, initials)
    p.end()
    return _frame(pm)


ALLOWED_IMAGE_FORMATS = {"jpeg", "jpg", "png", "webp"}
MAX_IMAGE_SIDE = 8000
MAX_IMAGE_PIXELS = 40_000_000


def read_image(path: str | Path, cover: tuple[int, int] | None = None) -> QImage:
    """Citește o imagine nesigură: doar JPEG/PNG/WebP, cu limite de dimensiune (altfel imagine nulă).
    `cover=(w, h)`: decodare direct la dimensiunea necesară (mult mai rapid pentru postere mari)."""
    r = QImageReader(str(path))
    fmt = bytes(r.format()).decode("ascii", "ignore").lower()
    if fmt not in ALLOWED_IMAGE_FORMATS:
        return QImage()
    sz = r.size()
    if (not sz.isValid() or sz.width() > MAX_IMAGE_SIDE or sz.height() > MAX_IMAGE_SIDE
            or sz.width() * sz.height() > MAX_IMAGE_PIXELS):
        return QImage()
    if cover and sz.width() > cover[0] and sz.height() > cover[1]:
        k = max(cover[0] / sz.width(), cover[1] / sz.height())
        r.setScaledSize(QSize(max(cover[0], round(sz.width() * k)), max(cover[1], round(sz.height() * k))))
    img = r.read()          # imagine nulă dacă decodarea eșuează (nu folosim r.error(): UnknownError == 0)
    return img if not img.isNull() else QImage()


class ElidedLabel(QLabel):
    """Etichetă care nu mai forțează lățimea ferestrei: textul lung se taie cu „…” (tooltip = textul întreg)."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full = ""
        self.setTextFormat(Qt.PlainText)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)
        self.setText(text)

    def setText(self, text: str) -> None:
        self._full = text
        self._apply()

    def text(self) -> str:
        return self._full

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply()

    def _apply(self) -> None:
        w = self.width()
        shown = self.fontMetrics().elidedText(self._full, Qt.ElideMiddle, w) if w > 24 else self._full
        if shown != QLabel.text(self):
            QLabel.setText(self, shown)
        self.setToolTip(tip(self._full) if shown != self._full else "")


def message(parent, kind: str, title: str, text: str):
    """QMessageBox care NU interpretează textul ca HTML (căi/erori pot conține markup)."""
    box = QMessageBox(parent)
    box.setIcon({"info": QMessageBox.Information, "warning": QMessageBox.Warning,
                 "error": QMessageBox.Critical}.get(kind, QMessageBox.Information))
    box.setWindowTitle(title)
    box.setTextFormat(Qt.PlainText)
    box.setText(text)
    box.exec()


def tip(text: str) -> str:
    """Tooltip sigur: textul simplu e escapat, ca un nume de folder cu <...> să nu devină HTML."""
    import html
    return "<qt>" + html.escape(text).replace("\n", "<br>") + "</qt>"


def pixel_poster(path: str | Path, w: int, h: int, block: int = 4, posterize: bool = True) -> QPixmap | None:
    """Poster „pixelat”: crop la raport, reducere la o grilă mică, culori limitate."""
    src = read_image(path, (w, h))
    if src.isNull():
        return None
    img = src.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    img = img.copy((img.width() - w) // 2, (img.height() - h) // 2, w, h)
    if block > 1:
        small = img.scaled(max(1, w // block), max(1, h // block), Qt.IgnoreAspectRatio,
                           Qt.SmoothTransformation).convertToFormat(QImage.Format_ARGB32)
        if posterize:
            # vectorizat: aceeași tabelă pe toți octeții (R, G, B, alfa=255 rămâne 255)
            step = 36
            table = bytes(min(255, v // step * step + step // 2) for v in range(256))
            bpl = small.bytesPerLine()
            data = bytes(small.constBits())[: bpl * small.height()].translate(table)
            small = QImage(data, small.width(), small.height(), bpl, QImage.Format_ARGB32).copy()
        img = small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    return _frame(QPixmap.fromImage(img))


def plain_poster(path: str | Path, w: int, h: int) -> QPixmap | None:
    src = read_image(path, (w, h))
    if src.isNull():
        return None
    img = src.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    img = img.copy((img.width() - w) // 2, (img.height() - h) // 2, w, h)
    return _frame(QPixmap.fromImage(img))


# ---------------------------------------------------------------- stil
def stylesheet() -> str:
    c = C
    bevel_o = f"border:3px solid; border-color:{c['orange_lt']} {c['orange_dk']} {c['orange_dk']} {c['orange_lt']};"
    bevel_o_down = f"border:3px solid; border-color:{c['orange_dk']} {c['orange_lt']} {c['orange_lt']} {c['orange_dk']};"
    bevel_g = f"border:3px solid; border-color:{c['panel3']} #000 #000 {c['panel3']};"
    bevel_g_down = f"border:3px solid; border-color:#000 {c['panel3']} {c['panel3']} #000;"
    return f"""
* {{ outline: 0; }}
QWidget {{ background-color:{c['bg']}; color:{c['text']}; }}
QMainWindow, QDialog {{ background-color:{c['bg']}; }}
QLabel {{ background:transparent; }}
QLabel#h1 {{ font-family:'{PIXEL_FONT}'; font-size:16px; color:{c['orange']}; }}
QLabel#logo {{ font-family:'{PIXEL_FONT}'; font-size:8px; color:{c['orange']}; padding:2px; }}
QLabel#muted {{ color:{c['muted']}; }}
QLabel#meta {{ color:{c['gold']}; }}
QLabel#section {{ font-family:'{PIXEL_FONT}'; font-size:8px; color:{c['orange']}; padding:6px 0 2px 0; }}
QToolTip {{ background:#000; color:{c['text']}; border:2px solid {c['orange']}; padding:3px; }}

QToolBar {{ background:{c['panel']}; border:0; border-bottom:4px solid #000; spacing:6px; padding:4px; }}
QToolButton {{ font-family:'{PIXEL_FONT}'; font-size:8px; background:{c['panel3']}; color:{c['text']};
    {bevel_g} padding:6px 8px; }}
QToolButton:hover {{ background:{c['orange']}; color:#000; {bevel_o} }}
QToolButton:pressed, QToolButton:checked {{ background:{c['orange_dk']}; color:{c['text']}; {bevel_o_down} }}

QPushButton {{ font-family:'{PIXEL_FONT}'; font-size:8px; background:{c['panel3']}; color:{c['text']};
    {bevel_g} padding:8px 10px; }}
QPushButton:hover {{ background:{c['orange']}; color:#000; {bevel_o} }}
QPushButton:pressed {{ background:{c['orange_dk']}; color:{c['text']}; {bevel_o_down} }}
QPushButton:disabled {{ background:{c['panel2']}; color:{c['muted']}; {bevel_g_down} }}
QPushButton[primary="true"] {{ background:{c['orange']}; color:#000; {bevel_o} }}
QPushButton[primary="true"]:hover {{ background:{c['orange_lt']}; }}
QPushButton[primary="true"]:pressed {{ background:{c['orange_dk']}; color:{c['text']}; {bevel_o_down} }}
QPushButton[primary="true"]:disabled {{ background:{c['panel2']}; color:{c['muted']}; {bevel_g_down} }}

QTreeWidget, QListWidget, QTableWidget, QTextBrowser, QTextEdit, QLineEdit, QComboBox, QSpinBox {{
    background:{c['panel']}; border:3px solid #000; selection-background-color:{c['orange']};
    selection-color:#000; alternate-background-color:{c['panel2']}; }}
QTreeWidget::item {{ padding:5px 4px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background:{c['orange']}; color:#000; }}
QTreeWidget::item:hover:!selected, QListWidget::item:hover:!selected {{ background:{c['panel3']}; }}
QListWidget::item {{ padding:4px; }}
QTableWidget::item {{ padding:2px 6px; }}
QTableWidget::item:selected {{ background:{c['orange']}; color:#000; }}
QHeaderView::section {{ font-family:'{PIXEL_FONT}'; font-size:8px; background:{c['panel3']}; color:{c['orange']};
    border:0; border-bottom:3px solid #000; border-right:2px solid #000; padding:7px 6px; }}
QTableCornerButton::section {{ background:{c['panel3']}; border:0; }}

QProgressBar {{ background:#000; border:3px solid #000; text-align:center; color:{c['text']};
    font-family:'{PIXEL_FONT}'; font-size:8px; min-height:20px; }}
QProgressBar::chunk {{ background:{c['orange']}; width:12px; margin:1px; }}

QSlider::groove:horizontal {{ height:8px; background:#000; border:2px solid #000; }}
QSlider::sub-page:horizontal {{ background:{c['orange']}; }}
QSlider::handle:horizontal {{ width:12px; margin:-8px 0; background:{c['text']};
    border:3px solid; border-color:#fff {c['orange_dk']} {c['orange_dk']} #fff; }}
QSlider::handle:horizontal:hover {{ background:{c['orange_lt']}; }}

QScrollBar:vertical {{ background:{c['panel']}; width:16px; border:0; border-left:2px solid #000; }}
QScrollBar::handle:vertical {{ background:{c['panel3']}; min-height:30px; border:3px solid; border-color:{c['muted']} #000 #000 {c['muted']}; }}
QScrollBar::handle:vertical:hover {{ background:{c['orange']}; border-color:{c['orange_lt']} {c['orange_dk']} {c['orange_dk']} {c['orange_lt']}; }}
QScrollBar:horizontal {{ background:{c['panel']}; height:16px; border:0; border-top:2px solid #000; }}
QScrollBar::handle:horizontal {{ background:{c['panel3']}; min-width:30px; border:3px solid; border-color:{c['muted']} #000 #000 {c['muted']}; }}
QScrollBar::handle:horizontal:hover {{ background:{c['orange']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width:0; height:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}

QSplitter::handle {{ background:#000; width:4px; }}
QMenu {{ background:{c['panel']}; border:3px solid {c['orange']}; padding:2px; }}
QMenu::item {{ padding:5px 22px; }}
QMenu::item:selected {{ background:{c['orange']}; color:#000; }}
QMenu::item:disabled {{ color:{c['muted']}; }}
QMenu::separator {{ height:3px; background:#000; margin:3px 4px; }}

QCheckBox {{ spacing:8px; background:transparent; }}
QCheckBox::indicator {{ width:14px; height:14px; background:#000; border:3px solid; border-color:#000 {c['panel3']} {c['panel3']} #000; }}
QCheckBox::indicator:checked {{ background:{c['orange']}; }}
QComboBox::drop-down {{ border:0; width:22px; }}
QComboBox QAbstractItemView {{ background:{c['panel']}; border:3px solid {c['orange']}; selection-background-color:{c['orange']}; selection-color:#000; }}
QSpinBox::up-button, QSpinBox::down-button {{ width:0; }}
QStatusBar {{ background:{c['panel']}; border-top:3px solid #000; font-family:'{PIXEL_FONT}'; font-size:8px; color:{c['muted']}; }}
QMessageBox {{ background:{c['bg']}; }}

#ctlbar {{ background:#0e0f12; border-top:4px solid {c['orange']}; }}
#ctlbar QLabel {{ background:transparent; }}
#ctlbar QWidget {{ background:transparent; }}
#ctlbar QPushButton {{ background:{c['panel3']}; }}
#ctlbar QPushButton:hover {{ background:{c['orange']}; }}
#ctlbar QPushButton:disabled {{ background:{c['panel2']}; }}
#ctlbar QCheckBox::indicator {{ background:#000; }}
#ctlbar QCheckBox::indicator:checked {{ background:{c['orange']}; }}
#ctlbar QSlider::groove:horizontal {{ background:#000; }}
#epname {{ font-family:'{BODY_FONT}'; font-size:26px; color:{c['orange']}; }}
#timelbl {{ font-family:'{BODY_FONT}'; font-size:26px; color:{c['text']}; min-width:78px; }}
"""


def apply_theme(app) -> None:
    load_fonts()
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.Window, QColor(C["bg"]))
    p.setColor(QPalette.WindowText, QColor(C["text"]))
    p.setColor(QPalette.Base, QColor(C["panel"]))
    p.setColor(QPalette.AlternateBase, QColor(C["panel2"]))
    p.setColor(QPalette.Text, QColor(C["text"]))
    p.setColor(QPalette.Button, QColor(C["panel3"]))
    p.setColor(QPalette.ButtonText, QColor(C["text"]))
    p.setColor(QPalette.ToolTipBase, QColor("#000000"))
    p.setColor(QPalette.ToolTipText, QColor(C["text"]))
    p.setColor(QPalette.Highlight, QColor(C["orange"]))
    p.setColor(QPalette.HighlightedText, QColor("#000000"))
    p.setColor(QPalette.PlaceholderText, QColor(C["muted"]))
    app.setPalette(p)
    f = QFont(BODY_FONT)
    f.setPixelSize(22)
    f.setStyleStrategy(QFont.NoAntialias)
    app.setFont(f)
    app.setStyleSheet(stylesheet())
    app.setWindowIcon(app_icon())
