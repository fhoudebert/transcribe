#!/bin/bash

set -e  # stop si erreur

echo "📦 compilation de transcribe..."
# Délégué à compiler_transcribe.sh (compilation + déploiement à la racine :
# binaire, assets fusionnés, i18n).
bash "$(dirname "$0")/compiler_transcribe.sh"
echo "📦 compilation de truchement..."
# Délégué à compiler_truchement.sh, qui embarque la stdlib complète dans le
# binaire (argostranslate étant chargé depuis le venv à l'exécution,
# l'analyse statique de PyInstaller ne suffit pas — cf. commentaires du
# script : ModuleNotFoundError pickletools sinon).
bash "$(dirname "$0")/compiler_truchement.sh"
echo "✅ compilation terminée"
