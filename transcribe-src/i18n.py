"""
i18n.py  —  Internationalisation de l'interface Transcribe.

API :
    init(base_dir)          appelez en PREMIER dans transcribe.py
    t("clé")                retourne le libellé traduit
    t("clé", var=val)       avec substitution de {var}
    set_locale("en")        change la langue et persiste le choix
    get_locale()            retourne le code actif ("fr", "en"…)
    available_locales()     [(code, label), …]

Fichiers :
    <base_dir>/i18n/fr.json
    <base_dir>/i18n/en.json
    <base_dir>/i18n/.locale   (préférence persistée, 2 caractères)

IMPORTANT : init(base_dir) DOIT être appelé avant tout appel à t().
            transcribe.py le fait avant d'importer main_window.
"""

import json
import os
from pathlib import Path

# ── État global ───────────────────────────────────────────────
_base_dir:     Path | None = None
_i18n_dir:     Path | None = None
_locale_file:  Path | None = None
_active:       str  = "fr"
_strings:      dict = {}       # cache de la locale active
def _detect_system_locale() -> str:
    """
    Détecte la locale UI du système d'exploitation.
    Retourne le code à 2 lettres (ex: "fr", "en", "de").
    Si non reconnu ou si la locale détectée n'a pas de fichier JSON,
    retourne "fr" (langue par défaut de l'application).
    """
    import locale as _locale
    code = None
    try:
        # getlocale() retourne ('fr_FR', 'UTF-8') ou (None, None)
        lang, _ = _locale.getlocale()
        if lang:
            code = lang[:2].lower()   # 'fr_FR' → 'fr'
    except Exception:
        pass

    if not code:
        # Fallback Windows : USERPROFILE ou LANG env var
        import os as _os
        for env in ("LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES"):
            val = _os.environ.get(env, "")
            if val and len(val) >= 2:
                code = val[:2].lower()
                break

    return code or "fr"   # défaut si rien trouvé


_DEFAULT       = "fr"   # défaut absolu si le JSON de la locale système manque
_initialized   = False


# ── Initialisation ────────────────────────────────────────────

def init(base_dir: str | Path) -> None:
    """
    Initialise i18n depuis base_dir.
    Doit être appelé UNE FOIS, avant tout import de module UI.
    """
    global _base_dir, _i18n_dir, _locale_file
    global _active, _strings, _initialized

    _base_dir    = Path(base_dir).resolve()
    _i18n_dir    = _base_dir / "i18n"
    _locale_file = _i18n_dir / ".locale"

    # Priorité de résolution de la langue :
    # 1. Préférence persistée dans .locale  (choix explicite de l'utilisateur)
    # 2. Locale du système (locale.getdefaultlocale / LANG)
    # 3. Langue par défaut (_DEFAULT = "fr")

    lang = None

    # 1. Préférence persistée
    if _locale_file.exists():
        try:
            saved = _locale_file.read_text(encoding="utf-8").strip()
            if saved:
                lang = saved
        except Exception:
            pass

    # 2. Locale système (si pas de préférence sauvegardée)
    if not lang:
        lang = _detect_system_locale()

    # 3. Fallback
    if not lang:
        lang = _DEFAULT

    _strings     = _load_json(lang) or _load_json(_DEFAULT) or {}
    _active      = lang if _strings else _DEFAULT
    _initialized = True


def _detect_system_locale() -> str | None:
    """
    Détecte la langue du système et retourne un code i18n disponible.
    Essaie dans l'ordre :
      - locale.getlocale()         (Python standard)
      - variable d'env LANG/LANGUAGE (Linux/Mac)
      - GetUserDefaultUILanguage() via ctypes (Windows)
    Ne retourne que des codes disponibles dans i18n/*.json.
    """
    import locale as _locale

    candidates = []

    # Python locale
    try:
        loc = _locale.getlocale()[0]   # ex: "fr_FR", "en_US", "de_DE"
        if loc:
            candidates.append(loc)
    except Exception:
        pass

    # Variables d'environnement (Linux/Mac)
    for var in ("LANGUAGE", "LANG", "LC_ALL", "LC_MESSAGES"):
        v = os.environ.get(var, "")
        if v and v != "C" and v != "POSIX":
            candidates.append(v)

    # Windows via ctypes
    try:
        import ctypes
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        # Convertir LANGID en code langue ISO 639-1
        primary = lang_id & 0xFF
        _WIN_LANG = {
            0x0c: "fr", 0x09: "en", 0x07: "de", 0x0a: "es",
            0x10: "it", 0x11: "ja", 0x12: "ko", 0x19: "ru",
            0x16: "pt", 0x15: "pl", 0x01: "ar", 0x08: "el",
            0x0b: "fi", 0x1d: "sv", 0x18: "ro", 0x1a: "cs",
            0x0d: "he", 0x29: "fa", 0x39: "hi", 0x04: "zh",
        }
        if primary in _WIN_LANG:
            candidates.append(_WIN_LANG[primary])
    except Exception:
        pass

    # Résoudre le premier candidat disponible dans i18n/
    if _i18n_dir is None:
        return None
    available = {p.stem for p in _i18n_dir.glob("*.json")}
    for c in candidates:
        # Normaliser : "fr_FR.UTF-8" → "fr", "en_US" → "en"
        code = c.split("_")[0].split(".")[0].split("@")[0].lower()
        if len(code) == 2 and code in available:
            return code

    return None


def _require_init() -> None:
    """Lève une erreur claire si init() n'a pas été appelé."""
    if not _initialized:
        raise RuntimeError(
            "i18n.init(base_dir) doit être appelé avant d'utiliser t().\n"
            "Assurez-vous que transcribe.py appelle i18n.init() avant\n"
            "d'importer main_window."
        )


# ── Chargement JSON ───────────────────────────────────────────

def _load_json(lang: str) -> dict:
    if _i18n_dir is None:
        return {}
    path = _i18n_dir / f"{lang}.json"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data.pop("_meta", None)
        return data
    except Exception:
        return {}


# ── API publique ──────────────────────────────────────────────

def t(key: str, **kwargs) -> str:
    """
    Retourne le libellé traduit pour key dans la locale active.
    Substitue les placeholders : t("hello", name="Alice").
    Si la clé est absente : retourne "[clé]" (visible, facile à repérer).
    Si init() n'a pas été appelé : retourne "[!init:clé]".
    """
    if not _initialized:
        return f"[!init:{key}]"

    val = _strings.get(key)
    if val is None:
        return f"[{key}]"

    if kwargs:
        try:
            return val.format(**kwargs)
        except Exception:
            pass
    return val


def set_locale(code: str) -> None:
    """Change la locale active et persiste le choix."""
    global _active, _strings

    _require_init()
    data = _load_json(code)
    if not data:
        return   # locale inconnue, on ne change pas

    _active  = code
    _strings = data

    # Persister
    if _locale_file:
        try:
            _locale_file.write_text(code, encoding="utf-8")
        except Exception:
            pass


def get_locale() -> str:
    """Retourne le code de la locale active."""
    return _active


def available_locales() -> list[tuple[str, str]]:
    """
    Retourne [(code, label), …] pour chaque fichier i18n/*.json.
    Ex : [("fr", "Français"), ("en", "English")]
    """
    if _i18n_dir is None or not _i18n_dir.exists():
        return []
    result = []
    for p in sorted(_i18n_dir.glob("*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            meta  = data.get("_meta", {})
            code  = meta.get("lang", p.stem)
            label = meta.get("label", p.stem.upper())
            result.append((code, label))
        except Exception:
            result.append((p.stem, p.stem.upper()))
    return result
