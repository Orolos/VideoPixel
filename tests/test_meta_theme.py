import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vlclibrary import metadata
from vlclibrary.theme import ICONS


def test_icons_are_rectangular():
    for name, rows in ICONS.items():
        assert len({len(r) for r in rows}) == 1, name
        assert set("".join(rows)) <= {"#", "."}, name


def test_strip_html():
    s = metadata.strip_html("Hello<br><br>World <i>x</i> &amp; y<br>(Source: Foo)")
    assert s == "Hello\n\nWorld x & y"


ANILIST = {"data": {"Page": {"media": [{
    "title": {"romaji": "Edgerunners", "english": None, "native": "x"},
    "coverImage": {"large": "https://s4.anilist.co/l.jpg", "extraLarge": "https://s4.anilist.co/xl.jpg"},
    "description": "Desc<br>more", "seasonYear": None, "startDate": {"year": 2022},
    "averageScore": 86, "genres": ["Action"]}]}}}


def test_anilist_parse(monkeypatch):
    monkeypatch.setattr(metadata, "_http", lambda *a, **k: json.dumps(ANILIST).encode())
    m = metadata.search_anilist("edgerunners")
    assert (m.name, m.year, m.score, m.poster_url) == ("Edgerunners", 2022, 8.6, "https://s4.anilist.co/xl.jpg")
    assert m.description == "Desc\nmore" and m.genres == "Action"


def test_tvmaze_404_and_parse(monkeypatch):
    def nf(*a, **k):
        raise urllib.error.HTTPError("u", 404, "nf", {}, None)
    monkeypatch.setattr(metadata, "_http", nf)
    assert metadata.search_tvmaze("zzz") is None
    d = {"name": "Show", "summary": "<p>Hi</p>", "premiered": "2014-05-01",
         "rating": {"average": 7.5}, "genres": ["Drama"], "image": {"original": "https://static.tvmaze.com/o.jpg"}}
    monkeypatch.setattr(metadata, "_http", lambda *a, **k: json.dumps(d).encode())
    m = metadata.search_tvmaze("show")
    assert (m.name, m.year, m.score, m.description) == ("Show", 2014, 7.5, "Hi")


def test_wikipedia(monkeypatch):
    calls = []

    def fake(url, *a, **k):
        calls.append(url)
        if "w/api.php" in url:
            return json.dumps({"query": {"search": [{"title": "Spirited Away"}]}}).encode()
        return json.dumps({"title": "Spirited Away", "extract": "A film.",
                           "thumbnail": {"source": "https://upload.wikimedia.org/x/320px-a.jpg"}}).encode()
    monkeypatch.setattr(metadata, "_http", fake)
    m = metadata.search_wikipedia("Spirited Away", "film")
    assert m.poster_url.endswith("/600px-a.jpg") and m.description == "A film."
    assert "Spirited_Away" in calls[1]


def test_fetch_order_and_offline(monkeypatch):
    monkeypatch.setattr(metadata, "search_anilist", lambda q: None)
    monkeypatch.setattr(metadata, "search_tvmaze", lambda q: metadata.Meta(name="T", description="d"))
    assert metadata.fetch_meta("x", "anime").name == "T"       # fallback pe TVMaze
    monkeypatch.setattr(metadata, "search_tvmaze", lambda q: None)
    assert metadata.fetch_meta("x", "anime") is None            # negăsit
    def boom(q):
        raise OSError("offline")
    monkeypatch.setattr(metadata, "search_anilist", boom)
    monkeypatch.setattr(metadata, "search_tvmaze", boom)
    with pytest.raises(ConnectionError):
        metadata.fetch_meta("x", "anime")


def test_download_poster(monkeypatch, tmp_path):
    monkeypatch.setattr(metadata, "_http", lambda *a, **k: b"\xff\xd8\xff" + b"x" * 2000)
    assert metadata.download_poster("https://s4.anilist.co/a.jpg", tmp_path / "p" / "1.jpg")
    assert (tmp_path / "p" / "1.jpg").stat().st_size == 2003
    monkeypatch.setattr(metadata, "_http", lambda *a, **k: b"tiny")
    assert not metadata.download_poster("https://s4.anilist.co/a.jpg", tmp_path / "2.jpg")
