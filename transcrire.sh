#!/bin/bash

# Vérification du paramètre
if [ $# -lt 1 ]; then
    echo "Usage : $0 <fichier_audio>"
    exit 1
fi

AUDIO="$1"
LANGUE="${2:-fr}"

WHISPER_DIR="build/whisper/"
WHISPER_BIN="$WHISPER_DIR/whisper-cli"
MODEL="$WHISPER_DIR/models/ggml-medium.bin"

# Génération du nom de sortie (sans extension)
BASENAME=$(basename "$AUDIO")
NAME_NO_EXT="${BASENAME%.*}"
OUTPUT_FILE="${NAME_NO_EXT}.txt"

# Vérifications
[ -f "$AUDIO" ] || { echo "Fichier audio introuvable : $AUDIO"; exit 1; }
[ -x "$WHISPER_BIN" ] || { echo "whisper-cli introuvable : $WHISPER_BIN"; exit 1; }
[ -f "$MODEL" ] || { echo "Modèle introuvable : $MODEL"; exit 1; }

echo "Lancement de la transcription..."
echo "Modèle : $MODEL"
echo "Audio  : $AUDIO"
echo "Sortie : $OUTPUT_FILE"

"$WHISPER_BIN" \
    -m "$MODEL" \
    -f "$AUDIO" \
    -l "$LANGUE" \
    -otxt \
    -of "$NAME_NO_EXT"

echo "Transcription terminée."
echo "Répertoire courant : $(pwd)"
echo "Fichier généré : ${NAME_NO_EXT}.txt"
