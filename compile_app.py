#!/usr/bin/env python3
"""
compile_app.py — Compile transcribe ou truchement (PyInstaller) et déploie
===========================================================================
Pilote UNIQUE et multiplateforme : utilisé sous Windows via les compiler_*.bat
et sous Linux/macOS via les compiler_*.sh, qui ne sont plus que de fins
lanceurs. Une seule recette de compilation → aucune dérive entre OS.

PRINCIPE DIRECTEUR — TAILLE MINIMALE
------------------------------------
Le binaire est posé À CÔTÉ du venv figé (build/python/venv[-windows]) : tout
paquet tiers présent dans ce venv n'a AUCUNE raison d'être copié une seconde
fois dans l'exécutable. Trois règles en découlent :

  1. VENV_ONLY (ci-dessous) : liste d'exclusion couvrant les distributions de
     requirements.txt. PyInstaller analyse le bytecode et voit les imports
     même imbriqués dans une fonction — sans exclusion explicite, un simple
     « from PIL import Image » au fond d'un except embarque Pillow et ses
     libjpeg/libtiff/libwebp (≈ 24 Mio mesurés), et « from argostranslate
     import translate » embarque ctranslate2 (≈ 37 Mio de roue). Ces paquets
     sont résolus À L'EXÉCUTION :
       • truchement : bootstrap.py injecte le site-packages du venv dans
         sys.path → argostranslate, argostranslatefiles, bs4, Pillow…
         restent pleinement disponibles, sans perte de fonctionnalité ;
       • transcribe : le venv est appelé en SOUS-PROCESSUS (traduire-srt.py,
         whisper, ffmpeg) ; le process GUI lui-même n'utilise que la stdlib
         et, si présent, Pillow — dont chaque import est protégé par
         « except ImportError » avec repli tk.PhotoImage (cf. main_window.py,
         about_window.py). L'exclure ne dégrade que la qualité de
         redimensionnement des icônes, jamais le fonctionnement.

  2. Stdlib complète : embarquée pour TRUCHEMENT SEULEMENT. Argostranslate
     est chargé depuis le venv à l'exécution, donc l'analyse statique de
     PyInstaller ne voit pas sa chaîne d'imports et le premier module stdlib
     manquant casse la première traduction :
         ModuleNotFoundError: No module named 'pickletools'
     Transcribe n'a pas ce besoin (aucun tiers chargé dans son process) :
     lui imposer la stdlib complète coûtait ≈ 11 Mio pour rien.
     Note : « ensurepip » et « venv » sont retirés de la liste — ils tirent
     pip._vendor (requests, urllib3, chardet…) dans le graphe, soit plusieurs
     Mio d'un code que l'application n'exécutera jamais.

  3. Rien en --add-data : les deux applications résolvent leurs chemins
     depuis le dossier de l'exécutable (BASE_DIR), jamais depuis sys._MEIPASS.
     Les assets embarqués n'étaient donc jamais lus — ils sont déployés à la
     racine par la phase de déploiement ci-dessous.

Ce que fait ce script, dans l'ordre :
  1. Vérifie qu'il tourne bien dans le venv de la clé (sinon message clair).
  2. Installe PyInstaller dans le venv s'il manque.
  3. Compile en onefile avec la recette minimale ci-dessus.
  4. Déploie à la racine : binaire, assets/ fusionnés (sans écraser ceux de
     l'autre application), i18n/ (en préservant .locale, la préférence de
     langue de l'utilisateur), plus les fichiers listés en deploy_files.

Usage : python compile_app.py truchement|transcribe
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
IS_WINDOWS = os.name == "nt"
IS_LINUX = sys.platform.startswith("linux")

# ── Paquets fournis par le venv figé → jamais embarqués ───────────────────────
# Noms d'IMPORT (et non de distribution) de ce que porte requirements.txt, y
# compris les dépendances transitives lourdes. Exclure un paquet absent du
# graphe est sans effet ni avertissement : la liste peut donc rester commune
# aux deux applications, ce qui évite qu'un import ajouté demain à l'une
# regonfle son binaire en silence.
VENV_ONLY: list[str] = [
    # Traduction (truchement + traduire-srt.py) — le plus gros poste
    "argostranslate", "argostranslatefiles", "ctranslate2", "sentencepiece",
    "sacremoses", "stanza", "minisbd", "mwt",
    # Calcul scientifique tiré par stanza / spacy / onnxruntime
    "torch", "numpy", "scipy", "onnxruntime", "sympy", "mpmath", "networkx",
    "flatbuffers", "google.protobuf",
    # spaCy / thinc et leur chaîne
    "spacy", "spacy_legacy", "spacy_loggers", "thinc", "blis", "cymem",
    "preshed", "murmurhash", "srsly", "catalogue", "confection", "wasabi",
    "weasel", "smart_open", "cloudpathlib", "pydantic", "pydantic_core",
    "typing_inspection", "annotated_types",
    # Documents / images / dictionnaires
    "PIL", "bs4", "soupsieve", "lxml", "fitz", "pymupdf", "pyglossary",
    "pysrt", "emoji", "chardet",
    # Interfaces et console (inutilisées par les GUI tkinter)
    "PyQt5", "rich", "pygments", "markdown_it", "mdurl", "click", "typer",
    "shellingham", "tqdm", "jinja2", "markupsafe", "matplotlib",
    # Réseau : les applications sont hors-ligne ; requests n'est tiré que par
    # argostranslate.package, résolu depuis le venv
    "requests", "urllib3", "certifi", "idna", "charset_normalizer",
    "httpx", "httpcore", "h11", "anyio",
    # Outillage de build / packaging : pip et setuptools traînent tout
    # pip._vendor derrière eux (≈ 4 Mio mesurés), via ensurepip
    "pip", "setuptools", "pkg_resources", "_distutils_hack", "wheel",
    "PyInstaller", "altgraph", "packaging",
    # Divers du gel
    "yaml", "regex", "joblib", "filelock", "fsspec", "wrapt",
]

APPS: dict[str, dict] = {
    "truchement": {
        "srcdir": "truchement-src",
        "entry": "main.py",
        "icon": os.path.join("assets", "dico.png"),
        # argostranslate est importé dans CE process depuis le venv
        # (bootstrap.py) → l'analyse statique ne voit pas sa chaîne d'imports.
        "full_stdlib": True,
        # Inutile : bootstrap.py fait déjà l'injection, plus finement
        # (site-packages en TÊTE de sys.path, plus les variables
        # d'environnement d'argostranslate).
        "venv_site_packages": False,
        "deploy_files": [],
    },
    "transcribe": {
        "srcdir": "transcribe-src",
        "entry": "transcribe.py",
        "icon": os.path.join("assets", "icon.png"),
        # Aucun tiers chargé dans le process GUI : le venv n'est appelé qu'en
        # sous-processus, l'analyse statique de PyInstaller suffit.
        "full_stdlib": False,
        # Désactivé, à dessein. Activer ce hook rendrait Pillow (du venv) de
        # nouveau visible sans l'embarquer — les icônes retrouveraient le
        # redimensionnement LANCZOS au lieu du repli tk.PhotoImage/subsample.
        # MAIS : mesuré, « from PIL import Image » échoue alors sur
        #     ModuleNotFoundError: No module named '__future__'
        # car importer du code du venv ramène le problème de truchement — le
        # binaire doit porter la stdlib COMPLÈTE. Le couple hook +
        # full_stdlib fonctionne (vérifié), au prix de 11,6 → 15,9 Mio.
        # Passer LES DEUX à True si la qualité des icônes vaut ces 4,3 Mio ;
        # activer celui-ci seul produirait un binaire cassé.
        "venv_site_packages": False,
        # Fichiers copiés tels quels du srcdir vers la racine au déploiement :
        # traduire-srt.py est exécuté par le python du venv depuis la racine
        # (<racine>/traduire-srt.py), pas depuis le bundle PyInstaller.
        "deploy_files": ["traduire-srt.py"],
    },
}


STDLIB_SKIP = {
    # Suites de test et modules interactifs sans objet dans un binaire figé
    "antigravity", "this", "idlelib", "turtledemo", "test", "lib2to3",
    "turtle", "pydoc_data",
    # Tirent tout pip._vendor (requests, urllib3, chardet…) dans le graphe :
    # plusieurs Mio de code que l'application n'exécutera jamais.
    "ensurepip", "venv",
}


def stdlib_hidden_imports() -> list[str]:
    """--hidden-import pour toute la bibliothèque standard, SOUS-MODULES
    COMPRIS.

    Lister seulement les noms de premier niveau ne suffit pas : un
    --hidden-import=xml n'embarque que le paquet xml, pas
    xml.etree.ElementTree. Jusqu'ici ces sous-modules n'arrivaient dans le
    binaire que par ricochet, tirés par des paquets tiers (bs4, lxml, pip…) —
    or ces paquets ne sont justement plus embarqués. On les énumère donc
    explicitement, en parcourant le dossier de la stdlib SANS rien importer
    (pkgutil.walk_packages, lui, importerait chaque paquet traversé).

    Les modules privés _* sont omis : ils suivent automatiquement leurs
    modules publics.
    """
    names: set[str] = {
        m for m in sys.stdlib_module_names
        if not m.startswith("_") and m not in STDLIB_SKIP
    }

    stdlib_dir = sysconfig.get_paths()["stdlib"]
    for top in sorted(names):
        pkg_dir = os.path.join(stdlib_dir, top)
        if not os.path.isdir(pkg_dir):
            continue                      # module simple, rien à parcourir
        for root, dirs, files in os.walk(pkg_dir):
            dirs[:] = [d for d in dirs
                       if d != "__pycache__" and not d.startswith(("test", "_"))]
            rel = os.path.relpath(root, stdlib_dir).replace(os.sep, ".")
            for f in files:
                if not f.endswith(".py") or f.startswith("_"):
                    continue
                names.add(f"{rel}.{f[:-3]}" if f != "__init__.py" else rel)

    return [f"--hidden-import={m}" for m in sorted(names)]


_VENV_RTHOOK = '''\
# Généré par compile_app.py — ne pas éditer.
#
# Rend visibles les paquets du venv figé de la clé SANS les embarquer dans le
# binaire : le site-packages est ajouté EN QUEUE de sys.path, donc les modules
# gelés gardent toujours la priorité et le venv ne peut rien masquer. Seuls
# les imports que le binaire ne satisfait pas (Pillow, par exemple) y sont
# résolus. Aucun effet si la clé est incomplète : l'application retombe sur
# ses replis habituels (except ImportError).
import glob
import os
import sys

_base = os.path.dirname(os.path.abspath(sys.executable))
_venv = os.path.join(_base, "build", "python")
for _cand in (
    glob.glob(os.path.join(_venv, "venv", "lib", "python3.*", "site-packages"))
    + glob.glob(os.path.join(_venv, "venv", "lib64", "python3.*", "site-packages"))
    + [os.path.join(_venv, "venv-windows", "Lib", "site-packages"),
       os.path.join(_venv, "venv", "Lib", "site-packages")]
):
    if os.path.isdir(_cand) and _cand not in sys.path:
        sys.path.append(_cand)
'''


def venv_runtime_hook(tmpdir: str) -> str:
    """Écrit le runtime hook d'accès au venv et retourne son chemin."""
    path = os.path.join(tmpdir, "pyi_rth_venv_site_packages.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_VENV_RTHOOK)
    return path


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller absent du venv, installation...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller"], check=True
        )


