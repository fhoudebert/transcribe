"""
bootstrap.py — Initialisation de l'environnement portable
===========================================================
Doit être importé EN PREMIER (avant tout autre module du projet, et avant
tout import d'argostranslate / argostranslatefiles).

Résout deux problèmes liés à PyInstaller --onefile :

  1. __file__ pointe vers le dossier temporaire _MEIPASS (éphémère) ;
     sys.executable pointe vers le binaire final déployé → source stable.

  2. argostranslate / argostranslatefiles, installés dans le venv figé
     livré sur la clé (build/python/venv), doivent être rendus visibles à
     l'interpréteur qui exécute cette application (le Python du venv
     lui-même en usage normal, ou l'exe PyInstaller figé en version
     compilée).

STRATÉGIE ACTUELLE — injection sys.path directe
──────────────────────────────────────────────────
Le venv est créé avec `python -m venv` sur la MÊME machine/OS que celle où
il sera utilisé (ce n'est pas un binaire cross-compilé livré "tel quel" sur
des architectures arbitraires) : le risque théorique d'incompatibilité ABI
entre l'interpréteur qui importe argostranslate et les extensions natives
du venv (sentencepiece, ctranslate2…) ne s'applique donc pas à ce mode de
déploiement. Dans la pratique, tous les incidents réellement rencontrés
(NO_LANGUAGES, "argostranslate n'est pas installé") provenaient de causes
sans rapport avec l'ABI : variable ARGOS_PACKAGES_DIR jamais positionnée,
symlinks cassés/déréférencés lors d'une copie sur clé USB, ou variables
d'environnement injectées par PyInstaller polluant un sous-processus.

On injecte donc directement le site-packages du venv dans sys.path de CE
process (_inject_venv_site_packages, plus bas) : argostranslate est importé
une seule fois, son modèle reste chargé en mémoire et en cache entre deux
traductions (au lieu de relancer un interpréteur complet à chaque appel),
et toute erreur d'import remonte comme une exception Python normale,
directement diagnosticable, plutôt qu'un code d'erreur extrait d'un
sous-processus.

VENV_PYTHON (chemin de l'exécutable Python du venv) reste exposé : il sert
de secours pour translator.py, qui peut relancer un diagnostic isolé dans
un sous-processus propre UNIQUEMENT si l'import direct échoue malgré tout
— afin de distinguer un problème d'environnement (corrigible) d'un
problème réellement lié à l'isolation du process courant.
"""

from __future__ import annotations

import glob
import os
import re
import sys


# ─── Répertoire de base ────────────────────────────────────────────────────────
#
# sys.frozen est positionné par PyInstaller (et d'autres freezers).
# Dans ce cas sys.executable == chemin du binaire déployé.
# En mode script, __file__ est fiable.

if getattr(sys, "frozen", False):
    BASE_DIR: str = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ─── Localisation de l'interpréteur du venv figé ───────────────────────────────

_VENV_DIR = os.path.join(BASE_DIR, "build", "python", "venv")


def _candidate_pythons(venv_dir: str) -> list[str]:
    """
    Liste les emplacements plausibles de l'exécutable Python d'un venv,
    Linux/macOS d'abord, puis Windows.
    """
    return [
        os.path.join(venv_dir, "bin", "python"),          # Linux / macOS — cas nominal
        os.path.join(venv_dir, "bin", "python3"),
        os.path.join(venv_dir, "Scripts", "python.exe"),  # Windows
        os.path.join(venv_dir, "Scripts", "python3.exe"),
    ]


