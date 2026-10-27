import sys
import traceback
from pathlib import Path


def _log_path() -> Path:
    try:
        from vlclibrary.paths import data_dir
        return data_dir() / "error.log"
    except Exception:
        return Path(__file__).with_name("error.log")


def report(text: str):
    log = _log_path()
    try:
        log.write_text(text, encoding="utf-8")
    except Exception:
        pass
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, f"A aparut o eroare. Detalii in:\n{log}\n\n" + text[-800:], "VideoPixel", 0x10)
        except Exception:
            pass


def _hook(exc_type, exc, tb):
    report("".join(traceback.format_exception(exc_type, exc, tb)))


sys.excepthook = _hook

if sys.platform.startswith("win"):
    try:                        # nu încărca DLL-uri din folderul curent (DLL planting)
        import ctypes
        ctypes.windll.kernel32.SetDllDirectoryW("")
    except Exception:
        pass

if __name__ == "__main__":
    try:
        from vlclibrary.ui import run
        run()
    except SystemExit:
        raise
    except BaseException:
        report(traceback.format_exc())
        raise
