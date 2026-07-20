#!/usr/bin/env python3
"""
compile_app.py — Compile transcribe ou truchement (PyInstaller) et déploie
===========================================================================
Pilote multiplateforme : c'est le chemin utilisé sous WINDOWS (via les
compiler_*.bat) ; il fonctionne à l'identique sous Linux/macOS. Les
compiler_*.sh Linux existants restent autonomes et font la même chose.

Ce que fait ce script, dans l'ordre :
  1. Vérifie qu'il tourne bien dans le venv de la clé (sinon message clair).
  2. Installe PyInstaller dans le venv s'il manque.
  3. Compile en onefile en embarquant la BIBLIOTHÈQUE STANDARD COMPLÈTE :
     argostranslate est chargé à l'exécution depuis le venv (injection
     sys.path par bootstrap.py), donc l'analyse statique de PyInstaller ne
     voit pas sa chaîne d'imports — sans cela, premier module stdlib
     manquant à la première traduction :
         ModuleNotFoundError: No module named 'pickletools'
  4. Déploie à la racine de l'application : binaire (truchement /
     truchement.exe), assets/ fusionnés (sans écraser ceux de l'autre
     application), i18n/ (en préservant .locale, la préférence de langue
     de l'utilisateur).

Usage : python compile_app.py truchement|transcribe
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
IS_WINDOWS = os.name == "nt"

APPS: dict[str, dict] = {
    "truchement": {
        "srcdir": "truchement-src",
        "entry": "main.py",
        "icon": os.path.join("assets", "dico.png"),
        "excludes": ["matplotlib", "numpy", "torch"],
        "add_data": [("assets", "assets")],
    },
    "transcribe": {
        "srcdir": "transcribe-src",
        "entry": "transcribe.py",
        "icon": os.path.join("assets", "icon.png"),
        "excludes": [],
        "add_data": [("traduire-srt.py", "."), ("assets", "assets")],
    },
}


def stdlib_hidden_imports() -> list[str]:
    """--hidden-import pour chaque module public de la stdlib (les modules
    privés _* suivent automatiquement leurs modules publics)."""
    skip = {"antigravity", "this", "idlelib", "turtledemo", "test", "lib2to3"}
    return [
        f"--hidden-import={m}"
        for m in sorted(sys.stdlib_module_names)
        if not m.startswith("_") and m not in skip
    ]


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

    sep = ";" if IS_WINDOWS else ":"   # séparateur --add-data de PyInstaller
    cmd = [sys.executable, "-m", "PyInstaller",
           "--onefile", "--noconfirm", "--windowed", "--name", name]
    for mod in cfg["excludes"]:
        cmd.append(f"--exclude-module={mod}")
    cmd += stdlib_hidden_imports()
    cmd += icon_args(srcdir, cfg["icon"])
    for src, dst in cfg["add_data"]:
        cmd.append(f"--add-data={src}{sep}{dst}")
    cmd.append(cfg["entry"])

    print(f"Compilation de {name} "
          f"(stdlib embarquée : {len(stdlib_hidden_imports())} modules)...")
    subprocess.run(cmd, cwd=srcdir, check=True)

    # ── Déploiement à la racine ──────────────────────────────────────────────
    exe = name + (".exe" if IS_WINDOWS else "")
    built = os.path.join(srcdir, "dist", exe)
    target = os.path.join(APP_ROOT, exe)
    shutil.copy2(built, target)
    if not IS_WINDOWS:
        os.chmod(target, 0o755)
    deploy_dir(os.path.join(srcdir, "assets"), os.path.join(APP_ROOT, "assets"))
    deploy_dir(os.path.join(srcdir, "i18n"), os.path.join(APP_ROOT, "i18n"))

    print(f"Compilation terminée avec succès : {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