def icon_args(srcdir: str, icon_rel: str) -> list[str]:
    """
    Sous Windows, PyInstaller exige un .ico (ou Pillow pour convertir) ;
    sous Linux, --icon est ignoré. On ne passe l'option que si elle a une
    chance d'aboutir, plutôt que de faire échouer toute la compilation.
    (Pillow n'est utilisé qu'ICI, à la compilation : il reste dans le venv et
    n'entre pas dans le binaire — cf. VENV_ONLY.)
    """
    path = os.path.join(srcdir, icon_rel)
    if not os.path.isfile(path):
        # essaie aussi la variante .ico à côté (assets/dico.ico, etc.)
        alt = os.path.splitext(path)[0] + ".ico"
        if os.path.isfile(alt):
            return [f"--icon={os.path.splitext(icon_rel)[0]}.ico"]
        print(f"[note] icône absente ({icon_rel}) — option --icon omise")
        return []
    if IS_WINDOWS and not path.lower().endswith(".ico"):
        try:
            import PIL  # noqa: F401  (Pillow sait convertir png → ico)
        except ImportError:
            print(f"[note] {icon_rel} n'est pas un .ico et Pillow est absent "
                  f"— option --icon omise sous Windows")
            return []
    return [f"--icon={icon_rel}"]


def deploy_dir(src: str, dest: str) -> None:
    """
    Fusionne src/ dans dest/ (créé si besoin) SANS supprimer ce qui vient
    d'autres sources (assets/ est partagé entre transcribe et truchement).
    Cas particulier : i18n/.locale mémorise la langue choisie par
    l'utilisateur → copiée uniquement si absente, pour ne pas écraser sa
    préférence à chaque recompilation.
    """
    if not os.path.isdir(src):
        return
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(src):
        s, d = os.path.join(src, name), os.path.join(dest, name)
        if name == ".locale" and os.path.exists(d):
            continue
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)


