#!/usr/bin/env bash
# ==============================================================================
#  compiler_transcribe.sh — Compile transcribe et déploie à la racine
#  (binaire transcribe, assets fusionnés, i18n, traduire-srt.py).
#
#  Toute la logique — recette PyInstaller et déploiement — vit désormais dans
#  compile_app.py, partagé avec compiler_transcribe.bat : une seule recette
#  pour les deux OS, donc aucune dérive possible entre la clé Linux et la clé
#  Windows. Voir l'en-tête de compile_app.py pour le détail de la recette
#  « taille minimale » (paquets laissés au venv, stdlib, --add-data).
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

exec "$VPY" "$SCRIPT_DIR/compile_app.py" transcribe
