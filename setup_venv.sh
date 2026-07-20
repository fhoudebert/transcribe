#!/bin/bash

set -e  # stop si erreur

# Se placer dans le répertoire du script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📁 Répertoire de travail : $SCRIPT_DIR"

# Nom du venv (modifiable)
VENV_DIR="build/python/venv"

echo "📦 Création du virtualenv..."
python3 -m venv $VENV_DIR

echo "🔌 Activation du virtualenv..."
source $VENV_DIR/bin/activate

echo "⬆️ Mise à jour de pip..."
pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    echo "📥 Installation des dépendances..."
    pip install -r requirements.txt
else
    echo "⚠️ Aucun requirements.txt trouvé"
fi

echo "✅ Installation terminée"
echo "👉 Pour activer le venv ensuite : source $VENV_DIR/bin/activate"
