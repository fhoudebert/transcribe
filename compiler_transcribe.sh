#!/usr/bin/env bash

set -e  # arrête le script si une commande échoue

echo "🚀 Activation de l'environnement Python..."
cd build/python/venv/bin/
source activate 

echo "✅ Environnement Python prêt."

echo "🚀 Compilation transcribe..."
cd ../../../../transcribe-src
../build/python/venv/bin/pyinstaller     --onefile     --name transcribe     --icon=assets/icone.png     --add-data "traduire-srt.py:."     --add-data "assets:assets"     --windowed     transcribe.py


echo "🎉 Compilation terminée avec succès."