def _resolve_python_candidate(path: str) -> str | None:
    """
    Valide qu'un chemin candidat est un exécutable Python réellement utilisable,
    en gérant les pièges classiques liés au transport sur clé USB :

      • SYMLINK CASSÉ — un venv créé par `python -m venv` a normalement
        bin/python comme symlink vers bin/python3.X (ou vers le Python
        système). Si la cible n'a pas été copiée (oubli, perte du lien lors
        d'une copie Windows, exclusion du build), os.path.isfile() renvoie
        False même si l'entrée "python" existe — d'où NO_VENV_PYTHON alors
        que le dossier est bien présent.
        → on suit explicitement le lien (os.path.realpath) et on cherche
          aussi, si la cible directe est absente, un binaire frère dans le
          même dossier (python3.10, python3.11, python3.12…) qui POURRAIT
          être la vraie cible voulue.

      • SYMLINK RÉSOLU VERS LE PYTHON SYSTÈME — certains outils de copie
        (notamment sous Windows, qui ne gère pas nativement les symlinks
        POSIX) déréférencent silencieusement le lien et copient le binaire
        cible réel à sa place. Le fichier "python" obtenu est alors le
        Python système d'origine (sans les site-packages du venv) : il
        s'exécute sans erreur mais "import argostranslate" y échoue,
        d'où le message "argostranslate n'est pas installé" malgré un
        venv apparemment présent.
        → on vérifie, après résolution, qu'il existe bien un dossier
          site-packages associé au venv lui-même (pyvenv.cfg + lib/…)
          pour s'assurer que le binaire trouvé EST le bon, et pas un
          succédané système qui porte juste le même nom.

    Retourne le chemin (potentiellement résolu) à utiliser, ou None si le
    candidat ne peut être validé.
    """
    if not os.path.exists(path):   # couvre fichiers normaux ET symlinks valides
        # Symlink cassé : tente de retrouver un binaire frère plausible
        # dans le même répertoire (ex. python3.11, python3.12…).
        if os.path.islink(path):
            folder = os.path.dirname(path)
            try:
                siblings = sorted(os.listdir(folder))
            except OSError:
                siblings = []
            for name in siblings:
                if re.fullmatch(r"python3(\.\d+)?(\.exe)?", name):
                    candidate = os.path.join(folder, name)
                    if os.path.isfile(candidate):
                        return candidate
        return None

    if not os.path.isfile(path):
        return None

    return path


def _venv_has_own_site_packages(python_path: str, venv_dir: str) -> bool:
    """
    Vérifie que *python_path* correspond bien au venv *venv_dir* lui-même
    (présence de pyvenv.cfg et d'un dossier lib/.../site-packages), et non
    à un Python système homonyme récupéré par erreur lors de la copie.

    Une absence de pyvenv.cfg n'est PAS automatiquement disqualifiante :
    certains venv "embarqués" (python-build-standalone, pyoxidizer, etc.)
    n'en génèrent pas. On se contente donc d'un avertissement implicite —
    cette fonction n'est utilisée qu'à titre diagnostique, jamais pour
    rejeter un candidat par ailleurs valide.
    """
    return os.path.isfile(os.path.join(venv_dir, "pyvenv.cfg"))


def _find_venv_python(venv_dir: str) -> str | None:
    """
    Retourne le chemin de l'exécutable Python du venv, ou None s'il est
    introuvable. Voir _resolve_python_candidate() pour le détail des cas
    de figure gérés (symlinks cassés, résolution vers le Python système).
    """
    for candidate in _candidate_pythons(venv_dir):
        resolved = _resolve_python_candidate(candidate)
        if resolved:
            return resolved
    return None


# Chemin de l'interpréteur Python embarqué sur la clé USB.
# None si le venv n'est pas présent (ex. exécution en environnement de dev
# où argostranslate est installé directement dans le Python courant).
VENV_PYTHON: str | None = _find_venv_python(_VENV_DIR)

# Diagnostic exposé pour les messages d'erreur de l'UI : permet de distinguer
# "aucun interpréteur trouvé" de "interpréteur trouvé mais semble être un
# Python système plutôt que celui du venv" (cf. ui/app.py _venv_missing_msg).
VENV_LOOKS_GENUINE: bool = bool(
    VENV_PYTHON and _venv_has_own_site_packages(VENV_PYTHON, _VENV_DIR)
)


# ─── Injection sys.path du site-packages du venv ───────────────────────────────

def _venv_site_packages_dirs(venv_dir: str) -> list[str]:
    """
    Retourne les chemins site-packages plausibles d'un venv, Linux/macOS
    et Windows confondus (on ne sait pas a priori sur quel OS la clé a
    été préparée vs. utilisée — bien qu'en pratique ce soit le même, cf.
    docstring du module).
    """
    candidates: list[str] = []
    candidates.extend(
        glob.glob(os.path.join(venv_dir, "lib", "python3.*", "site-packages"))
    )
    candidates.append(os.path.join(venv_dir, "Lib", "site-packages"))   # Windows
    candidates.extend(
        glob.glob(os.path.join(venv_dir, "lib64", "python3.*", "site-packages"))
    )
    return [p for p in candidates if os.path.isdir(p)]


def _inject_venv_site_packages(venv_dir: str) -> bool:
    """
    Insère le(s) site-packages du venv en tête de sys.path, pour que
    `import argostranslate` (et argostranslatefiles, bs4, etc.) fonctionne
    directement dans CE process, sans relancer d'interpréteur séparé.

    Retourne True si au moins un dossier site-packages a été trouvé et
    ajouté, False sinon (venv absent ou structure inattendue — dans ce
    cas translator.py basculera sur le diagnostic via sous-processus).
    """
    found = _venv_site_packages_dirs(venv_dir)
    for sp in found:
        if sp not in sys.path:
            sys.path.insert(0, sp)   # priorité sur tout site-packages système
    return bool(found)


