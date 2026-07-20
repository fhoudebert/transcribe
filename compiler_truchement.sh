#!/usr/bin/env bash

set -e  # arrête le script si une commande échoue

echo "🚀 Activation de l'environnement Python..."
cd build/python/venv/bin/
source activate 

echo "✅ Environnement Python prêt."

echo "🚀 Compilation truchement..."
cd ../../../../truchement-src
../build/python/venv/bin/pyinstaller \
         --onefile \
         --name truchement \
         --exclude-module matplotlib \
         --exclude-module numpy \
         --exclude-module torch \
         --icon=assets/dico.png \
        --add-data "assets:assets" \
         --windowed  \
        main.py

echo "🎉 Compilation terminée avec succès."
