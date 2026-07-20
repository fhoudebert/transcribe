"""
translator.py — Wrappers argostranslate, importé directement dans ce process
================================================================================
STRATÉGIE
──────────
argostranslate est importé DIRECTEMENT dans le process courant (le venv de
la clé étant rendu visible via l'injection sys.path faite par bootstrap.py).
Avantages déterminants par rapport à une délégation systématique vers un
sous-processus :

  • Le modèle de traduction (CTranslate2 + SentencePiece) n'est chargé
    QU'UNE FOIS et reste en mémoire (cache _TRANSLATION_CACHE) — les appels
    suivants sur la même paire de langues sont quasi instantanés, alors
    qu'un sous-processus rechargerait tout depuis zéro à chaque traduction.
  • Les erreurs sont des exceptions Python normales, immédiatement
    diagnosticables (traceback complet), plutôt que des codes extraits
    d'un JSON renvoyé par un sous-processus.
  • Pas de coût de démarrage d'interpréteur (~100-300 ms minimum) à chaque
    appel, ni de limite de taille sur le texte transmis.

Ce choix est valide parce que le venv (build/python/venv) est créé et
utilisé sur la même machine/OS — voir bootstrap.py pour la discussion
complète du compromis ABI qui justifiait l'ancienne approche par
sous-processus.

REPLI DIAGNOSTIC
──────────────────
Si l'import direct échoue MALGRÉ l'injection sys.path (venv corrompu,
dépendance manquante, etc.), on ne se contente pas de remonter l'échec :
on relance la même opération dans un sous-processus isolé lancé avec
bootstrap.VENV_PYTHON (l'interpréteur du venv lui-même). Si CE sous-
processus réussit là où l'import direct dans ce process a échoué, cela
prouve que le venv est sain et que le problème vient spécifiquement de
l'injection sys.path (conflit de module système homonyme, par exemple) —
information précieuse pour le diagnostic, qu'on remonte alors comme telle
plutôt que comme un simple "argostranslate n'est pas installé".

Codes d'erreur (RuntimeError levée côté appelant) :
    IMPORT_ERROR        argostranslate non importable, même en sous-processus
    IMPORT_FILES         argostranslatefiles non importable
    IMPORT_BS4            beautifulsoup4 / lxml non importable
    NO_LANGUAGES          aucune langue installée
    NO_LANG:<code>        langue <code> absente des packages installés
    NO_PKG:<s>:<t>        paire de traduction <s>→<t> non installée
    SYS_PATH_ONLY:<msg>   échec en import direct, mais succès en
                          sous-processus venv → problème d'injection sys.path
                          spécifiquement, pas du venv lui-même
    SUBPROCESS:<msg>      échec aussi en sous-processus (diagnostic complet)
    NO_VENV_PYTHON        ni import direct ni sous-processus possibles
"""

from __future__ import annotations

import json
import os
import subprocess

import bootstrap


TIMEOUT_TEXT = 120   # secondes — traduction de texte libre
TIMEOUT_FILE = 600   # secondes — traduction de fichier (peut être volumineux)


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE DES TRADUCTIONS CHARGÉES
# ═══════════════════════════════════════════════════════════════════════════════
#
# get_translation() d'argostranslate recharge le modèle CTranslate2 et le
# tokenizer SentencePiece à chaque appel si on ne le fait pas nous-mêmes.
# On cache l'objet ITranslation par paire (src, tgt) : le premier appel sur
# une paire reste coûteux (chargement modèle), les suivants sont rapides.

_TRANSLATION_CACHE: dict[tuple[str, str], object] = {}
_LANGUAGES_CACHE: list | None = None


def _get_installed_languages():
    """Charge (une seule fois, puis cache) la liste des langues installées."""
    global _LANGUAGES_CACHE
    if _LANGUAGES_CACHE is None:
        from argostranslate import translate
        _LANGUAGES_CACHE = translate.load_installed_languages()
    return _LANGUAGES_CACHE


