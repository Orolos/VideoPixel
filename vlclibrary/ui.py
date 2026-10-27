"""Interfața principală: bibliotecă cu postere, sezoane, episoade, „Continuă vizionarea”."""
from __future__ import annotations

import re
import time
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListView,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QTextBrowser,
    QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import metadata
from . import player as player_mod
from .db import Library
from .i18n import language, set_language, tr
from .scanner import guess_title_season, scan_folder
from . import shortcuts
from .paths import data_dir, migrate_legacy_data
from .theme import (
    C, ElidedLabel, apply_theme, app_icon, message, pixel_icon, pixel_poster, placeholder_poster, plain_poster,
    read_image, tip,
)

KIND_LABELS = {"anime": "Anime", "serial": "Serial", "film": "Film"}
KIND_ICONS = {"anime": "star", "serial": "tv", "film": "film"}


def posters_dir() -> Path:
    return data_dir() / "posters"


def fmt(ms: int) -> str:
    return player_mod.fmt_time(ms)


# ======================================================================
SAFE_POSTER = re.compile(r"[\w.\-]+\.(jpg|jpeg|png|webp)", re.I)
MAX_CUSTOM_POSTER = 20 * 1024 * 1024


def safe_poster_name(name: str | None) -> str | None:
    """Doar un nume simplu de fișier (fără foldere / ..), cu extensie de imagine."""
    if name and name == Path(name).name and SAFE_POSTER.fullmatch(name):
        return name
    return None


class PosterCache:
    """Încarcă posterele (sau un înlocuitor pixel-art) la dimensiunea cerută."""

    def __init__(self):
        self.pixel = False
        self._cache: dict = {}

    def get(self, poster: str | None, name: str, w: int, h: int, block: int) -> QPixmap:
        poster = safe_poster_name(poster)
        path = posters_dir() / poster if poster else None
        try:
            mtime = path.stat().st_mtime_ns if path else 0      # un singur apel (rapid și pe discuri de rețea)
        except OSError:
            mtime = 0
        key = (poster, mtime, name if not mtime else "", w, h, self.pixel)
        pm = self._cache.get(key)
        if pm is None:
            if mtime:
                pm = pixel_poster(path, w, h, block) if self.pixel else plain_poster(path, w, h)
            if pm is None:
                pm = placeholder_poster(name, w, h)
            if len(self._cache) > 300:
                self._cache.clear()
            self._cache[key] = pm
        return pm

    def peek(self, poster: str | None, name: str, w: int, h: int) -> QPixmap | None:
        """Poster deja în memorie (sau None) — fără citire de pe disc, doar un stat."""
        poster = safe_poster_name(poster)
        path = posters_dir() / poster if poster else None
        try:
            mtime = path.stat().st_mtime_ns if path else 0
        except OSError:
            mtime = 0
        return self._cache.get((poster, mtime, name if not mtime else "", w, h, self.pixel))


class MetaWorker(QThread):
    """Caută postere/descrieri în fundal. Nu atinge baza de date (o scrie firul principal)."""
    result = Signal(int, object, str, str)   # id, Meta|None, nume poster, stare

    def __init__(self, jobs, parent=None):
        super().__init__(parent)
        self.jobs = jobs

    def run(self):
        for tid, name, kind, query in self.jobs:
            if self.isInterruptionRequested():
                return
            try:
                meta = metadata.fetch_meta(query or name, kind)
            except ConnectionError:
                self.result.emit(tid, None, "", "offline")
                continue
            except Exception:
                self.result.emit(tid, None, "", "offline")
                continue
            if meta is None:
                self.result.emit(tid, None, "", "notfound")
                continue
            poster = ""
            if meta.poster_url:
                fname = f"{tid}.jpg"
                if metadata.download_poster(meta.poster_url, posters_dir() / fname):
                    poster = fname
            self.result.emit(tid, meta, poster, "ok")


