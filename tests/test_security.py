import io
import os
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vlclibrary import metadata


# ---------------- URL-uri: doar https + domenii cunoscute ----------------
@pytest.mark.parametrize("url", [
    "file:///C:/Windows/win.ini", "ftp://s4.anilist.co/a.jpg", "http://s4.anilist.co/a.jpg",
    "https://evil.example/a.jpg", "https://anilist.co.evil.example/a.jpg",
    "https://user:pw@s4.anilist.co/a.jpg", "https://s4.anilist.co:8443/a.jpg", "javascript:alert(1)",
    "https://notanilist.co/a.jpg",
])
def test_image_url_rejected(url):
    assert not metadata.is_image_url(url)


@pytest.mark.parametrize("url", [
    "https://s4.anilist.co/file/a.jpg", "https://static.tvmaze.com/x.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/600px-a.jpg",
])
def test_image_url_accepted(url):
    assert metadata.is_image_url(url)


def test_api_url_rules():
    assert metadata.is_api_url("https://graphql.anilist.co")
    assert metadata.is_api_url("https://api.tvmaze.com/singlesearch/shows?q=a")
    assert not metadata.is_api_url("https://s4.anilist.co/x")          # CDN-ul nu e API
    assert not metadata.is_api_url("http://api.tvmaze.com/x")
    with pytest.raises(ValueError):
        metadata._http("file:///etc/passwd")
    with pytest.raises(ValueError):
        metadata._http("https://evil.example/")


def test_download_refuses_bad_urls_without_network(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise AssertionError("nu trebuia să facă cerere")
    monkeypatch.setattr(metadata, "_http", boom)
    assert not metadata.download_poster("file:///etc/passwd", tmp_path / "a.jpg")
    assert not metadata.download_poster("https://evil.example/a.jpg", tmp_path / "b.jpg")
    assert not list(tmp_path.iterdir())


def test_redirects_are_checked():
    h = metadata._SafeRedirect(metadata.is_image_url)
    req = urllib.request.Request("https://s4.anilist.co/a.jpg")
    with pytest.raises(urllib.error.URLError):
        h.redirect_request(req, None, 302, "Found", {}, "file:///C:/secret")
    with pytest.raises(urllib.error.URLError):
        h.redirect_request(req, None, 302, "Found", {}, "https://evil.example/a.jpg")


def test_response_size_cap(monkeypatch):
    class FakeResp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): self.close()

    class FakeOpener:
        def open(self, req, timeout=None):
            return FakeResp(b"x" * (metadata.MAX_JSON + 10))
    monkeypatch.setattr(metadata.urllib.request, "build_opener", lambda *a, **k: FakeOpener())
    with pytest.raises(ValueError):
        metadata._http("https://api.tvmaze.com/x")


# ---------------- imagini: doar JPEG/PNG/WebP reale ----------------
def test_magic_bytes():
    assert metadata.looks_like_image(b"\xff\xd8\xff\xe0....")
    assert metadata.looks_like_image(b"\x89PNG\r\n\x1a\n....")
    assert metadata.looks_like_image(b"RIFF\x00\x00\x00\x00WEBPVP8 ")
    assert not metadata.looks_like_image(b"<html>")
    assert not metadata.looks_like_image(b"MZ\x90\x00")
    assert not metadata.looks_like_image(b"GIF89a")


def test_download_rejects_non_images(monkeypatch, tmp_path):
    monkeypatch.setattr(metadata, "_http", lambda *a, **k: b"<html>" + b"x" * 3000)
    assert not metadata.download_poster("https://s4.anilist.co/a.jpg", tmp_path / "a.jpg")
    assert not (tmp_path / "a.jpg").exists() and not list(tmp_path.glob("*.part"))


def test_read_image_limits(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication, QImage
    from vlclibrary.theme import read_image
    app = QGuiApplication.instance() or QGuiApplication([])
    ok = tmp_path / "ok.png"
    img = QImage(50, 70, QImage.Format_RGB32); img.fill(0xFF0000); img.save(str(ok))
    assert not read_image(ok).isNull()
    big = tmp_path / "big.png"
    img2 = QImage(8100, 4, QImage.Format_RGB32); img2.fill(1); img2.save(str(big))
    assert read_image(big).isNull()                       # peste limita de latură
    bmp = tmp_path / "x.bmp"; img.save(str(bmp))
    assert read_image(bmp).isNull()                       # format neacceptat
    junk = tmp_path / "junk.png"; junk.write_bytes(b"not an image" * 100)
    assert read_image(junk).isNull()


# ---------------- nume de poster din DB ----------------
def test_safe_poster_name():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from vlclibrary.ui import safe_poster_name
    assert safe_poster_name("12.jpg") == "12.jpg" and safe_poster_name("3_custom.PNG") == "3_custom.PNG"
    for bad in ("../x.jpg", "..\\x.jpg", "C:\\a.jpg", "/etc/passwd", "a/b.jpg", "x.exe", "", None, "a.jpg.exe"):
        assert safe_poster_name(bad) is None, bad


# ---------------- redare: doar fișiere video ----------------
def test_tooltip_and_message_are_plain():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from vlclibrary.theme import tip
    t = tip("<img src='file:///C:/x'> & <b>x</b>")
    assert "<img" not in t and "&lt;img" in t and t.startswith("<qt>")


import urllib.request  # noqa: E402  (folosit în test_redirects_are_checked)