def _get_cached_translation(src: str, tgt: str):
    """
    Retourne l'objet ITranslation pour (src, tgt), en le mettant en cache.
    Lève RuntimeError avec un code standard (NO_LANGUAGES / NO_LANG:.. /
    NO_PKG:..:..) si la paire n'est pas disponible.
    """
    key = (src, tgt)
    if key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[key]

    languages = _get_installed_languages()
    if not languages:
        raise RuntimeError("NO_LANGUAGES")

    il = next((l for l in languages if l.code == src), None)
    ol = next((l for l in languages if l.code == tgt), None)
    if il is None:
        raise RuntimeError(f"NO_LANG:{src}")
    if ol is None:
        raise RuntimeError(f"NO_LANG:{tgt}")

    tr = il.get_translation(ol)
    if tr is None:
        raise RuntimeError(f"NO_PKG:{src}:{tgt}")

    _TRANSLATION_CACHE[key] = tr
    return tr


def invalidate_language_cache() -> None:
    """
    Vide les caches de langues/traductions. À appeler après une éventuelle
    installation ou suppression de paquet argostranslate en cours de
    session (ex. futur écran de gestion des paquets dans l'UI), pour que
    le prochain appel reflète l'état réel des packages installés.
    """
    global _LANGUAGES_CACHE
    _LANGUAGES_CACHE = None
    _TRANSLATION_CACHE.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# REPLI DIAGNOSTIC — sous-processus isolé, lancé uniquement sur échec d'import
# ═══════════════════════════════════════════════════════════════════════════════

# Variables d'environnement positionnées par PyInstaller (--onefile et
# --onedir) pour que SON PROPRE interpréteur embarqué retrouve ses
# bibliothèques bundlées. Si elles sont transmises telles quelles au
# sous-processus de diagnostic, elles risquent de lui faire chercher
# modules et bibliothèques natives au mauvais endroit.
_PYINSTALLER_ENV_VARS = (
    "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH",
    "PYTHONHOME", "PYTHONPATH", "PYTHONEXECUTABLE", "_MEIPASS2",
)
_PYINSTALLER_ORIG_SUFFIX = "_ORIG"


def _clean_subprocess_env() -> dict:
    """Environnement sûr pour le sous-processus de diagnostic (voir translator.py docstring)."""
    env = os.environ.copy()
    for var in _PYINSTALLER_ENV_VARS:
        orig_key = var + _PYINSTALLER_ORIG_SUFFIX
        if orig_key in env:
            env[var] = env[orig_key]
        else:
            env.pop(var, None)
    env.pop("PYTHONPATH", None)
    return env


