"""
ytdlp_probe.py  —  Analyse d'une URL avec yt-dlp et finalisation du téléchargement.

Module volontairement sans Tk : testable seul.

  run_probe()          interroge `yt-dlp -J` et renvoie un ProbeResult :
                       sous-titres manuels, sous-titres automatiques,
                       langues audio disponibles, langue audio par défaut.
  finalize_download()  après téléchargement : écarte les SRT vides et
                       rétablit les étiquettes de langue des pistes audio
                       fusionnées (yt-dlp les laisse à « und »).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field

# Sélection de formats par défaut — À GARDER IDENTIQUE à download_url.sh /
# download_url.bat. Elle sert ici uniquement à demander à yt-dlp quelle piste
# audio il retiendrait spontanément (requested_formats), pour l'afficher
# comme « par défaut » : si les deux dérivent, seul ce repère est faussé.
DEFAULT_FORMAT = ("bv*[ext=mp4][vcodec^=avc1]+ba[ext=m4a]"
                  "/bv*+ba/best[ext=mp4]/best")
DEFAULT_SORT = "vcodec:h264,lang,quality,res,fps,hdr:12,acodec:aac"

# Codes de langue acceptés : ils sont insérés dans des sélecteurs yt-dlp et
# transmis aux scripts shell/batch — on refuse tout caractère inattendu.
LANG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,19}$")

# Pistes de « sous-titres » qui n'en sont pas (direct YouTube).
_IGNORED_SUBS = {"live_chat", "rechat"}

# ISO 639-1 → ISO 639-2/T (3 lettres), le jeu de codes attendu dans les
# métadonnées mp4. (La table ISO_639_2 d'app_config utilise les codes
# bibliographiques — fre, ger… — destinés à Matroska.) « iw » et « in » sont
# les anciens codes hébreu/indonésien que YouTube utilise encore.
_ISO_T = {
    "aa": "aar", "ab": "abk", "af": "afr", "am": "amh", "ar": "ara",
    "az": "aze", "be": "bel", "bg": "bul", "bn": "ben", "bs": "bos",
    "ca": "cat", "cs": "ces", "cy": "cym", "da": "dan", "de": "deu",
    "el": "ell", "en": "eng", "es": "spa", "et": "est", "eu": "eus",
    "fa": "fas", "fi": "fin", "fr": "fra", "ga": "gle", "gl": "glg",
    "gu": "guj", "he": "heb", "iw": "heb", "hi": "hin", "hr": "hrv",
    "hu": "hun", "hy": "hye", "id": "ind", "in": "ind", "is": "isl",
    "it": "ita", "ja": "jpn", "ka": "kat", "kk": "kaz", "km": "khm",
    "kn": "kan", "ko": "kor", "ky": "kir", "lo": "lao", "lt": "lit",
    "lv": "lav", "mk": "mkd", "ml": "mal", "mn": "mon", "mr": "mar",
    "ms": "msa", "my": "mya", "nb": "nob", "ne": "nep", "nl": "nld",
    "no": "nor", "pa": "pan", "pl": "pol", "pt": "por", "ro": "ron",
    "ru": "rus", "si": "sin", "sk": "slk", "sl": "slv", "sq": "sqi",
    "sr": "srp", "sv": "swe", "sw": "swa", "ta": "tam", "te": "tel",
    "th": "tha", "tl": "tgl", "tr": "tur", "uk": "ukr", "ur": "urd",
    "uz": "uzb", "vi": "vie", "zh": "zho", "zu": "zul",
}


class ProbeError(Exception):
    """L'analyse a échoué (réseau, vidéo indisponible, connexion exigée…)."""


@dataclass
class ProbeResult:
    title: str = ""
    # [(code, nom ou "")] — le nom vient de yt-dlp quand il le fournit
    subs: list[tuple[str, str]] = field(default_factory=list)
    auto: list[tuple[str, str]] = field(default_factory=list)
    # Langues audio distinctes, la langue par défaut en tête
    audio: list[str] = field(default_factory=list)
    default_audio: str | None = None


# ── Analyse ─────────────────────────────────────────────────────────────────

def is_valid_lang(code: str) -> bool:
    return bool(code) and bool(LANG_RE.match(code))


def iso639_2t(code: str | None) -> str | None:
    """Code yt-dlp (« fr », « pt-BR », « fil »…) → ISO 639-2/T, ou None."""
    if not code:
        return None
    base = code.split("-")[0].split("_")[0].lower()
    if base in _ISO_T:
        return _ISO_T[base]
    if len(base) == 3 and base.isalpha():
        return base          # déjà un code à 3 lettres (fil, haw, yue…)
    return None


def _sub_entries(block) -> list[tuple[str, str]]:
    out = []
    for code, items in (block or {}).items():
        if code in _IGNORED_SUBS or not is_valid_lang(code):
            continue
        name = ""
        if isinstance(items, list) and items and isinstance(items[0], dict):
            name = (items[0].get("name") or "").strip()
        out.append((code, name))
    return out


def _audio_only(f: dict) -> bool:
    # acodec peut valoir None (inconnu) — comme chez Arte : seul « none »
    # exclut. Les storyboards ont vcodec et acodec à « none ».
    return f.get("vcodec") == "none" and f.get("acodec") != "none"


