#!/usr/bin/env python3
"""
main.py — Point d'entrée de Truchement
========================================
Doit être exécuté directement :
    python main.py
ou figé par PyInstaller :
    pyinstaller --windowed --onefile --name truchement main.py

L'ordre d'import est critique :
  1. bootstrap  → BASE_DIR, injection venv, vars d'env argostranslate
  2. ui.app     → TranslatorApp (et tous ses modules)
"""

import bootstrap  # noqa: F401  — doit être le tout premier import

from ui.app import TranslatorApp


def main() -> None:
    app = TranslatorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
