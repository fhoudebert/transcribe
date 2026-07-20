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
cd truchement-src
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
echo "✅ compilation terminée"
