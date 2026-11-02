"""
pyi_env.py — environnement propre pour les programmes lancés par l'application
==============================================================================
Un exécutable PyInstaller « onefile » se décompresse dans un dossier
temporaire (/tmp/_MEIxxxx) et pose dans son propre environnement des
variables qui y renvoient : _PYI_APPLICATION_HOME_DIR, _PYI_ARCHIVE_FILE,
_PYI_PARENT_PROCESS_LEVEL…, LD_LIBRARY_PATH, et — via le hook tkinter —
TCL_LIBRARY / TK_LIBRARY. Tout programme lancé depuis l'application en
hérite : gestionnaire de fichiers ouvert par « Ouvrir le dossier », puis
tout terminal ouvert depuis celui-ci…

Une fois l'application fermée, son dossier temporaire est supprimé mais ces
variables survivent dans ces programmes. Conséquences constatées :
  • ./transcribe lancé depuis un tel terminal : « Failed to load Python
    shared library '/tmp/_MEI…/libpython3.12.so.1.0' » (il se croit déjà
    décompressé et cherche le dossier d'un autre processus) ;
  • compilation depuis un tel terminal : TK_LIBRARY vers un dossier absent,
    exécutable produit sans scripts Tk.

clean_inherited_env() retire ces variables de l'environnement du processus,
une fois Tk initialisé (il n'en a plus besoin : tcl_library / tk_library
sont alors fixés dans l'interpréteur), donc avant tout lancement de
programme externe. Sans effet hors exécutable PyInstaller.
"""

from __future__ import annotations

import os
import sys


def clean_inherited_env() -> None:
    if not getattr(sys, "frozen", False):
        return
    meipass = getattr(sys, "_MEIPASS", "") or ""

    # LD_LIBRARY_PATH : PyInstaller garde la valeur d'origine dans *_ORIG.
    orig = os.environ.pop("LD_LIBRARY_PATH_ORIG", None)
    if orig is not None:
        os.environ["LD_LIBRARY_PATH"] = orig
    elif meipass and "LD_LIBRARY_PATH" in os.environ:
        kept = [p for p in os.environ["LD_LIBRARY_PATH"].split(os.pathsep)
                if p and not p.startswith(meipass)]
        if kept:
            os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(kept)
        else:
            del os.environ["LD_LIBRARY_PATH"]

    for key in list(os.environ):
        if key.startswith("_PYI_") or key in ("_MEIPASS2", "_MEIPASS"):
            del os.environ[key]
        elif meipass and meipass in os.environ.get(key, ""):
            del os.environ[key]       # TCL_LIBRARY, TK_LIBRARY, SSL_CERT_FILE…
