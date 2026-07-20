#!/usr/bin/env bash
# ==============================================================================
#  setupPython_and_download.sh — Installation complète sur une clé USB neuve
#
#  À lancer UNE FOIS depuis la racine de l'application (clé exFAT incluse) :
#
#    1. Crée l'environnement Python portable (venv --copies, sans symlinks —
#       indispensable sur exFAT/FAT32/NTFS) et installe les paquets de
#       langues Argos Translate DIRECTEMENT sur la clé (build/argos-data).
#    2. Télécharge les composants listés dans downloads.csv (modèles
#       Whisper, dictionnaires…) via download-assistant s'il est présent,
#       sinon via le repli shell download_from_csv.sh.
#
#  Relançable sans risque : les composants déjà présents sont conservés.
# ==============================================================================

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📁 Répertoire de travail : $SCRIPT_DIR"

echo ""
echo "🚀 Étape 1 : environnement Python portable + paquets de langues..."
bash "$SCRIPT_DIR/setup_venv_lang.sh"
echo "✅ Environnement Python prêt."

echo ""
echo "🚀 Étape 2 : téléchargement des composants (downloads.csv)..."
if [ -x "$SCRIPT_DIR/download-assistant" ]; then
    "$SCRIPT_DIR/download-assistant"
else
    echo "   (download-assistant absent → repli download_from_csv.sh)"
    bash "$SCRIPT_DIR/download_from_csv.sh" "$SCRIPT_DIR/downloads.csv"
fi

echo ""
echo "🎉 Installation terminée avec succès."
echo "👉 Lancez maintenant ./truchement ou ./transcribe"
