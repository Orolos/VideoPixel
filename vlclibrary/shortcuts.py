"""Scurtături (Desktop + Meniul Start) cu iconița VideoPixel — Windows.

Securitate: scriptul PowerShell este o constantă; căile se transmit prin variabile de mediu,
nu sunt lipite în text (nicio posibilitate de injecție prin ghilimele/apostrofuri în nume de foldere).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .paths import APP_NAME, exe_dir, frozen, project_dir, resource_dir

POWERSHELL_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$sh = New-Object -ComObject WScript.Shell
foreach ($place in $env:VP_PLACES.Split(',')) {
  if ($place -notin @('Desktop', 'Programs')) { continue }
  $dir = [Environment]::GetFolderPath($place)
  $s = $sh.CreateShortcut((Join-Path $dir ($env:VP_NAME + '.lnk')))
  $s.TargetPath = $env:VP_TARGET
  $s.Arguments = $env:VP_ARGS
  $s.WorkingDirectory = $env:VP_WORKDIR
  $s.IconLocation = $env:VP_ICON + ',0'
  $s.Description = $env:VP_NAME
  $s.Save()
}
"""


def shortcut_target() -> tuple[str, str, str, str]:
    """(țintă, argumente, folder de lucru, iconiță)"""
    icon = resource_dir() / "assets" / "videopixel.ico"
    if frozen():
        exe = Path(sys.executable)
        return str(exe), "", str(exe_dir()), str(exe)       # iconița e încorporată în .exe
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    target = pyw if pyw.exists() else py
    return str(target), f'"{project_dir() / "main.py"}"', str(project_dir()), str(icon)


def shortcut_env(desktop: bool = True, start_menu: bool = True) -> dict[str, str]:
    target, args, workdir, icon = shortcut_target()
    places = [p for p, on in (("Desktop", desktop), ("Programs", start_menu)) if on]
    return {"VP_PLACES": ",".join(places), "VP_NAME": APP_NAME, "VP_TARGET": target,
            "VP_ARGS": args, "VP_WORKDIR": workdir, "VP_ICON": icon}


def _powershell() -> str:
    root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    full = root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return str(full) if full.exists() else "powershell.exe"      # cale completă: nu depinde de PATH


def create_shortcuts(desktop: bool = True, start_menu: bool = True) -> bool:
    if not sys.platform.startswith("win"):
        return False
    try:
        r = subprocess.run(
            [_powershell(), "-NoProfile", "-NonInteractive", "-Command", POWERSHELL_SCRIPT],
            capture_output=True, timeout=40, env={**os.environ, **shortcut_env(desktop, start_menu)},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return r.returncode == 0
    except Exception:
        return False
