"""Baza de date SQLite: titluri, sezoane, episoade și progresul vizionării."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from .scanner import (
    VIDEO_EXT, Episode, clean_movie_name, guess_title_season, list_videos, scan_folder,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS titles (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE COLLATE NOCASE,
    kind  TEXT NOT NULL DEFAULT 'anime'
);
CREATE TABLE IF NOT EXISTS seasons (
    id        INTEGER PRIMARY KEY,
    title_id  INTEGER NOT NULL REFERENCES titles(id) ON DELETE CASCADE,
    number    INTEGER NOT NULL,
    folder    TEXT,
    UNIQUE(title_id, number)
);
CREATE TABLE IF NOT EXISTS episodes (
    id           INTEGER PRIMARY KEY,
    season_id    INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    number       INTEGER NOT NULL,
    name         TEXT NOT NULL DEFAULT '',
    path         TEXT NOT NULL UNIQUE,
    duration_ms  INTEGER NOT NULL DEFAULT 0,
    position_ms  INTEGER NOT NULL DEFAULT 0,
    watched      INTEGER NOT NULL DEFAULT 0,
    last_played  TEXT
);
CREATE INDEX IF NOT EXISTS idx_ep_season ON episodes(season_id, number);
"""

WATCHED_RATIO = 0.90      # peste acest procent episodul e considerat văzut
RESUME_MIN_MS = 5000      # sub acest minut nu mai reluăm de unde a rămas


def _now() -> str:
    return datetime.now().isoformat(timespec="microseconds")


