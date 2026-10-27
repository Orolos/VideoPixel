"""Test de fum al interfeței (offscreen), cu VLC și internet simulate."""
import io, json, os, sys, types, tempfile, time
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---- VLC simulat ----
fake = types.ModuleType("vlc")
class State: Ended="E"; Error="X"; Playing="P"
class MP:
    def __init__(s): s.t=0; s.vol=0; s.paused=False
    def video_set_mouse_input(s,*a): pass
    def video_set_key_input(s,*a): pass
    def set_xwindow(s,*a): pass
    def set_media(s,m): s.t=0
    def play(s): pass
    def pause(s): s.paused = not s.paused
    def stop(s): pass
    def get_state(s): return State.Playing
    def get_time(s): return s.t
    def set_time(s,t): s.t=t
    def get_length(s): return 1_400_000
    def is_playing(s): return not s.paused
    def audio_set_volume(s,v): s.vol=v
    def audio_toggle_mute(s): pass
    def audio_get_track_description(s): return [(1,b"Japanese"),(2,b"English")]
    def audio_get_track(s): return 1
    def video_get_spu_description(s): return [(-1,b"Disable"),(3,b"English")]
    def video_get_spu(s): return 3
    def get_rate(s): return 1.0
class Media:
    def __init__(s,p): s.p=p
    def add_option(s,o): pass
class Inst:
    def __init__(s,*a): pass
    def media_player_new(s): return MP()
    def media_new(s,p): return Media(p)
    def media_new_path(s,p): return Media(p)
fake.Instance=Inst; fake.State=State
sys.modules["vlc"]=fake

from PySide6.QtCore import QPoint, Qt, QPointF, QEvent
from PySide6.QtGui import QImage, QColor, QWheelEvent
from PySide6.QtWidgets import QApplication

# ---- internet simulat ----
from vlclibrary import metadata
def poster_bytes():
    img = QImage(300, 450, QImage.Format_RGB32); img.fill(QColor("#2a5db0"))
    for y in range(450):
        for x in range(0, 300, 3):
            img.setPixelColor(x, y, QColor(255, (y*2) % 255, (x*3) % 255))
    from PySide6.QtCore import QBuffer, QByteArray
    ba = QByteArray(); buf = QBuffer(ba); buf.open(QBuffer.WriteOnly); img.save(buf, "JPG"); return bytes(ba)
POSTER = poster_bytes()
def fake_http(url, data=None, headers=None, **kw):
    if "graphql.anilist.co" in url and b"Cyberpunk" in (data or b""):
        return json.dumps({"data":{"Page":{"media":[{"id":1,"title":{"romaji":"Cyberpunk: Edgerunners","english":"Cyberpunk: Edgerunners","native":""},
          "coverImage":{"extraLarge":"https://s4.anilist.co/x.jpg"},"description":"A street kid tries to survive in a technology and body modification-obsessed city of the future.<br><br>(Source: Studio Trigger)",
          "seasonYear":2022,"startDate":{"year":2022},"averageScore":86,"genres":["Action","Sci-Fi"]}]}}}).encode()
    if url.endswith("x.jpg"): return POSTER
    raise OSError("offline")
metadata._http = fake_http

from vlclibrary.db import Library
# SIMULATE_WIN: pe Windows winId() declanșează moveEvent/resizeEvent în timpul __init__
from vlclibrary import player as _pm
_orig_embed = _pm.PlayerWindow._embed_video
def _embed(self):
    from PySide6.QtGui import QMoveEvent, QResizeEvent
    from PySide6.QtCore import QSize
    self.moveEvent(QMoveEvent(QPoint(1,1), QPoint(0,0)))
    self.resizeEvent(QResizeEvent(QSize(10,10), QSize(0,0)))
    self.hideEvent(None) if False else None
    _orig_embed(self)
_pm.PlayerWindow._embed_video = _embed
from vlclibrary import ui, theme

app = QApplication([])
theme.apply_theme(app)
tmp = Path(tempfile.mkdtemp())
ui.data_dir = lambda: tmp           # posterele/DB în folder temporar
d = tmp / "Cyberpunk.Edgerunners.S02.2160p.NF.WEB-DL.DDP5.1.DV.HDR.HEVC-NTb"
d.mkdir()
titles = ["Last.Chance.for.a.Slow.Dance","Give.Me.Another.Day","0.21","Someone.That.I.Used.To.Know","Fades.Pass.the.Distance"]
for i,t in enumerate(titles,1):
    (d/f"Cyberpunk.Edgerunners.S02E{i:02d}.{t}.2160p.NF.WEB-DL.DDP5.1.DV.HDR.HEVC-NTb.mkv").write_bytes(b"x")