# ======================================================================
class AddSeasonDialog(QDialog):
    """Alegi folderul cu episoade; aplicația le recunoaște și le arată în previzualizare."""

    def __init__(self, db: Library, parent=None):
        super().__init__(parent)
        self.db = db
        self.episodes = []
        self.folder = ""
        self.setWindowTitle(tr("Adaugă sezon"))
        self.resize(780, 580)

        form = QFormLayout()
        row = QHBoxLayout()
        self.ed_folder = QLineEdit()
        self.ed_folder.setPlaceholderText(tr("Folderul cu episoadele sezonului…"))
        self.ed_folder.editingFinished.connect(self._scan)
        b = QPushButton(tr("ALEGE…"))
        b.clicked.connect(self._browse)
        row.addWidget(self.ed_folder, 1)
        row.addWidget(b)
        form.addRow(tr("Folder:"), row)

        self.cb_title = QComboBox()
        self.cb_title.setEditable(True)
        self.cb_title.addItems([t["name"] for t in db.titles()])
        self.cb_title.setCurrentText("")
        form.addRow(tr("Titlu:"), self.cb_title)

        self.cb_kind = QComboBox()
        self.cb_kind.addItem(tr("Anime"), "anime")
        self.cb_kind.addItem(tr("Serial"), "serial")
        form.addRow(tr("Tip:"), self.cb_kind)

        self.sp_season = QSpinBox()
        self.sp_season.setRange(0, 99)
        self.sp_season.setValue(1)
        form.addRow(tr("Sezon nr.:"), self.sp_season)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([tr("SEZON"), tr("EP."), tr("TITLU / FIȘIER")])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("muted")

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok = self.buttons.button(QDialogButtonBox.Ok)
        ok.setText(tr("ADAUGĂ"))
        ok.setProperty("primary", True)
        self.buttons.button(QDialogButtonBox.Cancel).setText(tr("ANULEAZĂ"))
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        ok.setEnabled(False)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.lbl_info)
        lay.addWidget(self.buttons)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, tr("Alege folderul sezonului"), self.ed_folder.text())
        if d:
            self.ed_folder.setText(d)
            self._scan()

    def _scan(self):
        folder = self.ed_folder.text().strip()
        if not folder or not Path(folder).is_dir():
            return
        self.folder = folder
        self.episodes = scan_folder(folder)
        title, season = guess_title_season(folder)
        hints = {e.season for e in self.episodes if e.season}
        if not season and len(hints) == 1:
            season = next(iter(hints))
        if not self.cb_title.currentText().strip():
            self.cb_title.setCurrentText(title)
        self.sp_season.setValue(season or 1)
        self.table.setRowCount(len(self.episodes))
        for i, e in enumerate(self.episodes):
            self.table.setItem(i, 0, QTableWidgetItem(str(e.season or "")))
            self.table.setItem(i, 1, QTableWidgetItem(str(e.number)))
            self.table.setItem(i, 2, QTableWidgetItem(e.title or e.path.name))
        multi = len(hints) > 1
        self.lbl_info.setText(
            tr("{n} episoade găsite.").format(n=len(self.episodes))
            + (" " + tr("Folderul conține mai multe sezoane; vor fi create separat.") if multi else "")
            if self.episodes else tr("Niciun fișier video găsit în acest folder."))
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self.episodes))

    def _accept(self):
        if not self.episodes:
            return
        title = self.cb_title.currentText().strip()
        if not title:
            QMessageBox.warning(self, tr("Titlu lipsă"), tr("Scrie titlul serialului / anime-ului."))
            return
        self.db.add_scanned(title, self.cb_kind.currentData(), self.folder, self.episodes,
                            self.sp_season.value())
        self.accept()


