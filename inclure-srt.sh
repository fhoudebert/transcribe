#!/bin/bash
set -euo pipefail

INPUT="${1:-}"
SRT="${2:-}"

if [ -z "$INPUT" ]; then
  echo "Usage : $0 <video.mp4> [subtitles.srt]"
  exit 1
fi

if [ ! -f "$INPUT" ]; then
  echo "Vidéo introuvable : $INPUT"
  exit 1
fi

BASE="${INPUT%.*}"
DIR="$(dirname "$INPUT")"
BASENAME="$(basename "$BASE")"

OUTPUT="${BASE}.mkv"

# -----------------------------
# Détection automatique SRT
# -----------------------------
if [ -n "$SRT" ]; then
  SUB_FILE="$SRT"
else
  if [ -f "${BASE}.fr.srt" ]; then
    SUB_FILE="${BASE}.fr.srt"
  elif [ -f "${BASE}.en.srt" ]; then
    SUB_FILE="${BASE}.en.srt"
  else
    echo "Aucun fichier SRT trouvé (.fr.srt ou .en.srt)"
    exit 1
  fi
fi

if [ ! -f "$SUB_FILE" ]; then
  echo "Sous-titres introuvables : $SUB_FILE"
  exit 1
fi

echo "=== Création MKV ==="
echo "Vidéo : $INPUT"
echo "Sous-titres : $SUB_FILE"

ffmpeg -i "$INPUT" \
  -i "$SUB_FILE" \
  -map 0:v \
  -map 0:a? \
  -map 1:0 \
  -c:v copy \
  -c:a copy \
  -c:s srt \
  -metadata:s:s:0 language=fre \
  -disposition:s:0 default \
  "$OUTPUT"

echo "=== Terminé ==="
echo "Fichier généré : $OUTPUT"
bash