def parse_probe(data: dict) -> ProbeResult:
    """Extrait d'un JSON `yt-dlp -J` ce qui intéresse l'interface."""
    if not isinstance(data, dict):
        raise ProbeError("réponse inattendue")
    # Playlist : on n'analyse pas — le téléchargement garde son comportement.
    if data.get("_type") == "playlist":
        return ProbeResult(title=data.get("title") or "")

    res = ProbeResult(title=data.get("title") or "")
    res.subs = _sub_entries(data.get("subtitles"))
    res.auto = _sub_entries(data.get("automatic_captions"))

    # Langue audio retenue par défaut, d'après la sélection effectivement
    # calculée par yt-dlp (requested_formats).
    default = None
    for f in data.get("requested_formats") or []:
        if _audio_only(f) and f.get("language"):
            default = f["language"]
            break
    if default is None and not data.get("requested_formats"):
        default = data.get("language")

    seen: list[str] = []
    for f in data.get("formats") or []:
        lang = f.get("language")
        if _audio_only(f) and lang and is_valid_lang(lang) and lang not in seen:
            seen.append(lang)

    if default and is_valid_lang(default):
        if default in seen:
            seen.remove(default)
        seen.insert(0, default)
    res.audio = seen
    res.default_audio = seen[0] if seen else None
    return res


def probe_cmd(ytdlp: str, url: str) -> list[str]:
    return [ytdlp, "-J", "--no-playlist", "--no-warnings",
            "-f", DEFAULT_FORMAT, "-S", DEFAULT_SORT, url]


def run_probe(ytdlp: str, url: str, creationflags: int = 0,
              timeout: int = 75) -> ProbeResult:
    """Lance `yt-dlp -J` et analyse la réponse. Lève ProbeError en cas d'échec."""
    try:
        proc = subprocess.run(
            probe_cmd(ytdlp, url),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            creationflags=creationflags, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ProbeError("délai dépassé")
    except OSError as e:
        raise ProbeError(str(e))

    if proc.returncode != 0 or not proc.stdout.strip():
        lines = [l for l in (proc.stderr or "").splitlines() if l.strip()]
        err = next((l for l in reversed(lines) if "ERROR" in l),
                   lines[-1] if lines else f"code {proc.returncode}")
        raise ProbeError(err.strip())
    try:
        return parse_probe(json.loads(proc.stdout))
    except json.JSONDecodeError as e:
        raise ProbeError(f"JSON invalide ({e})")


# ── Finalisation ────────────────────────────────────────────────────────────

def _count_audio(ffprobe: str, path: str, creationflags: int) -> int:
    r = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=creationflags, timeout=30)
    return len([l for l in r.stdout.splitlines() if l.strip()])


def finalize_download(outfile: str, audio_langs: list[str],
                      ffmpeg: str, ffprobe: str,
                      creationflags: int = 0) -> list[tuple]:
    """
    Après téléchargement de `outfile` :
      1. supprime les sous-titres .srt vides à côté de la vidéo (une piste
         « forced » sans réplique est fréquente, et un SRT vide fait échouer
         tout mux ultérieur) ;
      2. si plusieurs pistes audio ont été fusionnées, rétablit leur langue
         (yt-dlp les laisse à « und »), sans ré-encodage ;
      3. liste les sous-titres conservés.

    Ne lève jamais : renvoie des événements (type, valeur…) que l'appelant
    traduit en messages :
      ("empty_srt", nom)   ("subs", [noms])   ("audio_tagged", "fra, deu")
      ("audio_tag_failed", raison)
    """
    events: list[tuple] = []
    folder = os.path.dirname(os.path.abspath(outfile))
    stem = os.path.splitext(os.path.basename(outfile))[0]

    # 1 — sous-titres à côté de la vidéo : « <stem>.<lang>.srt »
    kept = []
    try:
        for name in sorted(os.listdir(folder)):
            if not (name.startswith(stem + ".") and name.lower().endswith(".srt")):
                continue
            p = os.path.join(folder, name)
            if os.path.getsize(p) == 0:
                os.remove(p)
                events.append(("empty_srt", name))
            else:
                kept.append(name)
    except OSError as e:
        events.append(("audio_tag_failed", f"sous-titres : {e}"))
    if kept:
        events.append(("subs", kept))

    # 2 — étiquettes de langue des pistes audio
    if len(audio_langs) >= 2 and os.path.isfile(outfile):
        tmp = os.path.join(folder, stem + ".__tag__" + os.path.splitext(outfile)[1])
        try:
            n = _count_audio(ffprobe, outfile, creationflags)
            if n != len(audio_langs):
                events.append((
                    "audio_tag_failed",
                    f"{n} piste(s) audio présente(s) pour "
                    f"{len(audio_langs)} demandée(s)"))
            else:
                codes = [iso639_2t(l) for l in audio_langs]
                cmd = [ffmpeg, "-v", "error", "-y", "-i", outfile,
                       "-map", "0", "-c", "copy"]
                for i, code in enumerate(codes):
                    if code:
                        cmd += [f"-metadata:s:a:{i}", f"language={code}"]
                cmd.append(tmp)
                r = subprocess.run(
                    cmd, capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                    creationflags=creationflags, timeout=600)
                if r.returncode != 0:
                    raise OSError((r.stderr or "").strip().splitlines()[-1]
                                  if (r.stderr or "").strip() else
                                  f"ffmpeg code {r.returncode}")
                os.replace(tmp, outfile)
                events.append(("audio_tagged",
                               ", ".join(c or "und" for c in codes)))
        except (OSError, subprocess.SubprocessError) as e:
            events.append(("audio_tag_failed", str(e)))
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    return events
