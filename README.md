# VideoPixel

**EN:** A desktop app (Windows, Python + PySide6 + libvlc) to watch movies, series and anime stored on your PC.
Add a season folder and it tracks which episodes you watched, resumes where you stopped, fetches posters and
descriptions (AniList / TVMaze / Wikipedia, can be turned off), and plays with an embedded VLC engine.
Crunchyroll-orange + pixel-art theme, clean fullscreen, resizable window, Romanian and English UI.
Run from source: `pip install -r requirements.txt` then `python main.py` (needs VLC 64-bit installed).
Build a shareable .exe / installer on Windows with `build_exe.bat`. Licensed under MIT (see `LICENSE`).

**RO:** Aplicație desktop pentru filme, seriale și anime de pe PC — documentația în română e mai jos.

> Not affiliated with Crunchyroll, VideoLAN or any streaming service. "VLC" is a trademark of VideoLAN;
> this project only uses the libvlc library. Posters/descriptions come from AniList, TVMaze and Wikipedia
> and belong to their respective owners. Pixel fonts: Press Start 2P and VT323 (SIL OFL, in `assets/fonts/`).
> Release builds bundle VLC (LGPL/GPL components) — see videolan.org for its license.

---

# VideoPixel — biblioteca mea de filme, seriale și anime (VLC)

Aplicație desktop pentru filme, seriale și anime stocate pe PC. Ține minte ce episod ai văzut
și redă cu VLC (motorul libvlc, integrat în fereastră).

## Program (.exe) de împărțit cu alții
Dublu clic pe **`build_exe.bat`** (Windows). Creează în `dist\`:
- `VideoPixel-Setup.exe` – instalator (scurtături pe Desktop și în Meniul Start, cu iconița V pixel);
- `VideoPixel-portabil.zip` – dezarhivezi oriunde și pornești `VideoPixel.exe`.

VLC este inclus în pachet, deci cine îl primește nu are nevoie să instaleze nimic (nici Python, nici VLC).
Datele (bibliotecă, postere) stau în `%APPDATA%\VideoPixel`; la prima pornire a .exe-ului se
preia automat `library.db` din varianta cu scripturi, dacă există lângă proiect.
Scurtături fără instalator: butonul „Scurtături” din aplicație.
Iconița se regenerează cu `python tools/make_icon.py`.

## Pornire din sursă (Windows)
1. Instalează **VLC 64 de biți** (videolan.org) și **Python 3.9+** (python.org, bifează „Add to PATH”).
2. Dublu clic pe `run.bat` (prima dată instalează singur dependențele).

Manual: `pip install -r requirements.txt` apoi `python main.py`.

## Folosire
- **＋ Adaugă sezon** – alegi folderul; aplicația recunoaște episoadele (`S02E05`, `1x05`, `Episode 05`,
  `Titlu - 05`, `[05]`, altfel ordinea alfabetică) și arată o previzualizare. Poți corecta titlul/sezonul.
- **📁 Adaugă folder cu mai multe** – scanează un folder cu mai multe seriale/sezoane (ex. tot `D:\Anime`).
- **🎬 Adaugă filme** – fiecare fișier video din folder devine un film.
- Dublu clic pe episod = redă (reia de unde ai rămas). Clic pe bifă = văzut/nevăzut.
  Clic dreapta: „văzute până aici”, „de la început”.
- Episodul devine **văzut automat la 90%**; progresul se salvează la 5 secunde.
- Re-adăugarea unui folder (ex. au apărut episoade noi) păstrează progresul.

## Limba
Butonul „Limba: RO/EN” din bara de sus schimbă limba aplicației (repornește singur). Textele sunt în `vlclibrary/i18n.py`.

## Postere și descrieri
La adăugare (și la pornire) aplicația caută automat poster, descriere, an, scor și genuri:
anime → AniList, seriale → TVMaze, filme → Wikipedia (fără chei API, are nevoie de internet).
- Dacă a găsit altceva: clic dreapta pe titlu → „Caută poster și descriere…” și scrii alt nume.
- Poster propriu: clic dreapta pe titlu → „Alege poster din fișier…”.
- Posterele sunt afișate normal. Butonul „Postere pixel” din bara de sus le pixelează (opțional).
Posterele se salvează în `posters/`.

## Player – ecran complet
În ecran complet nu se vede nimic. Miști mouse-ul → apare bara cu timp și butoane,
după ~2,5 secunde fără mișcare dispare. Rotița mouse-ului schimbă volumul (apare un indicator),
clic = pauză, dublu clic = ecran complet.

## Player – scurtături
Space pauză · ←/→ ±10s · Shift+←/→ ±60s · ↑/↓ volum · M mut · F sau F11 ecran complet · Esc ieșire ·
N/P următor/anterior · S sari intro (+85s). Butoane pentru audio, subtitrări (și din fișier), viteză.

Datele sunt în `library.db` (lângă `main.py`, sau în `%APPDATA%\VideoPixel` pentru .exe). Fișierele video nu sunt modificate niciodată.

## Securitate (versiunea 1.1)
- Rețea: doar HTTPS către AniList, TVMaze și Wikipedia; redirecționările către alte domenii sunt blocate;
  răspunsurile sunt limitate ca mărime (JSON 2 MB, imagini 8 MB).
- Imagini: se acceptă doar JPEG/PNG/WebP reale (verificate după conținut, nu după extensie), cu limite de dimensiune.
- Postere: numele din baza de date sunt validate (nu pot ieși din folderul `posters`); posterul ales de tine e verificat.
- Scurtături: scriptul PowerShell e constant, căile se dau prin variabile de mediu (fără injecție prin nume de foldere).
- Text: nume de foldere/titluri/erori nu sunt interpretate ca HTML (etichete, tooltip-uri, ferestre de mesaj).
- Redare: doar fișiere video locale (`media_new_path`), nu URL-uri; VLC-ul inclus are prioritate; nu se încarcă DLL-uri din folderul curent.
- Confidențialitate: butonul „Info online” oprește orice conexiune; atunci titlurile nu pleacă de pe calculator.
- Build: dependențe cu limite de versiune; `build_exe.bat` generează `SHA256SUMS.txt` pentru fișierele de împărțit.
- Programul nu este semnat digital, deci Windows SmartScreen poate avertiza la prima rulare pe alt PC.
  Destinatarul poate compara suma SHA-256 din `SHA256SUMS.txt` cu cea a fișierului primit.

## Teste
`python -m pytest tests` (scanner, baza de date, metadate).

Fonturile pixel (Press Start 2P, VT323) sunt sub licența SIL OFL, în `assets/fonts/`.
