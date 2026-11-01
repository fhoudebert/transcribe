"""
detection.py — Détection de la langue d'un texte (bouton « Détecter »)
=======================================================================
Identification hors ligne par py3langid (fork maintenu de langid.py :
modèle n-grammes de 4,6 Mio, ~140 langues, numpy seul en dépendance, pur
Python donc identique sous Linux et Windows). Il vit dans le Python portable
de la clé comme argostranslate, et n'est importé qu'au premier clic : le
démarrage de l'application n'en paie rien.

Principe :
  1. Classement sur TOUTES les langues du modèle, puis on retient la
     première du classement qui est une langue source installée (MAPPING).
     Restreindre d'emblée le modèle aux langues installées forcerait une
     réponse même pour un texte dans une langue absente ; à l'inverse, ne
     regarder que le premier rang échouerait sur les voisines (« Я не
     знаю. » sort biélorusse à 38 %, russe juste derrière).
  2. Codes Argos absents de langid : nb (bokmål) → no, pb (portugais du
     Brésil) → pt, zt (chinois traditionnel) → zh ; le chinois est ensuite
     départagé simplifié/traditionnel par l'écriture.
  3. Échantillon : les ~5 000 premiers caractères suffisent largement ;
     pour un fichier (onglet Fichier), texte extrait de .txt/.srt/.html/
     .docx/.pdf sans traduire quoi que ce soit.

Aucune exception ne remonte vers l'UI autrement que sous forme de
DetectionError, au message affichable.
"""

from __future__ import annotations

import html
import os
import re
import threading
import zipfile

SAMPLE_CHARS = 5000
MIN_LETTERS = 3          # en deçà : texte trop court pour conclure
UNSURE_BELOW = 0.50      # probabilité sous laquelle le résultat est signalé incertain
ACCEPT_INSTALLED = 0.10  # une langue installée en 2e/3e rang reste acceptée au-delà

# Codes Argos → codes langid (le reste est identique)
_ARGOS_TO_LANGID = {"nb": "no", "pb": "pt", "zt": "zh"}

# Caractères propres à l'une des deux écritures du chinois (formes courantes)
_TRAD = set("們這說個國會來時對為學與開關還過後點長語東車書見門問間電話讓給聽從現發經動頭樣種實號機氣離歡謝請嗎麼愛買賣陽單應該當業體裡邊")
_SIMP = set("们这说个国会来时对为学与开关还过后点长语东车书见门问间电话让给听从现发经动头样种实号机气离欢谢请吗么爱买卖阳单应该当业体里边")


class DetectionError(Exception):
    """Erreur affichable telle quelle (code, détail)."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}:{detail}" if detail else code)
        self.code = code
        self.detail = detail


# ─── Identifiant py3langid (chargé une fois, ~1,5 s) ──────────────────────────

_ident = None
_ident_lock = threading.Lock()


def _identifier():
    global _ident
    with _ident_lock:
        if _ident is None:
            try:
                from py3langid.langid import LanguageIdentifier, MODEL_FILE
            except ImportError as exc:
                raise DetectionError("NO_MODULE", str(exc)) from exc
            _ident = LanguageIdentifier.from_model_file(MODEL_FILE,
                                                        norm_probs=True)
        return _ident


# ─── Détection ────────────────────────────────────────────────────────────────

def _chinese_variant(text: str, installed: set[str]) -> str:
    """zh (simplifié) ou zt (traditionnel) selon les caractères présents."""
    if "zt" not in installed:
        return "zh"
    if "zh" not in installed:
        return "zt"
    trad = sum(ch in _TRAD for ch in text)
    simp = sum(ch in _SIMP for ch in text)
    return "zt" if trad > simp else "zh"


def detect(text: str, installed: list[str] | set[str]) -> dict:
    """
    Détecte la langue de *text* parmi les langues sources *installed*
    (codes Argos). Retourne un dict :
        code      code Argos retenu, ou None si aucune langue installée ne convient
        prob      probabilité (0-1) de ce code
        top       code langid du premier rang (même s'il n'est pas installé)
        top_prob  sa probabilité
        unsure    True si prob < UNSURE_BELOW
    Lève DetectionError("TOO_SHORT") ou ("NO_MODULE", détail).
    """
    sample = text[:SAMPLE_CHARS]
    if sum(ch.isalpha() for ch in sample) < MIN_LETTERS:
        raise DetectionError("TOO_SHORT")

    installed = set(installed)
    # code langid → codes Argos installés qui lui correspondent
    reverse: dict[str, list[str]] = {}
    for code in installed:
        reverse.setdefault(_ARGOS_TO_LANGID.get(code, code), []).append(code)

    ranking = _identifier().rank(sample)        # [(langid, prob)], décroissant
    top, top_prob = ranking[0]

    for rank_pos, (lid, prob) in enumerate(ranking):
        if lid not in reverse:
            continue
        if rank_pos > 0 and prob < ACCEPT_INSTALLED:
            break
        codes = reverse[lid]
        if lid == "zh":
            code = _chinese_variant(sample, set(codes))
        elif lid == "pt":
            code = "pt" if "pt" in codes else codes[0]
        else:
            code = codes[0]
        return {"code": code, "prob": float(prob), "top": top,
                "top_prob": float(top_prob), "unsure": prob < UNSURE_BELOW}

    return {"code": None, "prob": 0.0, "top": top,
            "top_prob": float(top_prob), "unsure": True}


# ─── Échantillon de fichier (onglet Fichier) ──────────────────────────────────

_SRT_NOISE = re.compile(
    r"^\s*(\d+|\d\d:\d\d:\d\d[,.]\d+\s*-->\s*\d\d:\d\d:\d\d[,.]\d+.*)\s*$",
    re.M)
_TAGS = re.compile(r"<[^>]+>")
_SCRIPT_STYLE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)


def _read_text(path: str, limit: int) -> str:
    with open(path, "rb") as fh:
        raw = fh.read(limit * 4)
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def sample_from_file(path: str, limit: int = SAMPLE_CHARS) -> str:
    """
    Extrait jusqu'à *limit* caractères de texte d'un fichier pris en charge
    par l'onglet Fichier. Lève DetectionError("FILE", détail) si illisible.
    """
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".srt":
            text = _SRT_NOISE.sub("", _read_text(path, limit * 2))
            text = _TAGS.sub("", text)
        elif ext in (".html", ".htm"):
            text = _read_text(path, limit * 4)
            text = _SCRIPT_STYLE.sub(" ", text)
            body = re.search(r"<body\b.*", text, re.S | re.I)
            text = html.unescape(_TAGS.sub(" ", body.group(0) if body else text))
        elif ext == ".docx":
            with zipfile.ZipFile(path) as zf:
                xml = zf.read("word/document.xml").decode("utf-8", "replace")
            xml = re.sub(r"</w:p>", "\n", xml)
            text = html.unescape(_TAGS.sub("", xml))
        elif ext == ".pdf":
            import fitz  # PyMuPDF, dans le Python portable
            parts, total = [], 0
            with fitz.open(path) as doc:
                for page in doc:
                    t = page.get_text()
                    parts.append(t)
                    total += len(t)
                    if total >= limit:
                        break
            text = "\n".join(parts)
        else:                                   # .txt et tout le reste
            text = _read_text(path, limit)
    except DetectionError:
        raise
    except Exception as exc:                    # fichier absent, zip corrompu…
        raise DetectionError("FILE", str(exc)) from exc
    return re.sub(r"\s+", " ", text).strip()[:limit]
