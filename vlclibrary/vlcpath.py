"""Folosește VLC-ul inclus lângă program (folderul `vlc`), dacă există; altfel VLC-ul instalat.

Trebuie apelat ÎNAINTE de `import vlc`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .paths import exe_dir, frozen, project_dir, resource_dir


def setup() -> Path | None:
    candidates = [project_dir() / "vlc"]
    if frozen():
        candidates = [exe_dir() / "vlc", resource_dir() / "vlc"] + candidates
    lib_names = ("libvlc.dll", "libvlc.so", "libvlc.dylib")
    for d in candidates:
        lib = next((d / n for n in lib_names if (d / n).exists()), None)
        if lib is None:
            continue
        os.environ["PYTHON_VLC_LIB_PATH"] = str(lib)       # VLC-ul inclus bate orice variabilă din mediu
        plugins = d / "plugins"
        if plugins.is_dir():
            os.environ["PYTHON_VLC_MODULE_PATH"] = str(plugins)
            os.environ["VLC_PLUGIN_PATH"] = str(plugins)
        os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(str(d))
            except OSError:
                pass
        return d
    return None
