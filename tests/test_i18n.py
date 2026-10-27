import ast, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vlclibrary import i18n

SRC = Path(__file__).resolve().parent.parent / "vlclibrary"


def _keys(path):
    out = []
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "tr"
                and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
            out.append(n.args[0].value)
    return out


def test_every_tr_key_has_english():
    missing = []
    for f in ("ui.py", "player.py"):
        missing += [k for k in _keys(SRC / f) if k not in i18n.EN]
    # textele trimise prin act(...) / variabile sunt verificate separat
    assert not missing, missing


def test_switching_language():
    i18n.set_language("en")
    assert i18n.tr("Acasă") == "Home" and i18n.tr("necunoscut") == "necunoscut"
    i18n.set_language("ro")
    assert i18n.tr("Acasă") == "Acasă"
    i18n.set_language("xx")
    assert i18n.language() == "ro"


def test_format_placeholders_match():
    import string
    for ro, en in i18n.EN.items():
        f = lambda s: {x[1] for x in string.Formatter().parse(s) if x[1]}
        assert f(ro) == f(en), (ro, en)
