#!/bin/bash

set -e  # stop en cas d'erreur

VENV_DIR="build/python/venv"
# Se placer dans le répertoire du script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"


echo "📦 création du virtualenv..."
python3 -m venv $VENV_DIR

echo "🔌 activation du virtualenv..."
source $VENV_DIR/bin/activate

echo "⬆️ mise à jour de pip..."
pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    echo "📥 installation des dépendances Python..."
    pip install -r requirements.txt
else
    echo "⚠️ aucun requirements.txt trouvé"
fi

echo "🌐 installation du package Argos Translate de données linguistiques...Veuillez patienter!"
if ! argospm list | grep -q "translate"; then
    argospm install translate
fi

echo "✅ environnement prêt"
echo "👉 activation : source $VENV_DIR/bin/activate"
