"""Recunoaște episoadele din numele fișierelor și folderelor."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

VIDEO_EXT = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".webm", ".flv",
    ".ts", ".m2ts", ".mpg", ".mpeg",
}

# Etichete de calitate / release care marchează sfârșitul titlului real.
QUALITY = re.compile(
    r"(?i)(?<![a-z0-9])(?:2160p|1440p|1080[pi]|720p|576p|480p|4k|uhd|web[-. ]?dl|webrip|"
    r"bluray|blu-ray|bdrip|brrip|dvdrip|hdtv|hdr10\+?|hdr|dovi|x26[45]|h[. ]?26[45]|hevc|"
    r"avc|av1|aac\d?|dd[p+]?\d(?:\.\d)?|dts|flac|10bit|dual[-. ]audio|multi)(?![a-z0-9])"
)
BRACKETS = re.compile(r"\[[^\]]*\]|\([^)]*\)")

EP_PATTERNS = [
    # S02E05
    (re.compile(r"(?i)(?<![a-z0-9])S(\d{1,2})[ ._-]?E(\d{1,3})(?!\d)"), True),
    # 2x05
    (re.compile(r"(?i)(?<![0-9])(\d{1,2})x(\d{2,3})(?![0-9a-z])"), True),
    # Episode 05 / Ep05
    (re.compile(r"(?i)(?<![a-z])(?:episode|ep)[ ._-]*(\d{1,3})(?!\d)"), False),
    # [Grup] Titlu - 05 [1080p]   /   Titlu - 05v2
    (re.compile(r"(?:^|[\s_\]\)])-\s*(\d{1,3})(?:v\d+)?(?=[\s_.\[\(]|$)"), False),
    # [05]
    (re.compile(r"\[(\d{1,3})(?:v\d+)?\]"), False),
]
TRAILING_NUM = re.compile(r"(?:^|[\s._-])(\d{1,3})(?:v\d+)?\s*$")

SEASON_IN_NAME = re.compile(
    r"(?i)(?:^|[\s._-])(?:S(\d{1,2})|season[ ._-]*(\d{1,2})|(\d{1,2})(?:st|nd|rd|th)[ ._-]season"
    r"|sezon(?:ul)?[ ._-]*(\d{1,2}))(?![a-z0-9])"
)


@dataclass
class Episode:
    path: Path
    number: int
    title: str
    season: int | None = None


@dataclass
class Parsed:
    season: int | None
    episode: int | None
    title: str


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def clean_text(s: str) -> str:
    """Curăță un text de etichete de release, paranteze și separatori."""
    s = BRACKETS.sub(" ", s)
    m = QUALITY.search(s)
    if m:
        s = s[: m.start()]
    # puncte/underscore devin spații, dar nu cele dintre cifre (ex. "0.21")
    s = re.sub(r"(?<=\D)[._]|[._](?=\D)", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" -._")


def parse_filename(stem: str) -> Parsed:
    for pat, has_season in EP_PATTERNS:
        m = pat.search(stem)
        if not m:
            continue
        if has_season:
            season, ep = int(m.group(1)), int(m.group(2))
        else:
            season, ep = None, int(m.group(1))
        return Parsed(season, ep, clean_text(stem[m.end():]))
    m = TRAILING_NUM.search(QUALITY.split(BRACKETS.sub(" ", stem))[0])
    if m:
        return Parsed(None, int(m.group(1)), "")
    return Parsed(None, None, clean_text(stem))


def list_videos(folder: Path) -> list[Path]:
    files = [p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXT]
    return sorted(files, key=lambda p: natural_key(p.name))


def scan_folder(folder: str | Path) -> list[Episode]:
    """Scanează un folder (fără subfoldere) și întoarce episoadele numerotate.

    Dacă numerele nu pot fi recunoscute sigur (lipsesc sau se repetă),
    se folosește ordinea alfabetică natural ca numerotare 1..N.
    """
    groups: dict[int | None, list[tuple[Path, Parsed]]] = {}
    for f in list_videos(Path(folder)):
        p = parse_filename(f.stem)
        groups.setdefault(p.season, []).append((f, p))

    out: list[Episode] = []
    for season, items in groups.items():
        nums = [p.episode for _, p in items]
        ok = all(n is not None for n in nums) and len(set(nums)) == len(nums)
        for i, (f, p) in enumerate(items, 1):
            if ok:
                out.append(Episode(f, p.episode, p.title, season))
            else:
                out.append(Episode(f, i, p.title or clean_text(f.stem), season))
    out.sort(key=lambda e: (e.season or 0, e.number))
    return out


def guess_title_season(folder: str | Path) -> tuple[str, int | None]:
    """Ghicește titlul și sezonul din numele folderului (sau al părintelui)."""
    p = Path(folder)
    for candidate in (p.name, p.parent.name):
        text = BRACKETS.sub(" ", candidate)
        season = None
        cut = len(text)
        m = SEASON_IN_NAME.search(text)
        if m:
            season = int(next(g for g in m.groups() if g))
            cut = m.start()
        q = QUALITY.search(text)
        if q:
            cut = min(cut, q.start())
        title = clean_text(text[:cut])
        # folder de tip "Season 2": titlul e în folderul părinte
        if title:
            return title, season
        if season is None and candidate == p.name:
            continue
        # numele folderului era doar "Season N": păstrăm sezonul, căutăm titlul în părinte
        parent_title, _ = guess_title_season(p.parent) if candidate == p.name else ("", None)
        return parent_title, season
    return p.name, None


def clean_movie_name(stem: str) -> str:
    text = BRACKETS.sub(" ", stem)
    cut = len(text)
    q = QUALITY.search(text)
    if q:
        cut = q.start()
    for y in re.finditer(r"(?<!\d)(?:19|20)\d{2}(?!\d)", text):
        if y.start() > 0:
            cut = min(cut, y.start())
            break
    return clean_text(text[:cut]) or clean_text(stem) or stem
