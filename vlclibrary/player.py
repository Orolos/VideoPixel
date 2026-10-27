"""Fereastra de redare: VLC (libvlc) integrat, cu salvarea progresului.

Mouse-ul peste video este prins de un overlay transparent (fereastră Qt deasupra
ferestrei native VLC), altfel rotița/clicurile/mișcarea nu ajung niciodată la Qt.
În ecran complet nu se vede nimic; la mișcarea mouse-ului apare bara de control.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu,
    QPushButton, QSlider, QVBoxLayout, QWidget,
)

from .db import RESUME_MIN_MS, Library
from .i18n import tr
from .scanner import VIDEO_EXT
from .theme import BODY_FONT, C, ElidedLabel, message, pixel_icon

from . import vlcpath

vlcpath.setup()        # folosește VLC-ul inclus lângă program, dacă există
try:
    import vlc
    VLC_ERROR = ""
except Exception as exc:  # lipsește python-vlc sau VLC însuși
    vlc = None
    VLC_ERROR = str(exc)

SKIP_INTRO_MS = 85_000
SAVE_EVERY_MS = 5_000
TICK_MS = 500
HIDE_UI_AFTER_S = 2.5


def fmt_time(ms: int) -> str:
    s = max(0, int(ms // 1000))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class ClickSlider(QSlider):
    """Slider care sare direct unde dai clic."""

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            span = max(1, self.width())
            v = self.minimum() + (self.maximum() - self.minimum()) * e.position().x() / span
            self.setValue(int(round(v)))
            self.sliderPressed.emit()
            self.sliderMoved.emit(self.value())
        super().mousePressEvent(e)


class MouseOverlay(QWidget):
    """Strat transparent peste video: rotiță = volum, clic = pauză, dublu clic = fullscreen.

    Desenează și mesajele scurte (volum, ±secunde, pauză) peste imagine.
    """
    wheel = Signal(int)
    clicked = Signal()
    doubleClicked = Signal()

    def __init__(self, owner: QWidget):
        super().__init__(owner, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.NoFocus)
        self._text = ""
        self._level: float | None = None
        self._osd_timer = QTimer(self)
        self._osd_timer.setSingleShot(True)
        self._osd_timer.timeout.connect(self._clear_osd)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self.clicked.emit)

    def flash(self, text: str, level: float | None = None, ms: int = 1300):
        self._text, self._level = text, level
        self._osd_timer.start(ms)
        self.update()

    def _clear_osd(self):
        self._text = ""
        self.update()

    def set_cursor_hidden(self, hidden: bool):
        self.setCursor(Qt.BlankCursor if hidden else Qt.ArrowCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 1))   # aproape invizibil, dar „prinde” mouse-ul
        if not self._text:
            return
        f = QFont(BODY_FONT)
        f.setPixelSize(34)
        f.setStyleStrategy(QFont.NoAntialias)
        p.setFont(f)
        fm = p.fontMetrics()
        w = max(fm.horizontalAdvance(self._text) + 36, 170)
        h = 52 + (22 if self._level is not None else 0)
        box = QRect(self.width() - w - 28, 24, w, h)
        p.fillRect(box, QColor(0, 0, 0, 215))
        p.setPen(QPen(QColor(C["orange"]), 4))
        p.drawRect(box.adjusted(2, 2, -2, -2))
        p.setPen(QColor(C["text"]))
        p.drawText(QRect(box.x(), box.y() + 2, box.width(), 48), Qt.AlignCenter, self._text)
        if self._level is not None:
            n, on = 12, int(round(max(0.0, min(1.0, self._level)) * 12))
            bw = (box.width() - 36) // n
            x0 = box.x() + (box.width() - bw * n) // 2
            for i in range(n):
                col = QColor(C["orange"]) if i < on else QColor(C["panel3"])
                p.fillRect(x0 + i * bw + 1, box.y() + 54, bw - 2, 12, col)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._click_timer.start(QApplication.doubleClickInterval())

    def mouseDoubleClickEvent(self, e):
        self._click_timer.stop()
        self.doubleClicked.emit()

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if d:
            self.wheel.emit(1 if d > 0 else -1)
        e.accept()


class PlayerWindow(QMainWindow):
    progressChanged = Signal()   # s-a schimbat starea unui episod (pentru reîmprospătarea listei)

    def __init__(self, db: Library):
        super().__init__()
        self.overlay: MouseOverlay | None = None   # creat după ce fereastra nativă există
        self.db = db
        self.ep_id: int | None = None
        self.duration = 0
        self._since_save = 0
        self._seeking = False
        self._last_cursor = QPoint()
        self._last_move = time.monotonic()
        self._was_maximized = False
        self.settings = QSettings("VideoPixel", "VideoPixel")

        self.instance = vlc.Instance("--no-video-title-show", "--quiet")
        self.mp = self.instance.media_player_new()
        self.mp.video_set_mouse_input(False)
        self.mp.video_set_key_input(False)

        self.setMinimumSize(420, 260)
        self.resize(1100, 680)
        geo = self.settings.value("player_geometry")
        if geo:
            self.restoreGeometry(geo)
        self.setWindowTitle("Player")
        self._build_ui()
        self._build_shortcuts()
        self._embed_video()

        self.overlay = MouseOverlay(self)
        self.overlay.wheel.connect(lambda d: self._change_volume(5 * d))
        self.overlay.clicked.connect(self.toggle_pause)
        self.overlay.doubleClicked.connect(self.toggle_fullscreen)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(TICK_MS)
        self.fs_timer = QTimer(self)
        self.fs_timer.timeout.connect(self._fs_tick)

    # ---------- UI ----------
    def _build_ui(self):
        self._root = QWidget()
        self._root_layout = QVBoxLayout(self._root)
        lay = self._root_layout
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.video = QFrame()
        self.video.setStyleSheet("background:#000;")
        self.video.setAttribute(Qt.WA_NativeWindow, True)
        lay.addWidget(self.video, 1)

        self.bar = QWidget()
        self.bar.setObjectName("ctlbar")
        self.bar.setAttribute(Qt.WA_StyledBackground, True)
        bl = QVBoxLayout(self.bar)
        bl.setContentsMargins(12, 8, 12, 10)
        bl.setSpacing(6)

        self.lbl_title = ElidedLabel("")
        self.lbl_title.setObjectName("epname")
        bl.addWidget(self.lbl_title)

        seek = QHBoxLayout()
        self.lbl_time = QLabel("00:00")
        self.lbl_time.setObjectName("timelbl")
        self.slider = ClickSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setFocusPolicy(Qt.NoFocus)
        self.slider.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self.slider.sliderReleased.connect(self._seek_released)
        self.slider.sliderMoved.connect(self._seek_moved)
        self.lbl_len = QLabel("00:00")
        self.lbl_len.setObjectName("timelbl")
        seek.addWidget(self.lbl_time)
        seek.addWidget(self.slider, 1)
        seek.addWidget(self.lbl_len)
        bl.addLayout(seek)

        row = QHBoxLayout()

        def btn(text, tip, slot, icon=None):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.NoFocus)
            if icon:
                b.setIcon(pixel_icon(icon, C["text"], 2))
            b.clicked.connect(slot)
            return b

        self.btn_prev = btn("", tr("Episodul anterior (P)"), lambda: self.step_episode(-1), "prev")
        self.btn_play = btn("", tr("Pauză / Redare (Space)"), self.toggle_pause, "pause")
        self.btn_next = btn("", tr("Episodul următor (N)"), lambda: self.step_episode(1), "next")
        self.btn_back = btn("-10s", tr("Înapoi 10 secunde (←)"), lambda: self.seek_by(-10_000))
        self.btn_fwd = btn("+10s", tr("Înainte 10 secunde (→)"), lambda: self.seek_by(10_000))
        self.btn_skip = btn("INTRO +85s", tr("Sari peste intro (S)"), lambda: self.seek_by(SKIP_INTRO_MS))
        self.btn_audio = btn("AUDIO", tr("Piste audio"), lambda: self._track_menu("audio"))
        self.btn_subs = btn("SUB", tr("Subtitrări"), lambda: self._track_menu("sub"))
        self.btn_speed = btn("1.0x", tr("Viteză"), self._speed_menu)
        self.btn_full = btn("", tr("Ecran complet (F)"), self.toggle_fullscreen, "full")
        for b in (self.btn_prev, self.btn_play, self.btn_next, self.btn_back, self.btn_fwd,
                  self.btn_skip):
            row.addWidget(b)
        row.addStretch(1)
        self.chk_auto = QCheckBox(tr("Următorul automat"))
        self.chk_auto.setChecked(True)
        self.chk_auto.setFocusPolicy(Qt.NoFocus)
        row.addWidget(self.chk_auto)
        for b in (self.btn_audio, self.btn_subs, self.btn_speed):
            row.addWidget(b)
        self.vol = QSlider(Qt.Horizontal)
        self.vol.setRange(0, 120)
        self.vol.setFixedWidth(110)
        self.vol.setFocusPolicy(Qt.NoFocus)
        self.vol.setValue(int(self.settings.value("volume", 80)))
        self.vol.valueChanged.connect(self._set_volume)
        self.lbl_vol = QLabel("VOL")
        row.addWidget(self.lbl_vol)
        row.addWidget(self.vol)
        row.addWidget(self.btn_full)
        bl.addLayout(row)

        lay.addWidget(self.bar)
        self.setCentralWidget(self._root)

    def _build_shortcuts(self):
        def sc(key, fn):
            s = QShortcut(QKeySequence(key), self)
            s.setContext(Qt.WindowShortcut)
            s.activated.connect(fn)

        sc("Space", self.toggle_pause)
        sc("Left", lambda: self.seek_by(-10_000))
        sc("Right", lambda: self.seek_by(10_000))
        sc("Shift+Left", lambda: self.seek_by(-60_000))
        sc("Shift+Right", lambda: self.seek_by(60_000))
        sc("Up", lambda: self._change_volume(5))
        sc("Down", lambda: self._change_volume(-5))
        sc("M", self.toggle_mute)
        sc("F", self.toggle_fullscreen)
        sc("F11", self.toggle_fullscreen)
        sc("Esc", self.exit_fullscreen)
        sc("N", lambda: self.step_episode(1))
        sc("P", lambda: self.step_episode(-1))
        sc("S", lambda: self.seek_by(SKIP_INTRO_MS))

    def _embed_video(self):
        wid = int(self.video.winId())
        if sys.platform.startswith("win"):
            self.mp.set_hwnd(wid)
        elif sys.platform == "darwin":
            self.mp.set_nsobject(wid)
        else:
            self.mp.set_xwindow(wid)

    # ---------- overlay-ul de mouse urmărește fereastra ----------
    def _sync_overlay(self):
        if self.overlay is None:
            return
        if not self.isVisible() or self.isMinimized():
            self.overlay.hide()
            return
        top_left = self.video.mapToGlobal(QPoint(0, 0))
        self.overlay.setGeometry(QRect(top_left, self.video.size()))
        if not self.overlay.isVisible():
            self.overlay.show()
        self.overlay.raise_()
        if self.isFullScreen() and self.bar.isVisible():
            self.bar.raise_()

    def _apply_bar_layout(self):
        """Bara de control se strânge pe ferestre înguste: întâi dispar butoanele secundare."""
        w = self.width()
        for wd in (self.chk_auto, self.btn_skip):
            wd.setVisible(w >= 1060)
        for wd in (self.btn_back, self.btn_fwd, self.btn_speed):
            wd.setVisible(w >= 820)
        self.vol.setFixedWidth(110 if w >= 820 else 80)
        for wd in (self.vol, self.lbl_vol):
            wd.setVisible(w >= 600)
        for wd in (self.btn_audio, self.btn_subs):
            wd.setVisible(w >= 500)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply_bar_layout()
        self._sync_overlay()

    def moveEvent(self, e):
        super().moveEvent(e)
        self._sync_overlay()

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._sync_overlay)
        QTimer.singleShot(200, self._sync_overlay)

    def hideEvent(self, e):
        super().hideEvent(e)
        if self.overlay is not None:
            self.overlay.hide()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == e.Type.WindowStateChange:
            QTimer.singleShot(120, self._sync_overlay)

    # ---------- încărcare episod ----------
    def open_episode(self, ep_id: int, from_start: bool = False) -> bool:
        if self.ep_id is not None:
            self.save_progress()
        ep = self.db.episode(ep_id)
        if not ep or not Path(ep["path"]).is_file():
            message(self, "warning", tr("Fișier lipsă"),
                    tr("Fișierul nu a fost găsit:\n") + str(ep["path"] if ep else ep_id))
            return False
        if Path(ep["path"]).suffix.lower() not in VIDEO_EXT:      # doar fișiere video, nu orice cale din DB
            message(self, "warning", tr("Fișier nepermis"), tr("Se pot reda doar fișiere video."))
            return False
        self.ep_id = ep_id
        self.duration = int(ep["duration_ms"] or 0)
        self._since_save = 0
        media = self.instance.media_new_path(str(ep["path"]))   # strict cale locală, nu URL
        resume = (not from_start and not ep["watched"] and ep["position_ms"] > RESUME_MIN_MS)
        if resume:
            media.add_option(f":start-time={ep['position_ms'] / 1000:.2f}")
        self.mp.set_media(media)
        self.mp.play()
        QTimer.singleShot(600, lambda: self.mp.audio_set_volume(self.vol.value()))
        label = ep["name"] or tr("Episodul {n}").format(n=ep["number"])
        if ep["kind"] == "film":
            head = ep["title"]
        else:
            head = f"{ep['title']}  S{ep['season_number']:02d}E{ep['number']:02d}  {label}"
        self.lbl_title.setText(head)
        self.setWindowTitle(head)
        self.btn_prev.setEnabled(self.db.neighbor(ep_id, -1) is not None)
        self.btn_next.setEnabled(self.db.neighbor(ep_id, 1) is not None)
        self.show()
        self.raise_()
        self.activateWindow()
        return True

    def step_episode(self, step: int):
        if self.ep_id is None:
            return
        nb = self.db.neighbor(self.ep_id, step)
        if nb is not None:
            self.open_episode(nb["id"], from_start=(step < 0))

    # ---------- control ----------
    def toggle_pause(self):
        was_playing = bool(self.mp.is_playing())
        self.mp.pause()
        self.overlay.flash(tr("PAUZĂ") if was_playing else tr("REDARE"))

    def toggle_mute(self):
        self.mp.audio_toggle_mute()
        self.overlay.flash(tr("MUT / SUNET"))

    def seek_by(self, delta_ms: int):
        t = self.mp.get_time()
        if t < 0:
            return
        target = max(0, t + delta_ms)
        if self.duration:
            target = min(target, self.duration - 1000)
        self.mp.set_time(int(target))
        self.overlay.flash(f"{'+' if delta_ms > 0 else '-'}{abs(delta_ms) // 1000}s  ·  {fmt_time(target)}")

    def _seek_moved(self, v: int):
        if self.duration:
            self.lbl_time.setText(fmt_time(self.duration * v / 1000))

    def _seek_released(self):
        if self.duration:
            self.mp.set_time(int(self.duration * self.slider.value() / 1000))
        self._seeking = False

    def _set_volume(self, v: int):
        self.mp.audio_set_volume(int(v))
        self.settings.setValue("volume", int(v))

    def _change_volume(self, delta: int):
        v = max(0, min(120, self.vol.value() + delta))
        self.vol.setValue(v)          # declanșează _set_volume
        self.overlay.flash(f"{tr('VOLUM')} {v}%", v / 120)

    def _track_menu(self, kind: str):
        menu = QMenu(self)
        if kind == "audio":
            tracks = self.mp.audio_get_track_description() or []
            current = self.mp.audio_get_track()
            setter = self.mp.audio_set_track
        else:
            tracks = self.mp.video_get_spu_description() or []
            current = self.mp.video_get_spu()
            setter = self.mp.video_set_spu
        if not tracks:
            menu.addAction(tr("(nicio pistă disponibilă)")).setEnabled(False)
        for tid, name in tracks:
            if isinstance(name, bytes):
                name = name.decode("utf-8", "replace")
            act = menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(tid == current)
            act.triggered.connect(lambda _=False, t=tid: setter(t))
        if kind == "sub":
            menu.addSeparator()
            menu.addAction(tr("Încarcă subtitrare din fișier…")).triggered.connect(self._load_sub_file)
        btn = self.btn_audio if kind == "audio" else self.btn_subs
        menu.exec(btn.mapToGlobal(QPoint(0, -menu.sizeHint().height())))

    def _load_sub_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Alege subtitrarea"), "", tr("Subtitrări (*.srt *.ass *.ssa *.sub *.vtt);;Toate (*)"))
        if path:
            self.mp.video_set_subtitle_file(path)

    def _speed_menu(self):
        menu = QMenu(self)
        cur = round(self.mp.get_rate(), 2)
        for r in (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0):
            a = menu.addAction(f"{r}x")
            a.setCheckable(True)
            a.setChecked(abs(cur - r) < 0.01)
            a.triggered.connect(lambda _=False, rate=r: self._set_rate(rate))
        menu.exec(self.btn_speed.mapToGlobal(QPoint(0, -menu.sizeHint().height())))

    def _set_rate(self, r: float):
        self.mp.set_rate(r)
        self.btn_speed.setText(f"{r}x")
        self.overlay.flash(f"{tr('VITEZĂ')} {r}x")

    # ---------- ecran complet ----------
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
            return
        self._was_maximized = self.isMaximized()
        # bara devine o fereastră plutitoare, deasupra videoclipului
        self.bar.hide()
        self.bar.setParent(self, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus)
        self.bar.setAttribute(Qt.WA_ShowWithoutActivating, True)     # opacă: fără urme/artefacte la redesenare
        self.bar.setAttribute(Qt.WA_StyledBackground, True)
        self.showFullScreen()
        self._last_cursor = QCursor.pos()
        self._last_move = time.monotonic() - 100        # nimic pe ecran până miști mouse-ul
        self._set_fs_ui(False)
        self.fs_timer.start(80)
        QTimer.singleShot(150, self._sync_overlay)
        QTimer.singleShot(500, self._sync_overlay)

    def exit_fullscreen(self):
        if not self.isFullScreen():
            return
        self.fs_timer.stop()
        self.bar.hide()
        self.bar.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.bar.setParent(self._root)
        self._root_layout.addWidget(self.bar)
        self.bar.show()
        self.overlay.set_cursor_hidden(False)
        self.showMaximized() if self._was_maximized else self.showNormal()
        QTimer.singleShot(150, self._sync_overlay)
        QTimer.singleShot(500, self._sync_overlay)

    def _set_fs_ui(self, visible: bool):
        if visible:
            geo = self.screen().geometry()
            h = self.bar.sizeHint().height()
            self.bar.setGeometry(geo.x(), geo.y() + geo.height() - h, geo.width(), h)
            if not self.bar.isVisible():
                self.bar.show()
            self.bar.raise_()
        else:
            self.bar.hide()
        self.overlay.set_cursor_hidden(not visible)

    def _fs_tick(self):
        """Ecran complet: bara apare doar când miști mouse-ul, dispare după câteva secunde."""
        now = time.monotonic()
        pos = QCursor.pos()
        if pos != self._last_cursor:
            self._last_cursor = pos
            self._last_move = now
            if not self.bar.isVisible():
                self._set_fs_ui(True)
        if self.bar.isVisible():
            over_bar = self.bar.geometry().contains(pos)
            popup = QApplication.activePopupWidget() is not None
            if over_bar or popup or self._seeking:
                self._last_move = now
            elif now - self._last_move > HIDE_UI_AFTER_S:
                self._set_fs_ui(False)

    # ---------- progres ----------
    def save_progress(self):
        if self.ep_id is None:
            return
        t = self.mp.get_time()
        length = self.mp.get_length()
        if length > 0:
            self.duration = length
        if t < 0 or self.duration <= 0:
            return
        if t < 3000:           # nu înregistrăm deschideri accidentale
            return
        self.db.set_progress(self.ep_id, int(t), int(self.duration))
        self.progressChanged.emit()

    def _tick(self):
        if self.ep_id is None or vlc is None:
            return
        state = self.mp.get_state()
        if state == vlc.State.Ended:
            self._on_ended()
            return
        if state == vlc.State.Error:
            self.lbl_time.setText(tr("Eroare"))
            return

        length = self.mp.get_length()
        t = self.mp.get_time()
        if length > 0:
            self.duration = length
        if self.duration > 0 and t >= 0 and not self._seeking:
            self.slider.setValue(int(t * 1000 / self.duration))
            self.lbl_time.setText(fmt_time(t))
            self.lbl_len.setText(fmt_time(self.duration))
        self.btn_play.setIcon(pixel_icon("pause" if self.mp.is_playing() else "play", C["text"], 2))

        self._since_save += TICK_MS
        if self._since_save >= SAVE_EVERY_MS:
            self._since_save = 0
            self.save_progress()

    def _on_ended(self):
        ep_id = self.ep_id
        self.db.mark_finished(ep_id)
        self.progressChanged.emit()
        nb = self.db.neighbor(ep_id, 1)
        if nb is not None and self.chk_auto.isChecked() and self.open_episode(nb["id"]):
            return
        self.ep_id = None
        self.mp.stop()
        self.slider.setValue(0)
        self.btn_play.setIcon(pixel_icon("play", C["text"], 2))
        self.lbl_time.setText(tr("Terminat"))

    def closeEvent(self, e):
        if not self.isFullScreen():
            self.settings.setValue("player_geometry", self.saveGeometry())
        self.save_progress()
        self.mp.stop()
        self.ep_id = None
        self.exit_fullscreen()
        if self.overlay is not None:
            self.overlay.hide()
        self.progressChanged.emit()
        super().closeEvent(e)
