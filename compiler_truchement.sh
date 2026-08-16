#!/usr/bin/env bash
# ==============================================================================
#  compiler_truchement.sh — Compile truchement et déploie à la racine
#  (binaire truchement, assets fusionnés, i18n).
#
#  Toute la logique — recette PyInstaller et déploiement — vit désormais dans
#  compile_app.py, partagé avec compiler_truchement.bat : une seule recette
#  pour les deux OS, donc aucune dérive possible entre la clé Linux et la clé
#  Windows.
#
#  Rappel d'architecture : le binaire n'embarque PAS argostranslate / torch /
#  numpy / bs4 — ces paquets vivent dans le venv de la clé et sont chargés à
#  l'exécution par bootstrap.py (injection sys.path). En contrepartie
#  PyInstaller ne peut pas déduire leurs besoins par analyse statique, d'où la
#  bibliothèque standard COMPLÈTE embarquée dans le binaire (sinon :
#  ModuleNotFoundError: No module named 'pickletools' à la première
#  traduction). Détails dans l'en-tête de compile_app.py.
# ==============================================================================

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VPY="$SCRIPT_DIR/build/python/venv/bin/python"

if [ ! -x "$VPY" ]; then
    echo "❌ venv introuvable : $SCRIPT_DIR/build/python/venv"
    echo "   Lancez d'abord setupPython_and_download.sh"
    exit 1
fi

exec "$VPY" "$SCRIPT_DIR/compile_app.py" truchement
