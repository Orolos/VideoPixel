"""Benchmark de performanță (offscreen). Rulează:  python tests/perf_bench.py
Construiește o bibliotecă sintetică mare și măsoară operațiile din firul interfeței."""
import os, sys, time, shutil, tempfile, random, statistics, types
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

N_TITLES = int(os.environ.get("BENCH_TITLES", 300))
EPS = 12

def timeit(label, fn, n=1, unit="ms"):
    ts = []
    for _ in range(n):
        t = time.perf_counter(); r = fn(); ts.append((time.perf_counter() - t) * 1000)
    med = statistics.median(ts)
    print(f"  {label:<46} {med:9.1f} ms" + (f"   (min {min(ts):.1f}, max {max(ts):.1f}, n={n})" if n > 1 else ""))
    RESULTS[label] = med
    return r

RESULTS = {}
t0 = time.perf_counter()
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor
from vlclibrary import theme
app = QApplication([])
theme.apply_theme(app)
from vlclibrary import ui
from vlclibrary.db import Library
from vlclibrary.scanner import scan_folder
print(f"import + QApplication + tema: {(time.perf_counter()-t0)*1000:.0f} ms")

tmp = Path(tempfile.mkdtemp(prefix="vpbench_"))
ui.data_dir = lambda: tmp
lib = tmp / "lib"
rnd = random.Random(1)
print(f"\n== Construiesc biblioteca sintetică: {N_TITLES} titluri x {EPS} episoade ==")
t = time.perf_counter()
for i in range(N_TITLES):
    d = lib / f"Show.Number.{i:03d}.S01.1080p.WEB-DL.x265-GRP"
    d.mkdir(parents=True)
    for e in range(1, EPS + 1):
        (d / f"Show.Number.{i:03d}.S01E{e:02d}.Episode.Title.{e}.1080p.WEB-DL.x265-GRP.mkv").write_bytes(b"x")
print(f"  creare fișiere: {(time.perf_counter()-t):.1f} s")

print("\n== Scanner / import ==")
timeit("scan_folder (un sezon, 12 fișiere)", lambda: scan_folder(lib / "Show.Number.000.S01.1080p.WEB-DL.x265-GRP"), n=50)
db = Library(tmp / "l.db")
timeit(f"import_root ({N_TITLES*EPS} episoade)", lambda: db.import_root(lib))

# postere de mărimea celor de la AniList (460x650), diferite
(tmp / "posters").mkdir()
img = QImage(460, 650, QImage.Format_RGB32)
for tt in db.titles():
    img.fill(QColor(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)))
    for k in range(0, 650, 13):
        for x in range(0, 460, 41):
            img.setPixelColor(x, k, QColor(255, k % 255, x % 255))
    img.save(str(tmp / "posters" / f"{tt['id']}.jpg"), "JPG", 90)
    db.set_meta(tt["id"], "desc", 2020, 7.5, "Action", poster=f"{tt['id']}.jpg", status=1)

# simulează utilizare: 40 de titluri „începute”
titles = db.titles()
for tt in titles[:40]:
    eps = db.title_episodes(tt["id"])
    db.set_watched(eps[0]["id"], True)
    db.set_progress(eps[1]["id"], 400_000, 1_400_000)

print("\n== Baza de date ==")
timeit("titles()", db.titles, n=20)
timeit("continue_watching() (40 titluri începute)", db.continue_watching, n=10)
timeit("seasons(title)", lambda: db.seasons(titles[0]["id"]), n=50)
tid = db.title_episodes(titles[5]["id"])[3]["id"]
timeit("set_progress (commit pe disc)", lambda: db.set_progress(tid, 500_000, 1_400_000), n=40)

print("\n== Interfața (firul principal) ==")
t = time.perf_counter()
w = ui.MainWindow(db); w.resize(1240, 780); w.show(); app.processEvents()
print(f"  MainWindow init + primul desen: {(time.perf_counter()-t)*1000:.0f} ms  (cu {N_TITLES} titluri)")
RESULTS["MainWindow init"] = (time.perf_counter()-t)*1000
w._worker and w._worker.wait(2000)
timeit("refresh_tree()", lambda: (w.refresh_tree(), app.processEvents()), n=5)
w.tree.setCurrentItem(w.tree.topLevelItem(0)); app.processEvents()
timeit("refresh_home() — rafturi cu postere (rece+cald)", lambda: (w.refresh_home(), app.processEvents()), n=5)
top = w.tree.topLevelItem(1); w.tree.setCurrentItem(top.child(0)); app.processEvents()
timeit("refresh_season() (12 episoade)", lambda: (w.refresh_season(), app.processEvents()), n=20)
timeit("_soft_refresh() în pagina sezonului", lambda: (w._soft_refresh(), app.processEvents()), n=20)
w.tree.setCurrentItem(w.tree.topLevelItem(0)); app.processEvents()
timeit("_soft_refresh() pe Acasă (ce rulează la 5 s)", lambda: (w._soft_refresh(), app.processEvents()), n=10)
print(f"\nBibliotecă de test: {tmp}")
import json; json.dump(RESULTS, open(os.environ.get("BENCH_OUT", "/tmp/bench_result.json"), "w"), indent=1)
