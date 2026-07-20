#!/bin/bash

set -e  # stop si erreur

echo "📦 compilation de transcribe..."
cd build/python/venv/bin/
source activate 
cd ../../../../
cd truchement-src
../build/python/venv/bin/pyinstaller \
    --onefile \
    --name transcribe \
    --icon=assets/icone.png \
    --add-data "traduire-srt.py:." \
    --add-data "assets:assets" \
    --windowed \
    transcribe.py
echo "📦 compilation de truchement..."
# Délégué à compiler_truchement.sh, qui embarque la stdlib complète dans le
# binaire (argostranslate étant chargé depuis le venv à l'exécution,
# l'analyse statique de PyInstaller ne suffit pas — cf. commentaires du
# script : ModuleNotFoundError pickletools sinon).
bash "$(dirname "$0")/compiler_truchement.sh"
echo "✅ compilation terminée"