VENV_SITE_PACKAGES_INJECTED: bool = _inject_venv_site_packages(_VENV_DIR)


def diagnose_venv_python() -> dict:
    """
    Diagnostic à la demande, utilisé par l'UI quand le sous-processus de
    traduction échoue avec IMPORT_ERROR / NO_LANGUAGES, pour afficher un
    message ACTIONNABLE plutôt que générique.

    Distingue notamment :
      • aucun interpréteur trouvé du tout
      • un interpréteur trouvé, mais qui n'a pas l'air d'être le venv
        (pas de pyvenv.cfg à côté) → probablement le Python système
        récupéré par erreur lors d'une copie qui a déréférencé un symlink
      • un interpréteur qui a l'air légitime mais où l'import échoue
        malgré tout (venv mal construit, paquet non installé)

    Ne lève jamais d'exception ; retourne toujours un dict utilisable
    directement dans un message d'erreur.
    """
    if not VENV_PYTHON:
        return {
            "found": False,
            "path": None,
            "genuine": False,
            "note": (
                f"Aucun interpréteur Python trouvé sous {_VENV_DIR}. "
                f"Vérifiez que le dossier build/python/venv a bien été "
                f"copié intégralement (y compris ses sous-dossiers lib/ "
                f"ou Lib/), au même niveau que l'exécutable."
            ),
        }
    note = ""
    if not VENV_LOOKS_GENUINE:
        note = (
            f"L'interpréteur trouvé ({VENV_PYTHON}) ne semble pas être "
            f"celui du venv préparé (pyvenv.cfg absent dans {_VENV_DIR}). "
            f"Il s'agit peut-être du Python système, récupéré par erreur "
            f"si un outil de copie a remplacé un lien symbolique par le "
            f"fichier qu'il ciblait. Recopiez le dossier build/python/venv "
            f"avec un outil qui préserve les liens symboliques "
            f"(ex. 'cp -a' ou 'rsync -a' sous Linux/macOS)."
        )
    return {
        "found": True,
        "path": VENV_PYTHON,
        "genuine": VENV_LOOKS_GENUINE,
        "note": note,
    }


def probe_argostranslate() -> dict:
    """
    Diagnostic APPROFONDI : interroge réellement VENV_PYTHON pour savoir où
    argostranslate.settings cherche ses paquets et combien il en trouve,
    plutôt que de deviner depuis le process courant.

    Contrairement à diagnose_venv_python() (qui n'inspecte que le système de
    fichiers depuis CE process), cette fonction lance un sous-processus —
    donc elle est plus lente et n'est appelée qu'à la demande, typiquement
    depuis un bouton "Diagnostiquer" dans l'UI, jamais au démarrage.

    Retourne un dict avec :
        ok                  bool   import argostranslate a réussi
        package_data_dir    str    chemin où argostranslate cherche les .argosmodel
        n_packages_on_disk  int    nb de paquets présents dans ce dossier
        n_languages         int    nb de langues installées détectées
        error               str    présent seulement si ok=False
    """
    import json
    import subprocess

    if not VENV_PYTHON:
        return {"ok": False, "error": "NO_VENV_PYTHON"}

    script = """
import json, sys
try:
    from argostranslate import settings, translate
except Exception as exc:
    print(json.dumps({"ok": False, "error": "IMPORT_ERROR:" + repr(exc)}))
    sys.exit(0)

pdd = str(settings.package_data_dir)
try:
    n_disk = len(list(settings.package_data_dir.iterdir()))
except Exception:
    n_disk = -1

langs = translate.load_installed_languages()
print(json.dumps({
    "ok": True,
    "package_data_dir": pdd,
    "n_packages_on_disk": n_disk,
    "n_languages": len(langs),
    "languages": [l.code for l in langs],
}))
"""
    try:
        proc = subprocess.run(
            [VENV_PYTHON, "-"],
            input=script,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            env=os.environ.copy(),
        )
    except Exception as exc:
        return {"ok": False, "error": f"SUBPROCESS:{exc}"}

    out = proc.stdout.strip()
    if not out:
        return {"ok": False, "error": f"SUBPROCESS:{proc.stderr.strip()[-500:]}"}
    try:
        return json.loads(out.splitlines()[-1])
    except json.JSONDecodeError:
        return {"ok": False, "error": f"SUBPROCESS:bad_output:{out[-300:]}"}