def _run_diagnostic_subprocess(script: str, timeout: int) -> dict:
    """
    Relance *script* dans bootstrap.VENV_PYTHON, isolé de ce process —
    utilisé UNIQUEMENT comme repli quand l'import direct a déjà échoué,
    pour déterminer si le venv lui-même est sain.

    Lève RuntimeError("NO_VENV_PYTHON") si aucun interpréteur de venv
    n'est disponible pour ce diagnostic.
    Lève RuntimeError("SUBPROCESS:<détail>") si le sous-processus échoue
    aussi (confirmation que le problème vient bien du venv).
    """
    python_exe = bootstrap.VENV_PYTHON
    if not python_exe:
        raise RuntimeError("NO_VENV_PYTHON")

    if os.name != "nt":
        try:
            st = os.stat(python_exe)
            os.chmod(python_exe, st.st_mode | 0o111)
        except OSError:
            pass

    try:
        proc = subprocess.run(
            [python_exe, "-"],
            input=script,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            env=_clean_subprocess_env(),
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("SUBPROCESS:timeout")
    except OSError as exc:
        raise RuntimeError(f"SUBPROCESS:{exc}")

    out = proc.stdout.strip()
    if not out:
        detail = proc.stderr.strip()[-800:] if proc.stderr else f"exit={proc.returncode}"
        raise RuntimeError(f"SUBPROCESS:{detail}")

    last_line = out.splitlines()[-1]
    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        raise RuntimeError(f"SUBPROCESS:bad_output:{out[-400:]}")


_DIAGNOSTIC_HEADER = """
import json, sys

def _emit(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\\n")
    sys.exit(0)

def _fail(code):
    _emit({"ok": False, "error": code})
"""


def _build_diagnostic_translate_script(src: str, tgt: str, text: str) -> str:
    return _DIAGNOSTIC_HEADER + f"""
try:
    from argostranslate import translate
except ImportError:
    _fail("IMPORT_ERROR")

languages = translate.load_installed_languages()
if not languages:
    _fail("NO_LANGUAGES")

src = {src!r}
tgt = {tgt!r}
text = {text!r}

il = next((l for l in languages if l.code == src), None)
ol = next((l for l in languages if l.code == tgt), None)
if il is None:
    _fail("NO_LANG:" + src)
if ol is None:
    _fail("NO_LANG:" + tgt)

tr = il.get_translation(ol)
if tr is None:
    _fail("NO_PKG:" + src + ":" + tgt)

result = tr.translate(text)
_emit({{"ok": True, "result": result}})
"""


def _diagnose_import_failure(direct_error: Exception, script: str, timeout: int) -> None:
    """
    Appelé quand l'import/la traduction directe a échoué dans ce process.
    Relance la même opération via le venv en sous-processus pour
    distinguer un problème de venv (le sous-processus échoue aussi) d'un
    problème d'injection sys.path dans CE process (le sous-processus
    réussit, lui).

    Lève toujours une RuntimeError, avec un code qui reflète le diagnostic.
    """
    try:
        payload = _run_diagnostic_subprocess(script, timeout)
    except RuntimeError as sub_exc:
        # Le sous-processus échoue aussi : le problème est bien dans le
        # venv (ou son absence), pas seulement dans l'injection sys.path.
        sub_err = str(sub_exc)
        if sub_err == "NO_VENV_PYTHON":
            raise RuntimeError("NO_VENV_PYTHON")
        raise RuntimeError(f"SUBPROCESS:{sub_err}")

    if payload.get("ok"):
        # Le sous-processus a réussi là où l'import direct a échoué :
        # le venv est sain, le souci vient spécifiquement de l'injection
        # sys.path dans ce process (conflit avec un module système
        # homonyme, par exemple).
        raise RuntimeError(f"SYS_PATH_ONLY:{direct_error}")

    # Le sous-processus échoue avec un code structuré (NO_LANGUAGES,
    # NO_PKG:.., etc.) : on le remonte tel quel, c'est l'information utile.
    raise RuntimeError(payload.get("error", "UNKNOWN_ERROR"))


# ═══════════════════════════════════════════════════════════════════════════════
# TRADUCTION DE TEXTE — import direct, avec repli diagnostic
# ═══════════════════════════════════════════════════════════════════════════════

def translate_text(src: str, tgt: str, text: str) -> str:
    """
    Traduit *text* de *src* vers *tgt*.

    Import direct d'argostranslate dans ce process (rapide, modèle mis en
    cache). En cas d'échec d'import ou d'absence de paquet, et seulement
    dans ce cas, relance un diagnostic via le venv en sous-processus pour
    déterminer la cause exacte (cf. docstring du module).
    """
    try:
        tr = _get_cached_translation(src, tgt)
        return tr.translate(text)
    except RuntimeError as exc:
        err = str(exc)
        # NO_LANG / NO_PKG sont des erreurs DÉFINITIVES (la langue ou le
        # paquet n'existe pas, peu importe comment on importe argos-
        # translate) : pas besoin de relancer un diagnostic, ça ne
        # changera pas le résultat et ça ralentirait l'échec.
        if err.startswith("NO_LANG:") or err.startswith("NO_PKG:"):
            raise
        # NO_LANGUAGES ou erreur d'import : peut indiquer un souci propre
        # à l'injection sys.path → diagnostic via sous-processus.
        script = _build_diagnostic_translate_script(src, tgt, text)
        _diagnose_import_failure(exc, script, TIMEOUT_TEXT)
    except ImportError as exc:
        script = _build_diagnostic_translate_script(src, tgt, text)
        _diagnose_import_failure(exc, script, TIMEOUT_TEXT)


# ═══════════════════════════════════════════════════════════════════════════════
# TRADUCTION DE FICHIER — import direct, avec repli diagnostic
# ═══════════════════════════════════════════════════════════════════════════════

def _translate_plain_file(src: str, tgt: str, input_path: str) -> str:
    """Fichiers txt/srt/docx/pdf via argostranslatefiles, import direct."""
    from argostranslate import translate as _at
    from argostranslatefiles import argostranslatefiles as _atf

    languages = _at.get_installed_languages()
    if not languages:
        raise RuntimeError("NO_LANGUAGES")

    fl = next((l for l in languages if l.code == src), None)
    tl = next((l for l in languages if l.code == tgt), None)
    if fl is None:
        raise RuntimeError(f"NO_LANG:{src}")
    if tl is None:
        raise RuntimeError(f"NO_LANG:{tgt}")

    ut = fl.get_translation(tl)
    if ut is None:
        raise RuntimeError(f"NO_PKG:{src}:{tgt}")

    return str(_atf.translate_file(ut, os.path.abspath(input_path)))


def _translate_html_file(src: str, tgt: str, input_path: str) -> str:
    """
    Fichiers HTML/HTM : traduction des nœuds texte visibles + attributs
    (alt/title/placeholder/aria-label), structure/CSS/JS préservés.
    Import direct, utilise le cache de traduction partagé.
    """
    from bs4 import BeautifulSoup, Comment

    tr = _get_cached_translation(src, tgt)   # lève RuntimeError standard si absent

    _SKIP_TAGS = {"script", "style", "noscript", "code", "pre", "kbd", "samp"}

    def _tr(t: str) -> str:
        t = t.strip()
        if not t:
            return t
        try:
            return tr.translate(t)
        except Exception:
            return t

    with open(input_path, "r", encoding="utf-8", errors="replace") as fh:
        html = fh.read()

    soup = BeautifulSoup(html, "lxml")

    for tag in soup.find_all(True):
        for attr in ("alt", "title", "placeholder", "aria-label"):
            if tag.has_attr(attr) and tag[attr].strip():
                tag[attr] = _tr(tag[attr])

    for element in soup.find_all(string=True):
        if isinstance(element, Comment):
            continue
        if element.parent and element.parent.name in _SKIP_TAGS:
            continue
        skip = any(
            hasattr(a, "name") and a.name in _SKIP_TAGS
            for a in element.parents
        )
        if skip:
            continue
        new_text = _tr(str(element))
        if new_text != str(element):
            element.replace_with(new_text)

    base, ext = os.path.splitext(input_path)
    out_path = f"{base}_{tgt}{ext}"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(str(soup))

    return out_path


def _build_diagnostic_file_script(src: str, tgt: str, input_path: str) -> str:
    return _DIAGNOSTIC_HEADER + f"""
import os

try:
    from argostranslate import translate as _at
except ImportError:
    _fail("IMPORT_ERROR")

try:
    from argostranslatefiles import argostranslatefiles as _atf
except ImportError:
    _fail("IMPORT_FILES")

languages = _at.get_installed_languages()
if not languages:
    _fail("NO_LANGUAGES")

src = {src!r}
tgt = {tgt!r}
input_path = {input_path!r}

fl = next((l for l in languages if l.code == src), None)
tl = next((l for l in languages if l.code == tgt), None)
if fl is None:
    _fail("NO_LANG:" + src)
if tl is None:
    _fail("NO_LANG:" + tgt)

ut = fl.get_translation(tl)
if ut is None:
    _fail("NO_PKG:" + src + ":" + tgt)

out_path = str(_atf.translate_file(ut, os.path.abspath(input_path)))
_emit({{"ok": True, "result": out_path}})
"""


def translate_file(src: str, tgt: str, input_path: str) -> str:
    """
    Traduit un fichier. Import direct dans ce process ; repli diagnostic
    via sous-processus uniquement si l'import échoue (cf. translate_text).

    Les fichiers HTML/HTM préservent leur structure (BeautifulSoup) ; les
    autres formats (txt, srt, docx, pdf) passent par argostranslatefiles.
    Retourne le chemin absolu du fichier traduit.
    """
    ext = os.path.splitext(input_path)[1].lower()
    is_html = ext in (".html", ".htm")

    try:
        if is_html:
            return _translate_html_file(src, tgt, input_path)
        return _translate_plain_file(src, tgt, input_path)
    except RuntimeError as exc:
        err = str(exc)
        if err.startswith("NO_LANG:") or err.startswith("NO_PKG:"):
            raise
        script = _build_diagnostic_file_script(src, tgt, input_path)
        _diagnose_import_failure(exc, script, TIMEOUT_FILE)
    except ImportError as exc:
        script = _build_diagnostic_file_script(src, tgt, input_path)
        _diagnose_import_failure(exc, script, TIMEOUT_FILE)
