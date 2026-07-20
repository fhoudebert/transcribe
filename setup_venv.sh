#!/bin/bash
# ==============================================================================
#  setup_venv.sh — Environnement Python portable SANS les paquets de langues
#  (voir setup_venv_lang.sh pour la version complète, et pour la justification
#   du mode --copies : compatibilité exFAT/FAT32/NTFS et copie Windows).
# ==============================================================================

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$SCRIPT_DIR/build" ]; then
    APP_ROOT="$SCRIPT_DIR"
else
    APP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi
VENV_DIR="$APP_ROOT/build/python/venv"

echo "📁 Racine de l'application : $APP_ROOT"

echo "📦 Création du virtualenv (mode --copies, sans liens symboliques)..."
# Pré-création de lib64 en VRAI dossier : le module venv de CPython ne crée
# son symlink lib64 → lib (impossible sur exFAT/FAT32) que si le chemin
# n'existe pas déjà — voir le commentaire détaillé dans setup_venv_lang.sh.
mkdir -p "$VENV_DIR/lib64"
python3 -m venv --copies "$VENV_DIR"

if ! "$VENV_DIR/bin/python" -c "pass" 2>/dev/null; then
    echo "❌ $VENV_DIR/bin/python ne peut pas s'exécuter (montage 'noexec' ?)."
    echo "   Remontez la clé avec l'option exec puis relancez."
    exit 1
fi

echo "🔌 Activation du virtualenv..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "⬆️  Mise à jour de pip..."
pip install --upgrade pip

REQ=""
for candidate in "$APP_ROOT/build/python/requirements.txt" "$APP_ROOT/requirements.txt"; do
    [ -f "$candidate" ] && REQ="$candidate" && break
done
if [ -n "$REQ" ]; then
    echo "📥 Installation des dépendances ($REQ)..."
    pip install -r "$REQ"
else
    echo "⚠️  Aucun requirements.txt trouvé"
fi

echo "✅ Installation terminée"
echo "👉 Pour activer le venv ensuite : source $VENV_DIR/bin/activate"