class Library:
    def __init__(self, path: str | Path):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA trusted_schema=OFF")
        self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self):
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(titles)")}
        for name, ddl in (
            ("poster", "TEXT"), ("description", "TEXT"), ("year", "INTEGER"),
            ("score", "REAL"), ("genres", "TEXT"),
            ("meta_status", "INTEGER NOT NULL DEFAULT 0"),   # 0 necăutat, 1 găsit, 2 negăsit
            ("search_name", "TEXT"),
        ):
            if name not in cols:
                self.conn.execute(f"ALTER TABLE titles ADD COLUMN {name} {ddl}")
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ---------- adăugare ----------
    def _title_id(self, name: str, kind: str) -> int:
        row = self.conn.execute("SELECT id FROM titles WHERE name=?", (name,)).fetchone()
        if row:
            return row["id"]
        cur = self.conn.execute("INSERT INTO titles(name, kind) VALUES(?,?)", (name, kind))
        return cur.lastrowid

    def add_season(self, title: str, kind: str, number: int, folder: str,
                   episodes: list[Episode]) -> int:
        """Adaugă/actualizează un sezon. Progresul episoadelor existente se păstrează."""
        with self.conn:
            tid = self._title_id(title, kind)
            row = self.conn.execute(
                "SELECT id FROM seasons WHERE title_id=? AND number=?", (tid, number)
            ).fetchone()
            if row:
                sid = row["id"]
                self.conn.execute("UPDATE seasons SET folder=? WHERE id=?", (str(folder), sid))
            else:
                sid = self.conn.execute(
                    "INSERT INTO seasons(title_id, number, folder) VALUES(?,?,?)",
                    (tid, number, str(folder)),
                ).lastrowid
            for e in episodes:
                p = str(e.path)
                ex = self.conn.execute("SELECT id FROM episodes WHERE path=?", (p,)).fetchone()
                if ex:
                    self.conn.execute(
                        "UPDATE episodes SET season_id=?, number=?, name=? WHERE id=?",
                        (sid, e.number, e.title, ex["id"]),
                    )
                else:
                    self.conn.execute(
                        "INSERT INTO episodes(season_id, number, name, path) VALUES(?,?,?,?)",
                        (sid, e.number, e.title, p),
                    )
        return sid

    def add_scanned(self, title: str, kind: str, folder: str | Path, episodes: list[Episode],
                    season_override: int | None = None) -> list[int]:
        """Împarte episoadele pe sezoane (după S01Exx) și le adaugă."""
        groups: dict[int | None, list[Episode]] = {}
        for e in episodes:
            groups.setdefault(e.season, []).append(e)
        single = len(groups) == 1
        ids = []
        for hint, eps in groups.items():
            if single and season_override:
                season = season_override
            else:
                season = hint or season_override or 1
            ids.append(self.add_season(title, kind, season, str(folder), eps))
        return ids

    def import_root(self, root: str | Path, kind: str = "anime") -> int:
        """Parcurge un folder cu mai multe seriale/sezoane și le adaugă pe toate."""
        count = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            if not any(Path(f).suffix.lower() in VIDEO_EXT for f in filenames):
                continue
            eps = scan_folder(dirpath)
            if not eps:
                continue
            title, season = guess_title_season(dirpath)
            title = title or Path(dirpath).name
            count += len(self.add_scanned(title, kind, dirpath, eps, season))
        return count

    def add_movies(self, folder: str | Path) -> int:
        n = 0
        for f in list_videos(Path(folder)):
            name = clean_movie_name(f.stem)
            self.add_season(name, "film", 1, str(folder), [Episode(f, 1, "", None)])
            n += 1
        return n

    # ---------- metadate ----------
    def title(self, title_id: int):
        return self.conn.execute("SELECT * FROM titles WHERE id=?", (title_id,)).fetchone()

    def titles_needing_meta(self):
        return self.conn.execute(
            "SELECT id, name, kind, search_name FROM titles WHERE meta_status=0 ORDER BY name"
        ).fetchall()

    def set_meta(self, title_id: int, description: str = "", year=None, score=None,
                 genres: str = "", poster: str | None = None, status: int = 1,
                 search_name: str | None = None):
        with self.conn:
            self.conn.execute(
                "UPDATE titles SET description=?, year=?, score=?, genres=?, meta_status=?,"
                " poster=COALESCE(?, poster), search_name=COALESCE(?, search_name) WHERE id=?",
                (description, year, score, genres, status, poster, search_name, title_id),
            )

    def set_meta_status(self, title_id: int, status: int):
        with self.conn:
            self.conn.execute("UPDATE titles SET meta_status=? WHERE id=?", (status, title_id))

    def set_search_name(self, title_id: int, query: str | None):
        """Nume personalizat pentru căutarea metadatelor; resetează starea ca să se caute din nou."""
        with self.conn:
            self.conn.execute("UPDATE titles SET search_name=?, meta_status=0 WHERE id=?",
                              (query or None, title_id))

    def set_poster(self, title_id: int, filename: str | None):
        with self.conn:
            self.conn.execute("UPDATE titles SET poster=? WHERE id=?", (filename, title_id))

    # ---------- ștergere ----------
    def delete_title(self, title_id: int):
        with self.conn:
            self.conn.execute("DELETE FROM titles WHERE id=?", (title_id,))

    def delete_season(self, season_id: int):
        with self.conn:
            row = self.conn.execute("SELECT title_id FROM seasons WHERE id=?", (season_id,)).fetchone()
            self.conn.execute("DELETE FROM seasons WHERE id=?", (season_id,))
            if row and not self.conn.execute(
                "SELECT 1 FROM seasons WHERE title_id=?", (row["title_id"],)
            ).fetchone():
                self.conn.execute("DELETE FROM titles WHERE id=?", (row["title_id"],))

    # ---------- interogări ----------
    def titles(self):
        return self.conn.execute(
            """SELECT t.id, t.name, t.kind, t.poster, t.meta_status,
                      COUNT(e.id) AS total, COALESCE(SUM(e.watched),0) AS watched
               FROM titles t
               LEFT JOIN seasons s ON s.title_id=t.id
               LEFT JOIN episodes e ON e.season_id=s.id
               GROUP BY t.id ORDER BY t.name COLLATE NOCASE"""
        ).fetchall()

    def seasons(self, title_id: int):
        return self.conn.execute(
            """SELECT s.id, s.number, s.folder,
                      COUNT(e.id) AS total, COALESCE(SUM(e.watched),0) AS watched
               FROM seasons s LEFT JOIN episodes e ON e.season_id=s.id
               WHERE s.title_id=? GROUP BY s.id ORDER BY s.number""",
            (title_id,),
        ).fetchall()

    def season(self, season_id: int):
        return self.conn.execute(
            """SELECT s.id, s.number, s.folder, t.id AS title_id, t.name AS title, t.kind,
                      t.poster, t.description, t.year, t.score, t.genres, t.meta_status
               FROM seasons s JOIN titles t ON t.id=s.title_id WHERE s.id=?""",
            (season_id,),
        ).fetchone()

    def episodes(self, season_id: int):
        return self.conn.execute(
            "SELECT * FROM episodes WHERE season_id=? ORDER BY number, id", (season_id,)
        ).fetchall()

    def episode(self, ep_id: int):
        return self.conn.execute(
            """SELECT e.*, s.number AS season_number, s.title_id, t.name AS title, t.kind, t.poster
               FROM episodes e JOIN seasons s ON s.id=e.season_id
               JOIN titles t ON t.id=s.title_id WHERE e.id=?""",
            (ep_id,),
        ).fetchone()

    def title_episodes(self, title_id: int):
        return self.conn.execute(
            """SELECT e.*, s.number AS season_number FROM episodes e
               JOIN seasons s ON s.id=e.season_id WHERE s.title_id=?
               ORDER BY s.number, e.number, e.id""",
            (title_id,),
        ).fetchall()

    def neighbor(self, ep_id: int, step: int = 1):
        ep = self.episode(ep_id)
        if not ep:
            return None
        eps = self.title_episodes(ep["title_id"])
        ids = [e["id"] for e in eps]
        i = ids.index(ep_id) + step
        return eps[i] if 0 <= i < len(eps) else None

    def next_unwatched(self, season_id: int):
        """Episodul de continuat în sezon: cel început, altfel primul nevăzut."""
        eps = self.episodes(season_id)
        started = [e for e in eps if not e["watched"] and e["position_ms"] > RESUME_MIN_MS]
        if started:
            return max(started, key=lambda e: e["last_played"] or "")
        for e in eps:
            if not e["watched"]:
                return e
        return None

    def continue_watching(self, limit: int = 12):
        rows = self.conn.execute(
            """SELECT s.title_id, MAX(e.last_played) AS lp FROM episodes e
               JOIN seasons s ON s.id=e.season_id WHERE e.last_played IS NOT NULL
               GROUP BY s.title_id ORDER BY lp DESC"""
        ).fetchall()
        out = []
        for r in rows:
            eps = self.title_episodes(r["title_id"])
            last_i = max(range(len(eps)), key=lambda i: eps[i]["last_played"] or "")
            last = eps[last_i]
            target, resume = None, False
            if not last["watched"] and last["position_ms"] > RESUME_MIN_MS:
                target, resume = last, True
            else:
                target = next((e for e in eps[last_i + 1:] if not e["watched"]), None) \
                    or next((e for e in eps if not e["watched"]), None)
            if target is None:
                continue  # titlu terminat
            info = self.episode(target["id"])
            out.append({"episode": info, "resume": resume})
            if len(out) >= limit:
                break
        return out

    # ---------- progres ----------
    def set_progress(self, ep_id: int, pos_ms: int, dur_ms: int) -> bool:
        """Salvează poziția. Întoarce True dacă episodul e (acum) văzut."""
        row = self.conn.execute(
            "SELECT watched FROM episodes WHERE id=?", (ep_id,)
        ).fetchone()
        if not row:
            return False
        was = bool(row["watched"])
        finished = dur_ms > 0 and pos_ms / dur_ms >= WATCHED_RATIO
        if was:
            # reluat un episod văzut: nu atingem poziția, doar data
            with self.conn:
                self.conn.execute(
                    "UPDATE episodes SET duration_ms=?, last_played=? WHERE id=?",
                    (dur_ms, _now(), ep_id),
                )
            return True
        watched = finished
        with self.conn:
            self.conn.execute(
                "UPDATE episodes SET duration_ms=?, position_ms=?, watched=?, last_played=? WHERE id=?",
                (dur_ms, 0 if watched else max(0, pos_ms), int(watched), _now(), ep_id),
            )
        return watched

    def mark_finished(self, ep_id: int):
        with self.conn:
            self.conn.execute(
                "UPDATE episodes SET watched=1, position_ms=0, last_played=? WHERE id=?",
                (_now(), ep_id),
            )

    def set_watched(self, ep_id: int, flag: bool):
        with self.conn:
            if flag:
                self.conn.execute(
                    "UPDATE episodes SET watched=1, position_ms=0, last_played=? WHERE id=?",
                    (_now(), ep_id),
                )
            else:
                self.conn.execute(
                    "UPDATE episodes SET watched=0, position_ms=0 WHERE id=?", (ep_id,)
                )

    def mark_upto(self, season_id: int, number: int):
        """Marchează ca văzute toate episoadele cu numărul <= number."""
        with self.conn:
            self.conn.execute(
                "UPDATE episodes SET watched=1, position_ms=0, "
                "last_played=COALESCE(last_played, ?) WHERE season_id=? AND number<=?",
                (_now(), season_id, number),
            )

    def mark_season(self, season_id: int, flag: bool):
        with self.conn:
            if flag:
                self.conn.execute(
                    "UPDATE episodes SET watched=1, position_ms=0, "
                    "last_played=COALESCE(last_played, ?) WHERE season_id=?",
                    (_now(), season_id),
                )
            else:
                self.conn.execute(
                    "UPDATE episodes SET watched=0, position_ms=0 WHERE season_id=?",
                    (season_id,),
                )
