"""Căi pentru resurse (fonturi, iconițe) și date (bibliotecă, postere) — fără dependență de Qt.

- din sursă:      datele stau lângă main.py (ca până acum)
- din .exe:       datele stau în %APPDATA%\\VideoPixel (merge oriunde ai pune programul)
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "VideoPixel"


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def exe_dir() -> Path:
    return Path(sys.executable).parent


def project_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """Unde sunt `assets/` (fonturi, iconiță)."""
    if frozen():
        return Path(getattr(sys, "_MEIPASS", exe_dir()))
    return project_dir()


def data_dir() -> Path:
    if frozen():
        root = os.environ.get("APPDATA") or str(Path.home())
        d = Path(root) / APP_NAME
    else:
        d = project_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def migrate_legacy_data() -> bool:
    """La prima rulare a .exe-ului: preia biblioteca din varianta „script” dacă o găsește."""
    if not frozen():
        return False
    target = data_dir()
    if (target / "library.db").exists():
        return False
    for root in (exe_dir(), exe_dir().parent, exe_dir().parent.parent):
        db = root / "library.db"
        if db.exists():
            shutil.copyfile(db, target / "library.db")
            posters = root / "posters"
            if posters.is_dir():
                shutil.copytree(posters, target / "posters", dirs_exist_ok=True)
            return True
    return False