def human(nbytes: int) -> str:
    return f"{nbytes / (1024 * 1024):.1f} Mio"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in APPS:
        print(f"Usage : python {os.path.basename(argv[0])} "
              f"{'|'.join(APPS)}")
        return 2

    name, cfg = argv[1], APPS[argv[1]]
    srcdir = os.path.join(APP_ROOT, cfg["srcdir"])

    # Le script doit tourner avec le python du venv de la clé (c'est lui qui
    # porte PyInstaller et dont la version doit correspondre aux extensions
    # compilées du venv). sys.prefix != base_prefix ⇔ on est dans un venv.
    if sys.prefix == sys.base_prefix:
        venv_rel = os.path.join("build", "python",
                                "venv-windows" if IS_WINDOWS else "venv")
        print(f"[ERREUR] À lancer avec le python du venv de la clé "
              f"({venv_rel}) — utilisez compiler_{name}.bat / .sh")
        return 1

    ensure_pyinstaller()

    # Dossier de travail éphémère : ne sert qu'à porter le runtime hook
    # généré, qui n'a pas à salir l'arborescence des sources.
    tmpdir = tempfile.mkdtemp(prefix=f"compile_{name}_")

    cmd = [sys.executable, "-m", "PyInstaller",
           "--onefile", "--noconfirm", "--windowed", "--name", name,
           # -OO sur les seuls modules embarqués : supprime docstrings et
           # assertions (sans effet sur le code chargé du venv à l'exécution).
           "--optimize", "2"]

    # --strip : retire les tables de symboles des .so collectés. Gain net sous
    # Linux ; ignoré (avec avertissement) sous Windows et déconseillé sous
    # macOS, où il peut invalider les signatures de code.
    if IS_LINUX:
        cmd.append("--strip")

    for mod in VENV_ONLY:
        cmd.append(f"--exclude-module={mod}")
    if cfg["full_stdlib"]:
        cmd += stdlib_hidden_imports()
    if cfg["venv_site_packages"]:
        cmd.append(f"--runtime-hook={venv_runtime_hook(tmpdir)}")
    cmd += icon_args(srcdir, cfg["icon"])
    # Pas de --add-data : les deux applications lisent assets/ et i18n/ à côté
    # de l'exécutable (BASE_DIR), jamais dans le bundle (_MEIPASS).
    cmd.append(cfg["entry"])

    detail = (f"stdlib complète embarquée : {len(stdlib_hidden_imports())} "
              f"modules" if cfg["full_stdlib"]
              else "stdlib non embarquée (inutile ici)")
    print(f"Compilation de {name} ({detail} ; "
          f"{len(VENV_ONLY)} paquets laissés au venv)...")
    try:
        subprocess.run(cmd, cwd=srcdir, check=True)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ── Déploiement à la racine ──────────────────────────────────────────────
    exe = name + (".exe" if IS_WINDOWS else "")
    built = os.path.join(srcdir, "dist", exe)
    target = os.path.join(APP_ROOT, exe)
    shutil.copy2(built, target)
    if not IS_WINDOWS:
        os.chmod(target, 0o755)
    deploy_dir(os.path.join(srcdir, "assets"), os.path.join(APP_ROOT, "assets"))
    deploy_dir(os.path.join(srcdir, "i18n"), os.path.join(APP_ROOT, "i18n"))
    for fname in cfg.get("deploy_files", []):
        shutil.copy2(os.path.join(srcdir, fname),
                     os.path.join(APP_ROOT, fname))
        print(f"Déployé à la racine : {fname}")

    print(f"Compilation terminée avec succès : {target} "
          f"({human(os.path.getsize(target))})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
