"""
config.py — Configuration des langues et de l'apparence
=========================================================
• Paires de langues : scan des paquets réellement installés (build_mapping)
  avec fermeture par pivot via l'anglais, et repli sur le catalogue statique
  CATALOG_PAIRS si aucun paquet n'est trouvé (mode développement).
• Noms d'affichage des codes ISO (LANG_NAMES)
• Design tokens couleurs et polices (C, F)
• Utilitaires de locale (lang_code, detect_locale_lang)
"""

from __future__ import annotations

import json
import locale
import os

# ═══════════════════════════════════════════════════════════════════════════════
# PAIRES DE LANGUES
# ═══════════════════════════════════════════════════════════════════════════════
#
# STRATÉGIE (voir aussi bootstrap.py) :
#
#   1. bootstrap.py positionne ARGOS_PACKAGES_DIR vers build/argos-data/packages
#      AVANT l'import de ce module (ordre d'import imposé par main.py).
#   2. Chaque paquet argostranslate installé est un dossier contenant un
#      metadata.json avec from_code / to_code : on le lit avec la stdlib,
#      en quelques millisecondes, SANS importer argostranslate (dont l'import
#      coûte plusieurs secondes — il reste différé jusqu'à la 1re traduction,
#      ou au préchauffage en arrière-plan lancé par ui/app.py).
#   3. Les combobox reflètent donc EXACTEMENT ce qui est installé sur la clé :
#      plus de NO_PKG possible sur une paire pourtant proposée par l'UI.
#   4. argostranslate sait composer les paires via l'anglais (fr→es si fr_en
#      et en_es sont installés) : on ajoute cette fermeture par pivot, en
#      mémorisant dans PIVOT_PAIRS les paires indirectes pour que l'UI puisse
#      les signaler (qualité moindre qu'une paire directe).
#
# CATALOG_PAIRS n'est PLUS la source de vérité : c'est le catalogue des paires
# connues du projet, utilisé uniquement en repli quand aucun paquet n'est
# installé (poste de développement, venv système) — l'ancien comportement.

CATALOG_PAIRS: list[str] = [
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

# Alias de compatibilité (anciens imports / scripts).
PAIRS = CATALOG_PAIRS

PIVOT_LANG = "en"


def scan_installed_pairs(packages_dir: str) -> list[tuple[str, str]]:
    """
    Liste les paires (from_code, to_code) des paquets argostranslate
    réellement présents dans *packages_dir*, en lisant les metadata.json.

    Ne lève jamais d'exception ; retourne [] si le dossier est absent,
    vide, ou illisible (l'appelant replie alors sur CATALOG_PAIRS).
    Les paquets de type "sbd" (segmentation de phrases) sont ignorés :
    ce ne sont pas des paires de traduction.
    """
    pairs: list[tuple[str, str]] = []
    try:
        entries = sorted(os.listdir(packages_dir))
    except OSError:
        return pairs
    for name in entries:
        meta_path = os.path.join(packages_dir, name, "metadata.json")
        try:
            with open(meta_path, encoding="utf-8") as fh:
                meta = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("type") == "sbd":
            continue
        src, tgt = meta.get("from_code"), meta.get("to_code")
        if src and tgt and (src, tgt) not in pairs:
            pairs.append((src, tgt))
    return pairs


def _pivot_closure(
    mapping: dict[str, list[str]], pivot: str = PIVOT_LANG
) -> set[tuple[str, str]]:
    """
    Complète *mapping* (modifié en place) avec les paires composables via
    *pivot* : pour tout X ayant X→pivot et tout Y ayant pivot→Y, ajoute
    X→Y si absent. Retourne l'ensemble des paires AJOUTÉES (indirectes),
    pour que l'UI puisse les distinguer des paires directes.
    """
    added: set[tuple[str, str]] = set()
    if pivot not in mapping:
        return added
    sources = [s for s, targets in mapping.items() if pivot in targets]
    for s in sources:
        for t in mapping[pivot]:
            if t == s:
                continue
            if t not in mapping[s]:
                mapping[s].append(t)
                added.add((s, t))
    return added


def build_mapping() -> tuple[dict[str, list[str]], set[tuple[str, str]]]:
    """
    Construit (mapping, paires_pivot) depuis les paquets installés
    (ARGOS_PACKAGES_DIR, positionnée par bootstrap.py), avec repli sur
    CATALOG_PAIRS si aucun paquet n'est trouvé.
    """
    packages_dir = os.environ.get("ARGOS_PACKAGES_DIR", "")
    installed = scan_installed_pairs(packages_dir) if packages_dir else []

    mapping: dict[str, list[str]] = {}
    if installed:
        for src, tgt in installed:
            mapping.setdefault(src, [])
            if tgt not in mapping[src]:
                mapping[src].append(tgt)
    else:
        for p in CATALOG_PAIRS:
            src, tgt = p.split("_")
            mapping.setdefault(src, []).append(tgt)

    pivot_pairs = _pivot_closure(mapping)
    return mapping, pivot_pairs


# MAPPING / PIVOT_PAIRS sont des objets MUTÉS EN PLACE par refresh_mapping()
# (jamais réassignés) : les `from config import MAPPING` des autres modules
# restent ainsi valides après un rafraîchissement.
MAPPING: dict[str, list[str]] = {}
PIVOT_PAIRS: set[tuple[str, str]] = set()


def refresh_mapping() -> None:
    """
    Recalcule MAPPING / PIVOT_PAIRS depuis l'état actuel du dossier de
    paquets. À appeler après toute installation/suppression de paquet
    argostranslate en cours de session (couplé à
    translator.invalidate_language_cache()).
    """
    new_mapping, new_pivots = build_mapping()
    MAPPING.clear()
    MAPPING.update(new_mapping)
    PIVOT_PAIRS.clear()
    PIVOT_PAIRS.update(new_pivots)


refresh_mapping()


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
    """
    Convertit un nom affiché (ex. 'Français (French)') en code ISO-639-1.

    Tolère un suffixe ajouté après le nom (ex. la mention 'via English'
    apposée aux paires pivot par l'UI) : on teste l'égalité exacte puis
    le préfixe. Le repli display[:2] ne vaut que pour les codes bruts
    passés tels quels (jamais fiable pour les noms non latins).
    """
    for code, name in LANG_NAMES.items():
        if display == name or display.startswith(name):
            return code
    return display[:2].lower()


def detect_locale_lang() -> str:
    """
    Retourne le code ISO-639-1 de la langue système (ex. 'fr', 'de', 'en').
    Utilisé pour pré-sélectionner la langue source et le dictionnaire.

    locale.getdefaultlocale() est déprécié (retrait prévu en 3.15) :
    on interroge locale.getlocale() puis les variables d'environnement
    POSIX usuelles.
    """
    try:
        lc = locale.getlocale()[0] or ""
    except Exception:
        lc = ""
    if not lc:
        for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
            val = os.environ.get(var, "")
            if val:
                lc = val
                break
    return lc[:2].lower() if lc else "en"
