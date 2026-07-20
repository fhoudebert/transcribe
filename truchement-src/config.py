"""
config.py — Configuration statique
====================================
• Paires de langues supportées (PAIRS, MAPPING)
• Noms d'affichage des codes ISO (LANG_NAMES)
• Design tokens couleurs et polices (C, F)
• Utilitaires de locale (lang_code, detect_locale_lang)
"""

from __future__ import annotations

import locale

# ═══════════════════════════════════════════════════════════════════════════════
# PAIRES DE LANGUES
# ═══════════════════════════════════════════════════════════════════════════════

PAIRS: list[str] = [
    "tr_en", "sv_en", "es_en", "ru_en", "ro_en",
    "pt_en", "es_pt", "fa_en", "pt_es", "ko_en",
    "ja_en", "it_en", "hi_en", "he_en", "de_en",
    "fr_en", "fi_en", "en_tr", "en_sv", "en_es",
    "en_ru", "en_ro", "en_pt", "en_pl", "en_fa",
    "en_ko", "en_ja", "en_it", "en_hi", "en_he",
    "en_el", "en_de", "en_zh", "en_ar", "nl_en",
    "zh_en", "ar_en", "en_fi", "en_fr",
    # paires étendues
    "en_cs", "en_nl", "en_hu", "en_sk", "en_th", "en_id", "en_vi",
    "cs_en", "el_en",
]

MAPPING: dict[str, list[str]] = {}
for _p in PAIRS:
    _s, _t = _p.split("_")
    MAPPING.setdefault(_s, []).append(_t)


# ═══════════════════════════════════════════════════════════════════════════════
# NOMS DES LANGUES
# ═══════════════════════════════════════════════════════════════════════════════

LANG_NAMES: dict[str, str] = {
    "ar": "العربية (Arabic)",
    "cs": "Čeština (Czech)",
    "de": "Deutsch (German)",
    "el": "Ελληνικά (Greek)",
    "en": "English",
    "es": "Español (Spanish)",
    "fa": "فارسی (Persian)",
    "fi": "Suomi (Finnish)",
    "fr": "Français (French)",
    "he": "עברית (Hebrew)",
    "hi": "हिन्दी (Hindi)",
    "hu": "Magyar (Hungarian)",
    "id": "Bahasa Indonesia (Indonesian)",
    "it": "Italiano (Italian)",
    "ja": "日本語 (Japanese)",
    "ko": "한국어 (Korean)",
    "nl": "Nederlands (Dutch)",
    "pl": "Polski (Polish)",
    "pt": "Português (Portuguese)",
    "ro": "Română (Romanian)",
    "ru": "Русский (Russian)",
    "sk": "Slovenčina (Slovak)",
    "sv": "Svenska (Swedish)",
    "th": "ภาษาไทย (Thai)",
    "tr": "Türkçe (Turkish)",
    "vi": "Tiếng Việt (Vietnamese)",
    "zh": "中文 (Chinese)",
}


# ═══════════════════════════════════════════════════════════════════════════════
# DESIGN TOKENS
# ═══════════════════════════════════════════════════════════════════════════════

C: dict[str, str] = {
    "bg":     "#1E1E2E",
    "panel":  "#252538",
    "card":   "#2F2F4A",
    "accent": "#7C6AF7",
    "acc_hi": "#9B8CF9",
    "teal":   "#4ECDC4",
    "text":   "#E8E8F0",
    "muted":  "#8888AA",
    "border": "#44446A",
    "swap":   "#363654",
    "gold":   "#F6C90E",
}

F: dict[str, tuple] = {
    "title":    ("Segoe UI", 15, "bold"),
    "subtitle": ("Segoe UI", 9),
    "head":     ("Segoe UI", 10, "bold"),
    "body":     ("Segoe UI", 11),
    "small":    ("Segoe UI", 9),
    "btn":      ("Segoe UI", 10, "bold"),
    "mono":     ("Consolas", 10),
}


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════════

def lang_code(display: str) -> str:
    """Convertit un nom affiché (ex. 'Français (French)') en code ISO-639-1."""
    for code, name in LANG_NAMES.items():
        if name == display:
            return code
    return display[:2].lower()


def detect_locale_lang() -> str:
    """
    Retourne le code ISO-639-1 de la langue système (ex. 'fr', 'de', 'en').
    Utilisé pour pré-sélectionner la langue source et le dictionnaire.
    """
    try:
        lc = locale.getdefaultlocale()[0] or ""
        return lc[:2].lower() if lc else "en"
    except Exception:
        return "en"