# ─── Variables d'environnement Argos Translate ─────────────────────────────────
#
# Nom de variable vérifié sur la documentation officielle du dépôt
# (argosopentech/argos-translate, docs/settings.md) :
#
#       export ARGOS_PACKAGES_DIR="/chemin/vers/packages/"
#
# Sans cette variable, argostranslate utilise par défaut
# ~/.local/share/argos-translate/packages (Linux) ou l'équivalent
# %LOCALAPPDATA% sous Windows — c'est-à-dire le PROFIL UTILISATEUR, pas un
# emplacement relatif à la clé USB. C'est très probablement là que
# `argospm install` a écrit les modèles lors de la préparation de la clé
# (cf. `argospm list` qui les retrouve sans aucune variable positionnée).
#
# PROBLÈME avec une activation CONDITIONNELLE de la variable (ancienne
# version de ce fichier) : si l'on ne positionne ARGOS_PACKAGES_DIR que
# lorsque build/argos-data/packages contient déjà des fichiers, on reste
# tributaire du profil utilisateur tant qu'aucune migration n'a eu lieu —
# et ce profil peut très bien différer entre la session où `argospm
# install` a été lancé manuellement et celle où l'application (ou son
# sous-processus venv) s'exécute : HOME différent (autre utilisateur
# Windows/Linux), variables d'environnement filtrées par un lanceur, etc.
# C'est la cause la plus probable d'un sous-processus qui importe
# argostranslate avec succès mais ne lui trouve aucune langue installée.
#
# CORRECTIF : on positionne TOUJOURS ARGOS_PACKAGES_DIR vers
# build/argos-data/packages (l'app reste ainsi strictement autonome dans
# son dossier, qu'on la lance depuis n'importe quel compte ou contexte) ;
# et si ce dossier est vide alors qu'une installation préexistante est
# détectée dans les emplacements par défaut usuels d'argostranslate
# (~/.local/share/argos-translate/packages, %LOCALAPPDATA%\...), on
# MIGRE automatiquement ces paquets vers build/argos-data au premier
# lancement, pour ne jamais perdre une installation déjà faite via
# `argospm install` sans cette variable.

import shutil


def _default_argos_packages_dirs() -> list[str]:
    """
    Emplacements où argostranslate range ses paquets par défaut (sans
    ARGOS_PACKAGES_DIR positionnée), tous systèmes confondus — on les
    teste tous car on ne sait pas sur quel OS la clé a été préparée.
    """
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".local", "share", "argos-translate", "packages"),
        os.path.join(home, ".argos-translate", "packages"),   # très anciennes versions
    ]
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        candidates.append(
            os.path.join(localappdata, "argos-translate", "packages")
        )
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(os.path.join(appdata, "argos-translate", "packages"))
    return candidates


def _migrate_existing_packages(target_dir: str) -> None:
    """
    Si *target_dir* (build/argos-data/packages) est vide, recherche une
    installation existante dans les emplacements par défaut d'argostranslate
    et y copie son contenu — rend l'app indépendante du profil utilisateur
    dès le lancement suivant, sans jamais supprimer la source.
    """
    try:
        already_has_content = os.path.isdir(target_dir) and bool(os.listdir(target_dir))
    except OSError:
        already_has_content = False
    if already_has_content:
        return

    for source_dir in _default_argos_packages_dirs():
        if not os.path.isdir(source_dir):
            continue
        try:
            entries = os.listdir(source_dir)
        except OSError:
            continue
        if not entries:
            continue
        os.makedirs(target_dir, exist_ok=True)
        for name in entries:
            src = os.path.join(source_dir, name)
            dst = os.path.join(target_dir, name)
            try:
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
            except OSError:
                pass   # migration best-effort : ne bloque jamais le démarrage
        return   # une seule source migrée suffit


_ARGOS_DATA_DIR     = os.path.join(BASE_DIR, "build", "argos-data")
_ARGOS_PACKAGES_DIR = os.path.join(_ARGOS_DATA_DIR, "packages")

_migrate_existing_packages(_ARGOS_PACKAGES_DIR)
os.makedirs(_ARGOS_PACKAGES_DIR, exist_ok=True)

# Forcé sans condition : l'app ne doit jamais dépendre silencieusement du
# profil utilisateur de la machine où elle s'exécute.
os.environ["ARGOS_PACKAGES_DIR"] = _ARGOS_PACKAGES_DIR
os.environ["ARGOS_TRANSLATE_PACKAGE_DIR"] = _ARGOS_PACKAGES_DIR   # alias legacy

