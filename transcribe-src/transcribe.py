#!/usr/bin/env python3
"""
transcribe.py  —  Point d'entrée de l'application.

Structure :
    transcribe.py       ← ce fichier
    app_config.py       ← constantes, données, plateforme
    app_styles.py       ← palette, polices, widgets helpers, style TTK
    i18n.py              ← internationalisation (t(), set_locale()…)
    i18n/fr.json         ← libellés français
    i18n/en.json         ← libellés anglais
    main_window.py      ← fenêtre principale (classe Transcribe)
    recorder_window.py  ← dictaphone (RecorderWindow) + ChoiceDialog
    traduire-srt.py     ← traduction SRT hors-ligne (argostranslate)

Lancement (développement) :  python transcribe.py
Lancement (PyInstaller)    :  ./transcribe  /  transcribe.exe
"""

import os
import sys
from pathlib import Path


def _resolve_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR = _resolve_base_dir()
os.environ["TRANSCRIBE_BASE_DIR"] = str(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

# Initialise tr (i18n) AVANT tout import de module UI
import i18n as _i18n_module
_i18n_module.init(base_dir=str(BASE_DIR))

from main_window import Transcribe
from app_config import IS_WINDOWS


if __name__ == "__main__":
    # className="Transcribe" : pris en charge uniquement sous Linux/X11.
    # Sur Windows, tk.Tk() ne supporte pas ce paramètre → on l'omet.
    if IS_WINDOWS:
        app = Transcribe()
    else:
        app = Transcribe(className="Transcribe")
    app.mainloop()