# ======================================================================
class MainWindow(QMainWindow):
    CARD_W, CARD_H = 150, 215
    HDR_W, HDR_H = 176, 252

    def __init__(self, db: Library):
        super().__init__()
        self.db = db
        self.player = None
        self.season_id: int | None = None
        self.title_id: int | None = None
        self.settings = QSettings("VideoPixel", "VideoPixel")
        self.posters = PosterCache()
        self.posters.pixel = self.settings.value("pixel_posters", False, type=bool)
        self._lib_sig = None
        self._fill_gen = 0
        self._fill_todo: list = []
        self._fill_timer = QTimer(self)
        self._fill_timer.setSingleShot(True)
        self._fill_timer.timeout.connect(self._fill_posters)
        self._worker: MetaWorker | None = None
        self._pending: list = []
        self._meta_tried: set[int] = set()
        self._offline_notified = False
        self.online = self.settings.value("online_info", True, type=bool)

        self.setWindowTitle("VideoPixel")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(520, 380)
        self.resize(1240, 780)
        self._ready = False
        self._compact = False
        self._auto_hidden = False

        self._build_toolbar()
        self.split = QSplitter()
        self.sidebar = self._build_sidebar()
        self.split.addWidget(self.sidebar)
        self.stack = QStackedWidget()
        self.split.addWidget(self.stack)
        self.split.setStretchFactor(0, 0)
        self.split.setStretchFactor(1, 1)
        self.split.setChildrenCollapsible(False)
        self.split.setSizes([300, 940])
        self.setCentralWidget(self.split)
        self.statusBar().showMessage(tr("Gata."))

        self._build_home_page()
        self._build_season_page()
        geo = self.settings.value("main_geometry")
        if geo:
            self.restoreGeometry(geo)
        sizes = self.settings.value("main_split")
        if sizes:
            try:
                self.split.setSizes([int(x) for x in sizes])
            except (TypeError, ValueError):
                pass
        self._ready = True
        self._apply_responsive()
        self.refresh_tree()
        self._auto_meta()

    # ---------- bara laterală ----------
    def _build_sidebar(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QWidget()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(10, 10, 10, 10)
        ic = QLabel()
        ic.setPixmap(app_icon().pixmap(32, 32))
        logo = QLabel("VIDEO\nPIXEL")
        logo.setObjectName("logo")
        hl.addWidget(ic)
        hl.addWidget(logo)
        hl.addStretch(1)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(150)
        w.setMinimumWidth(170)
        self.tree.setIconSize(QSize(16, 16))
        self.tree.currentItemChanged.connect(self._on_tree_change)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)
        lay.addWidget(head)
        lay.addWidget(self.tree, 1)
        return w

    # ---------- bara de unelte ----------
    def _build_toolbar(self):
        tb = QToolBar(tr("Unelte"))
        self.toolbar = tb
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        def act(text, icon, key, slot, tip=""):
            text, tip = tr(text), tr(tip) if tip else ""
            a = QAction(pixel_icon(icon, C["text"], 2), "  " + text, self)
            if key:
                a.setShortcut(key)
            a.setToolTip(tip or text)
            a.triggered.connect(slot)
            tb.addAction(a)
            return a

        act("Adaugă sezon", "plus", "Ctrl+N", self.add_season, "Adaugă un sezon dintr-un folder (Ctrl+N)")
        act("Folder multiplu", "folder", "Ctrl+Shift+N", self.import_root,
            "Scanează un folder care conține mai multe seriale/sezoane")
        act("Filme", "film", "Ctrl+M", self.add_movies, "Fiecare fișier video din folder devine un film")
        tb.addSeparator()
        act("Scoate", "trash", "Del", self.delete_selected,
            "Scoate selecția din bibliotecă (fișierele rămân pe disc)")
        act("Reîncarcă", "refresh", "F5", self.refresh_all, "Reîmprospătează și caută din nou postere lipsă")
        tb.addSeparator()
        self.act_pixel = QAction(pixel_icon("image", C["text"], 2), "  " + tr("Postere pixel"), self)
        self.act_pixel.setCheckable(True)
        self.act_pixel.setChecked(self.posters.pixel)
        self.act_pixel.setToolTip(tr("Afișează posterele în stil pixel art"))
        self.act_pixel.toggled.connect(self._toggle_pixel)
        tb.addAction(self.act_pixel)
        self.act_online = QAction(pixel_icon("search", C["text"], 2), "  " + tr("Info online"), self)
        self.act_online.setCheckable(True)
        self.act_online.setChecked(self.online)
        self.act_online.setToolTip(tip(tr(
            "Caută automat postere și descrieri pe internet.\nOprit: nimic nu pleacă de pe calculator (titlurile nu sunt trimise nicăieri).")))
        self.act_online.toggled.connect(self._toggle_online)
        tb.addAction(self.act_online)
        tb.addSeparator()
        act("Bară laterală", "folder", "Ctrl+B", self._toggle_sidebar, "Arată / ascunde bara laterală (Ctrl+B)")
        act("Limba", "star", None, self._switch_language, "Schimbă limba aplicației (RO / EN)").setText(
            f"  {tr('Limba')}: {language().upper()}")
        if sys.platform.startswith("win"):
            act("Scurtături", "star", None, self.make_shortcuts,
                "Creează scurtături VideoPixel pe Desktop și în Meniul Start")

    def _toggle_sidebar(self):
        self._auto_hidden = False
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def _set_cards(self, compact: bool):
        """Carduri și poster de antet mai mici când fereastra e mică."""
        self.CARD_W, self.CARD_H = (108, 156) if compact else (150, 215)
        self.HDR_W, self.HDR_H = (112, 160) if compact else (176, 252)
        for shelf in (self.shelf_cont, self.shelf_lib):
            shelf.setIconSize(QSize(self.CARD_W, self.CARD_H))
            shelf.setGridSize(QSize(self.CARD_W + 28, self.CARD_H + 100))
        self.shelf_cont.setFixedHeight(self.CARD_H + 132)
        self.shelf_lib.setMinimumHeight(self.CARD_H + 112)
        self.hdr_poster.setFixedSize(self.HDR_W, self.HDR_H)
        self._lib_sig = None
        if self.stack.currentIndex() == 0:
            self.refresh_home()
        else:
            self.refresh_season()

    def _apply_responsive(self):
        w, h = self.width(), self.height()
        compact = w < 920 or h < 640
        if compact != self._compact:
            self._compact = compact
            self._set_cards(compact)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly if w < 1020 else Qt.ToolButtonTextBesideIcon)
        narrow = w < 700
        if narrow and not self._auto_hidden and self.sidebar.isVisible():
            self._auto_hidden = True
            self.sidebar.hide()
        elif not narrow and self._auto_hidden:
            self._auto_hidden = False
            self.sidebar.show()
        self.hdr_poster.setVisible(w >= 620)
        self.s_desc.setVisible(h >= 600)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._ready:
            self._apply_responsive()

    def _switch_language(self):
        new = "en" if language() == "ro" else "ro"
        set_language(new)                      # textul întrebării în limba nouă
        r = QMessageBox.question(self, "VideoPixel", tr("Limba se schimbă după repornire. Repornești VideoPixel acum?"))
        if r != QMessageBox.Yes:
            set_language("en" if new == "ro" else "ro")
            return
        self.settings.setValue("language", new)
        self.settings.sync()
        from PySide6.QtCore import QProcess
        QProcess.startDetached(sys.executable, sys.argv if not getattr(sys, "frozen", False) else [])
        self.close()
        QApplication.quit()

    def make_shortcuts(self, _checked=False, quiet=False):
        ok = shortcuts.create_shortcuts()
        if not quiet or not ok:
            if ok:
                QMessageBox.information(self, "VideoPixel",
                                        tr("Gata! Ai scurtături VideoPixel pe Desktop și în Meniul Start."))
            else:
                QMessageBox.warning(self, "VideoPixel", tr("Nu am putut crea scurtăturile."))
        return ok

    def maybe_offer_shortcuts(self):
        if not sys.platform.startswith("win") or self.settings.value("shortcuts_asked", False, type=bool):
            return
        self.settings.setValue("shortcuts_asked", True)
        r = QMessageBox.question(self, "VideoPixel",
                                 tr("Vrei scurtături VideoPixel (cu iconița V) pe Desktop și în Meniul Start?"))
        if r == QMessageBox.Yes:
            self.make_shortcuts()

    def _toggle_online(self, on: bool):
        self.online = on
        self.settings.setValue("online_info", on)
        if on:
            self._auto_meta()

    def _toggle_pixel(self, on: bool):
        self.posters.pixel = on
        self.settings.setValue("pixel_posters", on)
        self._soft_refresh()

    # ---------- pagina „Acasă” ----------
    def _make_shelf(self, wrapping: bool) -> QListWidget:
        lw = QListWidget()
        lw.setViewMode(QListView.IconMode)
        lw.setIconSize(QSize(self.CARD_W, self.CARD_H))
        lw.setGridSize(QSize(self.CARD_W + 28, self.CARD_H + 100))
        lw.setResizeMode(QListView.Adjust)
        lw.setMovement(QListView.Static)
        lw.setWordWrap(True)
        lw.setSpacing(2)
        lw.setUniformItemSizes(True)
        lw.setWrapping(wrapping)
        lw.setFlow(QListView.LeftToRight)
        lw.setTextElideMode(Qt.ElideRight)
        lw.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        lw.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        return lw

    def _build_home_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 8, 14, 10)
        self.lbl_cont = QLabel(tr("CONTINUĂ VIZIONAREA"))
        self.lbl_cont.setObjectName("section")
        self.shelf_cont = self._make_shelf(False)
        self.shelf_cont.setFixedHeight(self.CARD_H + 132)
        self.shelf_cont.itemDoubleClicked.connect(lambda it: self.play(it.data(Qt.UserRole)))
        self.home_empty = QLabel(
            tr("Nimic început încă.\nApasă «Adaugă sezon», alege folderul cu episoade\nși dă dublu clic pe un episod."))
        self.home_empty.setAlignment(Qt.AlignCenter)
        self.home_empty.setObjectName("muted")
        self.lbl_lib = QLabel(tr("BIBLIOTECA"))
        self.lbl_lib.setObjectName("section")
        self.shelf_lib = self._make_shelf(True)
        self.shelf_lib.itemDoubleClicked.connect(lambda it: self._open_title(it.data(Qt.UserRole)))
        lay.addWidget(self.lbl_cont)
        lay.addWidget(self.shelf_cont)
        lay.addWidget(self.home_empty)
        lay.addWidget(self.lbl_lib)
        lay.addWidget(self.shelf_lib, 1)
        self.shelf_lib.setMinimumHeight(self.CARD_H + 112)
        sc = QScrollArea()                       # pe ferestre mici pagina derulează, nu se suprapune
        sc.setWidgetResizable(True)
        sc.setFrameShape(QScrollArea.NoFrame)
        sc.setWidget(w)
        self.stack.addWidget(sc)

    def refresh_home(self):
        self.shelf_cont.clear()
        items = self.db.continue_watching()
        for it in items:
            ep = it["episode"]
            if ep["kind"] == "film":
                head = ep["title"]
                sub = tr("reia filmul") if it["resume"] else tr("nevăzut")
            else:
                head = ep["title"]
                sub = f"S{ep['season_number']:02d}E{ep['number']:02d}"
            sub += f" · {fmt(ep['position_ms'])}" if it["resume"] else " · " + tr("urmează")
            li = QListWidgetItem(QIcon(self.posters.get(ep["poster"], ep["title"], self.CARD_W, self.CARD_H, 5)),
                                 f"{head}\n{sub}")
            li.setData(Qt.UserRole, ep["id"])
            li.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            li.setToolTip(tip(f"{ep['title']}\n{ep['name'] or tr('Episodul {n}').format(n=ep['number'])}"))
            self.shelf_cont.addItem(li)
        self.shelf_cont.setVisible(bool(items))
        self.lbl_cont.setVisible(bool(items))
        self.home_empty.setVisible(not items and not self.db.titles())

        titles = self.db.titles()
        sig = (self.posters.pixel, tuple((t["id"], t["name"], t["poster"], t["watched"], t["total"]) for t in titles))
        if sig != self._lib_sig:                 # raftul bibliotecii se reface doar dacă s-a schimbat ceva
            self._lib_sig = sig
            self._fill_gen += 1
            self.shelf_lib.setUpdatesEnabled(False)
            self.shelf_lib.clear()
            todo = []
            for t in titles:
                li = QListWidgetItem(f"{t['name']}\n{t['watched']}/{t['total']} " + tr("văzute"))
                li.setData(Qt.UserRole, t["id"])
                li.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
                li.setToolTip(tip(t["name"]))
                cached = self.posters.peek(t["poster"], t["name"], self.CARD_W, self.CARD_H)
                if cached is not None:
                    li.setIcon(QIcon(cached))
                else:                            # posterul real vine pe rând, fereastra rămâne fluidă
                    li.setIcon(QIcon(self.posters.get(None, t["name"], self.CARD_W, self.CARD_H, 5)))
                    todo.append((li, t["poster"], t["name"]))
                self.shelf_lib.addItem(li)
            self.shelf_lib.setUpdatesEnabled(True)
            self._fill_todo = todo
            if todo:
                self._fill_timer.start(0)
        self.shelf_lib.setVisible(bool(titles))
        self.lbl_lib.setVisible(bool(titles))

    def _fill_posters(self, gen: int | None = None):
        """Încarcă posterele rămase în loturi mici (nu blochează interfața la pornire)."""
        deadline = time.perf_counter() + 0.012
        todo = self._fill_todo
        while todo and time.perf_counter() < deadline:
            li, poster, name = todo.pop(0)
            li.setIcon(QIcon(self.posters.get(poster, name, self.CARD_W, self.CARD_H, 5)))
        if todo:
            self._fill_timer.start(0)

    def _open_title(self, title_id: int):
        for i in range(self.tree.topLevelItemCount()):
            ti = self.tree.topLevelItem(i)
            d = ti.data(0, Qt.UserRole)
            if d[0] == "title" and d[1] == title_id and ti.childCount():
                self.tree.setCurrentItem(ti.child(0))
                return

    # ---------- pagina sezonului ----------
    def _build_season_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 12, 14, 10)

        top = QHBoxLayout()
        top.setSpacing(16)
        self.hdr_poster = QLabel()
        self.hdr_poster.setFixedSize(self.HDR_W, self.HDR_H)
        info = QVBoxLayout()
        self.s_title = QLabel("")
        self.s_title.setObjectName("h1")
        self.s_title.setWordWrap(True)
        self.s_sub = ElidedLabel("")
        self.s_sub.setObjectName("muted")
        self.s_meta = QLabel("")
        self.s_meta.setObjectName("meta")
        for lbl in (self.s_title, self.s_meta):
            lbl.setTextFormat(Qt.PlainText)
        self.s_meta.setWordWrap(True)
        self.s_desc = QTextBrowser()
        self.s_desc.setFrameShape(QTextBrowser.NoFrame)
        self.s_desc.setOpenLinks(False)
        self.s_desc.setOpenExternalLinks(False)
        self.s_desc.setStyleSheet(f"background:transparent; border:0; color:{C['text']};")
        self.s_desc.setMaximumHeight(150)
        self.btn_info = QPushButton(tr("  CAUTĂ INFO"))
        self.btn_info.setIcon(pixel_icon("search", C["text"], 2))
        self.btn_info.setToolTip(tr("Caută poster și descriere (poți schimba numele căutat)"))
        self.btn_info.clicked.connect(lambda: self._search_info(self.title_id))
        info.addWidget(self.s_title)
        info.addWidget(self.s_sub)
        info.addWidget(self.s_meta)
        info.addWidget(self.s_desc, 1)
        info.addWidget(self.btn_info, 0, Qt.AlignLeft)
        top.addWidget(self.hdr_poster, 0, Qt.AlignTop)
        top.addLayout(info, 1)

        self.s_bar = QProgressBar()
        self.s_bar.setTextVisible(True)

        btns = QHBoxLayout()
        self.btn_continue = QPushButton(tr("  CONTINUĂ"))
        self.btn_continue.setProperty("primary", True)
        self.btn_continue.setIcon(pixel_icon("play", "#000000", 2))
        self.btn_continue.clicked.connect(self._continue_season)
        b_all = QPushButton(tr("  TOT: VĂZUT"))
        b_all.setIcon(pixel_icon("check", C["green"], 2))
        b_all.clicked.connect(lambda: self._mark_season(True))
        b_none = QPushButton(tr("TOT: NEVĂZUT"))
        b_none.clicked.connect(lambda: self._mark_season(False))
        btns.addWidget(self.btn_continue)
        btns.addStretch(1)
        btns.addWidget(b_all)
        btns.addWidget(b_none)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", tr("EP."), tr("TITLU"), tr("PROGRES")])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 44)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setIconSize(QSize(16, 16))
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.itemDoubleClicked.connect(lambda it: self._play_row(it.row()))
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._row_menu)
        self.table.cellClicked.connect(self._cell_clicked)

        hint = ElidedLabel(tr("Dublu clic = redă  ·  clic pe prima coloană = văzut/nevăzut  ·  clic dreapta = mai multe"))
        hint.setObjectName("muted")
        lay.addLayout(top)
        lay.addWidget(self.s_bar)
        lay.addLayout(btns)
        lay.addWidget(self.table, 1)
        lay.addWidget(hint)
        self.stack.addWidget(w)

    def refresh_season(self):
        if self.season_id is None:
            return
        s = self.db.season(self.season_id)
        if not s:
            self.stack.setCurrentIndex(0)
            return
        self.title_id = s["title_id"]
        eps = self.db.episodes(self.season_id)

        self.hdr_poster.setPixmap(self.posters.get(s["poster"], s["title"], self.HDR_W, self.HDR_H, 4))
        if s["kind"] == "film":
            self.s_title.setText(s["title"])
            self.s_sub.setText(tr("Film"))
        else:
            self.s_title.setText(f"{s['title']} — {tr('Sezon')} {s['number']}")
            self.s_sub.setText(f"{tr(KIND_LABELS.get(s['kind'], ''))}  ·  {s['folder']}")
        bits = []
        if s["year"]:
            bits.append(str(s["year"]))
        if s["score"]:
            bits.append(f"★ {s['score']:.1f}")
        if s["genres"]:
            bits.append(s["genres"])
        self.s_meta.setText("   ·   ".join(bits))
        if s["description"]:
            self.s_desc.setPlainText(s["description"])
        elif self._is_fetching(s["title_id"]):
            self.s_desc.setPlainText(tr("Se caută descrierea…"))
        elif s["meta_status"] == 2:
            self.s_desc.setPlainText(tr("Nu am găsit descrierea. Apasă «Caută info» și încearcă alt nume."))
        else:
            self.s_desc.setPlainText(tr("Fără descriere încă. Apasă «Caută info»."))

        watched = sum(1 for e in eps if e["watched"])
        self.s_bar.setMaximum(max(1, len(eps)))
        self.s_bar.setValue(watched)
        self.s_bar.setFormat(f"{tr('VĂZUTE')} {watched} / {len(eps)}")

        nxt = self.db.next_unwatched(self.season_id)
        if nxt:
            started = nxt["position_ms"] > 5000
            self.btn_continue.setText(f"  {tr('REIA') if started else tr('CONTINUĂ')} {tr('EP.')} {nxt['number']}")
            self.btn_continue.setEnabled(True)
        else:
            self.btn_continue.setText("  " + tr("SEZON TERMINAT"))
            self.btn_continue.setEnabled(False)

        sel = self.table.currentRow()
        self.table.setRowCount(len(eps))
        green, grey = QBrush(QColor(C["green"])), QBrush(QColor(C["muted"]))
        for r, e in enumerate(eps):
            exists = Path(e["path"]).exists()
            icon, color = None, None
            if e["watched"]:
                icon, prog, color = pixel_icon("check", C["green"], 2), tr("Văzut"), green
            elif e["position_ms"] > 5000:
                pct = int(100 * e["position_ms"] / e["duration_ms"]) if e["duration_ms"] else 0
                icon = pixel_icon("play", C["orange"], 2)
                prog = f"{fmt(e['position_ms'])} / {fmt(e['duration_ms'])}  ({pct}%)"
            else:
                prog = "—"
            if not exists:
                prog, color = tr("fișier lipsă"), grey
            cells = ["", str(e["number"]), e["name"] or tr("Episodul {n}").format(n=e["number"]), prog]
            for c, text in enumerate(cells):
                it = QTableWidgetItem(text)
                it.setData(Qt.UserRole, e["id"])
                if color is not None:
                    it.setForeground(color)
                if c == 0 and icon is not None:
                    it.setIcon(icon)
                if c in (0, 1):
                    it.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, c, it)
        if 0 <= sel < len(eps):
            self.table.selectRow(sel)

    # ---------- arbore ----------
    def _title_text(self, t) -> str:
        return f"{t['name']}  ({t['watched']}/{t['total']})"

    def refresh_tree(self):
        cur = self.season_id
        self.tree.blockSignals(True)
        self.tree.clear()
        home = QTreeWidgetItem([tr("Acasă")])
        home.setIcon(0, pixel_icon("home", C["orange"], 2))
        home.setData(0, Qt.UserRole, ("home",))
        self.tree.addTopLevelItem(home)
        target = home
        for t in self.db.titles():
            ti = QTreeWidgetItem([self._title_text(t)])
            ti.setIcon(0, pixel_icon(KIND_ICONS.get(t["kind"], "star"), C["orange_lt"], 2))
            ti.setData(0, Qt.UserRole, ("title", t["id"]))
            self.tree.addTopLevelItem(ti)
            for s in self.db.seasons(t["id"]):
                label = tr("Film") if t["kind"] == "film" else f"{tr('Sezon')} {s['number']}"
                si = QTreeWidgetItem([f"{label}  ({s['watched']}/{s['total']})"])
                si.setData(0, Qt.UserRole, ("season", s["id"]))
                ti.addChild(si)
                if s["id"] == cur:
                    target = si
            ti.setExpanded(True)
        self.tree.setCurrentItem(target)          # cu semnalele blocate: pagina se construiește o singură dată
        self.tree.blockSignals(False)
        self._show_item(target)

    def _on_tree_change(self, item, _prev):
        if item:
            self._show_item(item)

    def _show_item(self, item):
        data = item.data(0, Qt.UserRole)
        if data[0] == "home":
            self.season_id = None
            self.refresh_home()
            self.stack.setCurrentIndex(0)
        elif data[0] == "title":
            if item.childCount():
                self.tree.setCurrentItem(item.child(0))
        else:
            self.season_id = data[1]
            self.refresh_season()
            self.stack.setCurrentIndex(1)

    def refresh_all(self):
        self._meta_tried.clear()
        self._offline_notified = False
        self.refresh_tree()
        self._auto_meta()

    def _soft_refresh(self):
        """Reîmprospătare ușoară (fără a reconstrui selecția) după progres sau info noi."""
        self._update_tree_counts()
        if self.season_id is not None and self.stack.currentIndex() == 1:
            self.refresh_season()
        else:
            self.refresh_home()

    def _update_tree_counts(self):
        titles = {t["id"]: t for t in self.db.titles()}
        for i in range(self.tree.topLevelItemCount()):
            ti = self.tree.topLevelItem(i)
            d = ti.data(0, Qt.UserRole)
            if d[0] != "title" or d[1] not in titles:
                continue
            t = titles[d[1]]
            ti.setText(0, self._title_text(t))
            seasons = {s["id"]: s for s in self.db.seasons(t["id"])}
            for j in range(ti.childCount()):
                si = ti.child(j)
                sid = si.data(0, Qt.UserRole)[1]
                if sid in seasons:
                    s = seasons[sid]
                    label = tr("Film") if t["kind"] == "film" else f"{tr('Sezon')} {s['number']}"
                    si.setText(0, f"{label}  ({s['watched']}/{s['total']})")

    # ---------- postere / descrieri ----------
    def _is_fetching(self, title_id: int) -> bool:
        return any(j[0] == title_id for j in self._pending) or (
            self._worker is not None and any(j[0] == title_id for j in self._worker.jobs))

    def _auto_meta(self):
        if not self.online:
            return
        jobs = [(t["id"], t["name"], t["kind"], t["search_name"])
                for t in self.db.titles_needing_meta() if t["id"] not in self._meta_tried]
        self._enqueue(jobs)

    def _enqueue(self, jobs):
        for j in jobs:
            self._meta_tried.add(j[0])
            self._pending = [p for p in self._pending if p[0] != j[0]] + [j]
        self._kick()

    def _kick(self):
        if self._worker is not None or not self._pending:
            return
        jobs, self._pending = self._pending, []
        w = MetaWorker(jobs)
        w.result.connect(self._on_meta)
        w.finished.connect(self._worker_done)
        self._worker = w
        self.statusBar().showMessage(tr("Caut postere și descrieri…"))
        w.start()

    def _worker_done(self):
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if not self._pending:
            self.statusBar().showMessage(tr("Gata."), 4000)
        self._kick()

    def _on_meta(self, tid: int, meta, poster: str, status: str):
        if status == "offline":
            if not self._offline_notified:
                self._offline_notified = True
                self.statusBar().showMessage(tr("Nu m-am putut conecta la internet: postere indisponibile."), 8000)
            return
        if status == "notfound" or meta is None:
            self.db.set_meta_status(tid, 2)
        else:
            self.db.set_meta(tid, meta.description, meta.year, meta.score, meta.genres,
                             poster=poster or None, status=1)
        self._soft_refresh()

    def _search_info(self, title_id: int | None):
        if title_id is None:
            return
        t = self.db.title(title_id)
        if not t:
            return
        q, ok = QInputDialog.getText(self, tr("Caută info"), tr("Nume de căutat (în engleză / romaji merge cel mai bine):"),
                                     QLineEdit.Normal, t["search_name"] or t["name"])
        if not ok or not q.strip():
            return
        self.db.set_search_name(title_id, q.strip())
        self._enqueue([(title_id, t["name"], t["kind"], q.strip())])
        self._soft_refresh()

    def _pick_poster(self, title_id: int):
        path, _ = QFileDialog.getOpenFileName(self, tr("Alege posterul"), "",
                                              tr("Imagini (*.jpg *.jpeg *.png *.webp *.bmp)"))
        if not path:
            return
        src = Path(path)
        if (src.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp") or not src.is_file()
                or src.stat().st_size > MAX_CUSTOM_POSTER or read_image(src).isNull()):
            message(self, "warning", tr("Poster nepermis"),
                    tr("Alege o imagine JPEG, PNG sau WebP validă (maxim 20 MB, cel mult 8000 px)."))
            return
        posters_dir().mkdir(parents=True, exist_ok=True)
        dest = posters_dir() / f"{title_id}_custom{src.suffix.lower()}"
        shutil.copyfile(src, dest)
        self.db.set_poster(title_id, dest.name)
        self._soft_refresh()

    # ---------- acțiuni ----------
    def add_season(self):
        dlg = AddSeasonDialog(self.db, self)
        if dlg.exec():
            self.refresh_tree()
            self._auto_meta()

    def import_root(self):
        d = QFileDialog.getExistingDirectory(self, tr("Folder cu mai multe seriale / sezoane"))
        if not d:
            return
        n = self.db.import_root(d, "anime")
        QMessageBox.information(self, tr("Gata"), tr("Au fost adăugate/actualizate {n} sezoane.").format(n=n))
        self.refresh_tree()
        self._auto_meta()

    def add_movies(self):
        d = QFileDialog.getExistingDirectory(self, tr("Folder cu filme"))
        if not d:
            return
        n = self.db.add_movies(d)
        QMessageBox.information(self, tr("Gata"), tr("Au fost adăugate {n} filme.").format(n=n))
        self.refresh_tree()
        self._auto_meta()

    def delete_selected(self):
        item = self.tree.currentItem()
        if not item:
            return
        data = item.data(0, Qt.UserRole)
        if data[0] == "home":
            return
        what = tr("titlul întreg") if data[0] == "title" else tr("sezonul")
        if QMessageBox.question(
                self, tr("Confirmare"),
                tr("Scoți {what} din bibliotecă?\nFișierele de pe disc nu sunt șterse.").format(what=what)) != QMessageBox.Yes:
            return
        if data[0] == "title":
            self.db.delete_title(data[1])
        else:
            self.db.delete_season(data[1])
        self.season_id = None
        self.refresh_tree()

    def _tree_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.UserRole)
        if data[0] == "home":
            return
        title_id = data[1] if data[0] == "title" else self.db.season(data[1])["title_id"]
        m = QMenu(self)
        m.addAction(tr("Caută poster și descriere…")).triggered.connect(lambda: self._search_info(title_id))
        m.addAction(tr("Alege poster din fișier…")).triggered.connect(lambda: self._pick_poster(title_id))
        m.addSeparator()
        m.addAction(tr("Scoate din bibliotecă")).triggered.connect(self.delete_selected)
        m.exec(self.tree.viewport().mapToGlobal(pos))

    def _row_ep_id(self, row: int):
        it = self.table.item(row, 0)
        return it.data(Qt.UserRole) if it else None

    def _cell_clicked(self, row, col):
        if col != 0:
            return
        ep_id = self._row_ep_id(row)
        ep = self.db.episode(ep_id)
        self.db.set_watched(ep_id, not ep["watched"])
        self._soft_refresh()

    def _row_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        ep_id = self._row_ep_id(row)
        ep = self.db.episode(ep_id)
        m = QMenu(self)
        m.addAction(tr("Redă") + (tr(" (reia)") if ep["position_ms"] > 5000 and not ep["watched"] else "")
                    ).triggered.connect(lambda: self.play(ep_id))
        m.addAction(tr("Redă de la început")).triggered.connect(lambda: self.play(ep_id, True))
        m.addSeparator()
        if ep["watched"]:
            m.addAction(tr("Marchează ca nevăzut")).triggered.connect(
                lambda: (self.db.set_watched(ep_id, False), self._soft_refresh()))
        else:
            m.addAction(tr("Marchează ca văzut")).triggered.connect(
                lambda: (self.db.set_watched(ep_id, True), self._soft_refresh()))
        m.addAction(tr("Marchează văzute până la ep. {n}").format(n=ep["number"])).triggered.connect(
            lambda: (self.db.mark_upto(self.season_id, ep["number"]), self._soft_refresh()))
        m.exec(self.table.viewport().mapToGlobal(pos))

    def _mark_season(self, flag: bool):
        if self.season_id is None:
            return
        self.db.mark_season(self.season_id, flag)
        self._soft_refresh()

    def _continue_season(self):
        if self.season_id is None:
            return
        nxt = self.db.next_unwatched(self.season_id)
        if nxt:
            self.play(nxt["id"])

    def _play_row(self, row: int):
        ep_id = self._row_ep_id(row)
        if ep_id:
            self.play(ep_id)

    # ---------- redare ----------
    def play(self, ep_id: int, from_start: bool = False):
        if player_mod.vlc is None:
            message(
                self, "error", tr("VLC nu a fost găsit"),
                tr("Nu pot încărca VLC.\n\n• Instalează VLC (64 de biți) de la videolan.org\n"
                   "• Rulează: pip install python-vlc\n\nDetalii: ") + str(player_mod.VLC_ERROR))
            return
        if self.player is None:
            self.player = player_mod.PlayerWindow(self.db)
            self.player.setWindowIcon(app_icon())
            self.player.progressChanged.connect(self._soft_refresh)
        self.player.open_episode(ep_id, from_start)

    def closeEvent(self, e):
        if self.player is not None:
            self.player.close()
        if self._worker is not None:
            self._worker.requestInterruption()
            self._worker.wait(4000)
        self.settings.setValue("main_geometry", self.saveGeometry())
        self.settings.setValue("main_split", self.split.sizes())
        super().closeEvent(e)


def _set_app_id():
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VideoPixel.App")
        except Exception:
            pass


def run():
    migrate_legacy_data()
    set_language(QSettings("VideoPixel", "VideoPixel").value("language", "ro"))
    _set_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("VideoPixel")
    app.setOrganizationName("VideoPixel")
    apply_theme(app)
    db = Library(data_dir() / "library.db")
    win = MainWindow(db)
    win.show()
    QTimer.singleShot(1200, win.maybe_offer_shortcuts)
    code = app.exec()
    db.close()
    sys.exit(code)
