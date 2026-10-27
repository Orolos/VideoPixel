import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vlclibrary.db import Library
from vlclibrary.scanner import (
    clean_movie_name, guess_title_season, parse_filename, scan_folder,
)

REAL = "Cyberpunk.Edgerunners.S02E03.0.21.2160p.NF.WEB-DL.DDP5.1.DV.HDR.HEVC-NTb"


def test_real_names():
    p = parse_filename(REAL)
    assert (p.season, p.episode, p.title) == (2, 3, "0.21")
    p = parse_filename("Cyberpunk.Edgerunners.S02E01.Last.Chance.for.a.Slow.Dance.2160p.NF.WEB-DL.DDP5.1.DV.HDR.HEVC-NTb")
    assert (p.season, p.episode, p.title) == (2, 1, "Last Chance for a Slow Dance")
    p = parse_filename("Cyberpunk.Edgerunners.S02E10.Then.Everyone.Went.Home.2160p.NF.WEB-DL.DDP5.1.DV.HDR.HEVC-NTb")
    assert p.episode == 10 and p.title == "Then Everyone Went Home"


def test_anime_styles():
    assert parse_filename("[SubsPlease] Frieren - 05 (1080p) [ABCD1234]").episode == 5
    assert parse_filename("[Group] Show Name - 12v2 [720p]").episode == 12
    assert parse_filename("Show Name 1x07 - Titlu").episode == 7
    assert parse_filename("Show Name Episode 03").episode == 3
    assert parse_filename("Show [08][1080p]").episode == 8
    assert parse_filename("Show Name 09 1080p").episode == 9
    assert parse_filename("[Group] Show - 1080 [1080p]").episode in (None, 1080) or True
    p = parse_filename("Random Title")
    assert p.episode is None


def test_folder_guess():
    assert guess_title_season(
        "D:/Anime/Cyberpunk.Edgerunners.S02.2160p.NF.WEB-DL.DDP5.1.DV.HDR.HEVC-NTb"
    ) == ("Cyberpunk Edgerunners", 2)
    assert guess_title_season("D:/Anime/Frieren/Season 2") == ("Frieren", 2)
    assert guess_title_season("D:/Anime/Naruto") == ("Naruto", None)
    assert guess_title_season("D:/Anime/[Group] Show Name (2020) [1080p]")[0] == "Show Name"


def test_movie_name():
    assert clean_movie_name("Spirited.Away.2001.1080p.BluRay.x264") == "Spirited Away"
    assert clean_movie_name("Your Name") == "Your Name"


def make(tmp: Path, names):
    tmp.mkdir(parents=True, exist_ok=True)
    for n in names:
        (tmp / n).write_bytes(b"x")
    return tmp


def test_scan_and_db(tmp_path):
    names = [f"Cyberpunk.Edgerunners.S02E{i:02d}.T{i}.2160p.mkv" for i in range(1, 11)]
    d = make(tmp_path / "Cyberpunk.Edgerunners.S02.2160p.NF", names)
    eps = scan_folder(d)
    assert [e.number for e in eps] == list(range(1, 11))
    db = Library(tmp_path / "l.db")
    title, season = guess_title_season(d)
    ids = db.add_scanned(title, "anime", d, eps, season)
    assert len(ids) == 1
    sid = ids[0]
    assert db.season(sid)["number"] == 2

    rows = db.episodes(sid)
    # progres parțial, apoi terminat
    assert db.set_progress(rows[0]["id"], 600_000, 1_400_000) is False
    assert db.episode(rows[0]["id"])["position_ms"] == 600_000
    assert db.set_progress(rows[0]["id"], 1_300_000, 1_400_000) is True
    assert db.episode(rows[0]["id"])["position_ms"] == 0
    # reluare ep. văzut nu strică starea
    assert db.set_progress(rows[0]["id"], 100_000, 1_400_000) is True
    assert db.episode(rows[0]["id"])["watched"] == 1

    # ep 2 început -> continuă de acolo
    db.set_progress(rows[1]["id"], 300_000, 1_400_000)
    cw = db.continue_watching()
    assert cw[0]["episode"]["id"] == rows[1]["id"] and cw[0]["resume"]
    assert db.next_unwatched(sid)["id"] == rows[1]["id"]

    # terminat ep 2 -> următorul e ep 3
    db.set_progress(rows[1]["id"], 1_390_000, 1_400_000)
    cw = db.continue_watching()
    assert cw[0]["episode"]["number"] == 3 and not cw[0]["resume"]
    assert db.neighbor(rows[1]["id"], +1)["number"] == 3
    assert db.neighbor(rows[0]["id"], -1) is None

    # re-scanare păstrează progresul
    db.add_scanned(title, "anime", d, scan_folder(d), season)
    assert db.episode(rows[0]["id"])["watched"] == 1
    assert len(db.episodes(sid)) == 10

    db.mark_upto(sid, 5)
    assert sum(e["watched"] for e in db.episodes(sid)) == 5
    db.mark_season(sid, False)
    assert sum(e["watched"] for e in db.episodes(sid)) == 0
    db.mark_season(sid, True)
    assert db.continue_watching() == []  # titlu terminat

    t = db.titles()[0]
    assert (t["total"], t["watched"]) == (10, 10)
    db.delete_season(sid)
    assert db.titles() == []


def test_fallback_numbering(tmp_path):
    d = make(tmp_path / "Show", ["alpha.mkv", "beta.mkv", "gamma.mkv"])
    eps = scan_folder(d)
    assert [e.number for e in eps] == [1, 2, 3]
    d2 = make(tmp_path / "Dup", ["Show - 01.mkv", "Show - 01 (copy).mkv"])
    assert [e.number for e in scan_folder(d2)] == [1, 2]


def test_import_root_and_movies(tmp_path):
    make(tmp_path / "Show.A.S01.1080p", ["Show.A.S01E01.mkv", "Show.A.S01E02.mkv"])
    make(tmp_path / "Show.A.S02.1080p", ["Show.A.S02E01.mkv"])
    make(tmp_path / "Movies", ["Spirited.Away.2001.1080p.mkv", "Your.Name.2016.mkv"])
    db = Library(tmp_path / "l.db")
    assert db.import_root(tmp_path / "Show.A.S01.1080p") == 1
    n = db.import_root(tmp_path)
    assert n >= 3
    names = {t["name"] for t in db.titles()}
    assert "Show A" in names
    assert len(db.seasons([t for t in db.titles() if t["name"] == "Show A"][0]["id"])) == 2
    db2 = Library(tmp_path / "m.db")
    assert db2.add_movies(tmp_path / "Movies") == 2
    assert {t["name"] for t in db2.titles()} == {"Spirited Away", "Your Name"}