# al doilea titlu: nu există nicăieri -> placeholder
(tmp/"Zzz Unknown Show").mkdir(); (tmp/"Zzz Unknown Show"/"Zzz Unknown Show - 01.mkv").write_bytes(b"x")
db = Library(tmp/"l.db")
db.import_root(tmp)
cy = [t for t in db.titles() if t["name"].startswith("Cyber")][0]
sid = db.seasons(cy["id"])[0]["id"]
rows = db.episodes(sid)
db.set_watched(rows[0]["id"], True); db.set_progress(rows[1]["id"], 700_000, 1_400_000)

w = ui.MainWindow(db); w.resize(1240, 780); w.show()
# așteaptă firul de fundal
t0 = time.time()
while (w._worker is not None or w._pending) and time.time()-t0 < 10:
    app.processEvents(); time.sleep(0.05)
for _ in range(20): app.processEvents(); time.sleep(0.02)
t = db.title(cy["id"])
assert t["meta_status"] == 1 and t["poster"] and t["year"] == 2022 and t["score"] == 8.6, dict(t)
assert "Source" not in t["description"] and "<br" not in t["description"], t["description"]
z = [t for t in db.titles() if t["name"].startswith("Zzz")][0]
assert z["meta_status"] == 0 and w._offline_notified          # offline -> reîncearcă data viitoare
assert (tmp/"posters"/t["poster"]).exists()
w.grab().save(str(tmp/"home.png"))
top = [w.tree.topLevelItem(i) for i in range(w.tree.topLevelItemCount())]
cyi = [i for i in top if i.data(0, Qt.UserRole)[0]=="title" and "Cyber" in i.text(0)][0]
w.tree.setCurrentItem(cyi.child(0)); app.processEvents()
w.grab().save(str(tmp/"season.png"))
w.act_pixel.setChecked(False); app.processEvents(); w.grab().save(str(tmp/"season_plain.png")); w.act_pixel.setChecked(True)

# ---- player ----
w.play(rows[1]["id"]); app.processEvents()
p = w.player
assert p.ep_id == rows[1]["id"]
# rotița = volum
v0 = p.vol.value()
ev = QWheelEvent(QPointF(10,10), QPointF(10,10), QPoint(0,0), QPoint(0,120), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
app.sendEvent(p.overlay, ev); app.processEvents()
assert p.vol.value() == v0 + 5 and p.mp.vol == v0 + 5, (p.vol.value(), p.mp.vol)
ev = QWheelEvent(QPointF(10,10), QPointF(10,10), QPoint(0,0), QPoint(0,-120), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
app.sendEvent(p.overlay, ev); app.sendEvent(p.overlay, ev); app.processEvents()
assert p.vol.value() == v0 - 5
p.overlay.flash("VOLUM 75%", 0.62); app.processEvents()
p.show(); app.processEvents()
p.grab().save(str(tmp/"player.png"))
p.overlay.grab().save(str(tmp/"overlay.png"))
# progres + următorul
p.mp.t = 1_300_000; p.save_progress()
assert db.episode(rows[1]["id"])["watched"] == 1
p.step_episode(1); assert p.ep_id == rows[2]["id"]
p._on_ended(); assert p.ep_id == rows[3]["id"]

# ---- fullscreen: nimic pe ecran, apare la mișcare ----
from vlclibrary import player as pm
pos = {"p": QPoint(100,100)}
pm.QCursor.pos = staticmethod(lambda: pos["p"])
p.toggle_fullscreen(); app.processEvents()
assert p.isFullScreen() and not p.bar.isVisible(), "bara trebuie ascunsă la intrare"
pos["p"] = QPoint(120,110); p._fs_tick(); app.processEvents()
assert p.bar.isVisible() and p.bar.isWindow(), "bara trebuie să apară la mișcare"
p.grab().save(str(tmp/"fullscreen.png")); p.bar.grab().save(str(tmp/"fs_bar.png"))
p._last_move -= 10; p._fs_tick(); app.processEvents()
assert not p.bar.isVisible(), "bara dispare după inactivitate"
p.exit_fullscreen(); app.processEvents()
assert not p.isFullScreen() and p.bar.isVisible() and not p.bar.isWindow() and p.bar.parent() is p._root
assert p._root_layout.indexOf(p.bar) >= 0
# a doua rundă
p.toggle_fullscreen(); pos["p"] = QPoint(5,5); p._fs_tick(); assert p.bar.isVisible(); p.exit_fullscreen()
p.close(); w.close()

dlg = ui.AddSeasonDialog(db); dlg.ed_folder.setText(str(d)); dlg._scan(); app.processEvents()
assert dlg.cb_title.currentText()=="Cyberpunk Edgerunners" and dlg.sp_season.value()==2 and len(dlg.episodes)==5
dlg.grab().save(str(tmp/"dialog.png"))
print("OK", tmp)
