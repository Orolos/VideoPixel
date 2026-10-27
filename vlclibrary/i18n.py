"""Traduceri RO/EN. Textele din cod sunt în română (cheia); `tr()` le dă în limba aleasă."""
from __future__ import annotations

_lang = "ro"
LANGUAGES = ("ro", "en")


def set_language(code: str) -> None:
    global _lang
    _lang = code if code in LANGUAGES else "ro"


def language() -> str:
    return _lang


def tr(text: str) -> str:
    return EN.get(text, text) if _lang == "en" else text


EN = {
    # ---- tipuri / general
    "Anime": "Anime", "Serial": "Series", "Film": "Movie", "Sezon": "Season", "Filme": "Movies",
    "Acasă": "Home", "Gata.": "Ready.", "Gata": "Done", "Gata!": "Done!",
    "Episodul {n}": "Episode {n}",
    # ---- dialog adaugă sezon
    "Adaugă sezon": "Add season",
    "Folderul cu episoadele sezonului…": "Folder with the season's episodes…",
    "ALEGE…": "BROWSE…", "Folder:": "Folder:", "Titlu:": "Title:", "Tip:": "Type:", "Sezon nr.:": "Season no.:",
    "EP.": "EP.", "SEZON": "SEASON", "TITLU / FIȘIER": "TITLE / FILE", "ADAUGĂ": "ADD", "ANULEAZĂ": "CANCEL",
    "Alege folderul sezonului": "Choose the season folder",
    "{n} episoade găsite.": "{n} episodes found.",
    "Folderul conține mai multe sezoane; vor fi create separat.":
        "The folder contains several seasons; they will be created separately.",
    "Niciun fișier video găsit în acest folder.": "No video files found in this folder.",
    "Titlu lipsă": "Missing title", "Scrie titlul serialului / anime-ului.": "Enter the series / anime title.",
    # ---- bara de unelte
    "Unelte": "Tools",
    "Adaugă un sezon dintr-un folder (Ctrl+N)": "Add a season from a folder (Ctrl+N)",
    "Folder multiplu": "Multiple folder",
    "Scanează un folder care conține mai multe seriale/sezoane": "Scan a folder that contains several series/seasons",
    "Fiecare fișier video din folder devine un film": "Every video file in the folder becomes a movie",
    "Scoate": "Remove",
    "Scoate selecția din bibliotecă (fișierele rămân pe disc)": "Remove the selection from the library (files stay on disk)",
    "Reîncarcă": "Reload",
    "Reîmprospătează și caută din nou postere lipsă": "Refresh and search again for missing posters",
    "Postere pixel": "Pixel posters", "Afișează posterele în stil pixel art": "Show posters in pixel-art style",
    "Info online": "Online info",
    "Caută automat postere și descrieri pe internet.\nOprit: nimic nu pleacă de pe calculator (titlurile nu sunt trimise nicăieri).":
        "Automatically look up posters and descriptions online.\nOff: nothing leaves this computer (titles are not sent anywhere).",
    "Scurtături": "Shortcuts",
    "Creează scurtături VideoPixel pe Desktop și în Meniul Start": "Create VideoPixel shortcuts on the Desktop and in the Start Menu",
    "Gata! Ai scurtături VideoPixel pe Desktop și în Meniul Start.": "Done! VideoPixel shortcuts are on your Desktop and in the Start Menu.",
    "Nu am putut crea scurtăturile.": "Could not create the shortcuts.",
    "Vrei scurtături VideoPixel (cu iconița V) pe Desktop și în Meniul Start?":
        "Do you want VideoPixel shortcuts (with the V icon) on the Desktop and in the Start Menu?",
    "Limba": "Language",
    "Bară laterală": "Sidebar",
    "Arată / ascunde bara laterală (Ctrl+B)": "Show / hide the sidebar (Ctrl+B)",
    "Schimbă limba aplicației (RO / EN)": "Change the application language (RO / EN)",
    "Limba se schimbă după repornire. Repornești VideoPixel acum?": "The language changes after a restart. Restart VideoPixel now?",
    # ---- acasă
    "CONTINUĂ VIZIONAREA": "CONTINUE WATCHING",
    "Nimic început încă.\nApasă «Adaugă sezon», alege folderul cu episoade\nși dă dublu clic pe un episod.":
        "Nothing started yet.\nPress “Add season”, choose the folder with episodes\nand double-click an episode.",
    "BIBLIOTECA": "LIBRARY", "nevăzut": "unwatched", "reia filmul": "resume movie", "urmează": "up next",
    "văzute": "watched",
    # ---- pagina sezonului
    "  CAUTĂ INFO": "  FIND INFO",
    "Caută poster și descriere (poți schimba numele căutat)": "Find poster and description (you can change the search name)",
    "  CONTINUĂ": "  CONTINUE", "  TOT: VĂZUT": "  ALL: WATCHED", "TOT: NEVĂZUT": "ALL: UNWATCHED",
    "TITLU": "TITLE", "PROGRES": "PROGRESS",
    "Dublu clic = redă  ·  clic pe prima coloană = văzut/nevăzut  ·  clic dreapta = mai multe":
        "Double-click = play  ·  click the first column = watched/unwatched  ·  right-click = more",
    "Se caută descrierea…": "Looking for the description…",
    "Nu am găsit descrierea. Apasă «Caută info» și încearcă alt nume.":
        "Description not found. Press “Find info” and try another name.",
    "Fără descriere încă. Apasă «Caută info».": "No description yet. Press “Find info”.",
    "VĂZUTE": "WATCHED", "REIA": "RESUME", "CONTINUĂ": "CONTINUE", "SEZON TERMINAT": "SEASON FINISHED",
    "Văzut": "Watched", "fișier lipsă": "file missing",
    # ---- postere / info
    "Caut postere și descrieri…": "Looking up posters and descriptions…",
    "Nu m-am putut conecta la internet: postere indisponibile.": "Could not connect to the internet: posters unavailable.",
    "Caută info": "Find info", "Nume de căutat (în engleză / romaji merge cel mai bine):":
        "Name to search (English / romaji works best):",
    "Alege posterul": "Choose the poster", "Imagini (*.jpg *.jpeg *.png *.webp *.bmp)": "Images (*.jpg *.jpeg *.png *.webp *.bmp)",
    "Poster nepermis": "Poster not allowed",
    "Alege o imagine JPEG, PNG sau WebP validă (maxim 20 MB, cel mult 8000 px).":
        "Choose a valid JPEG, PNG or WebP image (max 20 MB, at most 8000 px).",
    # ---- acțiuni
    "Folder cu mai multe seriale / sezoane": "Folder with several series / seasons",
    "Au fost adăugate/actualizate {n} sezoane.": "{n} seasons were added/updated.",
    "Folder cu filme": "Folder with movies", "Au fost adăugate {n} filme.": "{n} movies were added.",
    "titlul întreg": "the whole title", "sezonul": "the season", "Confirmare": "Confirm",
    "Scoți {what} din bibliotecă?\nFișierele de pe disc nu sunt șterse.":
        "Remove {what} from the library?\nFiles on disk are not deleted.",
    "Caută poster și descriere…": "Find poster and description…", "Alege poster din fișier…": "Choose poster from file…",
    "Scoate din bibliotecă": "Remove from library",
    "Redă": "Play", " (reia)": " (resume)", "Redă de la început": "Play from the beginning",
    "Marchează ca nevăzut": "Mark as unwatched", "Marchează ca văzut": "Mark as watched",
    "Marchează văzute până la ep. {n}": "Mark watched up to ep. {n}",
    "VLC nu a fost găsit": "VLC not found",
    "Nu pot încărca VLC.\n\n• Instalează VLC (64 de biți) de la videolan.org\n• Rulează: pip install python-vlc\n\nDetalii: ":
        "Cannot load VLC.\n\n• Install VLC (64-bit) from videolan.org\n• Run: pip install python-vlc\n\nDetails: ",
    # ---- player
    "Player": "Player",
    "Episodul anterior (P)": "Previous episode (P)", "Pauză / Redare (Space)": "Pause / Play (Space)",
    "Episodul următor (N)": "Next episode (N)", "Înapoi 10 secunde (←)": "Back 10 seconds (←)",
    "Înainte 10 secunde (→)": "Forward 10 seconds (→)", "INTRO +85s": "INTRO +85s",
    "Sari peste intro (S)": "Skip intro (S)", "AUDIO": "AUDIO", "Piste audio": "Audio tracks",
    "SUB": "SUB", "Subtitrări": "Subtitles", "Viteză": "Speed", "Ecran complet (F)": "Fullscreen (F)",
    "Următorul automat": "Auto-next", "VOL": "VOL",
    "Fișier lipsă": "File missing", "Fișierul nu a fost găsit:\n": "File not found:\n",
    "Fișier nepermis": "File not allowed", "Se pot reda doar fișiere video.": "Only video files can be played.",
    "PAUZĂ": "PAUSE", "REDARE": "PLAY", "MUT / SUNET": "MUTE / SOUND", "VOLUM": "VOLUME", "VITEZĂ": "SPEED",
    "(nicio pistă disponibilă)": "(no track available)", "Încarcă subtitrare din fișier…": "Load subtitles from file…",
    "Alege subtitrarea": "Choose the subtitles", "Subtitrări (*.srt *.ass *.ssa *.sub *.vtt);;Toate (*)":
        "Subtitles (*.srt *.ass *.ssa *.sub *.vtt);;All (*)",
    "Eroare": "Error", "Terminat": "Finished",
}
