"""
app_config.py  —  Constantes, données métier, détection plateforme.
Ne contient aucun import tkinter.
"""

import subprocess
import sys

# ── Plateforme ────────────────────────────────────────────────
IS_WINDOWS = sys.platform.startswith("win")

# Flag subprocess : empêche la fenêtre console noire sous Windows
NO_WINDOW = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0

# ── Modèles Whisper ───────────────────────────────────────────
MODELS: dict[str, str] = {
    "Base   — rapide  (~74 M)"    : "base",
    "Moyen  — équilibré (~244 M)" : "medium",
    "Large  — traduction  (~1.5 G)"   : "large-v3",
}

# ── Langues (traduction argostranslate + dictaphone) ─────────
# Triées par ordre alphabétique du nom français.
LANG_NAMES: dict[str, str] = {
    "de":"Allemand",  "en":"Anglais",  "ar":"Arabe",    "zh":"Chinois",
    "ko":"Coréen",    "cs":"Tchèque",  "es":"Espagnol", "fi":"Finnois",
    "fr":"Français",  "el":"Grec",     "he":"Hébreu",   "hi":"Hindi",
    "it":"Italien",   "ja":"Japonais", "fa":"Persan",
    "pl":"Polonais",  "pt":"Portugais","ro":"Roumain",  "ru":"Russe",
    "sv":"Suédois",   "tr":"Turc",
}

# Dédupliqué et trié par nom
_sorted = sorted(LANG_NAMES.items(), key=lambda x: x[1])
LANG_NAMES = dict(_sorted)

# Toutes les langues triées (traduction + dictaphone)
ALL_LANGUAGES: list[str] = list(LANG_NAMES.keys())

# Langues cibles pour la traduction argostranslate (sans doublons)
# = toutes les langues (en inclus pour retraduit vers anglais)
TARGET_LANGUAGES: list[str] = ALL_LANGUAGES

# Correspondance ISO 639-1 → 639-2 pour métadonnées MKV
ISO_639_2: dict[str, str] = {
    "fr":"fre","en":"eng","de":"ger","es":"spa","it":"ita",
    "pt":"por","ru":"rus","zh":"chi","ja":"jpn","ko":"kor",
    "ar":"ara","pl":"pol","nl":"dut","sv":"swe","tr":"tur",
    "ro":"rum","cs":"cze","he":"heb","fi":"fin","el":"ell",
    "hi":"hin","fa":"per",
}

def lang_label(code: str) -> str:
    """Retourne 'fr  Français' pour un menu déroulant."""
    return f"{code}  {LANG_NAMES.get(code, code)}"

def lang_code(label_or_code: str) -> str:
    """Extrait le code court depuis 'fr  Français' ou 'fr'."""
    return label_or_code.strip().split()[0]

# ── Langues source pour la transcription whisper ──────────────
AUTO_LANG = "auto"          # auto-détection whisper (-l omis / -l auto)
NO_TRANSLATION = "none"     # transcription seule, pas d'étape argos
SOURCE_LANGUAGES: list[str] = [AUTO_LANG] + ALL_LANGUAGES

# ── Préférences utilisateur (settings.json à la racine) ──────
import json as _json
import os as _os

def _settings_path(root_dir: str) -> str:
    return _os.path.join(root_dir, "settings.json")

def load_settings(root_dir: str) -> dict:
    """Charge settings.json (dict vide si absent/corrompu)."""
    try:
        with open(_settings_path(root_dir), "r", encoding="utf-8") as f:
            data = _json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_settings(root_dir: str, **values) -> None:
    """Fusionne et persiste des clés dans settings.json (best-effort)."""
    data = load_settings(root_dir)
    data.update(values)
    try:
        with open(_settings_path(root_dir), "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
