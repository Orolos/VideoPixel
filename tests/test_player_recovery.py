"""Recuperarea imaginii negre: dacă timpul merge dar nu există ieșire video, playerul reia redarea."""
import os, sys, tempfile
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
head = (ROOT / "tests" / "ui_smoke.py").read_text(encoding="utf-8").split("from PySide6.QtCore import QPoint")[0]
exec(compile(head, "smoke_head", "exec"))        # vlc simulat (fake) în sys.modules


def test_black_screen_recovery(monkeypatch=None):
    from PySide6.QtWidgets import QApplication
    from vlclibrary import player, theme, paths
    from vlclibrary.db import Library
    from vlclibrary.scanner import scan_folder
    tmp = Path(tempfile.mkdtemp())
    paths.data_dir = lambda: tmp
    player.data_dir = lambda: tmp
    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app)
    folder = tmp / "Show S01"; folder.mkdir()
    for i in (1, 2):
        (folder / f"Show.S01E0{i}.mkv").write_bytes(b"x")
    db = Library(tmp / "l.db")
    db.add_scanned("Show", "serial", str(folder), scan_folder(folder), 1)
    ep = db.title_episodes(db.titles()[0]["id"])[0]["id"]

    pw = player.PlayerWindow(db)
    pw.settings.setValue("hw_decode", True)
    pw.hw_decode = True
    calls = []
    orig_set = pw.mp.set_media
    pw.mp.set_media = lambda m: (calls.append(m), orig_set(m))
    pw.mp.has_vout = lambda: 0                  # videoul s-a pierdut
    pw.mp.video_get_track_count = lambda: 1
    pw.mp.get_time = lambda: 5000
    assert pw.open_episode(ep)
    n0 = len(calls)
    pw._opened_at -= 10
    for _ in range(4):
        pw._watchdog(5000)
    assert pw._recoveries == 1 and len(calls) == n0 + 1 and pw.hw_decode is True
    pw._opened_at -= 10
    for _ in range(4):
        pw._watchdog(5000)
    assert pw._recoveries == 2 and pw.hw_decode is False          # a doua oară: fără decodare hardware
    # cu imagine bună nu se întâmplă nimic
    pw.mp.has_vout = lambda: 1
    pw._opened_at -= 10
    for _ in range(10):
        pw._watchdog(5000)
    assert pw._recoveries == 2
    pw.settings.setValue("hw_decode", True)
