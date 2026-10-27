import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vlclibrary import paths, shortcuts, vlcpath


def test_powershell_script_is_constant_and_values_go_through_env(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    evil = r"C:\Users\O'Neil\x\u2019; calc; \u2018\VideoPixel.exe"
    monkeypatch.setattr(sys, "executable", evil)
    env = shortcuts.shortcut_env()
    assert env["VP_TARGET"] == evil                       # valoarea ajunge intactă, prin mediu
    assert evil not in shortcuts.POWERSHELL_SCRIPT and "calc" not in shortcuts.POWERSHELL_SCRIPT
    assert "Bypass" not in shortcuts.POWERSHELL_SCRIPT
    assert shortcuts.shortcut_env(desktop=False)["VP_PLACES"] == "Programs"
    assert env["VP_ICON"] == evil                          # iconița e cea încorporată în .exe


def test_script_mode_shortcut_uses_ico(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    target, args, workdir, icon = shortcuts.shortcut_target()
    assert icon.endswith("videopixel.ico") and Path(icon).exists()
    assert args.strip('"').endswith("main.py")


def test_bundled_vlc_is_picked_up(monkeypatch, tmp_path):
    d = tmp_path / "vlc"
    (d / "plugins").mkdir(parents=True)
    (d / "libvlc.dll").write_bytes(b"x")
    monkeypatch.setattr(os, "environ", dict(os.environ))
    for k in ("PYTHON_VLC_LIB_PATH", "PYTHON_VLC_MODULE_PATH", "VLC_PLUGIN_PATH"):
        os.environ.pop(k, None)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(vlcpath, "exe_dir", lambda: tmp_path)
    monkeypatch.setattr(vlcpath, "resource_dir", lambda: tmp_path / "nope")
    assert vlcpath.setup() == d
    assert os.environ["PYTHON_VLC_LIB_PATH"].endswith("libvlc.dll")
    assert os.environ["VLC_PLUGIN_PATH"].endswith("plugins")


def test_data_dir_and_migration(monkeypatch, tmp_path):
    exe = tmp_path / "proj" / "dist" / "VideoPixel"
    exe.mkdir(parents=True)
    (tmp_path / "proj" / "library.db").write_bytes(b"db")
    (tmp_path / "proj" / "posters").mkdir()
    (tmp_path / "proj" / "posters" / "1.jpg").write_bytes(b"p")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe / "VideoPixel.exe"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    assert paths.data_dir() == tmp_path / "appdata" / "VideoPixel"
    assert paths.migrate_legacy_data() is True
    assert (paths.data_dir() / "library.db").read_bytes() == b"db"
    assert (paths.data_dir() / "posters" / "1.jpg").exists()
    assert paths.migrate_legacy_data() is False            # a doua oară nu suprascrie
