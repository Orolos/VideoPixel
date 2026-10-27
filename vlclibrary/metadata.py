"""Postere și descrieri de pe internet (fără chei API).

- anime  -> AniList (GraphQL), apoi TVMaze
- serial -> TVMaze, apoi AniList
- film   -> Wikipedia, apoi AniList (filme anime)
"""
from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

UA = "VideoPixel/1.1 (personal media library; python-urllib)"
TIMEOUT = 12

# --- securitate: doar HTTPS, doar domenii cunoscute, răspunsuri limitate ---
MAX_JSON = 2 * 1024 * 1024
MAX_IMAGE = 8 * 1024 * 1024
API_HOSTS = {"graphql.anilist.co", "api.tvmaze.com", "en.wikipedia.org"}
IMAGE_SUFFIXES = (".anilist.co", ".tvmaze.com", ".wikimedia.org", ".wikipedia.org")


@dataclass
class Meta:
    name: str = ""
    description: str = ""
    year: int | None = None
    score: float | None = None      # 0-10
    genres: str = ""
    poster_url: str = ""
    source: str = ""


# ---------------------------------------------------------------- HTTP
def _parts(url: str):
    try:
        p = urllib.parse.urlparse(url)
        return p.scheme, (p.hostname or "").lower(), p.port, bool(p.username or p.password)
    except ValueError:
        return "", "", None, False


def is_api_url(url: str) -> bool:
    scheme, host, port, creds = _parts(url)
    return scheme == "https" and host in API_HOSTS and port in (None, 443) and not creds


def is_image_url(url: str) -> bool:
    scheme, host, port, creds = _parts(url)
    return (scheme == "https" and port in (None, 443) and not creds
            and any(host.endswith(sfx) for sfx in IMAGE_SUFFIXES))


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Nu urmăm redirecționări către alte scheme/domenii decât cele permise."""

    def __init__(self, check):
        self._check = check

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not self._check(newurl):
            raise urllib.error.URLError(f"redirecționare blocată: {newurl[:80]}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _http(url: str, data: bytes | None = None, headers: dict | None = None, *,
          check=None, limit: int = MAX_JSON) -> bytes:
    check = check or is_api_url
    if not check(url):
        raise ValueError(f"URL nepermis: {url[:80]}")
    opener = urllib.request.build_opener(_SafeRedirect(check))
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with opener.open(req, timeout=TIMEOUT) as r:
        buf = r.read(limit + 1)
    if len(buf) > limit:
        raise ValueError("răspuns prea mare")
    return buf


def _get_json(url: str):
    return json.loads(_http(url, headers={"Accept": "application/json"}).decode("utf-8"))


def _post_json(url: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    raw = _http(url, data=body, headers={"Content-Type": "application/json",
                                         "Accept": "application/json"})
    return json.loads(raw.decode("utf-8"))


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if not re.match(r"(?i)^\(?source:", ln)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# ---------------------------------------------------------------- surse
ANILIST_QUERY = """
query ($search: String) {
  Page(perPage: 5) {
    media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
      id
      title { romaji english native }
      coverImage { extraLarge large }
      description(asHtml: false)
      seasonYear
      startDate { year }
      averageScore
      genres
    }
  }
}
"""


def search_anilist(query: str) -> Meta | None:
    data = _post_json("https://graphql.anilist.co",
                      {"query": ANILIST_QUERY, "variables": {"search": query}})
    media = (((data or {}).get("data") or {}).get("Page") or {}).get("media") or []
    if not media:
        return None
    m = media[0]
    t = m.get("title") or {}
    cover = m.get("coverImage") or {}
    score = m.get("averageScore")
    return Meta(
        name=t.get("english") or t.get("romaji") or t.get("native") or query,
        description=strip_html(m.get("description")),
        year=m.get("seasonYear") or (m.get("startDate") or {}).get("year"),
        score=round(score / 10, 1) if score else None,
        genres=", ".join(m.get("genres") or []),
        poster_url=cover.get("extraLarge") or cover.get("large") or "",
        source="AniList",
    )


def search_tvmaze(query: str) -> Meta | None:
    url = "https://api.tvmaze.com/singlesearch/shows?q=" + urllib.parse.quote(query)
    try:
        d = _get_json(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    if not d:
        return None
    img = d.get("image") or {}
    year = None
    if d.get("premiered"):
        try:
            year = int(d["premiered"][:4])
        except ValueError:
            pass
    rating = (d.get("rating") or {}).get("average")
    return Meta(
        name=d.get("name") or query,
        description=strip_html(d.get("summary")),
        year=year,
        score=float(rating) if rating else None,
        genres=", ".join(d.get("genres") or []),
        poster_url=img.get("original") or img.get("medium") or "",
        source="TVMaze",
    )


def search_wikipedia(query: str, kind: str = "film") -> Meta | None:
    suffix = "film" if kind == "film" else "anime"
    q = urllib.parse.quote(f"{query} {suffix}")
    res = _get_json("https://en.wikipedia.org/w/api.php?action=query&list=search"
                    f"&srsearch={q}&format=json&srlimit=1")
    hits = ((res or {}).get("query") or {}).get("search") or []
    if not hits:
        return None
    title = hits[0]["title"]
    s = _get_json("https://en.wikipedia.org/api/rest_v1/page/summary/"
                  + urllib.parse.quote(title.replace(" ", "_"), safe=""))
    thumb = (s.get("thumbnail") or {}).get("source") or ""
    if thumb:
        thumb = re.sub(r"/(\d+)px-", "/600px-", thumb)
    return Meta(
        name=s.get("title") or title,
        description=strip_html(s.get("extract")),
        poster_url=thumb,
        source="Wikipedia",
    )


def providers_for(kind: str):
    if kind == "serial":
        return [search_tvmaze, search_anilist]
    if kind == "film":
        return [lambda q: search_wikipedia(q, "film"), search_anilist]
    return [search_anilist, search_tvmaze]


def fetch_meta(name: str, kind: str = "anime") -> Meta | None:
    """Întoarce Meta, None dacă nu s-a găsit nimic, sau ridică ConnectionError dacă nu există rețea."""
    providers = providers_for(kind)
    errors = 0
    for fn in providers:
        try:
            m = fn(name)
        except Exception:
            errors += 1
            continue
        if m and (m.description or m.poster_url):
            return m
    if errors == len(providers):
        raise ConnectionError("Nu m-am putut conecta la serviciile de metadate.")
    return None


def looks_like_image(data: bytes) -> bool:
    """Acceptăm doar JPEG / PNG / WebP (verificare după primii octeți, nu după extensie)."""
    return (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"
            or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"))


def download_poster(url: str, dest: Path) -> bool:
    if not url or not is_image_url(url):
        return False
    try:
        data = _http(url, check=is_image_url, limit=MAX_IMAGE)
    except Exception:
        return False
    if len(data) < 1000 or not looks_like_image(data):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)            # scriere atomică: nu rămân poze pe jumătate
    return True
